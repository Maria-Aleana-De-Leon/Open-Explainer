# User guide: your first film

## The loop

```
script  ->  record  ->  storyboard.json  ->  oex transcribe  ->  oex render --preview  ->  oex sheet  ->  oex render
                                     ^-------------------- fix and repeat ---------------------|
```

### 1. Create a project

```bash
oex new my-film --format 16:9 --style paper --language en      # 9:16 for Shorts/Reels/TikTok
```

```
my-film/
  project.json      settings
  storyboard.json   scenes (a 3-scene template to replace)
  audio/            your narration (and music)
  build/            generated - safe to delete
  renders/          finished films
```

### 2. Write the script, check its length, then record it

One paragraph per scene. Length comes from word count, about 150 spoken words per minute (75 words ≈ 30 s,
450 ≈ 3 min, 800 ≈ 5:30). Check before you record: `oex estimate script.txt --target 3:00` says how many words to
add or cut. After recording, `oex -C my-film estimate --target 3:00` uses your measured pace. A short film needs
more script, not slower speech. Record
it in one take (quiet room, phone 20 cm away is fine) and save as `audio/narration.wav` (MP3/M4A also fine:
set `narration.audio`). Pauses between paragraphs help: scenes are cut inside them.

No microphone? `oex tts --provider say` (macOS draft voice), `--provider elevenlabs --voice <id>` (your account;
`ELEVENLABS_API_KEY` in the environment), or `--provider command --command "..."` for a local engine.
Already have an ElevenLabs take with its timestamps JSON? Use `oex words import file.json` instead of transcribing.

### 3. Storyboard

Each scene carries the exact narration it covers (`say`) and what appears, with **cue phrases** taken from that
narration:

```json
{"id": "s02", "type": "bullets",
 "say": "Each satellite repeats a simple message. It says who it is, exactly where it is, and the precise time.",
 "heading": "Every message says",
 "items": [{"text": "Who it is", "at": "who it is"},
           {"text": "Exactly where it is", "at": "exactly where"},
           {"text": "The precise time", "at": "precise time"}]}
```

Scene types: `title`, `bullets`, `statement`, `flow`, `number`, `compare`, `image`, `end`. Full reference:
[skills/storyboard-builder/references/storyboard-reference.md](../skills/storyboard-builder/references/storyboard-reference.md).
Check it any time with `oex validate`.

### Swapping in your recording or your mascot later

`oex use-narration <file>` (copies it in, keeps the old take, re-times everything, reports pace and length),
`oex use-mascot <folder>` (copies your PNGs in, prepares and checks them, lists missing gestures),
`oex transcript` (your recording as paragraphs, when you have a voiceover but no script), `oex prompts` (the ChatGPT
mascot prompts).

### 4. Timings

```bash
oex -C my-film transcribe      # word timings (faster-whisper, offline after the first model download)
oex -C my-film plan            # aligns the storyboard to the words; prints scene times and any problems
```

### 5. Preview, look, fix

```bash
oex -C my-film render --preview     # 12 fps, half size, seconds to minutes
oex -C my-film sheet --film my-film/renders/<name>-preview.mp4
```

`build/sheet.png` shows three frames per scene. Fix wording, cue phrases or scene types in `storyboard.json`; only
the scenes you changed render again.

### 6. Final render

```bash
oex -C my-film render
```

You get, in `renders/`: the MP4, `.srt` and `.vtt` captions, a `-stems/` folder (voice, music, sfx, mix) and
`.credits.json` (licences of everything used; check `publish_safe`), `.VERIFY.md` (evidence) and `-sheet.png`.
The QA report and a quality review (`oex review`: empty stages, repeated layouts, long text, pauses, sound balance)
print at the end. Neither replaces watching the film.

## project.json

```json
{
  "title": "How GPS works",
  "format": "16:9",
  "fps": 30,
  "style": "paper",
  "accent": "#E4572E",
  "narration": {"audio": "audio/narration.wav", "language": "en", "prompt": "GPS, GLONASS", "model": "small"},
  "mascot": {"dir": "../my-mascot", "position": "left", "scale": 1.0},
  "music": {"file": "audio/bed.mp3", "gain_db": -20, "duck_db": 10, "license": "CC-BY-4.0 Jane Doe", "fade_out": 2},
  "sfx": {"catalog": "~/sfx/catalog.json", "auto": true, "max_per_minute": 6, "min_gap": 3},
  "captions": {"burn_in": true, "max_words": 6, "source": "script"},
  "audio": {"target_lufs": -16, "true_peak": -1.5},
  "tail": 1.2
}
```

Only `title` and `narration.audio` are required. Paths are relative to the project folder and may point outside it
(a shared music folder, a mascot folder): files are used where they are, never copied, so keep them in place - or
copy them into the project (e.g. `audio/`) to make it self-contained before archiving or sharing it. Styles: `paper` (warm light), `midnight` (dark technical),
`chalk` (classroom board), `pop` (bright short-form). `mascot`, `music`, `sfx` may be `null`.

## Sound catalog

```bash
oex sfx add ~/my-sounds --rights own                                   # sounds you made
oex sfx add ~/cc0-pack --rights licensed --licence CC0-1.0 --source https://...
oex sfx find whoosh kind:transition rights:safe max:1
```

### Importing another catalog

Any JSON catalog can be mapped field by field. Paths are relative to the source file; dotted paths reach nested
fields; `status_values` translates the source's rights wording to `own` / `licensed` / `unknown`:

```json
{"records": "items", "file": "path", "name": "title", "kind": "category", "labels": "tags",
 "good_for": "usage.when", "avoid": "usage.avoid", "status": "rights.state", "licence": "rights.name",
 "status_values": {"cleared": "licensed"}}
```

`oex sfx map other/catalog.json --mapping mapping.json`. Sounds are referenced in place; anything without a known
status is `unknown`, and films using it are marked "needs review" in their credits.

## Your own mascot

See [mascot/GUIDE.md](mascot/GUIDE.md).

## Languages

Set `narration.language` to the Whisper code (`tl` for Tagalog and Taglish, `es`, `ja`, ...) or `null` to detect it.
Captions are spelled as in your script, timed from the recording. Lip sync works the same in every language.
On-screen text uses Poppins (Latin script). Non-Latin scripts need a font change (see DEVELOPER.md).
