#!/usr/bin/env python3
"""
Generate natural-sounding narration audio for every tour track using
Kokoro-82M — a free, Apache-licensed TTS model with excellent intonation.
Runs fully offline on a Mac (fast on Apple Silicon, fine on Intel CPU),
or anywhere Python runs (Linux box, Google Colab).

SETUP (Mac):
    brew install espeak-ng ffmpeg          # espeak-ng = fallback phonemizer, ffmpeg = mp3
    python3 -m venv venv && source venv/bin/activate
    pip install kokoro soundfile

    (First run downloads the ~330 MB model from Hugging Face automatically.)

USAGE:
    python generate_audio.py --manifest ../tour/manifest.json \
                             --out ../tour/audio

    Then serve the web app. It plays the generated files from tour/audio/.

VOICES (British, fitting the trip — change with --kid-voice / --adult-voice):
    bf_emma    warm British female (default for kid tracks)
    bm_george  measured British male (default for adult tracks)
    bf_isabella, bm_lewis, af_heart, am_michael ... (see Kokoro docs)

CLOUD OPTION (no Mac horsepower needed): open colab.research.google.com,
new notebook, and run:
    !apt-get -qq install espeak-ng ffmpeg
    !pip -q install kokoro soundfile
    # upload manifest.json + content/ (zip them), unzip, then:
    !python generate_audio.py --manifest manifest.json --out audio
    # zip the audio/ folder and copy it into tour/audio/
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


def load_tracks(manifest_path: Path):
    man = json.loads(manifest_path.read_text())
    tracks = []
    for sight in man["sights"]:
        for audience in ("kid", "adult"):
            for t in sight["tracks"][audience]:
                tracks.append((audience, t["file"]))
                more = t.get("tell_me_more")
                if isinstance(more, list):
                    for c in more:
                        tracks.append((audience, c["file"]))
                elif isinstance(more, dict):
                    tracks.append((audience, more["file"]))
    return tracks


def md_to_speech_text(path: Path) -> str:
    lines = path.read_text().splitlines()
    if lines and lines[0].startswith("#"):
        lines = lines[1:]
    text = "\n".join(l.strip() for l in lines if l.strip())
    text = text.replace("\u2014", ", ").replace("\u2013", ", ")  # dashes -> pauses
    text = re.sub(r"\s+", " ", text).strip()
    return text


def split_for_kokoro(text: str, max_chars: int = 650) -> list[str]:
    """Keep chunks short enough that Kokoro never truncates long museum scripts."""
    parts = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    cur = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(cur) + len(part) + 1 <= max_chars:
            cur = f"{cur} {part}".strip()
        else:
            if cur:
                chunks.append(cur)
            cur = part
    if cur:
        chunks.append(cur)
    out: list[str] = []
    for chunk in chunks:
        if len(chunk) <= max_chars * 1.4:
            out.append(chunk)
            continue
        words = chunk.split()
        cur_words: list[str] = []
        cur_len = 0
        for word in words:
            if cur_words and cur_len + len(word) + 1 > max_chars:
                out.append(" ".join(cur_words))
                cur_words = [word]
                cur_len = len(word)
            else:
                cur_words.append(word)
                cur_len += len(word) + 1
        if cur_words:
            out.append(" ".join(cur_words))
    return out


def word_count(path: Path) -> int:
    text = md_to_speech_text(path)
    return len(re.findall(r"\b[\w']+\b", text))


def resolve_voice(voice: str, voices_dir: Path) -> str:
    if voice.endswith(".pt") or "/" in voice:
        return voice
    local = voices_dir / f"{voice}.pt"
    if local.exists():
        return str(local)
    return voice


def duration_seconds(path: Path) -> float | None:
    if not path.exists():
        return None
    r = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return None
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True, help="output dir, mirrors content/ paths")
    ap.add_argument("--kid-voice", default="bf_emma")
    ap.add_argument("--adult-voice", default="bm_george")
    ap.add_argument("--voices-dir", default=str(Path(__file__).resolve().parent / "voices"))
    ap.add_argument("--speed", type=float, default=0.92)
    ap.add_argument("--force", action="store_true", help="replace existing rendered audio")
    ap.add_argument("--mp3", action="store_true", default=True,
                    help="convert to mp3 with ffmpeg (default on; wav kept if ffmpeg missing)")
    ap.add_argument("--only", default=None, help="substring filter, e.g. day03")
    ap.add_argument("--shard-count", type=int, default=1, help="split manifest tracks across N workers")
    ap.add_argument("--shard-index", type=int, default=0, help="0-based shard index for this worker")
    ap.add_argument("--verify-report", default=None, help="write JSON duration audit")
    ap.add_argument("--expected-wpm", type=float, default=175.0)
    ap.add_argument("--min-wpm", type=float, default=130.0)
    ap.add_argument("--max-wpm", type=float, default=220.0)
    args = ap.parse_args()

    manifest = Path(args.manifest)
    content_root = manifest.parent
    out_root = Path(args.out)
    voices_dir = Path(args.voices_dir)

    try:
        from kokoro import KPipeline
        import soundfile as sf
    except ImportError:
        sys.exit("Missing deps. Run: pip install kokoro soundfile   (and: brew install espeak-ng)")

    # 'b' = British English pipeline; voices decide the actual speaker.
    # Local .pt voice packs prevent Hugging Face lookups while travelling/offline.
    pipeline = KPipeline(lang_code="b", repo_id="hexgrad/Kokoro-82M")
    have_ffmpeg = shutil.which("ffmpeg") is not None
    if args.verify_report and not have_ffmpeg:
        sys.exit("ffprobe/ffmpeg is required for --verify-report")
    if args.mp3 and not have_ffmpeg:
        print("note: ffmpeg not found — keeping .wav output (app plays wav too)")

    tracks = load_tracks(manifest)
    if args.only:
        tracks = [t for t in tracks if args.only in t[1]]
    if args.shard_count < 1:
        sys.exit("--shard-count must be >= 1")
    if not 0 <= args.shard_index < args.shard_count:
        sys.exit("--shard-index must be between 0 and shard-count - 1")
    if args.shard_count > 1:
        tracks = [t for idx, t in enumerate(tracks) if idx % args.shard_count == args.shard_index]
    print(f"{len(tracks)} tracks to render", flush=True)
    report = []
    started = time.time()

    for i, (audience, rel) in enumerate(tracks, 1):
        voice_name = args.kid_voice if audience == "kid" else args.adult_voice
        voice = resolve_voice(voice_name, voices_dir)
        src = content_root / rel
        dst_base = out_root / Path(rel).with_suffix("").relative_to("content")
        dst_wav = dst_base.with_suffix(".wav")
        dst_mp3 = dst_base.with_suffix(".mp3")
        final_path = dst_mp3 if args.mp3 and have_ffmpeg else dst_wav
        if args.force:
            dst_mp3.unlink(missing_ok=True)
            dst_wav.unlink(missing_ok=True)
        if dst_mp3.exists() or (not (args.mp3 and have_ffmpeg) and dst_wav.exists()):
            if args.verify_report:
                words = word_count(src)
                duration = duration_seconds(final_path)
                wpm = words / (duration / 60) if duration else None
                report.append({
                    "file": rel,
                    "audience": audience,
                    "words": words,
                    "duration_seconds": duration,
                    "spoken_wpm": wpm,
                    "target_seconds": words / args.expected_wpm * 60,
                    "ok": wpm is not None and args.min_wpm <= wpm <= args.max_wpm,
                    "skipped": True,
                })
            continue
        dst_wav.parent.mkdir(parents=True, exist_ok=True)

        text = md_to_speech_text(src)
        chunks = split_for_kokoro(text)
        print(f"[{i}/{len(tracks)}] {rel}  ({voice_name}, {len(chunks)} chunks)", flush=True)

        # Kokoro streams audio in chunks; concatenate them.
        import numpy as np
        audio_chunks = [
            audio
            for _, _, audio in pipeline(chunks, voice=voice, speed=args.speed, split_pattern=None)
        ]
        if not audio_chunks:
            raise RuntimeError(f"Kokoro produced no audio for {rel}")
        audio = np.concatenate(audio_chunks)
        sf.write(dst_wav, audio, 24000)

        if args.mp3 and have_ffmpeg:
            subprocess.run(
                ["ffmpeg", "-loglevel", "error", "-y", "-i", str(dst_wav),
                 "-b:a", "64k", str(dst_mp3)],
                check=True,
            )
            dst_wav.unlink()

        if args.verify_report:
            words = word_count(src)
            duration = duration_seconds(final_path)
            wpm = words / (duration / 60) if duration else None
            report.append({
                "file": rel,
                "audience": audience,
                "voice": voice_name,
                "words": words,
                "chunks": len(chunks),
                "duration_seconds": duration,
                "spoken_wpm": wpm,
                "target_seconds": words / args.expected_wpm * 60,
                "ok": wpm is not None and args.min_wpm <= wpm <= args.max_wpm,
                "skipped": False,
            })

    if args.verify_report:
        report_path = Path(args.verify_report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        summary = {
            "manifest": str(manifest),
            "out": str(out_root),
            "kid_voice": args.kid_voice,
            "adult_voice": args.adult_voice,
            "speed": args.speed,
            "expected_wpm": args.expected_wpm,
            "min_wpm": args.min_wpm,
            "max_wpm": args.max_wpm,
            "elapsed_seconds": time.time() - started,
            "tracks": report,
            "failures": [r for r in report if not r["ok"]],
        }
        report_path.write_text(json.dumps(summary, indent=2))
        print(f"duration audit: {report_path} ({len(summary['failures'])} outside range)", flush=True)
    print(f"\nDone. Audio in {out_root}/ - serve the web app and it will use these files.", flush=True)


if __name__ == "__main__":
    main()
