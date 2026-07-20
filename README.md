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

- Journey view for the itinerary, grouped by day and sight (London → Edinburgh
  → York). The list auto-scrolls to today's leg and marks it with a TODAY pill.
- Shared kids/grown-ups interface; the toggle (🧒 Kids / 🧑 Grown-ups, default
  Kids) changes the content and audio, not the controls. Switching mid-tour
  rebuilds the live queue in the new mode at the same story.
- Audio player with play/pause, previous/next, scrubber, and speed control
  (0.8× / 1.0× / 1.2× / 1.5×).
- Sub-chapters are shown as indented rows under each main story. Playing a main
  story automatically continues into its sub-chapters after a short beat
  (immediately when the phone is pocketed), announcing each sub-chapter title
  before the audio starts. Playback stops at the end of a story rather than
  running into the next main story on its own — the player shows "Story
  complete — up next: …" and ▶/⏭ resumes when the family is ready.
- Progress ("heard") is remembered locally per file, including sub-chapters;
  completed sights get a ✔ stamp.
- Resume-where-you-left-off: the days screen shows a "Continue" card and
  restores the screen, queue, position, and playback time from `localStorage`.
- Maps: each sight has an outdoor map (PNG) opened from a map row; two indoor
  sights (Churchill War Rooms, Hampton Court) also have an indoor SVG sketch;
  multi-sight days (3, 5, 6, 9) have a day-overview map (🗺 on the day header).
  All live in `tour/maps/` — see `scripts/build_maps.py`.
- Offline: a service worker caches the app shell and images. Each day header has
  a ⬇ button that pre-caches that whole day's audio for BOTH audiences plus its
  maps; already-saved days show a ✓ badge. Reading downloads are cached after
  first fetch.
- Read offline: each sight links to a PDF and EPUB of its narration
  (audience-specific) under `reading-pdfs/` and `reading-epubs/`.
- Lock-screen / earbud controls via the Media Session API (play/pause,
  previous/next, seek), with sight artwork as metadata.
- Images, markdown, and MP3 narration are served from committed static assets.
- A "Royal Family Tree" screen (entry card on the days list) shows a simplified
  monarch timeline with Wikipedia portraits, grouped into England / Scotland /
  Union sections; each monarch links to the chapters where they appear, and
  tracks show 👑 chips linking back to the tree. Data lives in
  `tour/monarchy.json`; portraits come from `scripts/fetch_monarch_images.py`
  into `tour/images/monarchs/`.
- A per-sight **media drawer** (opt-in): sights listed in `MEDIA_SIGHTS`
  (app.js) load `tour/media/<sight>.json` and show a "Gallery" row plus a media
  chip under each chapter. The drawer is a chapter-filtered grid of photos
  (Wikimedia, with visible credit/licence/source), short YouTube films (played
  in-app via a `youtube-nocookie` embed), and ~1–2 min period-music clips. Music
  plays through the main player with a one-tap "↩ Back to the tour"; every tile
  has a "▶ Listen to this story" backlink into the matching audio chapter.
  Gallery images and music ride along in the per-day ⬇ offline pre-cache (films
  stay online). Day 11 (Stirling Castle) is the pilot;
  `tour/media/<sight>-CREDITS.md` records attribution.

## Project layout

```text
index.html              web app shell
app.js                  UI, player, queueing, progress
styles.css              web styling
sw.js                   offline shell/audio cache
manifest.webmanifest    PWA metadata
icons/                  PWA icons
tour/
  manifest.json         itinerary and track manifest (source of truth)
  images.json           sight image metadata ({emoji, color, wiki[]} per sight)
  monarchy.json         royal family tree data + chapter links
  content/              narration markdown (per sight: kid/ and adult/)
  audio/                rendered Kokoro MP3 files (mirrors content/ paths)
  images/               bundled sight photos (+ images/monarchs/ portraits)
  maps/                 outdoor PNGs, indoor SVGs, and day-overview PNGs
  media/                media drawer: <sight>.json + <sight>/images|audio/
reading-pdfs/           per-sight, per-audience narration PDFs (in-app links)
reading-epubs/          per-sight, per-audience narration EPUBs (in-app links)
scripts/                asset, audio, and validation tools
```

