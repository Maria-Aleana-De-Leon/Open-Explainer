# ADR 0002: Deterministic Python compositor + FFmpeg as the default renderer

Status: accepted, 2026-11-11

## Options considered

| Option | For | Against |
|---|---|---|
| **A. Python (Pillow + numpy) frame compositor → raw frames piped to FFmpeg** | Fully deterministic; unit-testable per frame; no browser or GPU; identical under Claude Code and Codex; scenes from templates and a JSON manifest; per-scene caching is trivial | Less expressive than CSS/SVG/GSAP; we write our own easing, text layout and shapes |
| B. HyperFrames (HTML+GSAP → headless Chrome) | Rich motion, web fonts and SVG; widely used by agent video kits | 0.x CLI drifting fast (0.8.117 → 0.9.36); ~150 MB Chrome; GPU-sensitive render speed; in practice pulls toward LLM-authored HTML per scene, which is hard to make reproducible |
| C. FFmpeg filters + ASS subtitles only | Zero Python dependencies; fast native rendering | Huge filter graphs for many events; awkward diagrams; hard to test |

## Decision

**A is the default backend.** Scenes are described by a validated manifest (`scene.type`, text, items, cue words).
Each scene type is a Python template that draws a frame for time *t*. FFmpeg encodes H.264 1080p MP4 and muxes the
mastered audio.

The renderer sits behind a small interface (`render_scene(scene, ctx) -> mp4`), so a HyperFrames backend can be
added later for users who want CSS motion. It would remain optional, never required.

## Consequences

- Python 3.10+ with `numpy` and `Pillow` is required. `faster-whisper` is an optional extra; it is not needed when
  word timings are supplied (for example an ElevenLabs alignment JSON).
- Default 30 fps (configurable to 60) keeps CPU renders fast. Scenes render in parallel processes and are cached by
  content hash.
- Fonts: we ship only OFL fonts with their licence files, or fall back to system fonts.
