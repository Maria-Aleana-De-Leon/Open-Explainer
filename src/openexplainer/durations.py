"""Duration planning: predict a film's length from its script BEFORE recording, and calibrate with the real take.

Spoken length = words / effective pace, where the effective pace already includes the speaker's natural pauses.
Measured on our example takes: 148-155 effective words per minute (articulation ~190 wpm plus pauses). Between
paragraphs (= scene cuts) speakers pause a little longer; the film adds a short tail after the last word.
Nothing here slows narration down: if a script is short, the fix is more script, not slower speech.
"""
from __future__ import annotations

import json
from pathlib import Path

DEFAULT_WPM = 150.0          # effective words per minute when the speaker's pace is unknown
PARAGRAPH_PAUSE = 0.0        # the effective pace already includes paragraph pauses (verified on 3 takes)
TAIL = 1.2                   # film end hold (project.json "tail")


def count_words(text: str) -> int:
    return len([w for w in text.split() if any(ch.isalnum() for ch in w)])


def estimate(paragraphs: list[str], wpm: float = DEFAULT_WPM, tail: float = TAIL) -> dict:
    words = sum(count_words(p) for p in paragraphs)
    seconds = words / wpm * 60 + PARAGRAPH_PAUSE * max(0, len(paragraphs) - 1) + tail
    return {"words": words, "paragraphs": len(paragraphs), "wpm": round(wpm, 1), "seconds": round(seconds, 1)}


def words_for(target_s: float, paragraphs: int, wpm: float = DEFAULT_WPM, tail: float = TAIL) -> int:
    """Words a script needs to run `target_s` seconds at `wpm`."""
    return max(1, round((target_s - tail - PARAGRAPH_PAUSE * max(0, paragraphs - 1)) * wpm / 60))


def measured_wpm(words_json: Path, script_words: int) -> float | None:
    """The speaker's effective pace from an existing take: script words over the narration span."""
    if not words_json.exists():
        return None
    w = json.loads(words_json.read_text())["words"]
    if len(w) < 10:
        return None
    span = w[-1]["e"] - w[0]["s"]
    return script_words / span * 60 if span > 0 else None


def parse_target(s: str) -> float:
    """'3:00' / '180' / '3m' / '90s' -> seconds."""
    from .errors import OexError
    t = s.strip().lower()
    try:
        if ":" in t:
            m, sec = t.split(":")
            return int(m) * 60 + float(sec)
        if t.endswith("m"):
            return float(t[:-1]) * 60
        return float(t.rstrip("s"))
    except ValueError:
        raise OexError(f"cannot read the length '{s}'", "use 3:00, 180, 180s or 3m") from None


def fmt(seconds: float) -> str:
    return f"{int(seconds // 60)}:{seconds % 60:04.1f}"


def report(paragraphs: list[str], target: float | None, wpm: float, source: str) -> list[str]:
    e = estimate(paragraphs, wpm)
    lines = [f"{e['words']} words in {e['paragraphs']} paragraphs at {wpm:.0f} wpm ({source}) -> about "
             f"{fmt(e['seconds'])}"]
    if target:
        need = words_for(target, e["paragraphs"], wpm)
        diff = need - e["words"]
        off = e["seconds"] - target
        if abs(off) <= max(5.0, 0.05 * target):
            lines.append(f"on target ({fmt(target)}): within {abs(off):.0f} s")
        elif diff > 0:
            lines.append(f"short of {fmt(target)} by about {-off:.0f} s: add about {diff} words "
                         f"(~{max(1, round(diff / max(1, e['words'] / e['paragraphs'])))} paragraph(s))")
        else:
            lines.append(f"over {fmt(target)} by about {off:.0f} s: cut about {-diff} words")
    return lines
