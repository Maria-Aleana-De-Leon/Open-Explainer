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
| No recording yet | let them record from the approved script (recommended), or `oex tts --provider elevenlabs --voice <id>` (env `ELEVENLABS_API_KEY`, never written to disk) / `--provider say` (macOS drafts) / `--provider command --command "<engine> ... {text_file} ... {out}"` |

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
