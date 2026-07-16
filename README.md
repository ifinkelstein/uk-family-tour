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
- A "Royal Family Tree" screen (entry card on the days list) shows a simplified
  monarch timeline with Wikipedia portraits; each monarch links to the chapters
  where they appear, and tracks show 👑 chips linking back to the tree.
  Data lives in `tour/monarchy.json`; portraits come from
  `scripts/fetch_monarch_images.py` into `tour/images/monarchs/`.

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
  monarchy.json         royal family tree data + chapter links
  content/              narration markdown
  audio/                rendered Kokoro MP3 files
  images/               bundled sight photos (+ images/monarchs/ portraits)
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

## Cross-references ("Related listening")

Curated links between historically or practically related chapters live in
`scripts/add_related.py` (the LINKS table is the source of truth). Running it
rebuilds, idempotently:

- `related` arrays on base tracks in `tour/manifest.json` (audience-specific;
  the app shows them as tappable rows under the track and jumps to the target
  chapter), and
- trailing `> Related listening:` lines in the source markdown.

Markdown lines starting with `>` are transcript-only callouts: the TTS scripts
(`generate_audio.py`, `revoice.py`, `mimo_long.py`) and `check_durations.py`
skip them, while the reading PDF/EPUB builds render them as blockquote notes.
After editing links, rerun `add_related.py` and `build_reading_assets.py`.
