#!/usr/bin/env python3
"""Sanity-check composited mp3 lengths against their markdown word counts.

Expected duration = narration (words at 130–200 wpm) + ~6–16s overhead
(intro sting + spoken title + gaps + outro). Flags files outside the band,
truncated files, and missing audio.

Usage: python3 check_durations.py [sight-id ...]   (default: all sights)
"""
import json
import subprocess
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "tour"


def duration(p: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(p)],
        capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return -1.0


def words(rel: str) -> int:
    lines = (ASSETS / rel).read_text().splitlines()
    if lines and lines[0].startswith("#"):
        lines = lines[1:]
    return len(" ".join(lines).split())


def main():
    only = set(sys.argv[1:])
    man = json.loads((ASSETS / "manifest.json").read_text())
    bad = 0
    checked = 0
    for s in man["sights"]:
        if only and s["id"] not in only:
            continue
        for aud in ("kid", "adult"):
            for t in s["tracks"][aud]:
                for rel in [t["file"]] + [c["file"] for c in t.get("tell_me_more", [])]:
                    mp3 = (ASSETS / "audio" / Path(rel).relative_to("content")).with_suffix(".mp3")
                    if not mp3.exists():
                        print(f"MISSING  {rel}")
                        bad += 1
                        continue
                    w = words(rel)
                    d = duration(mp3)
                    # Calibrated on Kokoro voices: bf_emma ~180-215 wpm,
                    # bm_george ~140-150 wpm (tail-transcription verified).
                    lo = w / 230 * 60 + 5      # fast read + minimal overhead
                    hi = w / 110 * 60 + 20     # slow read + full overhead
                    checked += 1
                    if d < lo or d > hi:
                        print(f"OUT-OF-BAND  {rel}: {d:.0f}s for {w} words "
                              f"(expected {lo:.0f}-{hi:.0f}s)")
                        bad += 1
    print(f"checked {checked} tracks, {bad} problems")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
