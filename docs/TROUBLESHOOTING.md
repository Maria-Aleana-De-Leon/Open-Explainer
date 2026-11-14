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
| `say produced no audio file` / `no playable audio` / `silence` | macOS `say` could not reach the speech service, usually inside an agent's sandbox | run the same `oex tts --provider say` in your own Terminal (or let the agent run it outside its sandbox), or record the narration; your previous narration was kept |
| `... produced only Ns of audio for an N-word script` | the TTS engine stopped early | run it again; try a shorter text with your engine by hand; or record |
| review `music is barely audible` | `music.gain_db` too low | raise it towards the default -14 (in 2 dB steps), or leave music out |
| review `music competes with the voice` | not enough ducking | raise `music.duck_db` or lower `music.gain_db` |
| review `no pictures` / `three text-only scenes in a row` | the film explains with text only | draw a diagram for the mechanism being explained (storyboard-builder `references/diagrams.md`); ignore it where words really are clearest |
| review `the image covers only N% of the stage` | the picture was drawn too small | redraw it at the size in the diagram guide (images are never scaled up) |
| `warning: ... is in a temporary folder` / `inside the Open Explainer source folder` | the project was created in a poor place | move the project folder somewhere durable of your own, e.g. `~/OpenExplainer/` |