`tour/manifest.json` has top-level `title`, `wpm_assumption`, `sights`, and
`totals`. Each sight has `id`, `name`, `day`, `date`, `note`, per-audience
`kid_total_minutes` / `adult_total_minutes`, and `tracks.kid` / `tracks.adult`;
each track has `file`, `title`, `est_minutes`, and an optional `tell_me_more`
array of sub-chapters (each also `file` / `title` / `est_minutes`). Base tracks
may also carry a `related` array (see Cross-references below).

## Verify

```bash
python3 scripts/verify_assets.py
node --check app.js
python3 -m json.tool tour/manifest.json >/tmp/manifest-check.json
```

`scripts/verify_assets.py` is the asset completeness gate. It checks that every
manifest track (base + `tell_me_more`) has rendered audio (MP3 or WAV) and that
each sight has at least its first image; `--strict` also requires every image
listed in `images.json`. Related helpers: `scripts/check_durations.py`
(sanity-checks composited MP3 lengths against word counts) and
`scripts/verify_live_audio.py` (checks the deployed site serves the same audio
durations as local).

## Voices and assets

Kokoro-generated MP3s are committed under `tour/audio/` and are the audio the
web app serves. To regenerate audio, use the scripts in `scripts/`; generated
intermediates go under ignored directories such as `audio-raw/` and
`build-audio/`.

`tour/manifest.json` remains the single source of truth. Edit the markdown and
manifest together, then rerun the verification commands above.

The committed audio is composited (region music + spoken title + narration), so
adding or changing a chapter is a three-step render, not one: `generate_audio.py`
(raw narration into `audio-raw/`) → `render_titles.py` (title clips into
`build-audio/titles/`) → `compose_audio.py` (final MP3s into `tour/audio/`). Use
`generate_audio.py --only <slug>` to render just the changed files.

### Alternative voice: Google Gemini TTS (optional)

Kokoro is the default, free, offline voice and produces every committed MP3.
`scripts/gemini_tts.py` is an opt-in alternative that renders a single chapter
with Google's **prompt-steerable** Gemini TTS, for a more expressive "tour guide"
delivery. It takes a chapter markdown file and a voice, prepends a natural-language
style directive (a warm adult guide, or a playful kid storyteller — not SSML),
and writes an `.m4a`:

```bash
python3 scripts/gemini_tts.py \
  --md tour/content/day11-stirling-castle/adult/00-why-stirling-matters.md \
  --out gemini-tts-sample/why-stirling-adult-charon.m4a \
  --voice Charon --audience adult
```

Notes:

- Needs a **billed** Gemini API project — the TTS models are **not** on the free
  tier. The script reads `GEMINI_API_KEY` from the environment or a `.env` file
  and never prints it; **never commit the key**, and `gemini-tts-sample/` is
  git-ignored.
- Voices for a guide: `Charon` (informative), `Sulafat` (warm), `Iapetus`
  (clear); female narrators for kids: `Leda`, `Aoede`, `Kore`. `--audience`
  selects the adult vs kid style prompt.
- Cost is dominated by audio output: a chapter sample is pennies; re-voicing the
  whole tour would be roughly $15–40. Use it for marquee intro chapters and keep
  Kokoro for the long tail. These clips are experiments, not wired into the app.

## Reading downloads (PDF/EPUB)

The in-app "Read offline" links are **generated from the same manifest markdown**,
so they drift if you change content without rebuilding them. After editing any
sight's chapters, regenerate that sight:

```bash
python3 scripts/build_reading_assets.py --sight <sight-id> --audience both
```

This writes `reading-pdfs/DD <Sight> - {Kids,Grown-ups}.pdf` and the matching
EPUBs (pandoc + pdflatex). Rebuild whenever the audio content changes so the
written and spoken versions stay in sync.

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
