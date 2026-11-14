# Showcase: "How AI agents work" (60 seconds, 1920×1080)

The first production test project. It renders today with **temporary** assets, and is set up so you can swap in
your own ChatGPT mascot and your own voice with one command each.

| File | What it is |
|---|---|
| `script.txt` | the narration script (175 words, about 1:01 at a natural pace) |
| `storyboard.json` | 8 scenes: title hook, chatbot vs agent, the agent loop, tools, a worked example, retry, safety, ending |
| `project.json` | 16:9, style `midnight`, captions on, mascot, subtle music (the toolkit's demo bed `examples/audio/music/calm-loop.wav`, MIT), automatic sound effects |
| `audio/narration.mp3` | **temporary** narration (macOS system voice; testing only, not for publishing; not in git - recreate it with `python tools/say_narration.py showcase/ai-agents-60s --rate 165 --pause 500` then `oex -C showcase/ai-agents-60s transcribe`, or use your own) |
| `mascot.dir` in `project.json` | points to the **temporary** mascot "Pip" in `examples/mascots/pip` (this toolkit's own demo character), the technical baseline only. `use-mascot` switches it to `mascot/` (your images, kept out of git) |
| `my-mascot-goes-here/` | where to put your ChatGPT images (see its README) |
| `renders/how-ai-agents-work-16x9.mp4` | the rendered film |
| `renders/how-ai-agents-work-16x9-sheet.png` | one frame per scene |
| `renders/how-ai-agents-work-16x9.VERIFY.md` | evidence: inputs, every check, mascot coverage, publish safety |

Commands below run from the repository root (`open-explainer/`); with `oex` installed, drop the `.venv/bin/`.

## Replace the narration with your own MP3

1. Record `script.txt` word for word (a quiet room; a phone voice memo is fine). Small slips are OK. If you change
   wording, keep the meaning of each paragraph.
2. Run:
   ```bash
   .venv/bin/oex -C showcase/ai-agents-60s use-narration ~/Desktop/my-voice.mp3
   ```
   It copies your file into `audio/`, keeps the old take as `narration.previous.*`, transcribes it, and prints your
   pace and the new film length, plus a note for any line it could not match to the script.
3. Render:
   ```bash
   .venv/bin/oex -C showcase/ai-agents-60s render --preview     # quick look (optional)
   .venv/bin/oex -C showcase/ai-agents-60s render
   ```
   Every scene re-times to your voice automatically; nothing in the storyboard needs editing.

If you rephrased whole sentences, `oex -C showcase/ai-agents-60s plan` will name the scenes whose words no longer
match: update those scenes' `"say"` in `storyboard.json` to what you actually said.

## Replace the demo mascot with your ChatGPT mascot

1. Make the images with the prompts (`.venv/bin/oex prompts` lists them; `.venv/bin/oex prompts 1` prints the
   first). Save them into `my-mascot-goes-here/` with the exact names in its README.
2. Run:
   ```bash
   .venv/bin/oex -C showcase/ai-agents-60s use-mascot showcase/ai-agents-60s/my-mascot-goes-here
   ```
   It copies your images into `mascot/` (git-ignored: your likeness never enters the repository), points the
   project at it, prepares the images, and prints:
   - **READY**, or **NOT READY** with the images to fix (prompt 6 explains each message);
   - which optional images are missing (fallbacks are used);
   - which gestures the storyboard uses that your set lacks (the presenter keeps its pose there).
3. Open `showcase/ai-agents-60s/mascot/build/review.png` and check it against the list in
   `docs/mascot/GUIDE.md` ("Visual checklist").
4. Render as above.

This storyboard uses these gestures and expressions: **wave, present, point, surprised, thinking, happy**. Without
them the film still renders; with them it looks the way it was directed.
