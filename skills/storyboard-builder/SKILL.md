---
name: storyboard-builder
description: Write and fix storyboard.json for an open-explainer project - scenes (title, bullets, statement, flow, number, compare, image, diagram, end), animated diagrams whose parts, connectors, moving tokens and state changes are timed to the narration, original explanatory drawings, on-screen text, cue phrases that time every animation to the narration, mascot poses and sound cues. Use when creating or editing a storyboard, turning a script into scenes, or when `oex validate` / `oex plan` report storyboard problems.
---

# Storyboard builder

A storyboard is data, not prose: `storyboard.json` is validated by `oex validate` and timed by `oex plan`.
Full field reference: `references/storyboard-reference.md` (read it before writing your first storyboard).
Animated diagrams: `references/motion.md` (read it before writing a `diagram` scene).

## How timing works (no timestamps needed)

- Each scene's `"say"` is the exact narration it covers, in order. Together the scenes must cover the whole take.
- Anything that animates has `"at"`: a phrase copied from **that scene's** `say` (case and punctuation ignored;
  `"at": "phrase#2"` = second occurrence) or a number of seconds from the scene start.
- `oex plan` aligns the text to the recording, cuts scenes in the pauses, and lands every element on its word.

## Plan the pictures first

For each paragraph ask: *what would a good teacher draw on the board here?* Then pick the scene type that shows it:

- parts that talk to each other, something that travels between them, a process whose state changes → an
  animated `diagram` (`references/motion.md`): parts appear as they are named, requests and answers travel, states
  change on the words. Continue it across paragraphs with `"continue": true` instead of restarting the picture;
- a shape, a place, a cross-section or a physical mechanism → an original drawing (`image`; draw it with
  `references/diagrams.md`); simple steps in order → `flow` (2-5 items, `cycle` for loops);
- two things side by side → `compare`; one striking number → `number`; a short list → `bullets` (2-5);
- a question or topic → `title`; a punchline or definition → `statement` (`*accent*` + `emphasis`);
- something the user supplies (screenshot, photo, chart) → `image`; the close → `end`.

Pictures where they teach, words where they are clearest: never force a diagram into a scene that does not need
one. A film longer than ~30 s whose topic has a mechanism or structure usually needs at least one diagram.

## Composition, variety and pacing

1. **One focal point per scene.** Headline ≤ ~7 words, items ≤ ~5 words, at most ~20 words on screen. Never paste
   the narration on screen; captions already show it.
2. **Vary the layout:** no more than two text-only scenes (`title`, `statement`, `bullets`) in a row, and no type
   used for more than ~40% of the scenes.
3. **Keep the stage alive:** something new should land every ~3-6 s. A single short line alone for more than
   ~7 s looks empty: add items, a diagram, or split the paragraph into two scenes.
4. **Cue each item on the word that introduces it**, so the visual lands as the idea is said. Mark accent words
   with `*asterisks*` (`"Why is the sky *blue*?"`).
5. Mascot: `"mascot": [{"at": "...", "pose": "point"}, {"at": "...", "expression": "happy", "for": 1.5}]` using
   only states the prepared mascot has (`oex mascot check <dir>` lists them). Expressions have no lip sync, so
   keep them short with `"for"`.
6. Sound: leave it to `sfx.auto` in project.json, or add `"sfx": [{"at": "...", "tag": "whoosh"}]` sparingly.
7. **Motion explains, never decorates.** In a `diagram`, one change per phrase, cued on the word that names it;
   nothing frozen for more than ~6 s; keep the camera still. No motion that the narration is not talking about.

## Then

`oex validate` → `oex plan` → `oex render --preview` → look at `oex sheet` and read `oex review` (it flags text-only
runs, lonely lines, small diagrams, static or crowded animated diagrams and music levels). Errors list every problem with the scene id; fix them all, re-run.
Warnings such as `"X" was not recognised in the audio; time interpolated` are usually recogniser spelling
differences. If a cue lands visibly wrong in the preview, choose a nearby, more distinctive phrase.
