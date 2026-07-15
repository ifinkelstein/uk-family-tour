#!/usr/bin/env python3
"""Update manifest sight total minutes from a generate_audio.py audit file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "tour"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sight", required=True, help="manifest sight id")
    parser.add_argument("--audit", required=True, help="audio audit JSON")
    parser.add_argument("--manifest", default=str(ASSETS / "manifest.json"))
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text())
    audit = json.loads(Path(args.audit).read_text())
    totals = {"kid": 0.0, "adult": 0.0}
    for track in audit["tracks"]:
        totals[track["audience"]] += track["duration_seconds"] / 60

    for sight in manifest["sights"]:
        if sight["id"] == args.sight:
            sight["kid_total_minutes"] = round(totals["kid"], 1)
            sight["adult_total_minutes"] = round(totals["adult"], 1)
            break
    else:
        raise SystemExit(f"No sight found for {args.sight}")

    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(
        f"{args.sight}: kids {totals['kid']:.1f} min, "
        f"adults {totals['adult']:.1f} min"
    )


if __name__ == "__main__":
    main()
