# AGENT.md - web app runbook

This repository is the static web/PWA version of the UK Family Tour. Android,
Gradle, APK builds, and phone-side Android install steps have been removed.

## Definition of done

1. `python3 scripts/verify_assets.py` exits 0.
2. `node --check app.js` exits 0.
3. `python3 -m json.tool tour/manifest.json` exits 0.
4. The app serves locally and can fetch `tour/manifest.json`.

## Local run

```bash
python3 -m http.server 8787
open http://127.0.0.1:8787/
```

Use a normal browser install flow if the app should be saved as a PWA on a
phone. The service worker caches the app shell and caches audio on demand.

## Asset root

```text
tour/
  manifest.json      playlists and sub-chapter structure
  images.json        sight image metadata
  content/           narration markdown
  audio/             Kokoro MP3 files served by the app
  images/            bundled sight photos
```

## UX contract

- Kids and grown-ups use the same interface.
- The audience toggle changes the playlist, copy, and audio only.
- Sub-chapters are visible as indented rows under their main story.
- Playing a main story queues its sub-chapters automatically.
- Before a sub-chapter starts, the app announces the sub-chapter title.
- There is no separate "Tell me more" button in the UI.

## Common commands

```bash
python3 scripts/verify_assets.py
node --check app.js
python3 -m json.tool tour/manifest.json >/tmp/manifest-check.json
```

To rebuild static assets:

```bash
cd scripts
./prepare_assets.sh
```

Generated intermediates belong in ignored directories such as `audio-raw/` and
`build-audio/`. Composited app audio belongs in `tour/audio/`.

## Notes

- Do not add Android project files back unless the product direction changes.
- Do not stage unrelated local deletions when committing web changes.
- `tour/manifest.json` is the source of truth for what the app shows and plays.
