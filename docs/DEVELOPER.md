# Developer guide

## Layout

```
src/openexplainer/
  cli.py, cli_mascot.py, cli_sfx.py   argparse front end; every error is an OexError with a fix line
  config.py, schema.py                 project.json / storyboard.json schemas + defaults (all problems reported at once)
  words.py                             word-timing formats, number/fragment normalisation, onset refinement, faster-whisper
  timeline.py                          script <-> transcript alignment, frame-exact scene cuts, cue resolution
  scenes.py, text.py, styles.py        scene templates (pure functions of time), text layout, styles as data
  captions.py                          chunking, SRT/VTT, burned-in captions
  mascot.py, mascot_io.py              mascot preparation (registration, changed regions, patches, review) - spec S3
  mouthtrack.py                        mouth-shape track from audio (features + DP smoothing) - spec S1
  presenter.py                         presenter scheduling (shapes, poses, nods, blinks) and drawing - spec S4
  demo.py                              synthetic starter project (`oex new --demo`)
  durations.py                         length planning from word count and measured pace (`oex estimate`)
  review.py                            quality heuristics (`oex review`): layout, text, pacing, sound
  sfx.py                               catalog oex-sfx-2: add/map, labelling, query, check, cut, cue planning - spec S5
  audio.py                             voice master, speech-presence ducking, SFX track, oversampled limiter - spec S2
  render.py                            per-scene frame rendering -> ffmpeg, cache, concat, mux
  qa.py                                checks on the rendered file, contact sheets
  pipeline.py                          plan -> presenter -> mix -> render -> captions/stems -> QA -> credits -> VERIFY.md;
                                       preflight
  tts.py                               optional TTS providers; `synthesize` + `check_speech` (no silent failures)
skills/                                Agent Skills, canonical (SKILL.md + references + agents/openai.yaml)
.claude/skills/, .agents/skills/      generated mirrors for Claude Code and Codex (`tools/skills.py sync`)
AGENTS.md, CLAUDE.md, skills.lock.json generated from docs/agent-guide.md and skills/
prompts/                               mascot prompt library
tools/                                 skills.py (sync/install), agent_e2e.py, demo asset generators,
                                       test narration
tests/                                 pytest (unit + end-to-end renders with ffmpeg)
```

## Data flow

1. `config.load_project` validates both JSON files (the `schema.check` mini-validator collects every problem).
2. `timeline.build` aligns each scene's `say` with `build/words.json` (difflib on normalised tokens; unmatched
   tokens interpolated), cuts scenes inside pauses (never more than 0.45 s before the first word), snaps to whole
   frames, resolves every `at` to a global time → `build/timeline.json`.
3. `presenter.plan` (if any): mouth shapes at 24 Hz (`mouthtrack`), pose/expression changes from cues, emphasis
   nods on stressed words, seeded blinks away from changes; `for_scene(scene, fps)` returns serialisable per-frame data.
4. `sfx.plan_cues`: explicit cues + prioritised automatic cues under the density budget.
5. `audio.build_mix` (cached by a hash of its inputs) → `build/audio/{voice,music,sfx,mix}.wav`.
6. `render.render_all`: one process per scene; each draws frames with Pillow and pipes raw RGB to ffmpeg
   (libx264, yuv420p). Output cached at `build/cache/<final|preview>/<scene>.<hash>.mp4`; the hash covers the
   resolved scene, job settings, mascot track slice, images and the renderer's own source code (`render.RENDERER`).
7. `render.assemble` concatenates segments (stream copy) and muxes the mix.
8. `qa.run` checks the output file; `pipeline._provenance` writes `*.credits.json`.

Determinism: every visual is a pure function of global time t. No randomness except fixed-seed tools.

## Tests

```bash
uv sync --extra transcribe
.venv/bin/python -m pytest              # about a minute; e2e tests need ffmpeg
uvx ruff check src tools tests          # lint (as in CI)
```

End-to-end examples (`examples/*`) need narration generated locally, see `examples/README.md`.
Opt-in suites: `OEX_REAL_MASCOTS=<folder> pytest tests/test_real_mascots.py` (real generator-made mascots, kept
outside the repo) and `python tools/agent_e2e.py --agent claude` (Claude Code makes a film using only the skills;
this uses your own Claude account and costs usage).
After editing `skills/`, `docs/agent-guide.md`, `prompts/` or `docs/mascot/`: `python tools/skills.py sync`
(a test fails until you do).

New core components start from a written spec in `docs/specs/COMPONENTS.md`; do not port code from other projects
(see CONTRIBUTING.md).

## Extending

- **Scene type**: add `build_<type>(sc, st, R, root) -> Built` in `scenes.py`, register in `BUILDERS`, add the
  type + required fields in `config.py` (`SCENE_TYPES`, `REQUIRED_CONTENT`, fields in `SCENE`), list its cue times
  in `qa._cues` and `sfx._events`, document it in the storyboard reference, add a render test.
- **Style**: add a dict to `styles.STYLES` (colours, radius, decor, default transition/camera).
- **Font / non-Latin scripts**: `styles.FONTS` maps weights to files; bundle only OFL/permissive fonts with their
  licence file.
- **TTS provider**: add a function in `tts.py` and a branch in `tts.synthesize` (it writes to a temporary file and
  `check_speech` validates it before the narration is replaced); keys come from environment only.
- **Render backend** (e.g. HTML/CSS): implement `render_scene(scene, job) -> status dict` with the same caching
  contract; see ADR 0002.

## Conventions

- Errors are `OexError(message, fix)`; schema errors are `ValidationError` with every problem listed.
- Never write into a user's source folders (mascot sources, SFX libraries); outputs go to `build/` or `renders/`.
- Secrets only from environment variables, never logged or written to project files.
