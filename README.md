# UK Family Tour — Android App + Content + Voice Pipeline

Everything for your audio tour of the July 2026 trip (London → Edinburgh → York):
the Android app, all 220 narration scripts baked in, and scripts to add
natural voices and offline images.

## Fully offline

The app makes zero network requests — no INTERNET permission at all. All
photos and all narration audio are bundled into the APK during the prepare
step below, so it works in castle basements, on the Inchcolm ferry, and in
airplane mode. One command prepares everything:

    cd scripts && ./prepare_assets.sh

(downloads sight images from Wikipedia + renders all 220 tracks with the
free Kokoro-82M voices, then verifies completeness). Full agent-friendly
build/install runbook: see AGENT.md.

## What's in the box

    app/                     Android app (Kotlin + Jetpack Compose)
      src/main/assets/tour/  manifest.json, all content .md files, images.json
    scripts/
      generate_audio.py      free high-quality voice generation (Kokoro-82M)
      fetch_images.py        optional: bundle images for offline use
    README.md                this file

## Build the app (10 minutes)

1. Install Android Studio (free) on your Mac.
2. Open Android Studio → "Open" → select this folder. Let Gradle sync.
3. Plug in a phone with USB debugging enabled (or use the emulator) and press Run ▶.
   To share with the rest of the family: Build → Generate Signed App Bundle/APK
   → APK, then send the APK file to their Android phones.

## What the app does

- **Journey screen** — the itinerary day by day, color-coded per city
  (postbox red = London, thistle = Edinburgh, teal = York). Tap a sight.
- **Kids / Grown-ups toggle** — everywhere; kids get bigger art, playful type,
  and the same places told their way.
- **Player** — play/pause (works mid-sentence), next/previous, per-track
  progress bar, playback speed (0.8×–1.5×), and automatic advance to the
  next story. Audio pauses politely for phone calls and navigation prompts.
- **✨ Tell me MORE!** — after any story, one tap queues the deeper extension
  track for that exact subject, then continues the tour.
- **Images** — each sight and story shows real photos (Tower ravens, the
  Rosetta Stone, the Forth Bridge...) bundled into the app by
  `prepare_assets.sh`; no connection needed on the trip.
- **Tour Passport** — kids collect a gold VISITED stamp for each sight where
  they've heard every story. 18 stamps to earn across the trip.
- **Checkmarks** — finished tracks are remembered, so you can pick up where
  you left off after lunch.

## Voices

`prepare_assets.sh` renders every track with Kokoro-82M — a free,
Apache-licensed model with genuinely good intonation. Defaults: warm British
female (bf_emma) for kid tracks, measured British male (bm_george) for
adults — override with KID_VOICE / ADULT_VOICE env vars, e.g.
`KID_VOICE=bf_isabella ./prepare_assets.sh`. About 3 hours of audio renders
in well under an hour on an Apple Silicon Mac; a free Colab (cloud GPU)
recipe is in the header of generate_audio.py. Expect ~150–200 MB of MP3s.
The player shows 🎙 when using these; if you build without running the
prepare step, the app still works using Android's built-in UK voice (🤖) —
its only rough edge, and the images will be emoji placeholders.

## Notes

- Content and images are for your family's private use on the trip.
- No accounts, no tracking, no ads, no network access whatsoever.
- manifest.json remains the single source of truth — edit any .md file or
  add tracks there and the app picks them up on rebuild.
