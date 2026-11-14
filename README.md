# open-explainer

> **Public beta (v0.2.0).** Tested on macOS only; Linux and Windows are unverified. A GitHub Actions CI workflow is
> included but has **not passed yet**: so far the test suite has been run locally on macOS. Please
> [report problems](https://github.com/Maria-Aleana-De-Leon/Open-Explainer/issues).

Open-source toolkit for **narrated AI explainer videos**, driven by AI coding agents (Claude Code, Codex) or by hand.
Bring your narration and, optionally, your own cartoon mascot. open-explainer builds the storyboard timing,
animates scenes on your words, lip-syncs the mascot, mixes music and sound effects, renders 1080p MP4 and checks
the result.

- **Your voice is the clock.** Every scene cut, entrance, highlight and mascot gesture lands on a word of your
  recording. Storyboards name *phrases*, not timestamps; the toolkit aligns them to the audio.
- **Your own mascot.** Copy-ready prompts turn a photo of you into a cartoon in ChatGPT; the importer checks,
  aligns and prepares the images (mouth shapes, blinks, poses) and shows a review sheet before anything renders.
- **Deterministic and checkable.** Scenes are data (`storyboard.json`), rendered by code, cached per scene, and
  re-rendered only when they change. QA reads the finished MP4: frame count, duration, A/V offset, cue timing,
  loudness, true peak, black frames, captions.
- **Sound with provenance.** A searchable SFX catalog with licence status on every sound, restrained automatic cue
  placement, music ducked under the voice, a true-peak-limited mix, stems, and a credits file that says whether a
  film is safe to publish.
- **Multilingual.** Any Whisper language for timings (Tagalog-English code-switching included); lip sync is driven
  by the sound of the voice, not by language; captions use your script's spelling.

16:9 and 9:16 · 1080p H.264/AAC · SRT/VTT · stems · 30 s to 5+ min · runs on a laptop CPU, no GPU or browser.

## Quick start

You need FFmpeg and [uv](https://docs.astral.sh/uv/) (or Python 3.10+ with pip); see [docs/INSTALL.md](docs/INSTALL.md).

```bash
git clone https://github.com/Maria-Aleana-De-Leon/Open-Explainer.git open-explainer && cd open-explainer
uv tool install '.[transcribe]'          # installs the `oex` command (or, in a virtualenv: pip install '.[transcribe]')
oex doctor                               # checks Python, FFmpeg, encoders
oex new demo --demo && oex -C demo render    # try it: a short demo film, no recording needed -> demo/renders/
```

Your own film:

```bash
oex estimate script.txt --target 3:00    # is the script the right length? (before recording)
oex new my-film --format 16:9 --style paper
# put your recording at my-film/audio/narration.wav, write my-film/storyboard.json
oex -C my-film transcribe
oex -C my-film render --preview && oex -C my-film sheet
oex -C my-film render                    # final film + QA report + quality review + VERIFY.md
```

With an agent: open this folder in Claude Code or Codex (the skills are in `.claude/skills/` and `.agents/skills/`),
or install them for every project with `python tools/skills.py install --agent claude|codex|both`; then
say *"make an explainer video about how GPS works"*. See [docs/INSTALL.md](docs/INSTALL.md).

## Documentation

| | |
|---|---|
| [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md) | **start here** if you have never made a video |
| [showcase/ai-agents-60s/](showcase/ai-agents-60s/) | a complete 60-second production to copy from |
| [docs/INSTALL.md](docs/INSTALL.md) | installation, Claude Code and Codex setup |
| [docs/USER-GUIDE.md](docs/USER-GUIDE.md) | your first film, project and storyboard files |
| [docs/mascot/GUIDE.md](docs/mascot/GUIDE.md) · [prompts/](prompts/) | make and prepare your own mascot |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | errors and fixes |
| [docs/DEVELOPER.md](docs/DEVELOPER.md) | architecture, modules, tests, extending |
| [docs/specs/COMPONENTS.md](docs/specs/COMPONENTS.md) · [docs/adr/](docs/adr/) | component specifications, architecture decisions |
| [CONTRIBUTING.md](CONTRIBUTING.md) · [SECURITY.md](SECURITY.md) · [CHANGELOG.md](CHANGELOG.md) · [docs/RELEASE-CHECKLIST.md](docs/RELEASE-CHECKLIST.md) | contributors and maintainers |

## Requirements and platforms

| | Required | Notes |
|---|---|---|
| Python 3.10+ | yes | `uv` can install one (`uv python install 3.12`) |
| FFmpeg with libx264 | yes | `brew install ffmpeg` · `sudo apt install ffmpeg` · `winget install Gyan.FFmpeg` |
| `faster-whisper` (`[transcribe]` extra) | optional | automatic word timings; downloads a Whisper model (~0.5 GB) on first use. Without it, import timings with `oex words import` |
| ElevenLabs text-to-speech | optional | your own account; `ELEVENLABS_API_KEY` in the environment (paid service) |
| macOS `say` | optional | private draft narration and local tests only (macOS only; not for published films, see below) |

**Platforms.** Developed and tested on macOS (Apple Silicon, CPU only). The code is pure Python plus FFmpeg and
is expected to work on Linux and Windows, but those platforms have not been tested yet. A CI workflow for Ubuntu and
macOS is included but has not passed yet. Reports are welcome.

## Status and known limitations

Version 0.2.0, **public beta**. Known limitations:

- GitHub Actions CI has not passed yet; the test suite has only been run locally on macOS.
- Tested on macOS only; Linux and Windows are unverified. 30 fps is tested, 60 fps is not.
- The free draft voice (macOS `say`) is for private drafts and tests only. Apple's macOS licence allows its system
  voices only for personal, non-commercial use and not for publishing or public sharing (see the "Voices" section
  of the macOS licence for your version). It also sounds robotic, is macOS-only, and cannot run inside some AI
  agents' sandboxes (for example Codex). Record your own narration, or use a TTS service or model whose licence
  allows publishing, for anything you share.
- Lip sync is driven by the sound of the voice: cartoon quality, not phoneme-accurate.
- Custom mascots are tested with the bundled demo mascot and a procedurally drawn stand-in; mascots made with
  image generators may need the repair prompt (`oex prompts 6`).
- Agent use is exercised end to end with Claude Code; Codex finds and reads the skills, but a complete Codex run
  has not been verified yet.
- No HTML/CSS render backend and no bundled icon library yet.

## Credits and licence

MIT (see [LICENSE](LICENSE)). Fonts: Poppins (SIL OFL 1.1). Dependencies, acknowledgements and third-party
licences: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
