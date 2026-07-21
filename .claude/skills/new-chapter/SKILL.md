---
name: new-chapter
description: >-
  End-to-end pipeline to add a new chapter, sub-chapters, or a themed sight to the
  UK Family Tour audio-tour app. Researches and writes kid + adult narration, de-LLMs
  it, gathers an attributed media drawer (photos + optional video/audio), builds the
  PDF/EPUB, voices it with local Kokoro (optionally Gemini TTS), verifies audio length,
  and commits + pushes. Use when asked to add/write a new chapter, sub-chapters, a
  "significance & overview" opener, or a themed sight (e.g. "add a chapter on X",
  "write a sight about Y", "add an overview chapter to day N").
---

# Add a new chapter / sight to the UK Family Tour

One unified runbook. Work from the app root `/Users/ilya/projects/London-trip-vacation/tour-app`.
Follow the user's global shell rules: one command per Bash call, no `&&`/`;`/`|`, quote paths with spaces.
Kokoro steps load a model — never run two Kokoro passes at once. Everything committed is Kokoro-voiced;
Gemini TTS is an opt-in sample only.

## 0. Decide placement and gather parameters

Ask/derive:

- **TOPIC** — what the chapter is about.
- **PLACEMENT** — one of:
  - *New themed sight* (like `day09-whisky`, `day09-literary-edinburgh`): pick `SIGHT_ID = dayNN-slug`,
    content dir `tour/content/<SIGHT_ID>/`, base file `01-<slug>.md`.
  - *Overview opener* prepended to an existing sight's headline sight (chapter 1, renumbers): base file `00-<slug>.md`.
  - *Extra chapter* appended to an existing sight: base file `NN-<slug>.md` (next free number).
- **DAY** (integer) — sets the region music and the Gemini accent. London = days ≤ 7, Edinburgh/Scotland = 8–12, York = 13–14.
- Audiences are always **both** (kid + adult).

## 1. Research & write the narration (subagent)

Launch a `general-purpose` agent with a brief modeled on the existing ones (read
`AGENT-CONTENT-SPEC.md` first). It must:

- Read `AGENT-CONTENT-SPEC.md` and the target sight's existing content (connect, don't repeat).
- Write a **base** story + **2–6 sub-chapters**, BOTH `adult` and `kid`, at the exact paths above
  (`# <spoken title>` first line; flowing prose for the ear; no lists/headings/URLs/`>`-lines;
  spell out odd numbers; commas over dashes).
- Highly-educated GENERAL audience, not PhDs; gloss any specialist term. Kids: real storytelling, a wow/yuck,
  never dumbed-down. For sensitive topics (e.g. alcohol) keep the kid version safe and age-appropriate.
- **De-LLM as it writes** (see step 2 for the tell-list) and fact-check every date/name/claim with WebSearch.
- Write the sidecar `tour/content/<contentdir>/tracks.json` (or `overview-tracks.json` for openers),
  shape `{"kid":[{"file":...,"title":...,"est_minutes":n,"tell_me_more":[...]}],"adult":[...]}`,
  est_minutes = words / 150.

## 2. De-LLM / writing-style pass

Apply the `writing-style` skill to the new files. At minimum, scan and fix:

```bash
grep -rn "—" tour/content/<contentdir>
grep -rniE "\b(nestled|boasts?|testament|vibrant|tapestry|realm|delve|leverage|showcase|underscore|meticulous|intricate|renowned|pivotal|crucial|bustling|iconic|serves as|stands as|steeped in)\b" tour/content/<contentdir>
grep -rniE "not (just|only|merely|simply) .* (but|it)|here'?s (the|what|why)|it'?s worth noting|think of it as" tour/content/<contentdir>
```

Rewrite any hits in plain, human, tour-guide prose. Read the base + one hard sub-chapter to confirm the
voice reads like a person, not just that it is tell-free.

## 3. Media drawer

Search Commons and pick good, on-topic, freely-licensed files:

```bash
python3 scripts/chapter_media.py search "your subject here"
```

Write a media spec JSON (see the header of `scripts/chapter_media.py`) with 3–12 items — mostly `image`
(Commons `File:` titles + your `caption`/`kidcaption`/`chapter`), optionally `video` (verified embeddable
YouTube ids; keep as links) and `audio` (files you place under `tour/media/<SIGHT_ID>/audio/`, e.g. Kokoro
readings of public-domain text or short atmospheric clips). Then:

```bash
python3 scripts/chapter_media.py build /path/to/spec.json
```

That downloads images with full attribution and writes `tour/media/<SIGHT_ID>.json` + `-CREDITS.md`.
Then register the sight in `MEDIA_SIGHTS` in `app.js` (edit the array). For a **new sight**, also give it a
hero: add a `tour/images.json` entry (`emoji`, `color`, `wiki:[...]`) and run `python3 scripts/fetch_images.py`
so `tour/images/<SIGHT_ID>-0.jpg` exists (the card thumbnail + verify need it).

Single-base-chapter sights: tag all media `chapter: 1`. Multi-base sights: tag each item to its base index.

