---
name: render-qa
description: Render, preview, regenerate and quality-check open-explainer films - fast previews, contact sheets, cached per-scene rendering, re-rendering only failed or changed scenes, and the automatic checks on the final MP4 (frames, duration, A/V sync, visual cue timing, loudness, black frames, captions). Use when rendering, when a render fails, when a scene must be fixed, or to verify a finished film.
---

# Render and QA

## Commands

| Goal | Command |
|---|---|
| Fast look (12 fps, half size) | `oex render --preview` |
| See it | `oex sheet [--film <mp4>] [--scene s01,s02] [--every 5]` → `build/sheet.png`. Open and look at it |
| Before the final | `oex preflight`: timings, storyboard alignment, mascot states, sound files and rights, music |
| Final 1080p | `oex render` (runs QA, writes `<name>.VERIFY.md` and `<name>-sheet.png`) |
| Re-render some scenes | `oex render --only s03,s07 [--force]` |
| Check an existing film | `oex qa [--film <mp4>]` |
| Quality prompts | `oex review` (runs after every final render too): empty stages, repeated layouts, text-only films and runs of text-only scenes, lonely short lines, diagrams too small for the stage, long text, long pauses, loud or crowded effects, music too loud, barely audible or competing with the voice, loudness drift. Findings are things to look at, not failures |

Scenes render in parallel and are cached by everything that affects their pixels (content, timing, style,
mascot track and renderer code). Unchanged scenes are reused; changing one scene re-renders only that scene.

## When a scene fails

The other scenes still render; the film is not assembled; the error names each failed scene, the cause, and the
exact `oex render --only <ids>` to run after fixing. Logs: `build/logs/`. Status per scene:
`build/render-state.json`.

## QA (`build/qa.json`)

| Check | Pass condition |
|---|---|
| streams, codec, resolution, fps | 1 H.264 yuv420p video + 1 AAC 48 kHz stereo; size and fps as configured |
| frame count, duration | exactly the planned frames (±1); duration within 2 frames |
| mux offset | film audio vs mastered voice within ±1 frame (cross-correlation) |
| word timing (warn) | speech onsets vs word timings after pauses, median ≤ 60 ms |
| visual cues | on the scene model (no camera, captions, mascot): something appears or changes exactly at each cue |
| film = model | the decoded film matches the renderer's own frame (one per scene) within encoding noise |
| loudness, true peak | within ±2.5 LU of target; peak ≤ limit + 0.6 dB |
| black frames | no black segment ≥ 0.4 s |
| captions | SRT exists and ends within the film |

## Look at the sheet like a viewer

QA proves the file is correct, not that it explains anything. On `<name>-sheet.png` (and the preview sheet) check:

- **Explains, not just lists:** could a viewer follow the idea with the sound off? Where a mechanism or structure is
  described, is it shown (diagram, flow, comparison) rather than only written?
- **Composition:** one focal point per scene; nothing small and lost in a big empty stage; no lonely short line held
  for long; text inside diagrams readable at a glance.
- **Diagrams:** no line running through an object unless it is meant to; no label touching another label, a line
  or a shape's edge; nothing cramped against the edge; arrows start and end on the things they connect; even
  spacing. (The diagram kit prints these as warnings when it saves; look at the frames anyway.)
- **Variety:** not the same layout scene after scene.
- **Sound:** listen to `<name>-stems/mix.wav` or the film: is the music audible in pauses but never over the voice?

Fix what you find, re-render the changed scenes, and look again. Report what you checked and what you could not.

## Reporting

Report results exactly as printed. A WARN is not a PASS: explain it. Never say a film is done without `QA: PASS`.
QA and review cannot judge motion feel, clarity of the explanation, or tone of music and effects: say so, and
ask the user to watch the film.

## Outputs (`renders/`)

`<name>.mp4`, `<name>.srt`, `<name>.vtt`, `<name>-stems/{voice,music,sfx,mix}.wav`, `<name>.credits.json`
(licences of music/SFX used; `publish_safe` must be true before publishing), `<name>.VERIFY.md` (inputs, every
check, mascot coverage, publish safety) and `<name>-sheet.png` (one frame per scene).
