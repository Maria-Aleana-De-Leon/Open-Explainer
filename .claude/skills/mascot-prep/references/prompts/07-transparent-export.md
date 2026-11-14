# Prompt 7: Transparent-background exports

The importer needs to know which pixels are the character. A real transparent PNG is best.

## Ask for transparency

```
Give me this exact image again as a PNG with a TRANSPARENT background (alpha channel). Do not change the character.
Do not draw a grey-and-white checkerboard: that pattern is a picture of transparency, not real transparency.
```

## If the generator cannot do transparency

```
Give me this exact image again on a plain, flat, pure white (#FFFFFF) background with nothing else in the frame:
no shadow under the feet, no floor, no gradient, no border. Do not change the character.
```

The importer removes flat backgrounds and the fake checkerboard automatically and says so. Check the edges in
`review.png`: white parts of the character that touch the edge of the image (a white shirt cut off by the frame)
can be removed by mistake. If that happens, ask for transparency again, or remove the background in any editor
that exports PNG with alpha.

## Check a file yourself

- macOS Preview: transparency shows as a light checkerboard **only around** the character. If the checkerboard
  is part of the picture (it does not change when you zoom), it is fake.
- `oex mascot prepare` prints `no transparency - ... removed` for every file that had no real alpha channel.
