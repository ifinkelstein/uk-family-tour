#!/usr/bin/env python3
"""
Merge per-sight tracks.json sidecars (written by the content agents) into
manifest.json, and normalize every track's `tell_me_more` to the array shape.

- For each sight, if content/<sight-id>/tracks.json exists, replace that sight's
  `tracks` with it (both audiences).
- Any remaining legacy single-object `tell_me_more` is converted to a 1-element
  array so the whole manifest uses one shape.
- Validates every referenced .md file exists; reports missing ones.
- Recomputes the `totals` block.

Run from the scripts/ dir (or anywhere): python3 merge_manifest.py
"""
import json
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "tour"
MAN = ASSETS / "manifest.json"


def normalize_more(track):
    more = track.get("tell_me_more")
    if more is None:
        track["tell_me_more"] = []
    elif isinstance(more, dict):
        track["tell_me_more"] = [more]
    # list already fine


def main():
    man = json.loads(MAN.read_text())
    merged, missing = [], []

    for sight in man["sights"]:
        sidecar = ASSETS / "content" / sight["id"] / "tracks.json"
        if sidecar.exists():
            sight["tracks"] = json.loads(sidecar.read_text())
            merged.append(sight["id"])
        for aud in ("kid", "adult"):
            for t in sight["tracks"][aud]:
                normalize_more(t)
                refs = [t["file"]] + [c["file"] for c in t["tell_me_more"]]
                for r in refs:
                    if not (ASSETS / r).exists():
                        missing.append(r)

    # recompute totals
    files = kid_min = adult_min = kid_w = adult_w = 0
    def wc(rel):
        p = ASSETS / rel
        return len(p.read_text().split()) if p.exists() else 0
    for sight in man["sights"]:
        for aud in ("kid", "adult"):
            for t in sight["tracks"][aud]:
                allrefs = [t] + t["tell_me_more"]
                for c in allrefs:
                    files += 1
                    m = c.get("est_minutes", 1.5)
                    w = wc(c["file"])
                    if aud == "kid":
                        kid_min += m; kid_w += w
                    else:
                        adult_min += m; adult_w += w
    man["totals"] = {
        "files": files,
        "kid_words": kid_w, "kid_est_minutes": round(kid_min),
        "adult_words": adult_w, "adult_est_minutes": round(adult_min),
        "note": "Base + tell_me_more chapters. tell_me_more is an array of sub-chapters.",
    }

    MAN.write_text(json.dumps(man, indent=2, ensure_ascii=False))
    print(f"merged sidecars for: {', '.join(merged) or '(none)'}")
    print(f"totals: {files} files, kid ~{round(kid_min)} min, adult ~{round(adult_min)} min")
    if missing:
        print(f"\nMISSING {len(missing)} referenced files:")
        for m in sorted(set(missing)):
            print("  -", m)
        return 1
    print("all referenced .md files present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
