# Installation

## 1. Requirements

| Need | Notes |
|---|---|
| Python 3.10+ | `uv` installs one for you (`uv python install 3.12`) |
| FFmpeg with libx264 | macOS `brew install ffmpeg` · Windows `winget install Gyan.FFmpeg` · Debian/Ubuntu `sudo apt install ffmpeg` |
| ~1 GB disk | + ~0.5 GB for the Whisper `small` model, downloaded on the first `oex transcribe` |

No GPU, browser, Node.js or paid service is required.

Optional: `faster-whisper` (the `[transcribe]` extra) for automatic word timings; ElevenLabs text-to-speech with
your own account (`ELEVENLABS_API_KEY` in the environment); macOS `say` for draft narration.

**Platforms:** developed and tested on macOS (Apple Silicon). Linux and Windows are expected to work (Python +
FFmpeg) but are not yet tested; please report problems.

## 2. Install the `oex` command

```bash
git clone https://github.com/Maria-Aleana-De-Leon/Open-Explainer.git open-explainer
cd open-explainer
uv tool install '.[transcribe]'      # recommended (isolated); without [transcribe] there is no automatic timing
# or, in a virtualenv:  pip install '.[transcribe]'
oex doctor
```

`oex doctor` lists anything missing with the command that fixes it.

For development: `uv sync --extra transcribe` then `.venv/bin/oex ...` and `.venv/bin/python -m pytest`.

## 3. Agent Skills

Six skills route an agent through the work, each calling the same `oex` CLI:

| Skill | Use |
|---|---|
| `explainer-director` | the whole film, stage by stage with approval gates |
| `storyboard-builder` | write and fix `storyboard.json` |
| `voice-sync` | narration intake, transcription, timings, TTS |
| `mascot-prep` | make your own mascot (prompts) and prepare it |
| `sound-designer` | SFX catalog, cues, music |
| `render-qa` | preview, render, regenerate, QA |

**In this repository** nothing needs installing: Claude Code finds the skills in `.claude/skills/` and Codex in
`.agents/skills/` (generated mirrors of `skills/`, with `AGENTS.md` / `CLAUDE.md` as the standing guide).

**For every project** on your machine:

```bash
python tools/skills.py install --agent claude     # -> ~/.claude/skills/
python tools/skills.py install --agent codex      # -> ~/.codex/skills/
python tools/skills.py status --agent both        # ok / outdated / modified locally / missing
python tools/skills.py uninstall --agent both     # removes only our files, keeps your edits
```

Each installed skill carries `.oex-manifest.json` (version and file hashes). Install refuses to overwrite a folder
it did not create or one you edited (`--force` to override); `--dest DIR` installs elsewhere. The mascot prompts
and guides are bundled into `mascot-prep/references/`. Restart the agent afterwards.

### Claude Code

Skills load from `~/.claude/skills/` (or a project's `.claude/skills/`). Ask *"make an explainer video about …"* and
the `explainer-director` skill triggers. `oex` must be on the PATH Claude Code's shell sees.

### Codex

Skills load from `~/.codex/skills/`. Mention one explicitly if it does not trigger: *"Use $explainer-director to
make an explainer video about …"*. Codex runs commands in a sandbox. Allow it to run `oex` and `ffmpeg`, and to
write in the project folder. `oex transcribe` needs network access once to download the Whisper model; afterwards
it runs offline.

### What has been verified for each agent

The skills pass the Agent Skills validation rules and both install layouts are tested (`tests/test_skills.py`,
scratch-folder installs). Claude Code has been exercised end to end on the example
scenarios (`tools/agent_e2e.py`); Codex end-to-end runs are not yet verified.

## 4. Update / uninstall

`git pull`, then `uv tool install --force '.[transcribe]'` and `python tools/skills.py install --agent ...`.
Uninstall: `uv tool uninstall openexplainer`, delete the six skill folders, and optionally
`~/.open-explainer/` (default SFX catalog) and `~/.cache/huggingface/` (Whisper models).
