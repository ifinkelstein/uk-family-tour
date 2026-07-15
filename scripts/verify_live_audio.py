#!/usr/bin/env python3
"""Verify GitHub Pages serves the same MP3 durations as local generated audio."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "app/src/main/assets/tour"
DEFAULT_BASE_URL = "https://ifinkelstein.github.io/uk-family-tour/"


def load_sight(manifest: dict, sight_id: str) -> dict:
    for sight in manifest["sights"]:
        if sight["id"] == sight_id:
            return sight
    raise SystemExit(f"No sight found for {sight_id}")


def iter_tracks(sight: dict):
    for audience in ("kid", "adult"):
        for track in sight["tracks"][audience]:
            yield audience, track["file"]
            for more in track.get("tell_me_more", []):
                yield audience, more["file"]


def audio_rel(content_rel: str) -> str:
    return str(Path(content_rel).with_suffix(".mp3").relative_to("content"))


def duration_seconds(path: Path) -> float:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip() or f"ffprobe failed for {path}")
    return float(proc.stdout.strip())


def download(url: str, dest: Path) -> None:
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            if resp.status != 200:
                raise RuntimeError(f"HTTP {resp.status} for {url}")
            dest.write_bytes(resp.read())
    except urllib.error.URLError as exc:
        raise RuntimeError(f"failed to fetch {url}: {exc}") from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sight", required=True, help="manifest sight id")
    parser.add_argument("--manifest", default=str(ASSETS / "manifest.json"))
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--max-diff-seconds", type=float, default=0.25)
    args = parser.parse_args()

    manifest = json.loads(Path(args.manifest).read_text())
    sight = load_sight(manifest, args.sight)
    base_url = args.base_url.rstrip("/") + "/"

    failures = []
    count = 0
    total_live = {"kid": 0.0, "adult": 0.0}

    with tempfile.TemporaryDirectory(prefix=f"live-audio-{args.sight}-") as tmp_dir:
        tmp = Path(tmp_dir)
        for audience, content_rel in iter_tracks(sight):
            rel = audio_rel(content_rel)
            local = ASSETS / "audio" / rel
            live = tmp / rel.replace("/", "__")
            url_path = urllib.parse.quote(f"app/src/main/assets/tour/audio/{rel}")
            url = urllib.parse.urljoin(base_url, url_path)
            download(url, live)
            local_duration = duration_seconds(local)
            live_duration = duration_seconds(live)
            diff = abs(local_duration - live_duration)
            ok = diff <= args.max_diff_seconds
            total_live[audience] += live_duration
            count += 1
            status = "ok" if ok else "FAIL"
            print(
                f"{status} {audience} {rel}: "
                f"local {local_duration / 60:.2f} min, "
                f"live {live_duration / 60:.2f} min, diff {diff:.2f}s",
                flush=True,
            )
            if not ok:
                failures.append(rel)

    print(
        f"summary {args.sight}: {count} tracks, "
        f"live kids {total_live['kid'] / 60:.1f} min, "
        f"live adults {total_live['adult'] / 60:.1f} min",
        flush=True,
    )
    if failures:
        print("live duration mismatches:", file=sys.stderr)
        for rel in failures:
            print(f"  {rel}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
