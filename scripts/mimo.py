#!/usr/bin/env python3
"""DeepInfra MiMo-V2.5-TTS VoiceDesign helper. Reads the API key from the macOS
keychain (service 'deepinfra-api-key'). synth(text, desc, style, out_mp3)."""
import base64, json, subprocess, urllib.request, os

URL = "https://api.deepinfra.com/v1/inference/XiaomiMiMo/MiMo-V2.5-tts-VoiceDesign"
SEED = 20260714  # fix the designed-voice identity so it stays consistent across all tracks

def key():
    return subprocess.run(["security", "find-generic-password", "-s", "deepinfra-api-key", "-w"],
                          capture_output=True, text=True).stdout.strip()

ADULT_DESC = ("A cultured British man in his fifties with a warm baritone and Received "
              "Pronunciation, the engaging, measured delivery of a favourite museum docent.")
ADULT_STYLE = ("You are an exceptional private tour guide for well-travelled adults: warm, "
               "cultured, and quietly witty, with a rich British voice. Narrate with easy "
               "confidence and genuine curiosity; let real enthusiasm surface on the surprising, "
               "clever, or darker details. Unhurried and conversational, never announcer-like.")
KID_DESC = ("A warm, friendly British woman in her thirties with a bright, expressive storytelling "
            "voice and gentle Received Pronunciation warmth.")
KID_STYLE = ("You are a warm, playful British storyteller leading curious children on a real "
             "adventure around Britain. Bright, expressive energy, savour the funny and gross bits "
             "with a grin, build a little suspense before the surprises, sound genuinely delighted. "
             "Friendly and natural, never shouty, sing-song, babyish, or manic.")

def synth(text, desc, style, out_mp3, api_key=None, speed=1.0, tries=4):
    body = json.dumps({"text": text, "voice": desc, "instructions": style, "seed": SEED}).encode()
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(URL, data=body, method="POST", headers={
                "Authorization": f"Bearer {api_key or key()}", "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                j = json.loads(r.read())
            audio = j["audio"]
            b64 = audio.split(",", 1)[1] if audio.startswith("data:") else audio
            tmp = out_mp3 + ".wav"
            open(tmp, "wb").write(base64.b64decode(b64))
            af = ["-filter:a", f"atempo={speed}"] if abs(speed - 1.0) > 0.01 else []
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", tmp, *af,
                            "-ac", "1", "-b:a", "64k", out_mp3], check=True)
            os.remove(tmp)
            return j.get("inference_status", {})
        except Exception as e:
            last = e
            import time; time.sleep(2 * (attempt + 1))
    raise last

if __name__ == "__main__":
    k = key()
    n = synth("The White Tower is nearly a thousand years old. William the Conqueror began it "
              "around 1078, partly to guard the city, and partly to overawe the Londoners he had "
              "just conquered.", ADULT_DESC, ADULT_STYLE,
              "/Users/ilya/projects/London-trip-vacation/tour-app/scripts/sample-adult.mp3", k)
    print("adult sample bytes:", n)
    n = synth("Get ready to meet some very clever birds! These are the famous Tower ravens, and "
              "there is an old legend that says if the six ravens ever leave, the whole castle will "
              "come tumbling down. So nobody wants to risk it!", KID_DESC, KID_STYLE,
              "/Users/ilya/projects/London-trip-vacation/tour-app/scripts/sample-kid.mp3", k)
    print("kid sample bytes:", n)
