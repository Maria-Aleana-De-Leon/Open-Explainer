# Sheet prompts: a mascot and its variations in a few images

These are the **tested, working prompts** of the sheet workflow, preserved exactly as they were used (each file is
byte-identical to the tested original; checksums below). Copy a file's text into your image generator (for example
ChatGPT), with the image it asks for attached. Do not shorten or merge them: the repeated instructions are what made
them work.

How to turn the results into a mascot the film engine can use: `docs/mascot/SHEETS.md` (in the mascot-prep skill:
`references/SHEETS.md`).

| Step | Prompt | Attach | You get |
|---|---|---|---|
| 1 | [01-master-mascot.md](01-master-mascot.md) | your own photo | one full-body 2D mascot: the **master** you approve and reuse |
| 2 | [02-mouth-sheet.md](02-mouth-sheet.md) | the master | seven isolated mouth shapes on one sheet (4 + 3) |
| 3 | [03-pose-sheet.md](03-pose-sheet.md) | the master | nine full-body poses in a 3×3 sheet |
| 4 | [04-expression-sheet.md](04-expression-sheet.md) | the master | nine head-and-shoulders expressions in a 3×3 sheet |
| 5 | [05-mouthless-sheet.md](05-mouthless-sheet.md) | the sheet from step 4 | the same nine expressions without mouths |

Video-editing stickers (a separate collection, not part of the mascot) have their own prompt in the
storyboard-builder skill: `skills/storyboard-builder/references/sticker-sheet-prompt.md`.

## Notes on the wording

- The prompts were tested on one character. Step 4 asks to preserve "Ear shape and existing earrings" because that
  character wore earrings; with a character without earrings the line simply has nothing to preserve.
- Step 1 uses your photo only inside your image tool. Open Explainer never needs, stores or uploads the photo.
- The generator does not always follow every instruction: cells are not exactly equal, "transparent" art comes back
  slightly see-through, the mouthless sheet can redraw more than the mouths, and the mouth sheet has no labels.
  `oex assets split` copes with the first two and reports what it finds; the rest needs a person's eye
  (see the guide).

## Provenance

| File | SHA-256 |
|---|---|
| `01-master-mascot.md` | `3c0c130183ff5411877a788dd121df3eaec5b35bcfbc08aca653b78e54eab831` |
| `02-mouth-sheet.md` | `0f17ea91f7802503760ee854cb2d4eff02968cbb6d381da8bb883875a4c927c8` |
| `03-pose-sheet.md` | `7559b681b9b07324391c15e89fe514c50c2e1158d18b0202d967663c2577b569` |
| `04-expression-sheet.md` | `128a98a1e6c899a962cf066777355fbfa54737f665399a365280160a5632fc61` |
| `05-mouthless-sheet.md` | `66ba8bbf7e7f5819f4da30362a356c515b129bd9f9cfac83c0372199df2fd8df` |
| `sticker-sheet-prompt.md` | `cb835b6447f60a3fcbf909f1446bf9718a9bad278bc6f0d20dc724540336a64e` |

The prompts are part of this repository under its MIT licence. The images they were tested with (a person's photo
and the mascot made from it) are private and are not included.
