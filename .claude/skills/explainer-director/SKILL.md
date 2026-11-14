---
name: explainer-director
description: Produce a narrated explainer video end to end with the open-explainer toolkit (oex CLI) - topic or script in, 1080p MP4 + captions + audio stems out, optionally with the user's own talking mascot, music and sound effects, in 16:9 or 9:16. Use when the user asks to make an explainer video, an educational/animated video from a script or topic, or a talking-mascot video. Hands off to storyboard-builder, voice-sync, mascot-prep, sound-designer and render-qa for each stage.
---

# Explainer director

Run the film as gated stages. All timing, mixing, rendering and checking is done by the `oex` CLI: run its
commands; never re-implement them or hand-edit files under `build/` or `renders/`.

Before anything: `oex doctor` (if `oex` is missing: toolkit `docs/INSTALL.md`). To show what the toolkit makes before
they have any recording: `oex new demo --demo && oex -C demo render`.
Every `oex` command takes `-C <project>`.

**Where projects live:** in a durable folder the user chooses; if they have no preference, `~/OpenExplainer/<topic>`.
Never in a temporary folder (`/tmp`, the system temp dir; it is cleared) and never inside the toolkit's own folder
(their recordings must never be committed). `oex new` warns about both. Tell the user where the project is.

**Privacy:** work only in the user's project and the toolkit. Never search the user's other folders, caches or
other projects for voices, models, images, music or tools, and never reuse files from them. If something is
missing, say what and offer the documented options (see voice-sync for narration).

## Start from what the creator already has

Many creators have never used video software. Do not open with a questionnaire. Look first, then ask only for
what is missing, in plain words, one thing at a time, and choose everything else yourself (say what you chose).

| They have | Do |
|---|---|
| a voiceover (MP3/WAV/M4A) | `oex new <dir> --style midnight` then `oex -C <dir> use-narration <file>`. No script? `oex -C <dir> transcript` gives the recording as paragraphs: build one scene per paragraph from it |
| a script but no recording | check its length (`oex estimate script.txt --target <length>`), then ask them to record it (phone voice memo is fine) or offer `oex tts` |
| only a topic | write the script (rules below), check its length, show it, then ask them to record it |
| mascot images | `oex -C <dir> use-mascot <folder>`; show them `mascot/build/review.png` and ask "does this look right?" |
| no mascot yet | ask once: "Would you like a cartoon of yourself as the presenter?" If yes, `oex prompts` and give prompt 1 to paste into ChatGPT with their photo, then prompts 4, 3, 5 one at a time. If no or later, make the film without a mascot |

Defaults (do not ask): 16:9 1920x1080, captions on, style `midnight` (or `paper` for a light look), no music unless
they have music they may use or accept the toolkit's demo bed, automatic sound effects only with a rights-clear
catalog. Never ask about fps, LUFS, styles' internals or file formats.

Talk in outcomes: "your video", "the cartoon of you", "your voice recording" - not "storyboard JSON" or "visemes".

## Stages

| # | Stage | Do | Gate (do not continue until) |
|---|---|---|---|
| 1 | Inputs | As above: what they have, what is missing, defaults chosen. | a voice recording (or approved script + chosen voice route) |
| 2 | Script | Write or recover one paragraph per scene (below). Check the length with `oex estimate`; add or cut words until it says *on target*. Show it as plain paragraphs they can read aloud. | on target, and the creator approves it |
| 3 | Project | `oex new <dir>`; `oex use-narration <file>` (copies, transcribes, reports length and fit); `oex use-mascot <folder>` if they have one. | narration in place, plan prints the scene list |
| 4 | Storyboard | Use **storyboard-builder**: plan the pictures first. Where parts interact or something happens over time, use an animated `diagram` scene timed to the words (references/motion.md in the storyboard-builder skill); where a shape or place explains it, draw an original picture (references/diagrams.md). `"say"` = that paragraph's exact words. A strong hook: a striking `number`, a picture, or a short `title` whose `emphasis` lands on the key spoken phrase. `oex validate`. | 0 problems |
| 5 | Timing | `oex plan`. Fix every error; read every warning. | plan prints the scene list |
| 6 | Mascot / sound | Optional: **mascot-prep** (approve `review.png` with them), **sound-designer**. | they approved the mascot review |
| 7 | Preview | `oex render --preview`, then `oex sheet --film renders/<name>-preview.mp4` and LOOK at the sheet, and read `oex review`. Ask: would a viewer understand the idea with the sound off? Is any scene a lonely line, a wall of text, or a tiny drawing? Are labels readable? Does each animated diagram step land on its word, and does anything move that the narration is not talking about? Fix `storyboard.json` or the diagrams and re-render (only changed scenes re-render). | the sheet explains the topic; review warnings fixed or explained |
| 8 | Final | Use **render-qa**: `oex preflight`, then `oex render`. QA must print `QA: PASS`. Give them the MP4, show `*-sheet.png`, mention captions (`.srt`) and `*.credits.json`, and ask them to watch it once. | preflight PASS, then QA PASS shown in the output |

## Script rules

- Hook first: open on the most surprising true claim or a question. Name the topic by paragraph 2.
- One idea per paragraph, and each paragraph becomes one scene. Length comes from word count: about 150 words per
  minute for a typical narrator (75 words ≈ 30 s, 450 ≈ 3 min, 800 ≈ 5:30). Never fix a short film by asking for
  slower speech; add content. After the take is recorded, `oex estimate` measures the real pace.
- Plain spoken language; short sentences; say numbers the way they will be spoken.
- Facts must be checkable: research them, and tell the user which claims you are unsure of rather than inventing.
- Code-switched narration (e.g. Tagalog-English) is fine. Write it exactly as it will be spoken.

## Never

- Claim a film is in sync, complete or "passing" without the `oex render` / `oex qa` output that says so.
- Use music or sound effects whose licence the user has not confirmed. Unverified assets are flagged in
  `*.credits.json` (`publish_safe: false`). Tell the user before they publish.
- Ask for or store the user's photo. Mascots are prepared from their finished PNGs only.
- Present a film narrated with macOS `say` as ready to publish: its voices are licensed for personal, non-commercial
  use only. Say so, and offer the user's own recording instead.
- Search the user's computer for missing tools, voices, models or assets, or use files from their other projects.
- Leave a real project in a temporary folder.
