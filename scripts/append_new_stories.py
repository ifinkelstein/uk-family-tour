#!/usr/bin/env python3
"""Append new base stories from content/<sight>/new-stories.json to that sight in
the manifest (preserving existing stories). Validates referenced files exist and
recomputes totals. Usage: python3 append_new_stories.py <sight-id>"""
import json, sys
from pathlib import Path

ASSETS = Path("/Users/ilya/projects/London-trip-vacation/tour-app/tour")
MAN = ASSETS/"manifest.json"

def main():
    sight_id = sys.argv[1]
    man = json.loads(MAN.read_text())
    sidecar = ASSETS/"content"/sight_id/"new-stories.json"
    new = json.loads(sidecar.read_text())
    sight = next(s for s in man["sights"] if s["id"] == sight_id)

    existing = {aud: {t["file"] for t in sight["tracks"][aud]} for aud in ("kid","adult")}
    added = 0
    for aud in ("kid","adult"):
        for story in new.get(aud, []):
            if story["file"] in existing[aud]:
                continue  # idempotent
            sight["tracks"][aud].append(story)
            added += 1

    # validate + recompute totals
    missing, files, km, am, kw, aw = [], 0, 0, 0, 0, 0
    def wc(rel):
        p = ASSETS/rel
        return len(p.read_text().split()) if p.exists() else 0
    for s in man["sights"]:
        for aud in ("kid","adult"):
            for t in s["tracks"][aud]:
                for c in [t] + t.get("tell_me_more", []):
                    files += 1
                    if not (ASSETS/c["file"]).exists():
                        missing.append(c["file"])
                    w = wc(c["file"]); mnt = c.get("est_minutes",1.5)
                    if aud == "kid": km += mnt; kw += w
                    else: am += mnt; aw += w
    man["totals"] = {"files": files, "kid_words": kw, "kid_est_minutes": round(km),
                     "adult_words": aw, "adult_est_minutes": round(am),
                     "note": "Base + tell_me_more chapters."}
    MAN.write_text(json.dumps(man, indent=2, ensure_ascii=False))
    print(f"appended {added} new stories to {sight_id}; manifest now {files} tracks")
    if missing:
        print(f"MISSING {len(missing)} files:")
        for m in missing[:15]: print("  -", m)
        return 1
    print("all referenced files present.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
