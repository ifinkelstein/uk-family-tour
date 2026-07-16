#!/usr/bin/env python3
"""Chunk-and-stitch long narration through MiMo VoiceDesign (DeepInfra).

MiMo truncates past ~1 minute of generated audio per request, so long museum
scripts must be split, synthesized chunk by chunk (same seed -> same designed
voice), and stitched back together with small pads to hide the seams.

Usage:
  ./venv/bin/python mimo_long.py <markdown-file> <out.mp3> [--audience kid|adult] [--speed 1.0]

Programmatic:
  from mimo_long import synth_long
  synth_long(text, mimo.ADULT_DESC, mimo.ADULT_STYLE, Path("out.mp3"), speed=1.25)
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mimo

# ~350 chars ≈ 25-30 s of speech: safely inside MiMo's per-request ceiling,
# large enough that seams stay rare.
MAX_CHARS = 350


def split_text(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    """Split on paragraph boundaries first (best prosody seams), then
    sentences, then words as a last resort. Never returns an empty chunk."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    for para in paras:
        if len(para) <= max_chars:
            chunks.append(para)
            continue
        sentences = re.split(r"(?<=[.!?])\s+", para)
        cur = ""
        for sen in sentences:
            sen = sen.strip()
            if not sen:
                continue
            if len(sen) > max_chars:  # monster sentence: split by words
                words, piece = sen.split(), ""
                for w in words:
                    if piece and len(piece) + len(w) + 1 > max_chars:
                        chunks.append(piece)
                        piece = w
                    else:
                        piece = f"{piece} {w}".strip()
                sen = piece  # remainder joins the flow below
            if cur and len(cur) + len(sen) + 1 > max_chars:
                chunks.append(cur)
                cur = sen
            else:
                cur = f"{cur} {sen}".strip()
        if cur:
            chunks.append(cur)
    return chunks


def stitch(parts: list[Path], out: Path, pad: float = 0.15):
    """Decode every chunk, pad each with a short silence, concat, re-encode.
    Uniform re-encode (not -c copy) so mismatched frame headers can't click."""
    inputs, filters, labels = [], [], []
    for i, p in enumerate(parts):
        inputs += ["-i", str(p)]
        filters.append(f"[{i}:a]aresample=44100,apad=pad_dur={pad}[a{i}]")
        labels.append(f"[a{i}]")
    fc = ";".join(filters) + ";" + "".join(labels) + f"concat=n={len(parts)}:v=0:a=1[out]"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *inputs,
                    "-filter_complex", fc, "-map", "[out]",
                    "-ac", "1", "-b:a", "64k", str(out)], check=True)


def synth_long(text: str, desc: str, style: str, out_mp3: Path,
               speed: float = 1.0, api_key: str | None = None) -> int:
    """Synthesize arbitrarily long text through MiMo. Returns chunk count.
    The module-level fixed SEED in mimo.py keeps the designed voice
    consistent across chunks (mostly — designed voices can drift slightly;
    listen to seams on anything precious)."""
    key = api_key or mimo.key()
    chunks = split_text(text)
    with tempfile.TemporaryDirectory() as td:
        parts = []
        for i, chunk in enumerate(chunks):
            p = Path(td) / f"part-{i:03d}.mp3"
            mimo.synth(chunk, desc, style, p, api_key=key, speed=speed)
            parts.append(p)
        out_mp3.parent.mkdir(parents=True, exist_ok=True)
        stitch(parts, out_mp3)
    return len(chunks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("md", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--audience", choices=("kid", "adult"), default="adult")
    ap.add_argument("--speed", type=float, default=1.0)
    args = ap.parse_args()

    lines = args.md.read_text().splitlines()
    if lines and lines[0].startswith("#"):
        lines = lines[1:]
    # ">" lines are cross-reference callouts, never spoken
    lines = [l for l in lines if not l.lstrip().startswith(">")]
    text = "\n".join(lines).strip()

    desc, style = ((mimo.KID_DESC, mimo.KID_STYLE) if args.audience == "kid"
                   else (mimo.ADULT_DESC, mimo.ADULT_STYLE))
    n = synth_long(text, desc, style, args.out, speed=args.speed)
    print(f"{args.out}: stitched from {n} chunks")


if __name__ == "__main__":
    main()
