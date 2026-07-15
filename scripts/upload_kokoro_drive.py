#!/usr/bin/env python3
"""Mirror the app's Kokoro audio tree to a Drive folder, by <sight>/<audience>.
Idempotent: skips files already present. Usage: python3 upload_kokoro_drive.py <parent_folder_id>"""
import json, os, subprocess, sys
from pathlib import Path

AUDIO = Path("/Users/ilya/projects/London-trip-vacation/tour-app/tour/audio")
PARENT = sys.argv[1]
# gws only allows --upload of files within the current working directory, so run from AUDIO
# and pass paths relative to it.
os.chdir(AUDIO)

import time
def gws(args, tries=5):
    delay = 2.0
    last = ""
    for _ in range(tries):
        r = subprocess.run(["gws"] + args, capture_output=True, text=True)
        if r.returncode == 0:
            try:
                return json.loads(r.stdout)
            except json.JSONDecodeError:
                last = r.stdout[:300]
        else:
            last = r.stderr[-300:]
        time.sleep(delay); delay = min(delay * 2, 20)
    raise RuntimeError("gws failed after retries: " + last)

def folder(name, parent):
    q = f'name="{name}" and mimeType="application/vnd.google-apps.folder" and "{parent}" in parents and trashed=false'
    r = gws(["drive","files","list","--params",json.dumps({"q":q,"fields":"files(id)"})])
    if r.get("files"): return r["files"][0]["id"]
    return gws(["drive","files","create","--json",json.dumps({"name":name,"mimeType":"application/vnd.google-apps.folder","parents":[parent]}),"--params",json.dumps({"fields":"id"})])["id"]

def upload(path, name, parent):
    q = f'name="{name}" and "{parent}" in parents and trashed=false'
    if gws(["drive","files","list","--params",json.dumps({"q":q,"fields":"files(id)"})]).get("files"):
        return "exists"
    gws(["drive","files","create","--upload",str(path),"--json",json.dumps({"name":name,"parents":[parent]}),"--params",json.dumps({"fields":"id"})])
    return "up"

n=up=0
for sight in sorted(os.listdir(AUDIO)):
    sdir = AUDIO/sight
    if not sdir.is_dir(): continue
    sid = folder(sight, PARENT)
    for aud in ("kid","adult"):
        adir = sdir/aud
        if not adir.is_dir(): continue
        aid = folder(aud, sid)
        for fn in sorted(os.listdir(adir)):
            if not fn.endswith(".mp3"): continue
            st = upload(f"{sight}/{aud}/{fn}", fn, aid)  # relative path within AUDIO (CWD)
            n+=1; up += (st=="up")
            if n % 25 == 0: print(f"{n} processed ({up} uploaded)...", flush=True)
print(f"DONE: {n} files, {up} newly uploaded → folder {PARENT}")
