# Contributing

1. `uv sync --extra transcribe`, then `.venv/bin/python -m pytest` and `uvx ruff check src tools tests`. All tests
   and lint checks must pass (the CI workflow runs both).
2. Keep deterministic work in code (`src/openexplainer/`), not in skill instructions. Skills stay short and call `oex`.
3. Every user-facing error is an `OexError` with a `fix`. Validate inputs and report all problems at once.
4. A change that affects pixels or sound needs a test, and a look at a contact sheet (`oex sheet`) of an example.
5. Assets: contribute only material you made or that has a licence allowing redistribution. Record the source and
   licence in the PR. No third-party characters, logos, voices or sound packs with unclear rights. No real people's
   likenesses without their written permission.
6. Never commit narration recordings, renders, `build/` folders, API keys or personal data.
7. Update `docs/` and add a line under "Unreleased" in `CHANGELOG.md` when behaviour or commands change.
8. Original work only: start a new core component from a written spec in `docs/specs/COMPONENTS.md`, never by porting another
   project's code. Studying other projects' architecture is fine; copying their code, prompts, schemas or assets is
   not, unless the licence allows it AND it is recorded in THIRD_PARTY_NOTICES.md.
9. After editing `skills/`, `prompts/`, `docs/mascot/` or `docs/agent-guide.md`, run `python tools/skills.py sync`.

Architecture decisions go in `docs/adr/` (short: context, decision, consequences).
Security problems: please report them privately, see [SECURITY.md](SECURITY.md).
