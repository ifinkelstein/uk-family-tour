#!/usr/bin/env python3
"""Composite ONLY the given sights' tracks (intro sting + spoken title +
narration + outro) from audio-raw/ + build-audio/titles/ into tour/audio/.

Unlike compose_audio.py (whole library), this never touches other sights, so
older Kokoro re-voices can't be clobbered by stale raw files.

Usage: python3 compose_sight.py <sight-id> [<sight-id> ...] [--only NN]
       --only NN  restrict to base-story number NN (e.g. 01) and its subs
"""
import argparse
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from compose_audio import compose, region, ASSETS, AUDIO, RAW, TITLES, MUSIC


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sights", nargs="+")
    ap.add_argument("--only", help="base-story number filter, e.g. 01")
    args = ap.parse_args()

    man = json.loads((ASSETS / "manifest.json").read_text())
    jobs = []
    for s in man["sights"]:
        if s["id"] not in args.sights:
            continue
        reg = region(s["day"])
        intro, outro = MUSIC / f"{reg}-intro.mp3", MUSIC / f"{reg}-outro.mp3"
        for aud in ("kid", "adult"):
            for t in s["tracks"][aud]:
                for rel in [t["file"]] + [c["file"] for c in t.get("tell_me_more", [])]:
                    name = Path(rel).name
                    if args.only and not name.startswith(f"{args.only}-"):
                        continue
                    sub = Path(rel).relative_to("content").with_suffix(".mp3")
                    if not (RAW / sub).exists():
                        print(f"SKIP (no raw): {sub}")
                        continue
                    jobs.append((RAW / sub, TITLES / sub, intro, outro, AUDIO / sub))

    print(f"compositing {len(jobs)} tracks ...", flush=True)
    fails = []

    def run(j):
        good, err = compose(*j)
        return good, j[-1], err

    with ThreadPoolExecutor(max_workers=6) as ex:
        for good, out, err in ex.map(run, jobs):
            if not good:
                fails.append((str(out), err))
    print(f"composited {len(jobs) - len(fails)}/{len(jobs)}")
    for o, e in fails:
        print("FAIL", o, e)
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
