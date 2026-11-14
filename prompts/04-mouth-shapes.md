# Prompt 4: Mouth shapes for lip sync

Seven images, **one per message**, each an edit of `neutral.png`. The importer compares each one with `neutral.png`
and keeps **only the region that changed**, so the rest of the image does not have to be perfect, but the closer it
is, the cleaner the result.

## Base prompt

```
Edit this exact image. Keep EVERYTHING identical - eyes, eyebrows, face shape, hair, body, pose, clothing,
outlines, colours, size, position in the frame, canvas size and the transparent background. Do not redraw,
re-centre, zoom or crop.

Change ONLY the mouth, in the same drawing style, keeping it about the same width as the current mouth:
[MOUTH]
```

## The seven mouths

The names are the sounds they are used for, as in hand-drawn animation.

| Save as | `[MOUTH]` | Sounds |
|---|---|---|
| `mouth-ah.png` | open wide vertically, like saying "ah", tongue just visible | a **(the one you need first)** |
| `mouth-half.png` | slightly open and relaxed, a small dark opening | quiet syllables |
| `mouth-ee.png` | open and stretched sideways, top teeth visible, like saying "ee" | e, i |
| `mouth-oh.png` | open and rounded, like saying "oh" | o |
| `mouth-oo.png` | small, pursed and rounded, like saying "oo" or whistling | u, w |
| `mouth-fv.png` | top teeth resting on the lower lip, like saying "f" | f, v, s |
| `mouth-mbp.png` | lips pressed together in a flat line (no smile) | m, b, p |

Lip sync is driven by the sound of the voice (loudness and tone), not by language, so the same seven shapes work
for English, Tagalog and Taglish.

## Minimum set

`mouth-ah.png` alone makes the mascot talk. Missing shapes fall back to close ones (half → ah, ee → ah, oh → ah,
oo → oh, fv → mbp), and the importer lists the fallbacks it used. All seven look best.

## Checks

- [ ] The mouth sits in the same place as in `neutral.png`.
- [ ] Teeth and inside colours are the same across all seven.
- [ ] Nothing else moved: open `review.png` after `oex mascot prepare` and compare the bottom row.
