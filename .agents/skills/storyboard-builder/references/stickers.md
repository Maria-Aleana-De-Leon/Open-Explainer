# Stickers: small pictures for emphasis

A sticker sheet is a set of 25 small, colourful pictures in one image (a lightbulb, a check mark, a warning sign,
a trophy, arrows...) made in one image-generator message. Split, each sticker is an ordinary transparent PNG that a
storyboard can show in an `image` scene.

The prompt is [sticker-sheet-prompt.md](sticker-sheet-prompt.md), used word for word. It asks for a **style
reference** image: attach any illustration whose look you want the set to follow (one of your own, or one you are
allowed to use). Stickers are a separate collection: they are not part of a mascot.

## Make and split a sheet

1. Give the prompt and your style reference to the image generator; save the result, e.g. `sticker-sheet.png`.
2. Split it into the project's `assets/` folder:
   ```bash
   oex assets split sticker-sheet.png --kind stickers --out assets/stickers
   ```
   The files are named in the prompt's order (`lightbulb`, `question`, `brain`, `lightning`, `magnifier`, `check`,
   `cross`, `warning`, `trophy`, `target`, `book`, `clock`, `calendar`, `checklist`, `laptop`, `heart`, `thumbs-up`,
   `bell`, `speech-bubble`, `play`, `arrow-right`, `arrow-left`, `arrow-down`, `exclamation`, `star`).
3. Open `assets/stickers/split/review.png`: check every name matches its picture (the generator can change the
   order or replace an item) and that nothing is cut off. Rename files that are wrong; `--names a,b,c,...` sets
   other names in reading order.

## Use them

```json
{"id": "s04", "type": "image", "image": "assets/stickers/trophy.png", "heading": "It *works*",
 "say": "...", "at": "works"}
```

An `image` scene shows the picture rising in on its `at` word. Stickers are small (a few hundred pixels): they suit
a short moment of emphasis, not a scene that needs a detailed picture. There is no sticker overlay that pops up on
top of other scenes yet.

## Rights

The prompt is free to use. The stickers you generate follow your image tool's terms; if the style reference is
someone else's artwork, make sure you may use it. Record where they came from in the project's notes before you
publish.
