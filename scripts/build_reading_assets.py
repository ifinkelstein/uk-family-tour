#!/usr/bin/env python3
"""Build per-sight reading PDFs and EPUBs from the manifest markdown."""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "app/src/main/assets/tour"
PDF_DIR = ROOT / "reading-pdfs"
EPUB_DIR = ROOT / "reading-epubs"
TEX_CACHE = ROOT / "build-cache/tex"


def body(rel: str) -> str:
    lines = (ASSETS / rel).read_text().splitlines()
    if lines and lines[0].startswith("#"):
        lines = lines[1:]
    return "\n".join(lines).strip()


def title(rel: str) -> str:
    first = (ASSETS / rel).read_text().splitlines()[0].strip()
    return first[2:].strip() if first.startswith("# ") else first


def filename(sight: dict, audience: str, ext: str) -> str:
    label = "Kids" if audience == "kid" else "Grown-ups"
    return f"{sight['day']:02d} {sight['name']} - {label}.{ext}"


def words(text: str) -> int:
    return len(re.findall(r"\b[\w']+\b", text))


def assemble_markdown(sight: dict, audience: str) -> tuple[str, int]:
    label = "Kids" if audience == "kid" else "Grown-ups"
    chunks = [
        "\n".join([
            "---",
            f"title: \"{sight['name']} - {label}\"",
            "author: \"UK Family Tour\"",
            "lang: en-GB",
            "---",
            "",
        ]),
    ]
    for idx, track in enumerate(sight["tracks"][audience]):
        if idx:
            chunks.append("\\newpage\n\n* * *\n")
        chunks.append(f"# {title(track['file'])}\n")
        chunks.append(body(track["file"]))
        for more in track.get("tell_me_more", []):
            chunks.append(f"\n\n## {title(more['file'])}\n")
            chunks.append(body(more["file"]))
    text = "\n\n".join(part for part in chunks if part.strip()) + "\n"
    return text, words(text)


def run(cmd: list[str]) -> None:
    TEX_CACHE.mkdir(parents=True, exist_ok=True)
    (TEX_CACHE / "texmf-var").mkdir(parents=True, exist_ok=True)
    (TEX_CACHE / "texmf-cache").mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["TEXMFVAR"] = str(TEX_CACHE / "texmf-var")
    env["TEXMFCACHE"] = str(TEX_CACHE / "texmf-cache")
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if proc.returncode:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        raise SystemExit(proc.returncode)


def build_one(sight: dict, audience: str) -> dict:
    PDF_DIR.mkdir(exist_ok=True)
    EPUB_DIR.mkdir(exist_ok=True)
    md_text, word_count = assemble_markdown(sight, audience)
    pdf = PDF_DIR / filename(sight, audience, "pdf")
    epub = EPUB_DIR / filename(sight, audience, "epub")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "reading.md"
        src.write_text(md_text)
        run([
            "pandoc",
            str(src),
            "--pdf-engine=pdflatex",
            "-V",
            "geometry:margin=0.8in",
            "-V",
            "fontsize=11pt",
            "-o",
            str(pdf),
        ])
        run([
            "pandoc",
            str(src),
            "--metadata",
            f"title={sight['name']}",
            "--metadata",
            "creator=UK Family Tour",
            "-o",
            str(epub),
        ])
    return {
        "sight": sight["id"],
        "audience": audience,
        "words": word_count,
        "pdf": str(pdf.relative_to(ROOT)),
        "epub": str(epub.relative_to(ROOT)),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sight", action="append", help="sight id to build; repeatable")
    ap.add_argument("--audience", choices=["kid", "adult", "both"], default="both")
    args = ap.parse_args()

    manifest = json.loads((ASSETS / "manifest.json").read_text())
    audiences = ["kid", "adult"] if args.audience == "both" else [args.audience]
    built = []
    for sight in manifest["sights"]:
        if args.sight and sight["id"] not in args.sight:
            continue
        for audience in audiences:
            built.append(build_one(sight, audience))
            print(f"{built[-1]['pdf']} + {built[-1]['epub']} ({built[-1]['words']} words)", flush=True)
    if not built:
        raise SystemExit("No matching sights")


if __name__ == "__main__":
    main()
