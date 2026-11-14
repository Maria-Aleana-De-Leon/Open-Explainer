# Release checklist

## Quality
- [ ] `uv sync --extra transcribe && .venv/bin/python -m pytest` → all pass (paste the summary in the release notes)
- [ ] `uvx ruff check src tools tests` → no errors; CI green on the release commit
- [ ] Render every example (`examples/README.md`) → `QA: PASS` for each; look at `oex sheet` for each
- [ ] Fresh install in an empty environment: `uv tool install '.[transcribe]'` → `oex doctor` → `oex new` →
      `oex tts --provider say` (macOS) → `transcribe` → `render` → PASS
- [ ] `python tools/skills.py sync --check` → 0 problems; `install`/`status`/`uninstall` into a temp `--dest` per agent
- [ ] At least one agent run per supported agent (Claude Code, Codex) producing a film; note results in the release notes
- [ ] Version bumped in `pyproject.toml` and `src/openexplainer/__init__.py`

## Secrets and personal data
- [ ] `git ls-files | xargs grep -nIE '(api[_-]?key|secret|token|password|sk-[A-Za-z0-9]{20}|xi-api-key: [^"])'` → only code that reads env vars
- [ ] No personal names, e-mail addresses, home-directory paths (`/Users/`, `C:\Users\`) in tracked files
- [ ] No narration recordings, renders, `build/` or `.venv/` tracked (`git ls-files | grep -E '\.(mp4|wav|mp3|aiff)$'`
      → only `examples/audio/` demo files)

## Licences and provenance
- [ ] Every tracked binary asset is listed with its origin: fonts (OFL), Pip (generated), demo audio (generated)
- [ ] THIRD_PARTY_NOTICES.md lists all adapted code with its original notice
- [ ] No third-party artwork, recordings or demo media; THIRD_PARTY_NOTICES.md is current
- [ ] Example `credits.json` files report `publish_safe: true`

## Confidential content
- [ ] Nothing describes, reconstructs or references any private/proprietary workflow of the maintainers; the
      project works without any private component
- [ ] Review the diff since the last release for internal notes, client names or unpublished material

## Publish
- [ ] Move "Unreleased" in CHANGELOG.md to the new version; tag `vX.Y.Z`; release notes (features, known
      limitations from README.md)
