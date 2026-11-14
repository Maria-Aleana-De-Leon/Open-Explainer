# storyboard.json reference

```json
{
  "scenes": [
    {"id": "s01", "type": "title", "say": "<exact narration for this scene>", "title": "How does *GPS* find you?",
     "subtitle": "optional", "transition": "slide", "camera": "push",
     "mascot": [{"at": "find you", "pose": "wave", "for": 1.5}],
     "sfx": [{"at": "GPS", "tag": "whoosh"}]}
  ]
}
```

## Common fields (every scene)

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | `[a-z][a-z0-9_-]{0,31}`, unique. `oex render --only <id>` uses it. |
| `type` | yes | one of the types below |
| `say` | yes | the exact narration this scene covers, in order (the clock) |
| `at` | no | when the main element lands: phrase from `say`, or seconds from scene start (default: first word). For `title`, `statement` and `end` the text always appears at the scene start so the stage is never empty: time their beat with `emphasis` instead |
| `transition` | no | `fade`, `slide`, `wipe`, `zoom`, `none` (default from style) |
| `camera` | no | `push` (slow push-in) or `still` (default from style) |
| `mascot` | no | list of `{at, pose?, expression?, for?}`; or `false` to hide the mascot in this scene |
| `sfx` | no | list of `{at, sound? (catalog id), tag? (search words), gain_db?}` |
| `notes` | no | free text for humans; ignored |

## Scene types

| type | content fields | animation |
|---|---|---|
| `title` | `title` (required), `subtitle` | title rises, accent bar draws (or the `emphasis` highlight), subtitle follows |
| `bullets` | `heading`, `items` (required): strings or `{text, at}` | each item slides in on its cue, numbered |
| `statement` | `text` (required, `*accent*`), `emphasis` (phrase from `say`) | text rises; highlighter sweeps under the accent words on `emphasis` |
| `flow` | `heading`, `items` (required), `layout` (`row` default, or `cycle`) | nodes pop in on their cues, arrows draw between them (row in 16:9, column in 9:16 or > 5 items); `cycle` places 3-6 nodes in a loop and closes it with an arrow back to the first - use it for anything that repeats |
| `number` | `value` (required, e.g. `"300 billion"`, `"0.07 s"`, `"5-8%"`), `label` | the leading number counts up to its value on `at` |
| `compare` | `heading`, `left`/`right` (required): `{title, items, at}` | each card rises on its cue, items follow |
| `image` | `image` (required, path relative to the project), `heading` | the image rises on `at` (missing file = that scene fails, others still render) |
| `end` | `title` (required), `cta` | title, then a call-to-action pill |

Items without `at` are spread evenly across the scene's narration.

## Cue phrases

- Matching ignores case and punctuation; numbers match either way (`"thirty one"` matches a recognised `31`).
- `"phrase#2"` = the second occurrence within the scene.
- A phrase that is not in the scene's `say` is an error (with the scene id); a phrase the recogniser misheard is a
  warning and its time is interpolated from its neighbours.

## Validation messages you may see

| Message | Fix |
|---|---|
| `unknown field 'x' (did you mean 'y'?)` | rename the field |
| `a 'flow' scene needs 'items'` | add the content field for that type |
| `cue phrase "..." is not in this scene's 'say' text` | copy the phrase exactly from `say`, or move the item |
| `only N% of its 'say' text was heard in the recording` | `say` does not match the take: update it to what was recorded |
| `only 0.6s long (min 0.8s)` | merge the scene with a neighbour or give it more narration |
| `mascot has no state for pose='x'` | use a state listed by `oex mascot check`, or create `pose-x.png` |
