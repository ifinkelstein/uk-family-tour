#!/usr/bin/env python3
"""
Verify the app's offline assets are complete before building:
  - every sight in images.json has at least its first image bundled
  - every track in manifest.json (base + tell_me_more) has generated audio
Exit code 0 = ready to build fully offline. Non-zero = something missing.

USAGE:
    python3 verify_assets.py            # human-readable report
    python3 verify_assets.py --strict   # also require EVERY listed image
"""

import argparse
import json
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "app/src/main/assets/tour"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    problems = []

    # --- images ---
    images_cfg = json.loads((ASSETS / "images.json").read_text())
    img_dir = ASSETS / "images"
    total_imgs = expected_imgs = 0
    for sight_id, cfg in images_cfg.items():
        for idx in range(len(cfg["wiki"])):
            expected_imgs += 1
            if (img_dir / f"{sight_id}-{idx}.jpg").exists():
                total_imgs += 1
            elif idx == 0 or args.strict:
                problems.append(f"missing image: {sight_id}-{idx}.jpg ({cfg['wiki'][idx]})")
    print(f"images: {total_imgs}/{expected_imgs} bundled")

    # --- audio ---
    man = json.loads((ASSETS / "manifest.json").read_text())
    audio_dir = ASSETS / "audio"
    missing_audio = 0
    total_tracks = 0
    for sight in man["sights"]:
        for audience in ("kid", "adult"):
            for t in sight["tracks"][audience]:
                files = [t["file"]]
                more = t.get("tell_me_more")
                if isinstance(more, list):
                    files += [c["file"] for c in more]
                elif isinstance(more, dict):
                    files.append(more["file"])
                for f in files:
                    total_tracks += 1
                    stem = Path(f).with_suffix("")
                    rel = stem.relative_to("content")
                    if not ((audio_dir / rel).with_suffix(".mp3").exists()
                            or (audio_dir / rel).with_suffix(".wav").exists()):
                        missing_audio += 1
                        if missing_audio <= 5:
                            problems.append(f"missing audio: {f}")
    if missing_audio > 5:
        problems.append(f"...and {missing_audio - 5} more missing audio files")
    print(f"audio:  {total_tracks - missing_audio}/{total_tracks} tracks rendered")
    if missing_audio == total_tracks:
        print("        (no audio generated yet — app would fall back to robotic on-device TTS)")

    if problems:
        print("\nNOT fully offline yet:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("\nAll assets present — the app is fully offline. Build away.")


if __name__ == "__main__":
    main()
