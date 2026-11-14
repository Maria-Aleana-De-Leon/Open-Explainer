# Component specifications

Functional specifications for Open Explainer's core components. Each spec states **what** a component must do and
how it is tested. New core components start from a spec here (see CONTRIBUTING.md); change the spec and its tests
together with the code.

---

## S1. Mouth-shape track from narration audio

**Purpose.** Drive a cartoon mouth from any spoken language without a phoneme model.

**Inputs.** Mono float audio (16 kHz); word timings (optional, improves pauses); output rate R (default 24 Hz).

**Output.** One label per 1/R s from the shape vocabulary (S7): `rest`, `mbp`, `half`, `ah`, `ee`, `oh`, `oo`, `fv`.

**Requirements.**
1. Silence longer than 0.25 s → `rest` (the character's own drawn mouth). Short gaps inside speech → `mbp`.
2. Mouth **openness** follows loudness, normalised per take (robust to quiet/loud recordings).
3. **Shape** (spread vs rounded) follows the balance of energy between broad low and mid frequency bands.
4. Hissy frames (high-band dominant, moderate loudness) → `fv`.
5. Labels must not flicker: a shape is held at least 2 output frames unless the mouth closes; switching is
   decided by a global smoothing that trades fidelity against changes (not by local patching).
6. Deterministic: the same audio always gives the same track.
7. Report: share of spoken words that receive an open shape; share of long pauses at `rest`.

**Tests.** Synthetic: silence → rest; tone bursts with gaps → open/closed alternation; band-limited noise → fv;
low- vs high-formant vowel stand-ins → oh/oo vs ee; no label run shorter than 2 frames except `mbp`.
Real: example narrations give ≥ 90 % talking words and ≥ 80 % resting pauses.

## S2. Voice master, music ducking and final mix

1. Voice: EBU R128 loudness to a target (default −16 LUFS integrated, −1.5 dBTP) using FFmpeg's documented
   two-pass `loudnorm` measurement + linear normalisation. Voice timing is never altered.
2. Music: looped or trimmed to the film, faded in/out, at a base gain.
3. **Ducking computed by our code:** a speech-presence curve from the mastered voice (RMS in 20 ms frames,
   thresholded relative to the take's speech level), smoothed with separate attack (≤ 80 ms) and release (≥ 300 ms)
   times, lookahead so the duck starts before speech; music gain = base − duck_db × presence. Applied in numpy.
4. SFX placed at their times with gains; full mix through a true-peak limiter; report LUFS/peak for voice, music, mix.

**Tests.** Duck depth under speech ≈ duck_db (± 1.5 dB); music returns to base level in pauses longer than
release + 0.2 s; the duck begins before speech onset; mix true peak ≤ limit + 0.5 dB.

## S3. Mascot preparation

**Inputs** (names per S7): `neutral.png`, `mouth-<shape>.png`, `blink.png`,
`pose-*.png`, `expr-*.png`.

1. Background: keep real alpha; otherwise remove a uniform or fake-checkerboard background, refuse busy ones.
2. **Registration** of every image to `neutral.png` by similarity transform (scale + translation), estimated from
   the upper part of the silhouette and its edges with an FFT-based translation search over a small scale set,
   refined at full resolution. A registration quality score in 0..1 is reported per image.
3. **Changed region** of a mouth/blink variant = pixels whose colour difference from neutral exceeds a threshold
   after registration, restricted to the face area, cleaned morphologically. The patch mask is that region grown by a
   margin and **feathered by distance to the region edge** (shape-following, not a fixed geometric window).
4. **Colour consistency:** each patch is colour-corrected to neutral with a per-channel gain/offset fitted on the
   unchanged, opaque pixels around the region (least squares).
5. Drift outside the face is measured and reported; it is never copied.
6. Per state: talk/blink allowed only if its mouth/eye area matches neutral well enough; otherwise reported.
7. Outputs and checks: aligned states, patches, `mascot.json`, `review.png`, missing-shape fallbacks.

**Tests.** The generated drift set and a set with large drift; registration recovers known offsets/scales
(±2 px, ±2 %); no visible seam (mean colour error at patch border ≤ 6/255); missing/unchanged/busy cases.

## S4. Presenter motion

1. Feet stay planted; poses/expressions change on cue times with a short ease (cross-fade ≤ 80 ms, or cut).
2. **Speech emphasis nods:** a small head-and-body dip on stressed words (word onsets after pauses or with high
   loudness), decaying in ~0.3 s; no motion in long pauses except idle.
3. **Idle:** slow, low-amplitude sway (two incommensurate sines) so the figure is never frozen.
4. **Blinks:** deterministic pseudo-random intervals (seeded by the project title), 2.5-6 s apart, occasional
   double blink, never within 0.25 s of a state change.
5. Entrance at film start (rise from below) and optional exit; mirroring for right-side placement.
6. Mouth track (S1) at its own rate, mapped to video frames by time.

## S5. SFX catalog

1. Our own record schema `oex-sfx-2`:
   `{id, name, file, kind, labels[], length_s, loudest_at_s, peak_dbfs, rms_dbfs, brightness_hz, onset_s, sha256,
   guidance: {good_for[], avoid[]}, rights: {status: own|licensed|unknown, licence, holder, source, credit_line}}`.
2. Import a folder (auto-labelling from names + audio analysis) or **any JSON catalog via a mapping file**
   (generic interoperability).
3. Query language: words match name/labels/kind/guidance; `kind:`, `rights:` and `max:<seconds>` filters; results
   ranked by match count then length.
4. Integrity check by hash; cue export (trim, gain, fades) to a new file, never overwriting.
5. Cue planner: priorities, density budget and rotation, reading this schema.

## S6. Skill installer

1. Installs skills for Claude Code and/or Codex into their skill folders.
2. Writes an **install manifest** (`.oex-manifest.json`: version, files and hashes) per skill. Refuses to touch
   folders without our manifest unless `--force`; **detects local edits** (hash mismatch) and refuses to overwrite
   them unless `--force`.
3. `uninstall` removes only files listed in our manifests. `status` reports ok/outdated/modified/missing.
4. Bundles mascot prompts and guides into `mascot-prep/references/`.

## S7. Mouth-shape vocabulary and file names

Phonetic names users recognise from animation practice:

| Shape | File | Sounds |
|---|---|---|
| `mbp` | `mouth-mbp.png` | lips pressed: m, b, p |
| `half` | `mouth-half.png` | slightly open, relaxed (quiet syllables) |
| `ah` | `mouth-ah.png` | open (a) **minimum for talking** |
| `ee` | `mouth-ee.png` | spread, teeth visible (e, i) |
| `oh` | `mouth-oh.png` | open and rounded (o) |
| `oo` | `mouth-oo.png` | small and pursed (u, w) |
| `fv` | `mouth-fv.png` | upper teeth on lower lip (f, v) |

Fallbacks: `half→ah`, `ee→ah`, `oh→ah`, `oo→oh→half`, `fv→mbp`, `mbp→rest`.

## S8. Transcription settings

faster-whisper is a dependency used through its public API. Our defaults are chosen and documented by us:
word timestamps on, VAD on, previous-text conditioning off (prevents run-on hallucination across pauses), beam
size configurable, CPU int8 default with an optional device flag. Tested by the example films' QA.
