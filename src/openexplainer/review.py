"""Quality review: heuristics for what technical QA cannot see. Findings are prompts to LOOK, not verdicts.

Checked from the plan and the rendered audio stems:
  layout   - empty stage before a scene's first content; the same layout 3+ times in a row; one layout dominating
  text     - headlines or items too long for their size; too many items
  pacing   - long pauses inside the narration; very short or long static scenes
  sound    - SFX density; SFX louder than the voice; music too loud in pauses; loudness drifting through the film
Not checkable automatically (report them as such): whether the motion feels natural, whether the visuals explain
the idea, colour/brand fit, the mascot's personality, and whether music and effects suit the tone.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .scenes import LEAD

HEADLINE_WORDS = 8
ITEM_WORDS = 6


def _first_content(sc: dict) -> float:
    """When something first lands on the stage in this scene (global seconds)."""
    t, start = sc["t"], sc["start"]
    kind = sc["type"]
    if sc.get("heading"):
        return start + 0.12
    if kind in ("title", "statement", "end"):
        return min(t, start + 0.35)
    if kind == "number":
        return min(t - LEAD, (start + 0.35 if t - start > 0.6 else t + 0.4) if sc.get("label") else t)
    if kind in ("bullets", "flow"):
        return min(it["t"] for it in sc["items"]) - LEAD
    if kind == "compare":
        return min(sc["left"]["t"], sc["right"]["t"]) - LEAD
    return t - LEAD


def _words(s: str | None) -> int:
    return len((s or "").replace("*", "").split())


def _rms_db(x: np.ndarray) -> float:
    return float(20 * np.log10(np.sqrt((x.astype(np.float64) ** 2).mean()) + 1e-9))


def run(proj, tl: dict) -> list[dict]:
    out: list[dict] = []

    def note(area, level, where, msg):
        out.append({"area": area, "level": level, "where": where, "msg": msg})

    scenes = tl["scenes"]
    # ---- layout ----
    for sc in scenes:
        gap = _first_content(sc) - sc["start"]
        if gap > 1.5:
            note("layout", "warn", sc["id"], f"stage is empty for {gap:.1f}s at the start of the scene; show a heading "
                                             "or label first, or cue the main element earlier")
    types = [s["type"] for s in scenes]
    run_len = 1
    for i in range(1, len(types)):
        run_len = run_len + 1 if types[i] == types[i - 1] else 1
        if run_len == 3:
            note("layout", "suggest", scenes[i]["id"], f"three '{types[i]}' scenes in a row; vary the layout")
    if len(types) >= 6:
        top = max(set(types), key=types.count)
        if types.count(top) / len(types) > 0.45:
            note("layout", "suggest", "film", f"{types.count(top)}/{len(types)} scenes are '{top}'; mix in other types")
    # ---- text ----
    for sc in scenes:
        for field in ("title", "text", "heading"):
            if _words(sc.get(field)) > HEADLINE_WORDS:
                note("text", "warn", sc["id"], f"{field} has {_words(sc.get(field))} words (aim for <= {HEADLINE_WORDS})")
        items = sc.get("items", []) + sc.get("left", {}).get("items", []) + sc.get("right", {}).get("items", [])
        long = [it["text"] for it in items if _words(it["text"]) > ITEM_WORDS]
        if long:
            note("text", "suggest", sc["id"], f"long item(s): {long[0]!r}; keep items <= {ITEM_WORDS} words")
        if len(sc.get("items", [])) > 5:
            note("text", "warn", sc["id"], f"{len(sc['items'])} items; split into two scenes")
    # ---- pacing ----
    words = [w for sc in scenes for w in sc["words"]]
    for a, b in zip(words, words[1:]):
        if b[1] - a[2] > 1.5:
            note("pacing", "warn", f"{a[2]:.1f}s", f"{b[1] - a[2]:.1f}s pause in the narration (after '{a[0]}'); "
                                                  "consider trimming the take")
    for sc in scenes:
        d = sc["end"] - sc["start"]
        if d > 20:
            note("pacing", "suggest", sc["id"], f"{d:.0f}s scene; long static scenes lose attention, consider "
                                                "splitting it")
    # ---- sound ----
    ev = tl.get("sfx_events", [])
    if tl["duration"] > 20 and len(ev) / (tl["duration"] / 60) > 8:
        note("sound", "warn", "film", f"{len(ev)} sound effects ({len(ev) / (tl['duration'] / 60):.1f}/min); "
                                      "lower sfx.max_per_minute")
    d = proj.build / "audio"
    if (d / "voice.wav").exists():
        from .media import decode_mono
        sr = 16000
        voice = decode_mono(d / "voice.wav", sr)
        hop = sr // 2
        n = len(voice) // hop
        vdb = np.array([_rms_db(voice[i * hop:(i + 1) * hop]) for i in range(n)])
        speaking = vdb > np.percentile(vdb, 90) - 15
        ref = float(np.median(vdb[speaking])) if speaking.any() else -20.0
        if (d / "sfx.wav").exists() and ev:
            sfx = decode_mono(d / "sfx.wav", sr)
            for e in ev:
                a = int(e["t"] * sr)
                seg = sfx[a: a + int(max(0.2, e.get("duration") or 0.6) * sr)]
                loudest = max((_rms_db(seg[i:i + 1600]) for i in range(0, max(1, len(seg) - 1600), 800)), default=-99)
                if loudest > ref - 4:
                    note("sound", "warn", f"{e['event_t']:.1f}s", f"'{e['id']}' is nearly as loud as the narration "
                                                                   f"({loudest - ref:+.0f} dB); lower its gain")
        if (d / "music.wav").exists():
            music = decode_mono(d / "music.wav", sr)
            m = min(n, len(music) // hop)
            mdb = np.array([_rms_db(music[i * hop:(i + 1) * hop]) for i in range(m)])
            quiet = ~speaking[:m]
            if quiet.sum() >= 2 and float(np.median(mdb[quiet])) > ref - 8:
                note("sound", "suggest", "film", "music is close to the voice level in pauses; lower music.gain_db")
        if (d / "mix.wav").exists():
            mix = decode_mono(d / "mix.wav", sr)
            w3 = sr * 3
            k = len(mix) // w3
            lv = np.array([_rms_db(mix[i * w3:(i + 1) * w3]) for i in range(k)])
            lv = lv[lv > lv.max() - 25] if len(lv) else lv
            if len(lv) >= 4 and np.percentile(lv, 90) - np.percentile(lv, 10) > 6:
                note("sound", "warn", "film", f"loudness varies by {np.percentile(lv, 90) - np.percentile(lv, 10):.0f} dB "
                                              "between parts of the film")
    return out


def print_report(notes: list[dict], log=print) -> None:
    if not notes:
        log("review: no findings (this is not a verdict on quality - watch the film)")
        return
    for n in notes:
        log(f"  {n['level'].upper():<8} {n['area']:<7} {n['where']:<10} {n['msg']}")
    log(f"review: {len(notes)} finding(s) - prompts to look, not failures")


def save(notes: list[dict], path: Path) -> None:
    path.write_text(json.dumps(notes, indent=1))
