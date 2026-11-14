# ADR 0002: Deterministic Python compositor + FFmpeg as the default renderer

Status: accepted, 2026-11-11

## Options considered

| Option | For | Against |
|---|---|---|
| **A. Python (Pillow + numpy) frame compositor → raw frames piped to FFmpeg** | Fully deterministic; unit-testable per frame; no browser or GPU; identical under Claude Code and Codex; scenes from templates and a JSON manifest; per-scene caching is trivial | Less expressive than CSS/SVG and JavaScript animation libraries; we write our own easing, text layout and shapes |
| B. HTML/CSS animation rendered frame by frame in a headless browser | Rich motion, web fonts and SVG | Depends on fast-moving browser-rendering tooling; a ~150 MB browser download; render speed sensitive to the GPU; in practice pulls toward LLM-authored HTML per scene, which is hard to make reproducible |
| C. FFmpeg filters + ASS subtitles only | Zero Python dependencies; fast native rendering | Huge filter graphs for many events; awkward diagrams; hard to test |

## Decision

**A is the default backend.** Scenes are described by a validated manifest (`scene.type`, text, items, cue words).
Each scene type is a Python template that draws a frame for time *t*. FFmpeg encodes H.264 1080p MP4 and muxes the
mastered audio.

The renderer sits behind a small interface (`render_scene(scene, ctx) -> mp4`), so an HTML/CSS (browser-based)
backend can be added later for users who want CSS motion. It would remain optional, never required.

## Consequences

- Python 3.10+ with `numpy` and `Pillow` is required. `faster-whisper` is an optional extra; it is not needed when
  word timings are supplied (for example an ElevenLabs alignment JSON).
- Default 30 fps (configurable to 60) keeps CPU renders fast. Scenes render in parallel processes and are cached by
  content hash.
- Fonts: we ship only OFL fonts with their licence files, or fall back to system fonts.
