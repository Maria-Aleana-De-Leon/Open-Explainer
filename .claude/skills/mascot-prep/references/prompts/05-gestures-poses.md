# Prompt 5: Gestures and poses

One image per message, each an edit of `neutral.png`. Here the arms change, so the importer aligns each pose to
`neutral.png` **by the head**. Keep the head identical and pose swaps will never jump.

## Base prompt

```
Edit this exact image. Keep the head EXACTLY the same - face, mouth, eyes, hair, size and position in the frame -
and keep the body, clothing, outlines, colours, canvas size and transparent background the same.
Do not re-centre, zoom or crop. The character still faces the viewer.

Change only the arms and hands:
[GESTURE]
Keep both hands fully inside the frame and away from the face.
```

## Gestures

| Save as | `[GESTURE]` |
|---|---|
| `pose-point.png` | the right arm (on the viewer's right) raised diagonally, index finger pointing up and away to the side |
| `pose-present.png` | the right arm extended out to the side at waist height, palm open and facing up, as if presenting something |
| `pose-wave.png` | the right hand raised beside the head, palm facing the viewer, waving |
| `pose-thumbs-up.png` | the right hand in front of the chest giving a thumbs-up |

Any name works: `pose-<anything>.png` becomes the pose `<anything>` in the storyboard
(`{"at": "this phrase", "pose": "point"}`).

The mascot stands on the left of the frame by default and faces the content, so gestures toward the viewer's right
point at the slides. Placed on the right, it is mirrored automatically.

## Combining a pose with an expression (optional)

`pose-point-happy.png` (pointing + happy face) is used when a storyboard action asks for both
`"pose": "point", "expression": "happy"`. Without it, the pose wins.
