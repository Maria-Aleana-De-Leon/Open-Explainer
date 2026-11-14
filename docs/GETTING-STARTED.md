# Getting started (no video experience needed)

Open Explainer turns **your voice** and, if you like, **a cartoon of you** into a finished explainer video with
animated diagrams, captions, gentle music and sound effects.

## What you need

| Item | How to get it |
|---|---|
| A voice recording | Read your script aloud into your phone's voice memo app, or any microphone. A quiet room matters more than the microphone. MP3, WAV or M4A. |
| A script (optional) | Write one, or ask your AI agent to write it. If you only have a recording, that is enough. |
| A cartoon of you (optional) | Made in ChatGPT with our prompts (below). Without one, the video has no presenter. |

## The easy way: ask your agent

With the skills installed (see [INSTALL.md](INSTALL.md)), open Claude Code or Codex and say:

> Create an AI explainer video using my mascot and voiceover.

The agent checks what you have, asks only for what is missing, and makes the rest of the choices for you. You will be
asked to approve two things: the script (if it writes one) and the picture of your mascot. At the end you get an MP4
and a sheet of still frames, and you are asked to watch it once.

## Making your cartoon in ChatGPT

1. Show the prompts: `oex prompts`. Print one with `oex prompts 1`.
2. In ChatGPT, upload a clear photo of yourself with **prompt 1**. Ask for changes until you like it, then save it as
   `neutral.png`.
3. In the same chat, use **prompt 4** to make the mouth shapes (start with `mouth-ah.png`), **prompt 3** for blinking
   and expressions, **prompt 5** for gestures. One image per message, each an edit of `neutral.png`.
4. Put all the PNG files in one folder and tell your agent where it is (or run
   `oex -C <your project> use-mascot <that folder>`).
5. Look at the review picture you are shown. If something looks off, **prompt 6** says how to fix that image.

Your photo is only used inside ChatGPT. Open Explainer never asks for it.

## Doing it yourself

```bash
oex new my-video                                   # a new project folder
oex -C my-video use-narration ~/Desktop/voice.mp3  # your recording
oex -C my-video transcript                         # what you said, as paragraphs (for the storyboard)
oex -C my-video use-mascot ~/Desktop/my-mascot     # optional
oex -C my-video render --preview                   # quick look
oex -C my-video render                             # the finished video, in my-video/renders/
```

The storyboard (what appears on screen) is the one step that needs writing: your agent does it, or see the
[user guide](USER-GUIDE.md).

## Want to see an example first?

`oex new demo --demo && oex -C demo render` makes a short video without any recording. The 60-second showcase
`showcase/ai-agents-60s/` shows a full production with a mascot, music and effects.
