# ADR 0003: Six skills over one CLI

Status: accepted, 2026-11-11

## Context

The initial design listed eight skills (explainer-director, storyboard-builder, mascot-prep, voice-sync,
scene-animator, sound-designer, video-renderer, quality-checker). In this architecture, animation is data in
`storyboard.json` rendered by code, and rendering always ends with QA.

## Decision

| Proposed | Final | Why |
|---|---|---|
| explainer-director | `explainer-director` | orchestration with approval gates |
| storyboard-builder + scene-animator | `storyboard-builder` | scenes and their animation are one artefact (types + cue phrases); a separate animator skill would have nothing to do |
| voice-sync | `voice-sync` | |
| mascot-prep | `mascot-prep` | bundles the prompt library via the installer |
| sound-designer | `sound-designer` | |
| video-renderer + quality-checker | `render-qa` | every render ends with QA; preview/regenerate/check are one loop |

Every skill is a short router (< 120 lines) to the `oex` CLI. Deterministic work (validation, timing, mixing,
rendering, checks) never lives in instructions. The same skill folders serve Claude Code and Codex (`SKILL.md` +
`agents/openai.yaml`).

## Consequences

Fewer, sharper triggers; one tested implementation for both agents. Agent-specific differences (Codex sandbox and
network, explicit `$skill` mentions) are documented in INSTALL.md, not forked into separate skills.
