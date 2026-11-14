# Examples

| Folder | Scenario | Format · style | Mascot | Sound |
|---|---|---|---|---|
| `email-30s/` | 30-second simple explainer | 16:9 · paper | none | voice only |
| `mascot-30s/` | short film with the mascot | 9:16 · midnight | Pip | voice only |
| `gps-3min/` | 3-minute educational explainer (3:07), every scene type | 16:9 · paper | Pip | music + auto SFX |
| `power-6min/` | 5-6-minute narration-driven film (5:21, 36 scenes) | 16:9 · chalk | none | music |
| `taglish-email/` | Tagalog-English narration | 9:16 · pop | Pip | auto SFX |
| `mascots/pip/` | demo mascot source PNGs (drawn by `tools/make_demo_mascot.py`, MIT) | | | |
| `audio/` | demo SFX + music (synthesised by `tools/make_demo_audio.py`, MIT) + `catalog.json` | | | |

Narration is **not** included: real films use your own recording. To run an example on macOS, generate a test
narration with the system voice (stays local, not for distribution):

```bash
python tools/say_narration.py examples/gps-3min --rate 165 --pause 500
oex mascot prepare examples/mascots/pip              # once, for the mascot examples
oex -C examples/gps-3min transcribe
oex -C examples/gps-3min render
```

All examples are voiced the same way, at a natural pace: `--rate 165 --pause 500` (effective 165-174 words per
minute). Script lengths were planned with `oex estimate`, not by slowing the voice down.
On other systems, record the `say` text of each scene yourself or use `oex tts --provider command`.

The Taglish example spoken by an English system voice tests the pipeline mechanics only (Tagalog transcription,
alignment, captions, lip sync). It is not a test of Tagalog speech quality. Record it yourself for that.
