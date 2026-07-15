#!/usr/bin/env python3
"""Assemble per-sight reading text (base stories + sub-chapters, in manifest
order) into blank-line-separated paragraphs with asterisk section breaks, ready for
the read-later skill's format-article.py. One .txt per sight per audience.

Usage: python3 assemble_reading.py <out_dir> [--audience adult|kid|both] [--sight <id>]"""
import argparse, json
from pathlib import Path

ASSETS = Path("/Users/ilya/projects/London-trip-vacation/tour-app/tour")

def md_title(rel):
    first = (ASSETS/rel).read_text().splitlines()[0].strip()
    return first[2:].strip() if first.startswith("# ") else first

def md_body(rel):
    lines = (ASSETS/rel).read_text().splitlines()
    if lines and lines[0].startswith("#"): lines = lines[1:]
    # collapse to paragraphs separated by blank lines, drop leading blanks
    text = "\n".join(lines).strip()
    return text

def assemble(sight, aud):
    out = []
    for i, t in enumerate(sight["tracks"][aud]):
        if i > 0:
            out.append("* * *")
        out.append(md_title(t["file"]))
        out.append(md_body(t["file"]))
        for c in t.get("tell_me_more", []):
            out.append(md_title(c["file"]))
            out.append(md_body(c["file"]))
    # join blocks with blank lines
    return "\n\n".join(b for b in out if b.strip()) + "\n"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--audience", default="both")
    ap.add_argument("--sight", default=None)
    args = ap.parse_args()
    outd = Path(args.out_dir); outd.mkdir(parents=True, exist_ok=True)
    man = json.loads((ASSETS/"manifest.json").read_text())
    auds = ["adult","kid"] if args.audience=="both" else [args.audience]
    made = []
    for s in man["sights"]:
        if args.sight and s["id"] != args.sight: continue
        for aud in auds:
            txt = assemble(s, aud)
            fp = outd/f"{s['id']}--{aud}.txt"
            fp.write_text(txt)
            made.append((s["id"], s["name"], aud, str(fp), len(txt.split())))
    for sid, name, aud, fp, wc in made:
        print(f"{sid}\t{aud}\t{wc}w\t{name}")

if __name__ == "__main__":
    main()
