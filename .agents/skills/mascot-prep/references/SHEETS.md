# Your mascot from sheets: master, poses, expressions, mouths

The **sheet route** makes a whole mascot in five image-generator messages instead of one message per image: a
master character, then sheets of poses, expressions and mouths made from it. The sheets are split into separate
files with `oex assets split`, checked, and prepared like any other mascot with `oex mascot prepare`.

The prompts are in [prompts/sheets/](prompts/sheets/) and are used **word for word**. The one-image-per-message
route ([GUIDE.md](GUIDE.md), prompts 01-07) still works and gives the most exact lip sync; the sheet route is
faster, with more checking by eye.

A generated sheet is **not** animation-ready by itself. It becomes usable after splitting, checking, preparing and
approving the review sheet, and a few things still need a person's eye (below).

## What is tested, and what is not

| You make | Turn it into | Status |
|---|---|---|
| 3×3 pose sheet (prompt 03) | a full-body mascot that waves, points, presents, thinks | **works**: split, prepared (all poses registered) and rendered in a test film; no lip sync without mouths |
| 3×3 expression sheet (04) + mouthless sheet (05) + mouth sheet (02) | a head-and-shoulders mascot with expressions **and** lip sync | **works with checks**: split, mouths placed on the mouthless face, prepared and rendered in a test film; mouth position is measured by you, and an expression change can show a brief double image (below) |
| mouth sheet on a full-body mascot | lip sync for the full-body mascot | **not tested**: at sheet resolution the full-body mouth is only a few pixels wide |
| walking frames (bottom row of 03) | three separate poses | **poses only**: they are not played as a walk cycle |
| mouthless sheet (05) on its own | expression bases | used only as the face the mouths are painted on; the film does not swap mouths over every expression |
| 5×5 sticker sheet | 25 separate pictures | **works as pictures** in `image` scenes (storyboard-builder skill, `references/stickers.md`); there is no pop-up sticker overlay animation yet |

## Step by step

1. **Master** - [01-master-mascot.md](prompts/sheets/01-master-mascot.md) with your photo, in your image
   tool. Iterate until you like it, then save it (for example `master.png`). Every later prompt attaches this image.
2. **Poses** - [03-pose-sheet.md](prompts/sheets/03-pose-sheet.md) with the master attached. Save the sheet,
   then split it straight into a mascot folder:
   ```bash
   oex assets split pose-sheet.png --kind poses --out ~/OpenExplainer/my-mascot
   oex mascot prepare ~/OpenExplainer/my-mascot --name "Me" --license "all rights reserved (mine)"
   ```
   It writes `neutral.png` (top left) and `pose-wave`, `pose-point-right`, `pose-point-left`, `pose-present`,
   `pose-think`, `pose-walk-1/2/3`. In the storyboard: `"pose": "wave"`, `"pose": "point-right"`, ...
3. **Expressions** - [04-expression-sheet.md](prompts/sheets/04-expression-sheet.md) with the master attached,
   then [05-mouthless-sheet.md](prompts/sheets/05-mouthless-sheet.md) with the expression sheet attached.
   Split both on the **same canvas size**, so they line up:
   ```bash
   oex assets split expression-sheet.png --kind expressions --out ~/OpenExplainer/my-bust --canvas 420x460
   oex assets split mouthless-sheet.png --kind mouthless --out ~/OpenExplainer/my-bases --canvas 420x460
   ```
   (If a `--canvas` is too small for the artwork, the error says the smallest size that fits.)
4. **Mouths** - [02-mouth-sheet.md](prompts/sheets/02-mouth-sheet.md) with the master attached, then:
   ```bash
   oex assets split mouth-sheet.png --kind mouths --out ~/OpenExplainer/my-mouths
   ```
   Open `my-mouths/split/review.png` and **check every name**. The sheet has no labels; the files are named in the
   order the prompt asks for (ah, ee, oh, closed, fv, l, m), but the generator may not keep that order. Rename the
   files if needed; replace any mouth that does not look like its sound (the "fv" one often looks like a smile).
5. **Place the mouths** - measure where the mouth belongs on the mouthless face: open `my-bases/base-neutral.png`
   in any image viewer that shows pixel positions and note the centre x, centre y and the mouth width (about the
   width of the mouth in `my-bust/neutral.png`). Then:
   ```bash
   oex assets place-mouths ~/OpenExplainer/my-bust ~/OpenExplainer/my-mouths \
       --base ~/OpenExplainer/my-bases/base-neutral.png --box 214,235,60
   oex mascot prepare ~/OpenExplainer/my-bust --name "Me" --license "all rights reserved (mine)"
   ```
   This writes `neutral.png` (the mouthless face with the closed mouth) and `mouth-ah`, `mouth-ee`, `mouth-oh`,
   `mouth-fv`, `mouth-half` (from "l"), `mouth-mbp` (from "m"). There is no rounded "oo" mouth in the sheet; the
   film uses "oh" for it. Open `build/review.png` and look at every mouth on the face.
6. **Use it** - `"mascot": {"dir": "~/OpenExplainer/my-bust", "position": "left"}` in `project.json`, render a
   preview and watch it.

## What `oex assets split` does

- Cleans the transparency: generators return "transparent" art that is about 1% see-through, with faint specks
  around it. Background specks become fully clear and the artwork fully opaque; soft edges stay soft.
- Finds the rows and the gaps between items itself (it does not assume equal cells), cuts there, and crops each item
  to its artwork.
- Poses and expressions go onto one shared canvas, centred and standing on the same bottom line, so a set stays
  aligned; mouths and stickers are trimmed to their artwork with a small margin.
- Checks every item: the expected number, nothing empty, no cut through artwork (items that touch their neighbour),
  nothing running into the cell edge, similar sizes, at least 400 px tall for a mascot, and an alpha channel.
- Writes `split/review.png` (every item on a checkerboard, problems in red) and `split/manifest.json`.

## Known limits

- **Alignment between sheets.** The mouthless sheet is generated again, not edited pixel by pixel: hair and face
  outlines move a little. Mouths are therefore placed on the mouthless face (so mouth images differ from
  `neutral.png` only at the mouth), and the expressions from the other sheet are registered to it by the importer.
  When the film switches expression, the short crossfade can show a faint double outline.
- **Resolution.** A 3×3 sheet gives each item about a third of the image size. Generate sheets as large as your tool
  allows; `split` refuses mascot items under 400 px.
- **Mouth names and fit** are a person's decision, not the tool's: check the order, the look of each sound and the
  position on the face in `build/review.png`.
- **Your photo and your mascot are yours.** Nothing here uploads them; keep them out of public repositories unless you
  choose to share them.
