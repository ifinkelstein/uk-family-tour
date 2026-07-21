#!/usr/bin/env python3
"""Composite specific tracks = region intro music + spoken title + narration + outro.
Reads raw narration from audio-raw/ and title clips from build-audio/titles/, writes
the final MP3s the app serves into tour/audio/. Region music follows the day.

  compose_chapter.py --sight day09-whisky --day 9 \
      --files 01-water-of-life,01-water-of-life-more-1,01-water-of-life-more-2

--files are bare mp3 stems (no directory, no extension); both kid/ and adult/ are done.
"""
import sys, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compose_audio as C  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sight", required=True)
    ap.add_argument("--day", type=int, required=True)
    ap.add_argument("--files", required=True)
    a = ap.parse_args()
    reg = C.region(a.day)
    intro, outro = C.MUSIC / f"{reg}-intro.mp3", C.MUSIC / f"{reg}-outro.mp3"
    ok, fails = 0, []
    for aud in ("kid", "adult"):
        for f in a.files.split(","):
            sub = Path(f"{a.sight}/{aud}/{f}.mp3")
            raw, title, out = C.RAW / sub, C.TITLES / sub, C.AUDIO / sub
            if not raw.exists():
                fails.append((str(raw), "missing raw")); continue
            if not title.exists():
                fails.append((str(title), "missing title")); continue
            good, err = C.compose(raw, title, intro, outro, out)
            ok += 1 if good else 0
            if not good:
                fails.append((str(out), err))
    print(f"composited {ok}")
    for o, e in fails:
        print("FAIL", o, e)


if __name__ == "__main__":
    main()
