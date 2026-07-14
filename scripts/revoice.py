#!/usr/bin/env python3
"""Re-voice every track's narration AND title clip with DeepInfra MiMo VoiceDesign
(British), adults at 1.25x, kids at 1.0x. Narration -> audio-raw/, titles ->
build-audio/titles/. Resumable via a progress marker. Day 5 (National Gallery day)
is processed first. Compositing (music + title + narration) is a separate step."""
import json, re, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mimo

ROOT = Path("/Users/ilya/projects/London-trip-vacation/tour-app")
ASSETS = ROOT / "app/src/main/assets/tour"
RAW = ROOT / "audio-raw"
TITLES = ROOT / "build-audio/titles"
MARK = ROOT / "scripts/revoice-done.json"
KEY = mimo.key()
VC = {"adult": (mimo.ADULT_DESC, mimo.ADULT_STYLE, 1.25),
      "kid":   (mimo.KID_DESC,   mimo.KID_STYLE,   1.0)}

def body(rel):
    lines = (ASSETS / rel).read_text().splitlines()
    if lines and lines[0].startswith("#"): lines = lines[1:]
    t = " ".join(l.strip() for l in lines if l.strip())
    t = t.replace("—", ", ").replace("–", ", ")
    return re.sub(r"\s+", " ", t).strip()

def title(rel):
    first = (ASSETS / rel).read_text().splitlines()[0].strip()
    t = first[2:].strip() if first.startswith("# ") else first
    return re.sub(r"^\s*Tell Me More:\s*", "", t, flags=re.I)

def tasks():
    man = json.loads((ASSETS / "manifest.json").read_text())
    sights = sorted(man["sights"], key=lambda s: (0 if s["day"] == 5 else 1, s["day"], s["id"]))
    out = []
    for s in sights:
        for aud in ("kid", "adult"):
            for t in s["tracks"][aud]:
                for rel in [t["file"]] + [c["file"] for c in t.get("tell_me_more", [])]:
                    sub = Path(rel).relative_to("content").with_suffix(".mp3")
                    out.append(("narr", aud, rel, str(RAW / sub)))
                    out.append(("title", aud, rel, str(TITLES / sub)))
    return out

def run_one(t):
    kind, aud, rel, dst = t
    desc, style, spd = VC[aud]
    text = body(rel) if kind == "narr" else title(rel)
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    mimo.synth(text, desc, style, dst, api_key=KEY, speed=spd)
    return f"{kind}:{aud}:{rel}"

def main():
    done = set(json.loads(MARK.read_text())) if MARK.exists() else set()
    all_t = tasks()
    todo = [t for t in all_t if f"{t[0]}|{t[3]}" not in done]
    print(f"{len(all_t)} total, {len(todo)} to do ({len(done)} already done)", flush=True)
    ok = 0
    with ThreadPoolExecutor(max_workers=5) as ex:
        futs = {ex.submit(run_one, t): t for t in todo}
        for f in as_completed(futs):
            t = futs[f]
            try:
                f.result(); done.add(f"{t[0]}|{t[3]}"); ok += 1
                if ok % 25 == 0:
                    MARK.write_text(json.dumps(sorted(done)))
                    print(f"  {ok}/{len(todo)} ...", flush=True)
            except Exception as e:
                print(f"FAIL {t[0]} {t[2]}: {str(e)[:120]}", flush=True)
    MARK.write_text(json.dumps(sorted(done)))
    print(f"DONE re-voice: {ok}/{len(todo)} this run, {len(done)}/{len(all_t)} total", flush=True)

if __name__ == "__main__":
    main()
