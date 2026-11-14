# Explanatory diagrams for `image` scenes

Text cards say *what*; a picture shows *how*. When a paragraph explains a mechanism, a structure, a place, a
direction or a size, an original diagram usually teaches it better than words on screen. Choose by what the viewer
needs to see, not by a quota: some ideas (a definition, a punchline, an opinion) are clearest as text.

## When to draw

| The narration explains | Show |
|---|---|
| how something moves or pushes (forces, flow, circulation) | the object with labelled arrows |
| what something is made of / its parts | a simple cut-away or labelled outline |
| where things are relative to each other | a map-like layout or cross-section |
| a change from one state to another | before → after, side by side |
| a cycle or a pipeline with physical steps | shapes connected by arrows (or a `flow` scene if words suffice) |
| a number or comparison | prefer `number` / `compare` scenes; draw only if size or scale matters |

Do **not** draw: app or website screens and UI walkthroughs (use real screenshots the user supplies), logos,
brands, real people or other people's characters.

## Rules that make a diagram readable in a video

- **One idea per diagram.** If the narration makes two points, make two images (or reveal in steps, below).
- **Big labels:** at least 36 px (the kit refuses smaller), at most ~4 words each, at most ~6 labels.
- **Colour with meaning:** `accent` for the thing the narration names in this scene, `accent2` for flows or
  secondary paths, `ink`/`muted` for everything else. Never more than three colours.
- **Fill the stage:** draw at the canvas size below; leave ~40 px margin; no tiny drawing in a big empty frame.
- **Simplify honestly:** a schematic is fine, a wrong picture is not. Say "simplified" in the narration or a label
  when you leave things out.
- **Consistent look:** same style as the film (the kit uses its palette and the toolkit's Poppins font) and a
  transparent background so the film's background shows through.

## Check before you render

`save()` prints layout warnings for everything drawn through the kit (it still saves the file):

| Warning | Usually means | Fix |
|---|---|---|
| `line ... passes through ...` | a flow or arrow runs across a shape | route it around; if the crossing is the point (a reference line through a wing, a cut-line), pass `through=True` |
| `labels ... overlap` / `label ... sits on line ...` | text collides with text or with a line | move the label into clear space; leader lines may start right next to their label |
| `label ... crosses the edge of ...` | text half inside a shape, or too long for its box | put it fully inside (shorter words, bigger box) or fully outside |
| `low contrast` | e.g. `line` or `muted` colour on a card | use `ink` or `accent` |
| `cut off or touches the canvas edge` | something within ~16 px of the edge | keep ~40 px clear on every side |
| `uses only N% of the canvas` | the drawing will look small on screen | spread it out or draw it larger (the first step of a reveal may stay small) |

Warnings are prompts, not rules: an intended overlap is fine. Then open the PNG and look at it as a viewer would:
does each arrow start and end where it should, is the main object the biggest thing, is the spacing even, and could
someone who missed the narration tell what it shows? Drawing done directly with `PIL.ImageDraw` is not checked:
look at it extra carefully.

## Reveal in steps

An `image` scene shows its picture whole, on its `at` cue. To build an explanation up, draw 2-3 versions (base;
+ arrows; + labels) and give each its own consecutive scene, splitting the paragraph where the narration moves to the
next part. Keep everything that already appeared in the same place in every version.

## Sizes (draw at this size; images are scaled down to fit, never up)

| Film | Canvas | Kit name |
|---|---|---|
| 16:9, no mascot | 1580 × 600 | `"16:9"` |
| 16:9 with mascot | 1170 × 600 | `"16:9-mascot"` |
| 9:16, no mascot | 920 × 1000 | `"9:16"` |
| 9:16 with mascot | 920 × 640 | `"9:16-mascot"` |

These leave room for the scene's `heading`. `oex review` warns when an image covers too little of the stage.

## Drawing with the kit (Pillow only, no other dependency)

`scripts/diagram_kit.py` in this skill draws boxes, labels, straight and curved arrows, ellipses and polygons in
the film's style. Write a small script in the **project** folder and run it with any Python that has Pillow 10.1+:

```bash
uv run --no-project --with pillow python make_diagrams.py      # or: python3 make_diagrams.py if Pillow is installed
```

```python
import sys
sys.path.insert(0, "<path to this skill>/scripts")          # e.g. .claude/skills/storyboard-builder/scripts
from diagram_kit import Diagram

d = Diagram("midnight", "16:9")                              # style and canvas of the film
d.box((60, 220, 420, 380), "Sea water")                      # x0, y0, x1, y1 in canvas pixels
d.arrow((420, 300), (760, 300), label="heat lifts vapour")   # label sits above the arrow
d.ellipse((780, 180, 1140, 420), outline="accent2")
d.text((960, 300), "Cloud", size=48, weight="bold")
d.curve([(1140, 300), (1300, 330), (1400, 450), (1440, 560)], color="accent2")   # smooth path with arrowhead
d.text((1380, 200), "Rain", size=44, color="accent2", weight="bold")
d.save("assets/water-cycle.png")
```

Then in `storyboard.json`: `{"type": "image", "image": "assets/water-cycle.png", "heading": "Where rain comes from",
"at": "<phrase where the picture should appear>"}`. Render a preview and look at the sheet: if a label is hard to
read or the drawing looks lost on the stage, fix the drawing, not the narration.

Plain Pillow (`PIL.ImageDraw`) works too: use the same canvas sizes, the style colours from the kit's `PALETTES`
and labels of at least 36 px.

## Rights

Diagrams you draw this way are original work for the user's film. An image the user supplies must be theirs or
licensed for this use: ask, and note the source in the scene's `"notes"`. Never download images from the web, and
never use an online image generator or any other paid or outward-facing service without the user's go-ahead.
