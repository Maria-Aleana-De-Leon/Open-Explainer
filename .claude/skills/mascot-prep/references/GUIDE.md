# Bring your own mascot

Your presenter is a cartoon of **you**, made with ChatGPT (or any image generator), then checked and prepared by
open-explainer. There is no fixed house mascot. The demo character "Pip" is only there for examples and tests.

```
Step A  photo -> neutral.png        (prompt 1)          you approve the look
Step B  neutral.png -> variants      (prompts 3, 4, 5)   one edit per image
Step C  oex mascot prepare           (this toolkit)      checks + review.png -> you approve
Step D  project.json "mascot"        (this toolkit)      lip sync, blinks, poses on cue words
```

Your photo is used only in Step A, inside your image generator. open-explainer never asks for it and never
stores it. After Step C, the prepared folder is all a film needs.

## Step A: create the character

Use [prompt 1](prompts/01-photo-to-mascot.md). Choose a style (flat vector animates best), iterate one change
at a time, and save the approved image as `neutral.png` in a new folder, e.g. `my-mascot/`.
Optional: make a reference sheet with [prompt 2](prompts/02-character-sheet.md) to keep later chats consistent.

## Step B: make the animation images

Every image is an **edit of `neutral.png`**: upload it each time and change one thing. Do not ask for a grid or
sheet of many poses in one image. Single edits stay consistent, and the importer checks each one separately.

| Folder file | Prompt | Needed? |
|---|---|---|
| `neutral.png` | 1 | **required** |
| `mouth-ah.png` | 4 | needed for talking |
| `mouth-half/ee/oh/oo/fv/mbp.png` | 4 | recommended (better lip sync) |
| `blink.png` | 3 | recommended |
| `pose-point.png`, `pose-present.png`, `pose-wave.png`, ... | 5 | optional gestures |
| `expr-happy.png`, `expr-surprised.png`, `expr-confused.png`, `expr-thinking.png` | 3 | optional reactions |

*(Image in the Open Explainer repository: `docs/mascot/img/pip-inputs.png`: The demo mascot's input images: neutral, mouth-ah, blink, point, happy, wave)*

## Step C: prepare and review

```bash
oex mascot prepare my-mascot --name "Me" --author "Your Name" --license "all rights reserved (mine)" \
    --generated-with "ChatGPT"
```

It writes `my-mascot/build/`. Your source PNGs are only read, never modified. Steps:

1. **Transparency**: images without a real alpha channel get their plain or checkerboard background removed (and
   it tells you). Busy backgrounds are refused rather than guessed.
2. **Registration**: every image is registered to `neutral.png` (scale and position, from the head and shoulders)
   and placed on one shared canvas, so swaps never jump. Each gets a registration score (≥ 0.6 passes).
3. **Patches**: each mouth image and the blink are compared with `neutral.png`, tolerating a pixel or two of
   drift. Only the region that really changed is kept, with a soft edge that follows its shape, colour-corrected to
   neutral. Changes elsewhere in the image are measured, reported and discarded.
4. **Checks**: missing mouth shapes (with the fallbacks used), images whose face differs from neutral (no lip sync
   in that state), regions spilling outside the face, images that did not change at all, low resolution.
5. **`review.png`**: top row = every state with the mouth (red) and eye (blue) regions; bottom row = neutral with
   each mouth shape and the blink applied.

*(Image in the Open Explainer repository: `docs/mascot/img/pip-review.png`: Review sheet for the demo mascot)*

### Visual checklist for `review.png`

- [ ] **Top row:** every state is the same size and the heads line up. Red text means a low registration score.
- [ ] **Red/blue boxes** sit on the mouth and eyes in every state where `talk Y` / `blink Y`.
- [ ] **Bottom row:** each mouth reads as a different shape; no visible box, seam or colour patch around it.
- [ ] **Blink:** both eyes closed, no ghost of the open eyes, eyebrows unchanged.
- [ ] **Edges:** no white halo or missing pieces where a background was removed.
- [ ] **Labels:** no `(missing)` or `->` on shapes you meant to provide.

Anything wrong: fix the image with [prompt 6](prompts/06-repair-inconsistent.md) and run `prepare` again.
Check the result with `oex mascot check my-mascot`.

## Step D: use it in a film

In `project.json`:

```json
"mascot": {"dir": "my-mascot", "position": "left", "scale": 1.0}
```

In `storyboard.json`, trigger poses and expressions on words from the scene's narration:

```json
"mascot": [{"at": "three steps", "pose": "present"},
           {"at": "surprising", "expression": "surprised", "for": 1.2}]
```

The mouth follows your voice automatically; blinks are scheduled automatically (never during a pose change).
`"mascot": false` on a scene hides the mascot for that scene. Leave `"mascot": null` in `project.json` for a film
without a presenter.

## Rights

Only use a likeness you have the right to use (your own, or with permission). Record the artwork's licence with
`--license`. It is saved in `build/mascot.json` under `provenance`. Do not publish other people's characters as
demo art.
