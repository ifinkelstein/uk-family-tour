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
  manifest.json      playlists and sub-chapter structure (source of truth)
  images.json        sight image metadata ({emoji, color, wiki[]} per sight)
  monarchy.json      royal family tree: sections, monarchs, chapter links
  content/           narration markdown (per sight: kid/ and adult/)
  audio/             Kokoro MP3 files served by the app (mirrors content/)
  images/            bundled sight photos (+ images/monarchs/ portraits)
  maps/              outdoor PNGs, indoor SVGs, day-overview PNGs
```

Reading downloads (in-app "Read offline" PDF/EPUB links) live at the app root
under `reading-pdfs/` and `reading-epubs/`, one file per sight per audience.

## UX contract

- Kids and grown-ups use the same interface. The audience toggle (default Kids)
  changes the playlist, copy, and audio only, never the controls.
- Switching audience mid-tour rebuilds the live queue in the new mode at the
  same story (do not leave the old mode's audio playing against the new list).
- Sub-chapters are visible as indented rows under their main story
  (`tell_me_more` in the manifest); there is no separate "Tell me more" button.
- Playing a main story queues its sub-chapters and chains into them after a
  short beat, announcing each sub-chapter title first. Playback STOPS at the end
  of a story — it must not auto-cross into the next main story; the player shows
  "Story complete — up next: …" and the user resumes with ▶/⏭.
- Progress ("heard") is stored per file in `localStorage`; resume state
  (screen, queue, position, playback time, audience) is saved so the days
  screen can offer a "Continue" card.
- Offline: the service worker (`sw.js`) caches the shell + images; the per-day
  ⬇ button pre-caches that day's audio for BOTH audiences plus its maps. Audio
  is cached whole and Range requests are sliced from the cached body (iOS
  Safari requirement) — keep that path intact.
- Maps: each sight has an outdoor PNG (`tour/maps/<sight-id>.png`); indoor
  sights use `<sight-id>-indoor.svg` (the `INDOOR_MAPS` list in app.js); multi-
  sight days use `day-NN.png` day-overview maps (the `DAY_MAPS` list).
- Lock-screen / earbud controls run through the Media Session API.
- The Royal Family Tree screen and 👑 crown backlinks read from
  `tour/monarchy.json`. Cross-references ("Related listening") come from the
  `related` arrays on base tracks (see README).

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
