# Mascot asset contract

A mascot is a folder of PNG files. File names are the contract; anything else is ignored with a warning.

| File | Required | What it must show |
|---|---|---|
| `neutral.png` | **yes** | front-facing, full body (or bust), mouth closed, eyes open, arms relaxed |
| `mouth-ah.png` `mouth-half.png` `mouth-ee.png` `mouth-oh.png` `mouth-oo.png` `mouth-fv.png` `mouth-mbp.png` | `ah` for talking | `neutral.png` with ONLY the mouth changed |
| `blink.png` | recommended | `neutral.png` with ONLY the eyes closed |
| `pose-<name>.png` | optional | same head as neutral, arms/hands changed |
| `expr-<name>.png` | optional | same body as neutral, face changed |
| `pose-<name>-<expr>.png` | optional | a gesture with an expression |

Technical requirements:
- PNG, at least 400 px tall (1024+ recommended), one character per image, nothing else in the frame;
- transparent background (plain white or a fake checkerboard is removed automatically, with a warning);
- same character size and framing in every image (small drift is corrected; large drift is reported).

What `oex mascot prepare <folder>` produces in `<folder>/build/`:

| File | Content |
|---|---|
| `states/<name>.png` | every neutral/pose/expression registered to neutral on one shared canvas |
| `mouths/<shape>.png`, `eyes/closed.png` | feathered patches cut from the changed region only |
| `mascot.json` | geometry, per-state `talk`/`blink` flags and scores, viseme fallbacks, checks, provenance |
| `review.png` | the sheet you approve before the mascot is used |

The film engine reads only `build/`. Your source images and the original photo are not needed to render.
