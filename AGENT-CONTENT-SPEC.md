# Sub-chapter content agent - shared contract

You are writing narration scripts for an **offline audio walking-tour app** used by one
family (worldly, well-travelled adults + kids about 8–11) on a July 2026 UK trip. You are
expanding the sub-chapter content for ONE sight, in a **per-story mini-series**
structure: each existing base story gets 2–3 new sub-chapters. The manifest field is still
named `tell_me_more` for compatibility, but the web UI presents these as child rows under
the main story and auto-plays them after the main story.

## Paths
- Assets root: `/Users/ilya/projects/London-trip-vacation/tour-app/tour`
- Manifest: `<assets root>/manifest.json`
- Your sight's content: `<assets root>/content/<SIGHT>/kid/` and `.../adult/`

## Steps
1. **Read the current base stories** for your sight (both `kid/` and `adult/`) so your new
   chapters ADD material and never repeat the base track. Get each base story's exact
   `file`, `title`, and `est_minutes` from `manifest.json` — **kid and adult base slugs can
   differ**, so read them per audience; do not assume they match.
2. For **each base story**, write **2–3 sub-chapter** markdown files, for **BOTH** kid and
   adult. Naming: for base `NN-slug.md`, write `NN-slug-more-1.md`, `NN-slug-more-2.md`
   (and `-more-3.md` if warranted), in the same `kid/` or `adult/` folder.
   - First line of each file: `# <Chapter Title>` (a short spoken-ish title; it is stripped
     before TTS). Then the narration body as flowing prose.
3. **Length target:** the WHOLE sight should total **~15–20 minutes of NEW narration per
   audience** across all its chapters — roughly **2500–3000 words per audience**. Give the
   richest stories more chapters. Chapter length should FIT THE MATERIAL: ~300 words for a
   single tight anecdote, up to ~900 for a story that earns it. Do not pad thin material or
   squeeze rich material to hit a uniform ~2-minute length; variety is good.
4. Write a sidecar `<assets root>/content/<SIGHT>/tracks.json` — see format below.

## Quality bar
- **Adults:** an outstanding, worldly guide. Real history, dates, names, cultural
  significance, and the tourist's-eye detail — what to look for, why it matters, the
  surprising connection or the darker footnote. Confident, vivid, a little wit. Not a
  textbook; a brilliant docent.
- **Kids:** genuine storytelling — a story arc, vivid sensory images, a "wow" or a "yuck",
  direct address ("look up…", "imagine…"), the odd question. Simpler, never dumbed-down,
  never fake-jolly.
- **ACCURACY IS MANDATORY.** Every fact TRUE. Use WebSearch/WebFetch to confirm any date,
  number, measurement, "first/largest/oldest", or attribution you're unsure of. If a
  beloved tale is legend, say so ("the story goes…"), don't assert it as fact.
- **Write for the ear** (this is text-to-speech): flowing prose, no bullet lists, no
  headings inside the body, no URLs, no heavy parentheticals, spell out symbols and odd
  numbers. Prefer commas to dashes. Vary sentence length; it should sound spoken.
- No repetition between chapters, or with the base story.

## Sidecar format - `content/<SIGHT>/tracks.json`
The COMPLETE tracks object for your sight, ready to drop into the manifest. Preserve each
base story's existing `file`/`title`/`est_minutes` EXACTLY; add a `tell_me_more` array of
your chapters. `est_minutes` for any chapter = its word count divided by 150, rounded to
one decimal.

```json
{
  "kid": [
    {
      "file": "content/<SIGHT>/kid/01-slug.md",
      "title": "<existing base title>",
      "est_minutes": <existing>,
      "tell_me_more": [
        {"file": "content/<SIGHT>/kid/01-slug-more-1.md", "title": "<chapter title>", "est_minutes": <n>},
        {"file": "content/<SIGHT>/kid/01-slug-more-2.md", "title": "<chapter title>", "est_minutes": <n>}
      ]
    }
  ],
  "adult": [ ... same shape, using the adult base files/titles ... ]
}
```

Return only a short summary (sight id, chapters written per audience, approx minutes per
audience). The md files + tracks.json are the deliverable.
