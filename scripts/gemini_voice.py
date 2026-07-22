#!/usr/bin/env python3
"""Voice a sight's narration with Gemini TTS as the app's second voice engine.

For each track of --sight (kid + adult, base + tell_me_more): synthesize the
narration with Gemini (styles/accent per gemini_tts.py), keeping the raw take in
audio-raw-gemini/; synthesize a short spoken title clip into
build-audio/titles-gemini/; then composite region intro + title + narration +
outro into tour/audio-gemini/ — the same layout as tour/audio/, which the app
swaps to when the 'gemini' voice is selected.

Already-rendered files are skipped, so an interrupted run resumes where it left
off. Requires GEMINI_API_KEY (or GEMINI_ENV pointing at a .env).

  python3 gemini_voice.py --sight day09-harry-potter --day 9
"""
import argparse, base64, json, subprocess, sys, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compose_audio as C          # noqa: E402
import gemini_tts as G             # noqa: E402

RAW_G = C.ROOT / "audio-raw-gemini"
TITLES_G = C.ROOT / "build-audio/titles-gemini"
AUDIO_G = C.ASSETS / "audio-gemini"

TITLE_STYLE = ("Announce this chapter title warmly and clearly, like a "
               "storyteller opening a new chapter, then stop: ")


def accent_for(day):
    return "a gentle Scottish accent" if 8 <= day <= 12 else \
        "a warm British Received Pronunciation accent"


def synth(text, voice, out_mp3, tries=6):
    body = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    req = urllib.request.Request(
        G.ENDPOINT, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": G.load_key()})
    for i in range(tries):
        try:
            resp = json.load(urllib.request.urlopen(req, timeout=300))
            break
        except urllib.error.HTTPError as e:
            detail = e.read().decode()[:200]
            if e.code in (429, 500, 503) and i < tries - 1:
                time.sleep(30 * (i + 1))
                continue
            raise RuntimeError(f"HTTP {e.code}: {detail}")
        except Exception as e:   # timeouts, transient DNS/socket errors
            if i < tries - 1:
                time.sleep(30 * (i + 1))
                continue
            raise RuntimeError(str(e))
    pcm = base64.b64decode(resp["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    wav = out_mp3.with_suffix(".wav")
    wav.write_bytes(G.pcm_to_wav(pcm))
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav),
                    "-ac", "1", "-b:a", "96k", str(out_mp3)], check=True)
    wav.unlink()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sight", required=True)
    ap.add_argument("--day", type=int, required=True)
    ap.add_argument("--kid-voice", default="Leda")
    ap.add_argument("--adult-voice", default="Iapetus")
    ap.add_argument("--accent", default=None)
    ap.add_argument("--workers", type=int, default=1)
    a = ap.parse_args()
    accent = a.accent or accent_for(a.day)
    man = json.loads((C.ASSETS / "manifest.json").read_text())
    sight = next(s for s in man["sights"] if s["id"] == a.sight)

    jobs = []   # (aud, rel-path, title)
    for aud in ("kid", "adult"):
        for t in sight["tracks"][aud]:
            for e in [t] + t.get("tell_me_more", []):
                jobs.append((aud, e["file"], e["title"]))

    voices = {"kid": a.kid_voice, "adult": a.adult_voice}
    accent_line = f"Speak throughout in {accent}. "

    def render(job):
        aud, rel, title = job
        sub = Path(rel).relative_to("content").with_suffix(".mp3")
        raw, tclip = RAW_G / sub, TITLES_G / sub
        try:
            if not raw.exists():
                text = G.md_text(C.ASSETS / rel)
                synth(accent_line + G.STYLES[aud] + text, voices[aud], raw)
            if not tclip.exists():
                synth(accent_line + TITLE_STYLE + title, voices[aud], tclip)
            return sub, None
        except Exception as e:
            return sub, str(e)

    print(f"{len(jobs)} tracks to voice with Gemini ({a.sight})", flush=True)
    fails = []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for sub, err in ex.map(render, jobs):
            print(("ok  " if not err else "FAIL ") + str(sub) + (f"  {err}" if err else ""), flush=True)
            if err:
                fails.append((sub, err))
    if fails:
        sys.exit(f"{len(fails)} failures; not compositing. Re-run to resume.")

    reg = C.region(a.day)
    intro, outro = C.MUSIC / f"{reg}-intro.mp3", C.MUSIC / f"{reg}-outro.mp3"
    ok = 0
    for aud, rel, _ in jobs:
        sub = Path(rel).relative_to("content").with_suffix(".mp3")
        good, err = C.compose(RAW_G / sub, TITLES_G / sub, intro, outro, AUDIO_G / sub)
        ok += 1 if good else 0
        if not good:
            print("FAIL compose", sub, err, flush=True)
    print(f"composited {ok}/{len(jobs)} → {AUDIO_G}", flush=True)


if __name__ == "__main__":
    main()
