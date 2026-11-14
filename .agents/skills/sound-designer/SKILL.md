---
name: sound-designer
description: Add sound effects and background music the user has rights to, in an Open Explainer film - build a catalog from their own or licensed sounds (or map another catalog's JSON), label and query sounds, let the toolkit place restrained cues on scene events, and mix music ducked under the voice. Use for whooshes, pops, clicks, impacts, transitions, music beds, or when a film's audio is too busy, quiet or clipping.
---

# Sound designer

Restraint first: a cue on every cut is noise. The toolkit enforces `max_per_minute` and `min_gap`, but you decide
whether a film needs sound at all.

## Rights (ask before adding anything)

Every sound records `rights.status`: `own` (the user made it), `licensed` (licence checked: give `--licence`, and
`--credit` if the licence requires attribution) or `unknown`. Unknown sounds still work but mark the film
`publish_safe: false` in `renders/*.credits.json`. Never download sounds or music from random sites. Sounds are
referenced where they are, never copied into projects or this repository.

## Catalog

```
oex sfx --catalog <file> add <folder> --rights own|licensed|unknown [--licence ... --holder ... --source ... --credit ...]
oex sfx --catalog <file> map <other-catalog.json> --mapping <mapping.json>     # any JSON catalog, see USER-GUIDE
oex sfx --catalog <file> find whoosh kind:transition rights:safe max:1.0       # words + filters
oex sfx --catalog <file> label <id> --kind transition --add soft --good-for "slide changes"
oex sfx --catalog <file> check                                                 # files present and unchanged
oex sfx --catalog <file> cut <id> cue.wav --offset 0.2 --length 0.8 --gain -6
```

Default catalog: `~/.open-explainer/sfx/catalog.json`. `add` labels each sound from its name and from audio
analysis (length, brightness, attack), marking guessed kinds with `kind-guessed`. Fix anything wrong with `label`.

## In the film (`project.json`)

```json
"sfx":   {"catalog": "<file>", "auto": true, "max_per_minute": 6, "min_gap": 3.0, "gain_db": -12},
"music": {"file": "audio/bed.mp3", "gain_db": -14, "duck_db": 8, "license": "<licence>", "fade_out": 2}
```

Music level: start from the defaults above (`gain_db` -14, `duck_db` 8). That keeps the bed clearly audible in
pauses, about 14-18 dB under the voice, and well under it while the voice speaks. Change them only after
listening, in steps of 2 dB: too loud → lower `gain_db` or raise `duck_db`; barely heard → raise `gain_db`.
`oex review` warns when music is barely audible (more than ~19 dB under the voice in pauses) or competes with the
voice while it speaks. No suitable music? Leave `music` out rather than adding an inaudible bed. The toolkit's
own demo bed (`examples/audio/music/calm-loop.wav`, MIT) and demo sounds (`examples/audio/catalog.json`) are
always safe to use.

- `auto` places cues by priority: scene changes (transition) > number landings, emphasis words, the call to action
  (chime, impact) > item reveals (pop, click). Sounds rotate so the same one never repeats back to back; `voice` and
  `ambience` kinds and sounds labelled speech/music/explicit/long are never chosen automatically.
- Explicit cues in a scene: `"sfx": [{"at": "phrase", "sound": "<id>"}]` or `{"tag": "pop kind:pop"}` (a query).
- `oex plan` prints every chosen cue and why. Too busy: lower `max_per_minute` or raise `min_gap`.

## Mix

Voice to −16 LUFS / −1.5 dBTP (two-pass loudness normalisation); music looped/trimmed, faded, and ducked by
`duck_db` wherever the voice speaks (the duck starts just before speech and recovers in pauses); SFX aligned so
their loudest moment hits the event; an oversampled true-peak limiter on the full mix. `renders/<film>-stems/`
holds voice, music, sfx and mix. QA reports loudness and true peak.
