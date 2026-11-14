---
name: voice-sync
description: Bring narration into an open-explainer project and turn it into word-level timings - a recorded MP3/WAV, a pre-recorded ElevenLabs take (with or without its timestamp JSON), or optional text-to-speech - including Tagalog-English and other code-switched narration. Use when adding or replacing a voiceover, transcribing, importing timings, or when cues/captions drift from the voice.
---

# Voice sync

The narration is the clock. It is only loudness-mastered, never time-stretched or edited: the visuals move to the
words. Word timings live in `build/words.json`.

## Routes

| The user has | Do |
|---|---|
| A recording (MP3/WAV/M4A) | copy it to the path in `project.json` → `narration.audio`; `oex transcribe` |
| An ElevenLabs take + its timestamps JSON (`alignment` or Scribe `words`) | `oex words import <file.json>` (no transcription) |
| An ElevenLabs take only | treat it as a recording: `oex transcribe` |
| No recording yet | let them record from the approved script (recommended), or use text-to-speech (below) |

## Text-to-speech options

| Option | Needs | Notes |
|---|---|---|
| The user's own recording | a phone or microphone | best result; any MP3/WAV/M4A |
| `oex tts --provider say [--voice Samantha] [--rate 165]` | macOS (built in, free) | **private drafts and tests only**: Apple's macOS licence allows its system voices only for personal, non-commercial use and not for publishing or public sharing. Robotic but clear. List voices: `say -v '?'` |
| `oex tts --provider command --command "<engine> ... {text_file} ... {out}"` | a local TTS engine **the user has installed and chosen** (e.g. Piper, espeak-ng) | runs entirely on their machine |
| `oex tts --provider elevenlabs --voice <id>` | the user's ElevenLabs account; `ELEVENLABS_API_KEY` in the environment | paid, online: ask first; the key is never written to disk |

`oex tts` checks the result and replaces the narration only if it is real, audible speech of a plausible length.
If it reports an error, nothing was overwritten:

- **`say produced no audio` / `no playable audio`**: macOS `say` cannot reach the speech service from some sandboxed
  shells (for example an AI agent's sandbox). Ask the user to run the same `oex tts` command in their own Terminal,
  or to allow it to run outside the sandbox, or to record the narration.
- Any other provider failing: report the error and offer the other documented options. Never switch provider
  without asking.

Before a film is published, its narration must be the user's own recording or a voice whose licence allows
publishing: tell the user if the current take is a `say` draft.

Never search the computer for other voices, TTS models or audio from other projects, and never reuse files from
outside the user's project and this toolkit. If no documented option works, ask the user to record.

## Transcribe

```
oex transcribe [--language en|tl|...] [--model small|medium|large-v3]
```

- Set `narration.language` (Whisper code). **Tagalog / Taglish: `tl`**; English words inside are kept as spoken.
  Unsure? Leave it null to auto-detect, then set it.
- Put names and jargon in `narration.prompt` (e.g. `"GLONASS, BeiDou, Galileo"`) to improve their spelling.
- `small` is fast and usually enough; use `medium` for noisy takes or heavy code-switching.
- Words after a pause are snapped to the real speech onset (recognisers place them up to ~0.3 s early).

## Check

`oex plan` reports scenes whose `say` text was not heard (wrong take or edited script). Captions show the script's
own spelling (`captions.source: "script"`) with the recording's timing, so misheard words never appear on screen.

## Replacing the take

Copy the new file over the old one, run `oex transcribe` again, then `oex render`. Only scenes whose timing
changed are re-rendered.
