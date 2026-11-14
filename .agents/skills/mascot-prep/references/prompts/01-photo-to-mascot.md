# Prompt 1: Photo → mascot

Use in ChatGPT (or any image generator that accepts a reference photo). Upload **one** clear, front-facing photo of
yourself (good light, neutral background, face and shoulders visible). Pick one style line and paste it into the
prompt where it says `[STYLE]`.

You only need the photo for this step. open-explainer never asks for it, and it is never stored in your project.

## Style options (pick one)

| Style | Paste this as `[STYLE]` |
|---|---|
| Flat vector (recommended) | flat 2D vector cartoon, clean bold outlines of even thickness, flat colours with at most one soft shadow tone, no gradients, no texture |
| Chibi | cute chibi 2D cartoon, head about one third of the total height, big expressive eyes, clean outlines, flat colours |
| Editorial line art | minimal 2D line-art illustration, confident black outlines, 3-4 flat accent colours, plenty of negative space |
| Soft storybook | soft 2D storybook cartoon, gentle rounded shapes, flat pastel colours, thin warm outlines, no paper texture |

Flat styles animate best. Lip sync and blinks are cut out of edited copies of one image, so painterly texture,
gradients and photo-real shading make the seams visible.

## The prompt

```
Create a 2D cartoon mascot of the person in this photo, for use as an animated presenter in explainer videos.

Style: [STYLE].

Keep what makes them recognisable: face shape, hairstyle and hair colour, skin tone, eye shape, glasses or facial
hair if any, and their usual style of clothing. Simplify everything else.

Pose: standing, full body, facing the viewer straight on, arms relaxed at the sides, feet together.
Face: looking at the viewer, eyes open, mouth CLOSED in a small relaxed smile, eyebrows neutral.

Design it for animation:
- the face is fully visible, with nothing (hair, hands, props) covering the eyes or the mouth
- the mouth is simple and clearly separate from the chin and nose
- clean outlines of even thickness; flat colours; no gradients, glow, texture or drop shadow
- no text, logos or props

Image: the character centred, filling about 80% of the height, on a TRANSPARENT background (PNG).
If transparency is not possible, use a plain flat pure white background with nothing else in the frame.
Portrait orientation, at least 1024 px tall.
```

## Review before moving on

- [ ] It looks like you (or the version of you that you want), and you would be happy to see it in every video.
- [ ] Front-facing, full body, arms down, mouth closed, eyes open.
- [ ] Nothing covers the mouth or eyes.
- [ ] Plain transparent or flat white background, nothing else in the frame.

Not right? Ask for one change at a time ("make the hair shorter, keep everything else the same"). When you approve
it, download it and save it as **`neutral.png`**. Every other image is made from this one.
