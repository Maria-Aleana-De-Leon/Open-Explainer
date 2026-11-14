# Prompt 6: Repairing inconsistent assets

`oex mascot prepare` tells you which image drifted and how. Match the message to a fix below. Always upload
`neutral.png` **and** the bad image together.

| The importer says | Use this prompt |
|---|---|
| `does not register well to neutral` | **Re-align** |
| `also changed outside the face` / `region extends outside the character` | **Re-align**, then re-run |
| `area differs from neutral` on a `pose-` image | **Re-align** (its face changed; a gesture must keep the exact face) |
| `area differs from neutral` on an `expr-` image | nothing: expressions keep their own face and do not lip-sync |
| `nothing changed compared with neutral.png` | **Redo the edit**: the generator returned the original |
| `missing mouth shapes` | prompt 4 for the listed shapes (optional: fallbacks are used meanwhile) |
| colours look different in `review.png` | **Match colours** |
| `no transparency - ... removed` and edges look rough in `review.png` | prompt 7 |

## Re-align

```
Image 1 is the master. Image 2 is a variant of it that drifted.
Redraw image 2 so that everything except [the mouth | the eyes | the arms] matches image 1 EXACTLY:
same head size and position in the frame, same body, outlines, colours, canvas size and transparent background.
Keep the [mouth | eyes | arm pose] from image 2.
```

## Redo the edit

```
This is the master image. Make exactly this change and nothing else: [the change from prompt 3, 4 or 5].
The result must be visibly different in that one area.
```

## Match colours

```
Image 1 is the master. Recolour image 2 so every colour (skin, hair, clothing, outlines) matches image 1 exactly.
Do not change any shapes.
```

After each repair, run `oex mascot prepare <folder>` again and re-check `review.png`. The importer never edits
your source images: it only reads them.
