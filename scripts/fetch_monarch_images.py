#!/usr/bin/env python3
"""Pre-download monarch portraits for the royal family tree screen.

Reads each monarch's `wiki` title from tour/monarchy.json and saves the
Wikipedia lead image to tour/images/monarchs/<id>.jpg. The app falls back to
the monarch's emoji when a portrait is missing. Same polite-client rules as
fetch_images.py. Usage: python3 fetch_monarch_images.py
"""

import json
import time
from pathlib import Path

from fetch_images import fetch_thumb_url, download, POLITE_DELAY

APP_ASSETS = Path(__file__).resolve().parent.parent / "tour"
OUT_DIR = APP_ASSETS / "images/monarchs"


def main():
    mon = json.loads((APP_ASSETS / "monarchy.json").read_text())
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ok = fail = 0
    for m in mon["monarchs"]:
        title = m.get("wiki")
        dest = OUT_DIR / f"{m['id']}.jpg"
        if not title or dest.exists():
            continue
        try:
            src = fetch_thumb_url(title)
            if not src:
                raise ValueError("no image on article")
            download(src, dest)
            print(f"ok   {m['id']}  ({title})")
            ok += 1
        except Exception as e:
            print(f"skip {m['id']}  ({title}): {e}")
            fail += 1
        time.sleep(POLITE_DELAY)
    print(f"\n{ok} portraits saved to {OUT_DIR}  ({fail} skipped — emoji fallback)")


if __name__ == "__main__":
    main()
