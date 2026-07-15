# UK Family Tour - Web Audio Tour

Static offline-capable web app for the July 2026 UK trip. The project is now
web-only: no Android app, Gradle build, or APK packaging is supported.

## Run locally

```bash
python3 -m http.server 8787
open http://127.0.0.1:8787/
```

The app can be installed from the browser as a PWA. Once the shell and a day's
audio are cached, it works offline.

## What the app does

- Journey view for the itinerary, grouped by day and sight.
- Shared kids/grown-ups interface; the toggle changes the content and audio,
  not the controls.
- Audio player with play/pause, previous/next, scrubber, speed control, and
  automatic advance.
- Sub-chapters are shown as rows under each main story. Playing a main story
  automatically continues into its sub-chapters, announcing each sub-chapter
  title before the audio starts.
- Progress is remembered locally, including sub-chapter completion.
- Images, markdown, and MP3 narration are served from committed static assets.

## Project layout

```text
index.html              web app shell
app.js                  UI, player, queueing, progress
styles.css              web styling
sw.js                   offline shell/audio cache
manifest.webmanifest    PWA metadata
icons/                  PWA icons
tour/
  manifest.json         itinerary and track manifest
  images.json           sight image metadata
  content/              narration markdown
  audio/                rendered Kokoro MP3 files
  images/               bundled sight photos
reading-pdfs/           optional reading downloads
reading-epubs/          optional reading downloads
scripts/                asset, audio, and validation tools
```

## Verify

```bash
python3 scripts/verify_assets.py
node --check app.js
python3 -m json.tool tour/manifest.json >/tmp/manifest-check.json
```

`scripts/verify_assets.py` is the asset completeness gate. It checks that every
manifest track has markdown and MP3 audio, including sub-chapters.

## Voices and assets

Kokoro-generated MP3s are committed under `tour/audio/` and are the audio the
web app serves. To regenerate audio, use the scripts in `scripts/`; generated
intermediates go under ignored directories such as `audio-raw/` and
`build-audio/`.

`tour/manifest.json` remains the single source of truth. Edit the markdown and
manifest together, then rerun the verification commands above.