## 4. Wire the manifest

```bash
# new themed sight (after an existing sight on the day, or end of the day):
python3 scripts/manifest_tools.py add-sight --id <SIGHT_ID> --name "<Name>" --day <DAY> --date "<Ddd Mmm D>" --note "Optional · <hook>" --after <existing-sight-id>
# overview opener prepended to an existing sight (renumbers it):
python3 scripts/manifest_tools.py prepend --sight <existing-sight-id> --tracks tour/content/<contentdir>/overview-tracks.json
# extra chapter appended:
python3 scripts/manifest_tools.py append --sight <existing-sight-id> --tracks tour/content/<contentdir>/tracks.json
```

Validate: `python3 -m json.tool tour/manifest.json > /dev/null`. To customize sub-chapter play order,
edit the `tell_me_more` array order before adding.

## 5. Voice with Kokoro (the committed audio)

Three steps, in order, one Kokoro pass at a time (`bf_emma` kids, `bm_george` adults, speed 1.0):

```bash
cd scripts
HF_HUB_OFFLINE=1 venv/bin/python generate_audio.py --manifest ../tour/manifest.json --out ../audio-raw --only <slug> --speed 1.0 --kid-voice bf_emma --adult-voice bm_george
HF_HUB_OFFLINE=1 venv/bin/python render_titles.py
cd ..
python3 scripts/compose_chapter.py --sight <SIGHT_ID> --day <DAY> --files <base-stem,sub1-stem,sub2-stem,...>
```

`--only <slug>` should match all the new files (e.g. `water-of-life`). `render_titles.py` renders any missing
title clips and skips the rest. `compose_chapter.py` builds the final MP3s (region music + spoken title +
narration) into `tour/audio/`. The `--files` are bare mp3 stems (base + each sub), no directory/extension.
Long renders: run `generate_audio.py` in the background and continue when it finishes.

## 6. PDF / EPUB

```bash
python3 scripts/build_reading_assets.py --sight <SIGHT_ID> --audience both
```

Rebuild whenever the text changes so the "Read offline" downloads stay in sync.

## 7. (Optional) Gemini TTS sample

Off by default (Kokoro is the committed voice). If the user wants to audition Gemini:

```bash
# British voice by default; gentle Scottish accent for Scotland days (8–12).
GEMINI_ENV=<path to .env with GEMINI_API_KEY> python3 scripts/gemini_tts.py \
  --md tour/content/<contentdir>/adult/<base>.md \
  --out gemini-tts-sample/<slug>-adult.m4a \
  --voice Iapetus --audience adult --accent "a warm British Received Pronunciation accent"
```

For a Scotland day (8–12) use `--accent "a gentle Scottish accent"`. Kid samples: `--audience kid --voice Leda`
(or Sulafat/Aoede). Needs a billed Gemini key (TTS is not free-tier). `gemini-tts-sample/` is git-ignored and
these are never wired into the app; force-add only if the user asks to share them.

## 8. Verify

```bash
python3 scripts/verify_assets.py
node --check app.js
python3 scripts/check_durations.py <SIGHT_ID>
```

`verify_assets.py` must report all tracks rendered and the sight's first image present.
`check_durations.py` checks each composited MP3's spoken length against its word count (flag anything far
outside ~130–220 wpm — usually a truncated or mis-composited file; re-render it).

## 9. Commit & push

Stage only this chapter's files plus the touched shared files (`app.js`, `tour/manifest.json`,
`tour/images.json`), confirm nothing secret/sample is staged, then commit and push:

```bash
git add tour/content/<contentdir> tour/audio/<SIGHT_ID> tour/media/<SIGHT_ID>.json tour/media/<SIGHT_ID>-CREDITS.md "tour/media/<SIGHT_ID>/" app.js tour/manifest.json tour/images.json
git add "reading-pdfs/DD <Name> - Kids.pdf" "reading-pdfs/DD <Name> - Grown-ups.pdf" "reading-epubs/DD <Name> - Kids.epub" "reading-epubs/DD <Name> - Grown-ups.epub"
git diff --cached --name-only | grep -iE "\.env|gemini-tts-sample|api.?key" || echo "clean"
git commit -m "feat(dayN): <one-line>" -m "<body>" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
git push origin main
```

Never stage `.env` files or `gemini-tts-sample/`. If the render re-encoded already-committed audio (only when
composing a whole day at once), `git checkout --` those unchanged files before committing to avoid noise.

## Reference

- Region music: `london` (days ≤7), `edinburgh` (8–12), `york` (13–14) — handled by day in `compose_chapter.py`.
- Voices: kids `bf_emma`, adults `bm_george`, speed 1.0 (Kokoro-82M, British English pipeline).
- Helpers added for this skill: `scripts/chapter_media.py`, `scripts/manifest_tools.py`, `scripts/compose_chapter.py`.
- Existing tools reused: `generate_audio.py`, `render_titles.py`, `compose_audio.py`, `build_reading_assets.py`,
  `verify_assets.py`, `check_durations.py`, `fetch_images.py`, `gemini_tts.py`.
