#!/usr/bin/env python3
"""Generate magazine-style reading PDFs for every sight (adult + kid) via the
read-later skill, collecting them into one folder with clean names."""
import json, subprocess, shutil, os
from pathlib import Path

ASSETS = Path("/Users/ilya/projects/London-trip-vacation/tour-app/tour")
SCRIPTS = Path("/Users/ilya/projects/London-trip-vacation/tour-app/scripts")
SCRATCH = Path("/private/tmp/claude-502/-Users-ilya-projects-London-trip-vacation/c1c8ad87-7830-4567-99e1-9b08493f82d1/scratchpad")
TXT = SCRATCH/"reading-txt"
WORK = SCRATCH/"reading-work"
OUT = SCRATCH/"reading-pdfs-final"
FMT = Path.home()/".claude/skills/read-later/scripts/format-article.py"
for d in (WORK, OUT): d.mkdir(parents=True, exist_ok=True)

man = json.loads((ASSETS/"manifest.json").read_text())
# order sights by day; label region
def region(day): return "London" if day <= 7 else ("Edinburgh" if day <= 12 else "York")

done, failed = [], []
for s in man["sights"]:
    for aud, label in (("adult","Grown-ups"), ("kid","Kids")):
        txt = TXT/f"{s['id']}--{aud}.txt"
        if not txt.exists():
            failed.append((s['id'], aud, "no txt")); continue
        title = f"{s['name']} ({label})"
        r = subprocess.run(["uv","run",str(FMT),"--file",str(txt),"--title",title,
                            "--author","UK Family Tour","--no-html","--output",str(WORK)],
                           capture_output=True, text=True)
        # find produced pdf
        pdfs = list(WORK.rglob("*.pdf"))
        src = None
        # newest pdf whose folder matches title slug
        cand = sorted(WORK.rglob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
        if cand:
            src = cand[0]
        if src and src.exists():
            dayn = f"{s['day']:02d}"
            dest = OUT/f"{dayn} {s['name']} - {label}.pdf"
            shutil.copy(src, dest)
            done.append(str(dest.name))
        else:
            failed.append((s['id'], aud, r.stderr[-200:]))

print(f"generated {len(done)} PDFs into {OUT}")
for d in sorted(done): print("  ", d)
if failed:
    print("FAILED:")
    for f in failed: print("  ", f)
