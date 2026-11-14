# Put your ChatGPT mascot images here

Make them in ChatGPT with the prompts (from the repository root: `.venv/bin/oex prompts`, then
`.venv/bin/oex prompts <number>` to print one). Upload your photo only to ChatGPT, for prompt 1. Open Explainer
never needs it.

Save each image as a PNG with **exactly** these names (lower-case):

| File | Prompt | Needed for this film |
|---|---|---|
| `neutral.png` | 1 | **required**: front-facing, mouth closed, eyes open, arms down |
| `mouth-ah.png` | 4 | **required for talking** |
| `mouth-half.png`, `mouth-ee.png`, `mouth-oh.png`, `mouth-oo.png`, `mouth-fv.png`, `mouth-mbp.png` | 4 | strongly recommended (natural lip sync) |
| `blink.png` | 3 | recommended |
| `pose-wave.png`, `pose-present.png`, `pose-point.png` | 5 | used by this film |
| `expr-surprised.png`, `expr-thinking.png`, `expr-happy.png` | 3 | used by this film |

Every image except `neutral.png` is an **edit of `neutral.png`**: upload `neutral.png` to ChatGPT each time and
change only one thing. Do not ask for a sheet or grid of several poses in one image.

Before importing, check that each file:
- is a PNG at least 1024 px tall, with a transparent background (or plain white; prompt 7);
- shows the same character, the same size and position as `neutral.png`;
- has nothing in front of the mouth or eyes.

Then, from the repository root:

```bash
.venv/bin/oex -C showcase/ai-agents-60s use-mascot showcase/ai-agents-60s/my-mascot-goes-here
```

These images are your likeness: they stay on your computer and are not part of the repository (`.gitignore`).
