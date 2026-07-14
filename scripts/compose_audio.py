#!/usr/bin/env python3
"""Composite each track's final audio = region intro music + spoken title +
narration + region outro music (short gaps between). Raw narration is preserved
in audio-raw/; composites overwrite assets/tour/audio/ (what the APK bundles).

The 30-second end gap is handled in-app (TourPlayer), not baked, to avoid bloat."""
import json, shutil, subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ROOT = Path("/Users/ilya/projects/London-trip-vacation/tour-app")
ASSETS = ROOT/"app/src/main/assets/tour"
AUDIO = ASSETS/"audio"
RAW = ROOT/"audio-raw"
TITLES = ROOT/"build-audio/titles"
MUSIC = ROOT/"build-audio/music"

def region(day):
    return "london" if day <= 7 else ("edinburgh" if day <= 12 else "york")

def compose(raw, title, intro, outro, out):
    out.parent.mkdir(parents=True, exist_ok=True)
    inputs, filters, labels = [], [], []
    n_in = 0
    def add(path, pad):
        nonlocal n_in
        idx = n_in; n_in += 1
        inputs.extend(["-i", str(path)])
        lab = f"a{idx}"
        pad_f = f",apad=pad_dur={pad}" if pad else ""
        filters.append(f"[{idx}:a]aresample=44100{pad_f}[{lab}]")
        labels.append(f"[{lab}]")
    add(intro, 0.25)
    if title.exists():
        add(title, 0.35)
    add(raw, 0.30)
    add(outro, 0)
    fc = ";".join(filters) + ";" + "".join(labels) + f"concat=n={len(labels)}:v=0:a=1[out]"
    cmd = ["ffmpeg","-loglevel","error","-y",*inputs,"-filter_complex",fc,
           "-map","[out]","-ac","1","-b:a","64k",str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0, (r.stderr[-200:] if r.returncode else "")

def main():
    # one-time: preserve raw narration
    if not RAW.exists():
        print("copying raw narration → audio-raw/ ...", flush=True)
        shutil.copytree(AUDIO, RAW)
    man = json.loads((ASSETS/"manifest.json").read_text())
    jobs = []
    for s in man["sights"]:
        reg = region(s["day"])
        intro, outro = MUSIC/f"{reg}-intro.mp3", MUSIC/f"{reg}-outro.mp3"
        for aud in ("kid","adult"):
            for t in s["tracks"][aud]:
                for rel in [t["file"]] + [c["file"] for c in t.get("tell_me_more",[])]:
                    sub = Path(rel).relative_to("content").with_suffix(".mp3")
                    jobs.append((RAW/sub, TITLES/sub, intro, outro, AUDIO/sub))
    print(f"compositing {len(jobs)} tracks ...", flush=True)
    ok = 0; fails = []
    def run(j):
        good, err = compose(*j)
        return good, j[-1], err
    with ThreadPoolExecutor(max_workers=6) as ex:
        for good, out, err in ex.map(run, jobs):
            if good: ok += 1
            else: fails.append((str(out), err))
    print(f"composited {ok}/{len(jobs)}", flush=True)
    for o,e in fails[:10]: print("FAIL", o, e)

if __name__ == "__main__":
    main()
