---
name: storyboard-builder
description: Write and fix storyboard.json for an open-explainer project - scenes (title, bullets, statement, flow, number, compare, image, end), on-screen text, cue phrases that time every animation to the narration, mascot poses and sound cues. Use when creating or editing a storyboard, turning a script into scenes, or when `oex validate` / `oex plan` report storyboard problems.
---

# Storyboard builder

A storyboard is data, not prose: `storyboard.json` is validated by `oex validate` and timed by `oex plan`.
Full field reference: `references/storyboard-reference.md` (read it before writing your first storyboard).

## How timing works (no timestamps needed)

- Each scene's `"say"` is the exact narration it covers, in order. Together the scenes must cover the whole take.
- Anything that animates has `"at"`: a phrase copied from **that scene's** `say` (case and punctuation ignored;
  `"at": "phrase#2"` = second occurrence) or a number of seconds from the scene start.
- `oex plan` aligns the text to the recording, cuts scenes in the pauses, and lands every element on its word.

## Writing the scenes

1. One scene per script paragraph. Pick the type by the idea:
   - a question or topic → `title`; a punchline or definition → `statement` (with `*accent*` + `emphasis`);
   - steps or a process → `flow` (2-5 items); a list → `bullets` (2-5); one striking number → `number`;
   - two things side by side → `compare`; a screenshot/diagram the user supplies → `image`; the close → `end`.
2. On-screen text is short: headlines ≤ ~7 words, items ≤ ~5 words. Never paste the narration on screen; captions
   already show it.
3. Cue each item on the word where the narration introduces it, so the visual lands as the idea is said.
4. Mark accent words with `*asterisks*` in on-screen text (`"Why is the sky *blue*?"`).
5. Mascot: `"mascot": [{"at": "...", "pose": "point"}, {"at": "...", "expression": "happy", "for": 1.5}]` using
   only states the prepared mascot has (`oex mascot check <dir>` lists them). Expressions have no lip sync, so
   keep them short with `"for"`.
6. Sound: leave it to `sfx.auto` in project.json, or add `"sfx": [{"at": "...", "tag": "whoosh"}]` sparingly.

## Then

`oex validate` → `oex plan`. Errors list every problem with the scene id; fix them all, re-run.
Warnings such as `"X" was not recognised in the audio; time interpolated` are usually recogniser spelling
differences. If a cue lands visibly wrong in the preview, choose a nearby, more distinctive phrase.
