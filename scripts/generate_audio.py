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
    python generate_audio.py --manifest ../app/src/main/assets/tour/manifest.json \
                             --out ../app/src/main/assets/tour/audio

    Then just rebuild the app: it automatically prefers these files over
    on-device TTS (you'll see the 🎙 icon in the player instead of 🤖).

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
    # zip the audio/ folder and download it into app/src/main/assets/tour/
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
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
    text = " ".join(l.strip() for l in lines if l.strip())
    text = text.replace("\u2014", ", ").replace("\u2013", ", ")  # dashes -> pauses
    text = re.sub(r"\s+", " ", text).strip()
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True, help="output dir, mirrors content/ paths")
    ap.add_argument("--kid-voice", default="bf_emma")
    ap.add_argument("--adult-voice", default="bm_george")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--mp3", action="store_true", default=True,
                    help="convert to mp3 with ffmpeg (default on; wav kept if ffmpeg missing)")
    ap.add_argument("--only", default=None, help="substring filter, e.g. day03")
    args = ap.parse_args()

    manifest = Path(args.manifest)
    content_root = manifest.parent
    out_root = Path(args.out)

    try:
        from kokoro import KPipeline
        import soundfile as sf
    except ImportError:
        sys.exit("Missing deps. Run: pip install kokoro soundfile   (and: brew install espeak-ng)")

    # 'b' = British English pipeline; voices decide the actual speaker.
    pipeline = KPipeline(lang_code="b")
    have_ffmpeg = shutil.which("ffmpeg") is not None
    if args.mp3 and not have_ffmpeg:
        print("note: ffmpeg not found — keeping .wav output (app plays wav too)")

    tracks = load_tracks(manifest)
    if args.only:
        tracks = [t for t in tracks if args.only in t[1]]
    print(f"{len(tracks)} tracks to render")

    for i, (audience, rel) in enumerate(tracks, 1):
        voice = args.kid_voice if audience == "kid" else args.adult_voice
        src = content_root / rel
        dst_base = out_root / Path(rel).with_suffix("").relative_to("content")
        dst_wav = dst_base.with_suffix(".wav")
        dst_mp3 = dst_base.with_suffix(".mp3")
        if dst_mp3.exists() or (not (args.mp3 and have_ffmpeg) and dst_wav.exists()):
            continue
        dst_wav.parent.mkdir(parents=True, exist_ok=True)

        text = md_to_speech_text(src)
        print(f"[{i}/{len(tracks)}] {rel}  ({voice})")

        # Kokoro streams audio in chunks; concatenate them.
        import numpy as np
        chunks = [audio for _, _, audio in pipeline(text, voice=voice, speed=args.speed)]
        audio = np.concatenate(chunks)
        sf.write(dst_wav, audio, 24000)

        if args.mp3 and have_ffmpeg:
            subprocess.run(
                ["ffmpeg", "-loglevel", "error", "-y", "-i", str(dst_wav),
                 "-b:a", "64k", str(dst_mp3)],
                check=True,
            )
            dst_wav.unlink()

    print(f"\nDone. Audio in {out_root}/ — rebuild the app and it will use these files.")


if __name__ == "__main__":
    main()
