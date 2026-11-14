# Open Explainer: guide for AI agents

<!-- AGENTS.md and CLAUDE.md are generated from docs/agent-guide.md by `python tools/skills.py sync`. Edit this file. -->

This repository is a toolkit for narrated explainer videos. All production work goes through the `oex` command
line tool (Python package in `src/openexplainer/`); the Agent Skills route you through it.

## Skills

Claude Code reads `.claude/skills/`; Codex reads `.agents/skills/`. Both are generated mirrors of the canonical
`skills/`. Edit `skills/`, then run `python tools/skills.py sync`.

| Need | Skill |
|---|---|
| A whole film, stage by stage | `explainer-director` |
| Write or fix `storyboard.json` | `storyboard-builder` |
| Narration, transcription, timings, TTS | `voice-sync` |
| The user's own mascot (prompts + preparation) | `mascot-prep` |
| Sound effects, music, licences | `sound-designer` |
| Preview, render, regenerate, QA | `render-qa` |

## Working rules

- Run `oex doctor` first. The command is `oex` (only contributors working on the toolkit's own code use
  `.venv/bin/oex` after `uv sync`).
- Create film projects in a durable folder the user chooses (default `~/OpenExplainer/<topic>`), never in a
  temporary folder and never inside this repository.
- Work only in the user's project and this toolkit. Never search the user's other folders, caches or projects for
  voices, models, images, music or tools, and never reuse files from them; if something is missing, ask.
- Pictures where they teach: draw original diagrams for mechanisms and structures (storyboard-builder,
  `references/diagrams.md`) instead of filling a film with text cards.
- Deterministic work (validation, timing, mixing, rendering, checks) is done by `oex`. Never re-implement it,
  and never hand-edit `build/` or `renders/`.
- Before a final render, run `oex preflight`. After it, `QA: PASS` and `VERIFY.md` are the evidence. Never claim
  a film is in sync or finished without them, and never treat a passing check as proof of visual quality: look at
  `oex sheet`.
- Ask before anything paid or outward-facing (TTS APIs, uploads, publishing). Read API keys from the environment
  only; never print or store them.
- Never ask for or store a person's photo; mascots are prepared from finished PNGs. Use only music and sounds whose
  rights the user has confirmed. Unknown rights must stay visible in `*.credits.json`.
- Projects, recordings and renders are the user's private material. Do not copy them into examples or the repo.

## Development

`uv sync --extra transcribe`, then `.venv/bin/python -m pytest`. Specs for core components: `docs/specs/COMPONENTS.md`.
Contribution and licensing rules: `CONTRIBUTING.md`. Add a test with every behaviour change.
