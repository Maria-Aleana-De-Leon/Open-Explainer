# Prompt 3: Expressions (and the blink)

Make **one image per message**. Each one is an EDIT of `neutral.png`, so upload `neutral.png` in the same chat (or
use the image editor on it). The base prompt stays the same; only the last line changes.

## Base prompt

```
Edit this exact image. Keep EVERYTHING identical - the character, pose, body, clothing, outlines, colours, size,
position in the frame, canvas size and the transparent background. Do not redraw, re-centre, zoom or crop.

Change only the face, as follows:
[CHANGE]
```

## The changes (one image each)

| Save as | `[CHANGE]` |
|---|---|
| `blink.png` | Close both eyes (simple curved lines, as in a relaxed blink). Change NOTHING else - same mouth, same eyebrows. |
| `expr-happy.png` | A big happy smile with the mouth open, eyes squinting happily. Eyebrows slightly raised. |
| `expr-surprised.png` | Surprised: eyes wide open, eyebrows raised high, mouth a small round "o". |
| `expr-confused.png` | Confused: one eyebrow raised and the other lowered, mouth a small wavy line pulled to one side. |
| `expr-thinking.png` | Thinking: eyes looking up and to the side, mouth closed in a flat line, one hand touching the chin. |

`blink.png` is the important one: the importer cuts the eyes out of it and uses them for every blink, in every pose.
Keep everything but the eyes identical.

Expressions are full-face changes, so they are shown as whole images: no lip sync runs while one is on screen.
Use them as short reactions (the storyboard's `"for": 1.5`), and the toolkit warns you if one is held while you talk.
