---
name: mascot-prep
description: Guide a user through creating their own talking cartoon mascot with ChatGPT or another image generator (copy-ready prompts), then import, validate and prepare the PNGs with open-explainer (`oex mascot prepare`) - transparency, alignment, mouth shapes, blinks, review sheet. Use when the user wants their own presenter/character/mascot, has mascot images to import, or a mascot looks wrong in a film.
---

# Mascot prep

Prompts: `references/prompts/01-07` (bundled by the installer; in the repo they are in `prompts/`). Walkthrough and
checklist: `references/GUIDE.md`; file names: `references/ASSETS.md` (repo: `docs/mascot/`).
Give the user the prompt text itself, never a summary of it.

## Flow

1. **Look** - prompt 01 with their photo, in their image tool. They choose a style. Iterate one change at a time.
   Approved image → `neutral.png` in a new folder. You never need or receive the photo.
2. **Variants** - one edit of `neutral.png` per message:
   prompt 04 (seven `mouth-*.png`; `mouth-ah.png` is the minimum), prompt 03 (`blink.png`, `expr-*.png`),
   prompt 05 (`pose-*.png`). File names are the contract (`references/ASSETS.md`).
3. **Prepare** - `oex mascot prepare <folder> --name ... --author ... --license ... --generated-with ...`
4. **Review** - open `<folder>/build/review.png` and go through the checklist in `references/GUIDE.md` with the
   user. Read every WARN line aloud in plain words. Fix with prompt 06 (drift) or 07 (backgrounds), re-run 3.
5. **Use** - `project.json`: `"mascot": {"dir": "<folder>", "position": "left", "scale": 1.0}`. States for the
   storyboard: `oex mascot check <folder>` (e.g. `pose-point` → `"pose": "point"`, `expr-happy` →
   `"expression": "happy"`).

## Reading the results

| Output | Meaning |
|---|---|
| `head ... score < 0.6` | the character changed between images; regenerate from neutral (prompt 06) |
| `talk n` on an expression | expected: its own mouth is kept, no lip sync while it shows |
| `talk n` on a pose | its face differs from neutral; fix that image or avoid long speech in that pose |
| `missing mouth shapes ... fallbacks` | it still talks; adding the shapes improves lip sync |
| `NOT READY` | errors; the film refuses to use the mascot until they are fixed |

Do not edit `build/` by hand. It is regenerated on every `prepare`.
