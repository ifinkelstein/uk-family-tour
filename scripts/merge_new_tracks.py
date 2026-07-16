#!/usr/bin/env python3
"""Merge a sight's new-tracks.json sidecar (one new base track per audience,
written by a content agent) into tour/manifest.json. Idempotent: replaces any
existing track with the same file. Usage: python3 merge_new_tracks.py <sight-id>"""
import json
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "tour"


def main():
    sight_id = sys.argv[1]
    sidecar = ASSETS / "content" / sight_id / "new-tracks.json"
    new = json.loads(sidecar.read_text())
    man = json.loads((ASSETS / "manifest.json").read_text())
    s = next(x for x in man["sights"] if x["id"] == sight_id)
    for aud in ("kid", "adult"):
        t = new[aud]
        for f in [t["file"]] + [c["file"] for c in t.get("tell_me_more", [])]:
            assert (ASSETS / f).exists(), f"missing markdown: {f}"
        s["tracks"][aud] = [x for x in s["tracks"][aud] if x["file"] != t["file"]] + [t]
        print(f"{aud}: {t['title']} + {len(t.get('tell_me_more', []))} chapters")
    (ASSETS / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main()
