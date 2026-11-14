"""Word timings: the clock every scene, cue, caption and mouth shape is timed against.

Canonical file (build/words.json):
    {"language": "en", "source": "faster-whisper medium", "duration": 31.2,
     "words": [{"w": "Hello,", "s": 0.12, "e": 0.40}, ...]}

Importers accept: the canonical format; ElevenLabs TTS `alignment` (per-character times); ElevenLabs Scribe
speech-to-text (`words` with text/start/end/type); and segment lists ([{"words": [{"w"|"word", "s"|"start", ...}]}])
such as faster-whisper dumps.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .errors import OexError


@dataclass(frozen=True)
class Word:
    w: str
    s: float
    e: float


def norm(token: str) -> str:
    """Matching key: NFKC, lowercase, letters/digits only (keeps ñ, accents, Tagalog hyphen-free forms)."""
    t = unicodedata.normalize("NFKC", token).lower()
    return "".join(ch for ch in t if ch.isalnum())


_UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                      "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if i > 1}
_SCALES = {"hundred": 100, "thousand": 1000, "million": 1_000_000, "billion": 1_000_000_000}


def _numbers(toks: list[str]) -> list[str]:
    """English number words -> digits ('thirty one' -> '31', 'three hundred' -> '300'), because recognisers write
    numbers as digits while scripts often spell them out. Applied to script and transcript alike."""
    out, i = [], 0
    while i < len(toks):
        if toks[i] in _UNITS or toks[i] in _TENS:
            total, cur, j = 0, 0, i
            while j < len(toks):
                t = toks[j]
                if t in _UNITS:
                    cur += _UNITS[t]
                elif t in _TENS:
                    cur += _TENS[t]
                elif t in _SCALES and (cur or total):
                    if _SCALES[t] == 100:
                        cur *= 100
                    else:
                        total += cur * _SCALES[t]
                        cur = 0
                elif t == "and" and j + 1 < len(toks) and (toks[j + 1] in _UNITS or toks[j + 1] in _TENS) and cur >= 100:
                    pass
                else:
                    break
                j += 1
            out.append(str(total + cur))
            i = j
        else:
            out.append(toks[i])
            i += 1
    return out


def word_key(w: str) -> str:
    """Matching key for ONE recognised word (keeps a 1:1 index with the transcript)."""
    n = norm(w)
    return _numbers([n])[0] if n else ""


def tokens(text: str) -> list[str]:
    return _numbers([n for n in (norm(t) for t in re.split(r"[\s—–/]+", text)) if n])


# ---------- import ----------

def _from_chars(chars, starts, ends) -> list[Word]:
    out, buf, s0, e0 = [], "", None, None
    for c, s, e in zip(chars, starts, ends):
        if c.isspace():
            if buf.strip():
                out.append(Word(buf, round(s0, 3), round(e0, 3)))
            buf, s0 = "", None
            continue
        if s0 is None:
            s0 = s
        buf += c
        e0 = e
    if buf.strip():
        out.append(Word(buf, round(s0, 3), round(e0, 3)))
    return out


def parse(data) -> tuple[list[Word], str | None]:
    """Return (words, language) from any supported JSON shape."""
    lang = None
    if isinstance(data, dict):
        lang = data.get("language") or data.get("language_code")
        al = data.get("alignment") or data.get("normalized_alignment")
        if al is None and "characters" in data:
            al = data
        if al is not None:
            return _from_chars(al["characters"], al["character_start_times_seconds"],
                               al["character_end_times_seconds"]), lang
        if "words" in data:
            items = data["words"]
        elif "segments" in data:
            items = [w for seg in data["segments"] for w in seg.get("words", [])]
        else:
            raise OexError("unrecognised word-timing JSON (no words, segments or alignment key)",
                           "supply faster-whisper output, ElevenLabs alignment/Scribe JSON, or run `oex transcribe`")
    elif isinstance(data, list):
        items = [w for seg in data for w in seg.get("words", [])] if data and "words" in data[0] else data
    else:
        raise OexError("word-timing JSON must be an object or a list")
    out = []
    for it in items:
        if it.get("type") not in (None, "word"):
            continue  # Scribe "spacing" / "audio_event"
        text = it.get("w", it.get("word", it.get("text")))
        s = it.get("s", it.get("start"))
        e = it.get("e", it.get("end"))
        if text is None or s is None or e is None or not str(text).strip():
            continue
        out.append(Word(str(text).strip(), round(float(s), 3), round(float(e), 3)))
    return out, lang


def validate(words: list[Word], audio_duration: float | None = None) -> list[str]:
    problems = []
    if not words:
        problems.append("no words")
    prev = -1.0
    for i, w in enumerate(words):
        if w.e < w.s:
            problems.append(f"word {i} '{w.w}' ends before it starts ({w.s} > {w.e})")
        if w.s < prev - 0.05:
            problems.append(f"word {i} '{w.w}' starts at {w.s}s, before the previous word ({prev}s): not in order")
        prev = max(prev, w.s)
    if audio_duration is not None and words and words[-1].e > audio_duration + 0.25:
        problems.append(f"last word ends at {words[-1].e}s but the audio is only {audio_duration:.2f}s long: "
                        "timings belong to a different take")
    return problems


def save(path: Path, words: list[Word], language: str | None, source: str, duration: float | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"language": language, "source": source, "duration": duration,
                                "words": [{"w": w.w, "s": w.s, "e": w.e} for w in words]},
                               ensure_ascii=False, indent=0), encoding="utf-8")


def load(path: Path) -> list[Word]:
    if not path.exists():
        raise OexError(f"no word timings at {path}",
                       "run `oex transcribe` (needs the transcribe extra) or `oex words import <file.json>`")
    words, _ = parse(json.loads(path.read_text(encoding="utf-8")))
    return words


_FRAGMENT = re.compile(r"^[-,.'’%][\w%]")


def merge_fragments(words: list[Word], max_gap: float = 0.06) -> list[Word]:
    """Recognisers split some words: '400' + ',000', 'long' + '-distance', 'don' + "'t". Join a piece that starts
    with a joining character and follows the previous word without a pause."""
    out: list[Word] = []
    for w in words:
        if out and _FRAGMENT.match(w.w) and w.s - out[-1].e <= max_gap:
            p = out.pop()
            out.append(Word(p.w + w.w, p.s, max(p.e, w.e)))
        else:
            out.append(w)
    return out


# ---------- onset refinement ----------

def speech_onsets(x, rate: int = 16000, hop: float = 0.01):
    """Times (s) where the signal rises out of silence. Speech at t=0 counts as an onset at 0."""
    import numpy as np

    n = int(rate * hop)
    frames = len(x) // n
    if frames == 0:
        return np.zeros(0)
    e = np.sqrt((x[: frames * n].reshape(frames, n) ** 2).mean(1) + 1e-12)
    db = 20 * np.log10(e)
    thr = max(np.percentile(db, 95) - 30, -55)
    on = db > thr
    # ignore 1-2 frame blips
    for i in range(1, len(on) - 1):
        if on[i] and not on[i - 1] and not on[i + 1]:
            on[i] = False
    idx = np.nonzero(on[1:] & ~on[:-1])[0] + 1
    if on[0]:
        idx = np.concatenate([[0], idx])
    return idx * hop


def refine(words: list[Word], x, rate: int = 16000, min_gap: float = 0.08,
           early: float = 0.12, late: float = 0.4) -> tuple[list[Word], int]:
    """Snap the start of every word that follows a pause to the real speech onset.

    Recognisers place word starts at pauses up to ~0.3 s early (measured on our test takes: +0.10..+0.26 s), and
    those are exactly the words scenes and cues land on. Mid-phrase words are left alone (no reliable onset)."""
    import numpy as np

    on = speech_onsets(x, rate)
    if not len(on):
        return words, 0
    out, moved = [], 0
    for i, w in enumerate(words):
        prev_e = out[-1].e if out else -1.0
        if i == 0 or w.s - prev_e >= min_gap:
            lo, hi = max(prev_e + 0.02, w.s - early), min(w.s + late, w.e - 0.05)
            cand = on[(on >= lo) & (on <= hi)]
            if len(cand):
                ns = float(cand[np.argmin(np.abs(cand - w.s))])
                if abs(ns - w.s) >= 0.02:
                    w = Word(w.w, round(ns, 3), w.e)
                    moved += 1
        out.append(w)
    return out, moved


# ---------- transcription ----------

# Our transcription defaults (spec S8), each with its reason:
WHISPER = {
    "word_timestamps": True,             # the whole pipeline is timed by words
    "vad_filter": True,                  # skip non-speech: fewer invented words in pauses and music
    "vad_min_silence_ms": 500,           # only split on clear pauses; onset refinement handles the fine timing
    "condition_on_previous_text": False, # one misheard phrase must not propagate into the next ones
    "beam_size": 5,                      # library default; exposed for slow/noisy takes
}


def transcribe(audio: Path, language: str | None, model: str = "small", prompt: str = "",
               device: str = "cpu", compute_type: str = "int8", beam_size: int | None = None) -> tuple[list[Word], str]:
    """Word timings with faster-whisper (dependency, public API). language=None lets Whisper detect it.
    Taglish: language "tl" (Tagalog) - English words inside are kept as spoken."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise OexError("faster-whisper is not installed",
                       "uv sync --extra transcribe   (or pip install 'openexplainer[transcribe]'), "
                       "or import timings with `oex words import`") from e
    from .media import decode_mono

    samples = decode_mono(audio, 16000)
    whisper = WhisperModel(model, device=device, compute_type=compute_type)
    segments, info = whisper.transcribe(
        samples, language=language, initial_prompt=prompt or None,
        word_timestamps=WHISPER["word_timestamps"], vad_filter=WHISPER["vad_filter"],
        vad_parameters={"min_silence_duration_ms": WHISPER["vad_min_silence_ms"]},
        condition_on_previous_text=WHISPER["condition_on_previous_text"],
        beam_size=beam_size or WHISPER["beam_size"])
    words = [Word(w.word.strip(), round(w.start, 3), round(w.end, 3))
             for seg in segments for w in (seg.words or []) if w.word.strip()]
    words, _ = refine(merge_fragments(words), samples)
    return words, info.language
