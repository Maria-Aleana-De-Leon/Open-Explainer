# Troubleshooting

Every `oex` error says what is wrong and prints a `fix:` line. Logs of every render: `build/logs/`.

| You see | Cause | Fix |
|---|---|---|
| `ffmpeg not found on PATH` | FFmpeg missing | install it (see INSTALL.md), then `oex doctor` |
| `faster-whisper is not installed` | installed without the extra | `uv tool install --force '.[transcribe]'`, or `oex words import` |
| `project.json: N problem(s)` | schema errors (all listed) | fix each line; unknown fields suggest the right name |
| `narration audio not found` | wrong `narration.audio` path | put the take there or fix the path |
| `only N% of the storyboard narration was found in the recording` | wrong take, or the script changed after recording | re-record, or update each scene's `say` to what was said |
| `scene X: cue phrase "..." is not in this scene's 'say' text` | the phrase is not in that scene's narration | copy it exactly from `say` (or move the item) |
| warning `"..." was not recognised in the audio; time interpolated` | the recogniser spelled it differently | usually fine; add the word to `narration.prompt`, or cue a nearby word |
| `scene X: only 0.6s long` | a tiny scene | merge it with a neighbour |
| `N scene(s) failed; the film was not assembled` | a per-scene problem (e.g. missing image) | fix it, then the printed `oex render --only ...` |
| `mascot in DIR is not prepared` | no `build/mascot.json` | `oex mascot prepare DIR`, approve `review.png` |
| `mascot has no state for pose='x'` | the storyboard asks for an image you have not made | `oex mascot check DIR` lists states; add `pose-x.png` |
| warning `'expr-…' has no lip sync but is held over Ns of speech` | an expression held while talking | add `"for": 1.5` to that action |
| `background is not plain or transparent` | a busy background in a mascot image | re-export transparent (prompt 7) |
| `does not register well to neutral` | the generator changed the character | prompt 6 (re-align) |
| mouth patch shows a visible box/oval | variant colours or framing drifted | prompt 6, then re-prepare; check `review.png` |
| QA `FAIL mux offset` | audio/video misaligned in the final file (should never happen) | delete `build/`, re-render; report a bug with `build/logs/` |
| QA `WARN word timing` | recogniser timings off (noisy take) | `oex transcribe --model medium`; record closer to the mic |
| QA `WARN visual cues` | a cue produced no visible change | check that scene in `oex sheet --scene <id>` |
| QA `FAIL loudness` | very quiet/loud source, or heavy music | check the take; lower `music.gain_db` |
| `film is older than the current plan` | you ran `oex qa` after changing timings | `oex render` |
| `publish_safe: false` in credits | a sound/music without a verified licence | replace it, or confirm its licence and add it again with `oex sfx add <folder> --rights licensed --licence ...` |
| Render seems stuck | long film on a slow CPU | watch `build/logs/`; use `--preview` while iterating; `--workers N` |
| Codex cannot run `oex` | sandbox/PATH | allow the command; ensure `uv tool` bin dir is on PATH |
