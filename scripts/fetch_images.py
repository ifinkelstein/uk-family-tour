#!/usr/bin/env python3
"""
Optional: pre-download the sight images so the app works fully offline
(useful on UK roaming data). Without this, the app fetches the same images
live from Wikipedia and caches them on the phone.

Downloads the lead image of each Wikipedia article listed in images.json
into app/src/main/assets/tour/images/<sight-id>-<index>.jpg. The app checks
for these files first and only goes online if they're missing.

USAGE (from the scripts/ folder, needs only the Python standard library):
    python3 fetch_images.py
"""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

APP_ASSETS = Path(__file__).resolve().parent.parent / "app/src/main/assets/tour"
IMAGES_JSON = APP_ASSETS / "images.json"
OUT_DIR = APP_ASSETS / "images"

# Wikimedia asks for a descriptive User-Agent with contact info; a generic one
# gets rate-limited (HTTP 429). See https://meta.wikimedia.org/wiki/User-Agent_policy
HEADERS = {
    "User-Agent": "UKFamilyTour/1.0 (private family trip app; contact ilya@finkelsteinlab.org)",
    "Accept": "application/json",
}
TARGET_WIDTH = 800          # bundled image width; never upscale past the original
POLITE_DELAY = 0.6          # seconds between requests, to stay under rate limits


def _open(url: str):
    req = urllib.request.Request(url, headers=HEADERS)
    return urllib.request.urlopen(req, timeout=30)


def _with_retry(fn, *, tries=4):
    delay = 2.0
    for attempt in range(tries):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < tries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise


def get_json(url: str):
    def go():
        with _open(url) as r:
            return json.load(r)
    return _with_retry(go)


def download(url: str, dest: Path):
    def go():
        with _open(url) as r:
            dest.write_bytes(r.read())
    _with_retry(go)


def fetch_thumb_url(title: str) -> str | None:
    """Ask the MediaWiki pageimages API for a ready-made thumbnail at TARGET_WIDTH.

    The API returns a URL for a thumbnail size it actually supports (clamped to
    the original width), so we never trigger the 400 "use listed thumbnail
    sizes" error that hand-rewriting the width causes under Wikimedia's current
    thumbnail-bucketing policy.
    """
    params = urllib.parse.urlencode({
        "action": "query",
        "format": "json",
        "prop": "pageimages",
        "piprop": "thumbnail|original",
        "pithumbsize": str(TARGET_WIDTH),
        "titles": title,
        "redirects": "1",
    })
    data = get_json("https://en.wikipedia.org/w/api.php?" + params)
    pages = (data.get("query") or {}).get("pages") or {}
    for page in pages.values():
        thumb = (page.get("thumbnail") or {}).get("source")
        if thumb:
            return thumb
        orig = (page.get("original") or {}).get("source")
        if orig:
            return orig
    return None


def main():
    data = json.loads(IMAGES_JSON.read_text())
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ok = fail = 0
    for sight_id, cfg in data.items():
        for idx, title in enumerate(cfg["wiki"]):
            dest = OUT_DIR / f"{sight_id}-{idx}.jpg"
            if dest.exists():
                continue
            try:
                src = fetch_thumb_url(title)
                if not src:
                    raise ValueError("no image on article")
                download(src, dest)
                print(f"ok   {sight_id}-{idx}  ({title})")
                ok += 1
            except Exception as e:
                print(f"skip {sight_id}-{idx}  ({title}): {e}")
                fail += 1
            time.sleep(POLITE_DELAY)
    print(f"\n{ok} images saved to {OUT_DIR}  ({fail} skipped — app will fetch those online)")
    print("Note: images come from Wikipedia/Wikimedia; fine for private family use.")


if __name__ == "__main__":
    main()
