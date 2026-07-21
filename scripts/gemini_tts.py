#!/usr/bin/env python3
"""Experimental: synthesize one narration file with Google's Gemini TTS, as an
alternative voice to Kokoro, prompted to sound like a warm, knowledgeable tour
guide.

Gemini TTS is *prompt-steerable*: you prepend a natural-language STYLE directive
describing HOW to speak (pace, warmth, emphasis), then the text. This is what
gives the most natural cadence — it is not SSML.

Key handling: reads GEMINI_API_KEY from the environment; if absent, loads it from
a .env file (default: the deep-research skill's .env). The key is never printed.

Usage:
    python3 gemini_tts.py --md ../tour/content/day11-stirling-castle/adult/00-why-stirling-matters.md \
        --out ../gemini-tts-sample/why-stirling-guide.m4a --voice Charon

Voices worth trying for a guide (Google prebuilt): Charon (informative),
Sulafat (warm), Iapetus (clear), Sadaltager (knowledgeable), Vindemiatrix (gentle).
"""
import argparse, base64, json, os, re, struct, subprocess, sys, urllib.request, urllib.error
from pathlib import Path

MODEL = "gemini-2.5-flash-preview-tts"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

# The style directive that makes it sound like a real docent. Tuned for natural
# cadence: unhurried, conversational, warm, with natural pauses and light
# emphasis on names, dates and the "why it matters" beats.
STYLE_ADULT = (
    "You are a warm, worldly, knowledgeable tour guide speaking to a curious "
    "family standing in front of a great castle. Read the following aloud "
    "unhurried and conversational, as if telling a story you love. Use natural "
    "pauses at the commas and full stops, let the rhythm breathe, land gently on "
    "names, places and dates, and let genuine curiosity and quiet wonder colour "
    "your voice. Do not sound like a news reader or an advert. Warm, clear, "
    "human. Here is what to say:\n\n"
)
STYLE_KID = (
    "You are a warm, playful storyteller talking to an eight year old at a "
    "castle. Read the following aloud with bright, friendly energy and a smile "
    "in your voice, unhurried, with lots of natural expression and a real sense "
    "of wonder and fun. Slow down for the exciting or spooky bits, and sound "
    "genuinely delighted, never fake-jolly or sing-song. Here is what to say:\n\n"
)
STYLES = {"adult": STYLE_ADULT, "kid": STYLE_KID}


def load_key():
    k = os.environ.get("GEMINI_API_KEY")
    if k:
        return k
    for p in [os.environ.get("GEMINI_ENV"),
              Path.home() / ".claude/skills/deep-research/.env",
              Path.home() / ".claude/skills/networking/.env"]:
        if not p:
            continue
        p = Path(p)
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if line.startswith("GEMINI_API_KEY"):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("GEMINI_API_KEY not found in env or .env")


def md_text(path: Path) -> str:
    lines = path.read_text().splitlines()
    if lines and lines[0].startswith("#"):
        lines = lines[1:]
    lines = [l for l in lines if not l.lstrip().startswith(">")]
    return re.sub(r"[ \t]+", " ", "\n".join(l.strip() for l in lines)).strip()


def pcm_to_wav(pcm: bytes, rate=24000) -> bytes:
    # Gemini returns raw 16-bit little-endian mono PCM at 24 kHz.
    n = len(pcm)
    header = b"RIFF" + struct.pack("<I", 36 + n) + b"WAVEfmt " + struct.pack(
        "<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16) + b"data" + struct.pack("<I", n)
    return header + pcm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--voice", default="Charon")
    ap.add_argument("--audience", choices=["adult", "kid"], default="adult")
    ap.add_argument("--accent", default="",
                    help='accent instruction injected into the style prompt, e.g. '
                         '"British Received Pronunciation" or "a gentle Scottish lilt"')
    ap.add_argument("--model", default=MODEL)
    args = ap.parse_args()

    text = md_text(Path(args.md))
    accent = f"Speak throughout in {args.accent}. " if args.accent else ""
    body = {
        "contents": [{"parts": [{"text": accent + STYLES[args.audience] + text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": args.voice}}},
        },
    }
    req = urllib.request.Request(
        ENDPOINT.replace(MODEL, args.model),
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": load_key()},
    )
    try:
        resp = json.load(urllib.request.urlopen(req, timeout=120))
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode()[:400]}")
    part = resp["candidates"][0]["content"]["parts"][0]
    pcm = base64.b64decode(part["inlineData"]["data"])
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    wav = out.with_suffix(".wav")
    wav.write_bytes(pcm_to_wav(pcm))
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav),
                    "-c:a", "aac", "-b:a", "128k", str(out)], check=True)
    wav.unlink()
    print(f"ok  {out}  ({len(pcm)//48000}s, voice={args.voice})")


if __name__ == "__main__":
    main()
