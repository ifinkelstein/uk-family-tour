#!/usr/bin/env python3
"""Render a short spoken 'heading' clip for every track title (base + chapters)
with Kokoro, mirroring the content path into build-audio/titles/. Kid titles use
bf_emma, adult use bm_george. Loads the model once. Run: HF_HUB_OFFLINE=1 python3 ..."""
import json, re, subprocess, sys
from pathlib import Path

ROOT = Path("/Users/ilya/projects/London-trip-vacation/tour-app")
ASSETS = ROOT/"tour"
TITLES = ROOT/"build-audio/titles"
VOICES = ROOT/"scripts/voices"

def title_of(rel):
    first = (ASSETS/rel).read_text().splitlines()[0].strip()
    t = first[2:].strip() if first.startswith("# ") else first
    # drop a leading "Tell Me More:" label so the heading is the topic itself
    t = re.sub(r'^\s*Tell Me More:\s*', '', t, flags=re.I)
    return t

def main():
    from kokoro import KPipeline
    import soundfile as sf
    import numpy as np
    pipe = KPipeline(lang_code="b")
    voices = {"kid": str(VOICES/"bf_emma.pt"), "adult": str(VOICES/"bm_george.pt")}
    man = json.loads((ASSETS/"manifest.json").read_text())
    items = []
    for s in man["sights"]:
        for aud in ("kid","adult"):
            for t in s["tracks"][aud]:
                for rel in [t["file"]] + [c["file"] for c in t.get("tell_me_more",[])]:
                    items.append((aud, rel))
    print(f"{len(items)} titles to render", flush=True)
    for i,(aud,rel) in enumerate(items,1):
        dst = (TITLES/Path(rel).relative_to("content")).with_suffix(".mp3")
        if dst.exists(): continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        text = title_of(rel)
        chunks = [a for _,_,a in pipe(text, voice=voices[aud], speed=1.0)]
        wav = dst.with_suffix(".wav")
        sf.write(wav, np.concatenate(chunks), 24000)
        subprocess.run(["ffmpeg","-loglevel","error","-y","-i",str(wav),
                        "-b:a","64k",str(dst)], check=True)
        wav.unlink()
        if i % 40 == 0: print(f"  {i}/{len(items)}", flush=True)
    print("DONE titles", flush=True)

if __name__ == "__main__":
    main()
