# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Animated `diagram` scenes: nodes (box, pill, circle, diamond) placed by hand or by a `row`, `column`, `cycle` or
  `hub` layout, labelled groups, and straight, curved or right-angled connectors with labels. Steps cued on the
  narration's words show and hide parts, draw connectors, send tokens along one connector or a chain (with an answer
  coming back), switch states (active, done, error), dim or focus parts, relabel nodes (the node resizes smoothly to
  its new label) and move them with one of ten easing curves. `"continue": true` carries a diagram on into the next
  scene without a visible cut. Every style gains `good` and `bad` colours for done and error states.
- Diagram rendering is fast and deterministic: frames are drawn at 2x and box-filtered (sharp text and thin lines
  without halos), and a diagram that is not changing is drawn once and reused. About 6-12 ms per 1080p frame on
  an Apple Silicon laptop; output is identical in any frame order, on any number of workers and with or without
  the cache.
- `oex validate` checks animated diagrams: unknown ids (it lists the valid ones), an id of the wrong kind,
  duplicate ids, broken token paths, nodes without a position in a manual layout.
- QA checks that every diagram step lands on its word; automatic sound effects can mark diagram reveals.
- `oex review` prompts on animated diagrams that never move or freeze for long, steps too close together or that
  start too many changes at once, nodes that touch, diagrams that are small or off-centre, and camera pushes over
  diagrams.
- The storyboard-builder skill's motion guide (`references/motion.md`) tells agents when and how to plan animated
  diagrams; the explainer-director and render-qa skills plan and check them (including `oex sheet --every 0.5` to
  look at motion).

### Fixed
- Text no longer shakes when the camera push is on. The push resized each frame to a truncated whole-pixel size and
  cropped at a truncated offset, so text jumped back and forth by about a pixel; the camera push, zoom and slide now
  use one sub-pixel transform (premultiplied alpha), so the push is a smooth, steady drift.
- `oex sheet --every N` now respects `--scene` and labels each frame with its scene and time.
- `oex review` no longer calls a run of `image` or `diagram` scenes repetitive (each picture is its own layout),
  and counts animated diagrams as pictures.

### Changed
- New projects (`oex new`, including `--demo`) set `"camera": "still"` in `project.json`. Existing projects without a
  `camera` setting keep their style's camera; a scene's own `camera` still overrides both.
- Existing projects re-render (the renderer changed, so cached scenes are rebuilt). Frames are unchanged except
  where the camera push, slide or zoom moves them: those are now positioned with sub-pixel accuracy, so they differ
  by a fraction of a pixel from v0.2.0.
- The user guide's example `project.json` now uses the default music levels (`gain_db` -14, `duck_db` 8).

### Documentation
- macOS `say` narration is for private drafts and tests only: Apple's macOS licence allows its system voices for
  personal, non-commercial use and not for publishing or public sharing. The README, install and user guides, the
  voice-sync and explainer-director skills and the TTS docstrings now say so.

## [0.2.0] - 2026-11-14

Second public beta: illustrated explainers, more reliable narration and audio, and a cleaner emphasis highlight.
Tested on macOS only; Linux and Windows are unverified; GitHub Actions CI has not passed yet.

### Fixed
- `oex tts` no longer reports success when the engine produced no audio: every provider writes to a temporary file
  that must contain real, audible speech of a plausible length before it replaces the narration. A failure is an
  error with a fix, the previous narration is kept, and no other provider is tried. (macOS `say` inside a sandbox
  could exit successfully and leave an empty file.)
- The emphasis highlight under `*accent*` text (`statement` emphasis, titles) is one continuous bar per line of
  accented text, exactly as wide as the accented letters (not unaccented punctuation such as the "?" in
  `*fly*?`), drawn just below their lowest ink. It used to be one bar per word, with gaps between words, sitting on
  top of descenders (g, p, y). Animation and timing are unchanged.

### Added
- Diagram guide and Pillow-only diagram kit in the storyboard-builder skill (`references/diagrams.md`,
  `scripts/diagram_kit.py`) for original explanatory diagrams in `image` scenes, in the film's style.
- `oex review` visual prompts (no pictures in a longer film, runs of text-only scenes, lonely short lines, diagrams
  too small for the stage) and music-level prompts (barely audible, competing with the voice).
- `oex new` warns when a project is created in a temporary folder or inside the toolkit's source folder.

### Changed
- Skills: storyboard guidance on choosing pictures, composition, variety, pacing and text density; documented
  narration options and failure handling; durable project folders; agents must not search the user's other
  folders or toolchains for missing assets.
- sound-designer's music example now matches the defaults (`gain_db` -14, `duck_db` 8); the previous example
  (-20 / 10) made music almost inaudible.

## [0.1.0]

First public beta. Tested on macOS only; Linux and Windows are unverified; GitHub Actions CI has not passed yet.

- `oex` command line tool: project scaffolding (`oex new`, `oex new --demo`), script length planning
  (`oex estimate`), narration intake, transcription with faster-whisper (optional) or imported word timings,
  optional text-to-speech providers.
- Storyboards as data: scene types `title`, `bullets`, `statement`, `flow`, `number`, `compare`, `image`, `end`,
  with entrances and highlights timed to words of the narration; styles; 16:9 and 9:16; 1080p H.264/AAC.
- User-made mascots: prompt library, preparation and review sheet, audio-driven lip sync, blinks, poses and
  expressions on cue words.
- Sound: SFX catalog with licence status, automatic cue placement, music ducked under the voice, true-peak
  limited mix, stems, credits file.
- Captions (SRT/VTT, optional burn-in), per-scene render cache, previews and contact sheets.
- QA on the rendered file (integrity, duration, A/V sync, cue timing, loudness, black frames, captions),
  `oex review` and a per-render `VERIFY.md`.
- Six Agent Skills for Claude Code and Codex, with an installer (`tools/skills.py`).
- Examples, a 60-second showcase project, demo mascot "Pip" and demo sounds generated by the repository's scripts.
