#!/usr/bin/env python3
"""
Render a subset of tour audio in PARALLEL by fanning out several
generate_audio.py workers, each handling a disjoint `--only` filter.

Usage:
  python3 render_parallel.py --sights day04-greenwich [day03-tower-of-london ...] [--workers 4]
  python3 render_parallel.py --only day04-greenwich/kid day04-greenwich/adult --workers 2

Each worker is an independent generate_audio.py process (skips files already
rendered), so filters must be disjoint. We split each sight into per-audience,
per-base-story filters for good parallelism. macOS / local Kokoro voices; no
network (HF_HUB_OFFLINE=1).
"""
import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ASSETS = ROOT / "tour"
MAN = ASSETS / "manifest.json"
VOICES = HERE / "voices"
PY = HERE / "venv/bin/python"
GEN = HERE / "generate_audio.py"


def filters_for_sights(sight_ids):
    """One filter per (sight, audience, base-story-number) for fine parallelism."""
    man = json.loads(MAN.read_text())
    out = []
    for s in man["sights"]:
        if s["id"] not in sight_ids:
            continue
        for aud in ("kid", "adult"):
            nums = set()
            for t in s["tracks"][aud]:
                nums.add(Path(t["file"]).name.split("-")[0])  # e.g. "01"
            for n in sorted(nums):
                out.append(f"{s['id']}/{aud}/{n}")
    return out


def run_worker(flt):
    env = dict(os.environ, HF_HUB_OFFLINE="1", PYTHONUNBUFFERED="1")
    cmd = [str(PY), str(GEN),
           "--manifest", str(MAN),
           "--out", str(OUT),
           "--kid-voice", str(VOICES / "bf_emma.pt"),
           "--adult-voice", str(VOICES / "bm_george.pt"),
           "--speed", "1.0",
           "--only", flt]
    if FORCE:
        cmd.append("--force")
    r = subprocess.run(cmd, env=env, capture_output=True, text=True)
    rendered = r.stdout.count("] content/")
    tag = "ok" if r.returncode == 0 else f"FAIL({r.returncode})"
    return f"[{tag}] {flt}: {rendered} rendered" + (
        "\n" + r.stderr[-400:] if r.returncode != 0 else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sights", nargs="*", default=[])
    ap.add_argument("--only", nargs="*", default=[])
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=str(ASSETS / "audio"))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    global OUT, FORCE
    OUT = Path(args.out)
    FORCE = args.force

    filters = list(args.only) + (filters_for_sights(args.sights) if args.sights else [])
    if not filters:
        sys.exit("no filters (pass --sights or --only)")
    print(f"{len(filters)} worker filters, {args.workers} concurrent:")
    for f in filters:
        print("  ", f)
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for line in ex.map(run_worker, filters):
            print(line, flush=True)
    print("BATCH DONE")


if __name__ == "__main__":
    main()
