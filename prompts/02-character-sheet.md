# Prompt 2: Consistent character sheet (reference only)

A turnaround sheet gives the image generator a stable reference of your character in later chats. **open-explainer
does not cut this sheet into sprites.** It is a memory aid for the generator. The animation images come from prompts
3-5, made one at a time as edits of `neutral.png`.

Upload `neutral.png`, then:

```
This is my approved mascot. Create a character reference sheet of exactly this character - same proportions,
outline thickness, colours, hairstyle, clothing and face.

Show, left to right, evenly spaced on one row: front view, three-quarter view, side view, back view.
Below that, a colour palette row: 6-8 flat swatches of the exact colours used (skin, hair, eyes, clothing, outline),
each labelled with its hex code.

Plain white background, no other text, no scenery.
```

Save it as `reference-sheet.png`, **outside** the mascot folder (the importer ignores unknown names, but keeping it
apart avoids confusion). When a later chat drifts, upload both `neutral.png` and this sheet and say "match this
reference exactly".
