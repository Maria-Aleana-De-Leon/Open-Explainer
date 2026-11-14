"""Quality review: heuristics for what technical QA cannot see. Findings are prompts to LOOK, not verdicts.

Checked from the plan and the rendered audio stems:
  layout   - empty stage before a scene's first content; the same layout 3+ times in a row; one layout dominating
  visuals  - no pictures in a longer film; runs of text-only scenes; a short line alone on stage for long;
             diagrams drawn too small for the stage
  motion   - animated diagrams that never move, or freeze for long stretches; steps that crowd too many actions
             into one moment; a camera push over a diagram (it moves every label for no reason)
  text     - headlines or items too long for their size; too many items
  pacing   - long pauses inside the narration; very short or long static scenes
  sound    - SFX density; SFX louder than the voice; music too loud in pauses, barely audible, or competing with
             the voice; loudness drifting through the film
Not checkable automatically (report them as such): whether the motion feels natural, whether the visuals explain
the idea, colour/brand fit, the mascot's personality, and whether music and effects suit the tone.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .scenes import LEAD, regions

HEADLINE_WORDS = 8
ITEM_WORDS = 6
TEXT_ONLY = {"title", "statement", "bullets"}
LONE_LINE_WORDS = 6         # a statement/title this short ...
LONE_LINE_S = 7.0           # ... alone on stage for longer than this
IMAGE_MIN_FILL = 0.35       # an image covering less of the stage than this reads as a thumbnail
MUSIC_TOO_LOUD_DB = -8      # music in pauses closer to the voice than this competes with it
MUSIC_TOO_QUIET_DB = -19    # music in pauses further under the voice than this is barely heard (default is ~-15)
MUSIC_UNDER_SPEECH_DB = -12  # music while the voice speaks should stay at least this far under it
DIAGRAMS = "storyboard-builder: references/diagrams.md"
MOTION = "storyboard-builder: references/motion.md"
FROZEN_S = 6.0              # an animated diagram where nothing changes for longer than this looks frozen
DIAGRAM_MIN_SPAN = 0.6     # a settled diagram narrower AND shorter than this share of its area looks lost
STATIC_DIAGRAM_S = 4.0      # a diagram scene with no steps, longer than this
CROWDED_KINDS = 3           # more kinds of change than this in one step (show + flow + label + ...) is hard to follow
CROWDED_IDS = 8             # more elements than this in one step, even staggered
STEPS_TOO_CLOSE_S = 0.35    # two steps closer than this read as one


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
    # repetition of the same template layout; 'image' and 'diagram' scenes are excluded: every picture is a different
    # layout (and a continued diagram is deliberately one picture)
    PICTURES = ("image", "diagram")
    types = [s["type"] for s in scenes]
    run_len = 1
    for i in range(1, len(types)):
        run_len = run_len + 1 if types[i] == types[i - 1] and types[i] not in PICTURES else 1
        if run_len == 3:
            note("layout", "suggest", scenes[i]["id"], f"three '{types[i]}' scenes in a row; vary the layout")
    templated = [t for t in types if t not in PICTURES]
    if len(types) >= 6 and templated:
        top = max(set(templated), key=templated.count)
        if templated.count(top) / len(types) > 0.45:
            note("layout", "suggest", "film", f"{templated.count(top)}/{len(types)} scenes are '{top}'; mix in other types")
    # ---- visuals ----
    _visuals(proj, tl, scenes, note)
    _motion(proj, scenes, note, (tl["width"], tl["height"]))
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
            quiet, talk = ~speaking[:m], speaking[:m]
            if quiet.sum() >= 2:
                pause_db = float(np.median(mdb[quiet])) - ref
                if pause_db > MUSIC_TOO_LOUD_DB:
                    note("sound", "suggest", "film", "music is close to the voice level in pauses; lower music.gain_db")
                elif pause_db < MUSIC_TOO_QUIET_DB:
                    note("sound", "warn", "film", f"music is barely audible: {-pause_db:.0f} dB under the voice in "
                                                  "pauses (about 14-18 dB sounds right); raise music.gain_db towards "
                                                  "the default -14, or leave music out")
            if talk.sum() >= 2 and float(np.median(mdb[talk])) - ref > MUSIC_UNDER_SPEECH_DB:
                note("sound", "warn", "film", f"music competes with the voice: only "
                                              f"{ref - float(np.median(mdb[talk])):.0f} dB under it while it speaks; "
                                              "raise music.duck_db or lower music.gain_db")
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


def _visuals(proj, tl: dict, scenes: list[dict], note) -> None:
    """Visual storytelling prompts. They never demand a picture: words are sometimes the clearest explanation."""
    if tl["duration"] > 30 and len(scenes) >= 4 and not any(s["type"] in ("image", "diagram") for s in scenes):
        note("visuals", "suggest", "film", "no pictures: every scene is text or cards. If the topic has a mechanism, "
                                           "a structure, a place or a shape, an original diagram usually explains it "
                                           f"better ({DIAGRAMS}); keep text where words are clearest")
    run_start = None
    for i, sc in enumerate(scenes):
        if sc["type"] in TEXT_ONLY:
            run_start = i if run_start is None else run_start
            if i - run_start == 2:
                note("visuals", "suggest", f"{scenes[run_start]['id']}-{sc['id']}",
                     "three text-only scenes in a row; could one be a diagram, a flow, a comparison or a number?")
        else:
            run_start = None
    for sc in scenes:
        line = sc.get("text") if sc["type"] == "statement" else sc.get("title") if sc["type"] == "title" else None
        d = sc["end"] - sc["start"]
        if line is not None and _words(line) <= LONE_LINE_WORDS and not sc.get("subtitle") and d > LONE_LINE_S:
            note("visuals", "suggest", sc["id"], f"a {_words(line)}-word line is alone on stage for {d:.0f}s; add a "
                                                 "supporting visual or give part of the narration to a new scene")
    m = proj.cfg.get("mascot") or {}
    R = regions(tl["width"], tl["height"], m.get("position") if m.get("enabled") else None)
    sw, sh = R.stage[2] - R.stage[0], R.stage[3] - R.stage[1]
    for sc in scenes:
        if sc["type"] != "image":
            continue
        src = Path(sc["image"]) if Path(sc["image"]).is_absolute() else proj.root / sc["image"]
        try:
            from PIL import Image
            with Image.open(src) as im:
                w, h = im.size
        except Exception:  # noqa: BLE001 - a missing/unreadable image is the renderer's error to report
            continue
        box_h = sh - (140 if sc.get("heading") else 0)
        k = min(1.0, sw / w, box_h / h)            # images are scaled down to fit, never up
        fill = (w * k) * (h * k) / (sw * sh)
        if fill < IMAGE_MIN_FILL:
            note("visuals", "warn", sc["id"], f"the image covers only {fill:.0%} of the stage ({w}x{h} px); draw it "
                                              f"at about {sw}x{box_h} px ({DIAGRAMS})")


_ACTIONS = ("show", "hide", "draw", "activate", "deactivate", "done", "error", "dim", "undim", "label", "move")


def _motion(proj, scenes: list[dict], note, tl_size) -> None:
    """Animated-diagram prompts: motion should explain, on the words, one thing at a time."""
    from .styles import get as style
    st = style(proj.cfg["style"], proj.cfg.get("accent"))
    default_cam = proj.cfg.get("camera") or st["camera"]
    m = proj.cfg.get("mascot") or {}
    R = regions(tl_size[0], tl_size[1], m.get("position") if m.get("enabled") else None)
    for sc in scenes:
        if sc["type"] != "diagram":
            continue
        d, steps = sc["end"] - sc["start"], sc.get("steps", [])
        try:
            from .scenes import build_diagram
            dia = build_diagram(sc, st, R, proj.root).els[-1].draw.__self__
            x0, y0, x1, y1 = dia.extent()
            ax0, ay0, ax1, ay1 = dia.area
            fw, fh = (x1 - x0) / (ax1 - ax0), (y1 - y0) / (ay1 - ay0)
            cx, cy = ((x0 + x1) / 2 - ax0) / (ax1 - ax0), ((y0 + y1) / 2 - ay0) / (ay1 - ay0)
            if fw < DIAGRAM_MIN_SPAN and fh < DIAGRAM_MIN_SPAN:
                note("motion", "warn", sc["id"], f"the diagram uses only {fw:.0%} of the width and {fh:.0%} of the "
                                                 "height of its area: spread the nodes out (x, y 0..1 cover the "
                                                 "whole stage under the heading) or use a layout")
            elif abs(cx - 0.5) > 0.2 or abs(cy - 0.5) > 0.2:
                note("motion", "suggest", sc["id"], "the diagram sits off-centre (centre at "
                                                    f"x {cx:.2f}, y {cy:.2f} of its area); centre it unless the "
                                                    "space is kept for something that arrives later")
            for a, b in dia.crowded():
                note("motion", "warn", sc["id"], f"nodes '{a}' and '{b}' touch or overlap; move them apart, shorten "
                                                 "their labels, or use a layout")
        except Exception:  # noqa: BLE001 - a broken diagram is the renderer's error to report
            pass
        if (sc.get("camera") or default_cam) == "push":
            note("motion", "suggest", sc["id"], "camera push over an animated diagram: it moves every label and line "
                                                "while the steps already carry the motion; use \"camera\": \"still\"")
        if not steps:
            if d > STATIC_DIAGRAM_S and not sc.get("continue"):
                note("motion", "warn", sc["id"], f"a static diagram for {d:.0f}s: reveal it in steps on the words "
                                                 f"that introduce each part ({MOTION})")
            continue
        times = sorted(s["t"] for s in steps)
        marks = [sc["start"]] + times + [sc["end"]]
        for a, b in zip(marks, marks[1:]):
            busy_until = a + 1.5 if a > sc["start"] else max(sc["t"], sc["start"]) + 0.5   # what a step sets moving
            if b - busy_until > FROZEN_S:
                note("motion", "suggest", sc["id"], f"nothing changes for {b - busy_until:.0f}s "
                                                    f"({busy_until - sc['start']:.1f}-{b - sc['start']:.1f}s into the "
                                                    "scene): cue a step on a phrase in that stretch, or split the scene")
        for k, (a, b) in enumerate(zip(times, times[1:])):
            if b - a < STEPS_TOO_CLOSE_S:
                note("motion", "suggest", sc["id"], f"two steps {1000 * (b - a):.0f} ms apart read as one moment: merge "
                                                    "them, or cue the second on a later word")
        for k, s in enumerate(steps):
            flows = s["flow"] if isinstance(s.get("flow"), list) else [s["flow"]] if s.get("flow") else []
            kinds = sum(1 for a in _ACTIONS if s.get(a)) + len(flows)
            ids = sum(len(s.get(a) or []) for a in _ACTIONS)
            if kinds > CROWDED_KINDS or ids > CROWDED_IDS:
                note("motion", "suggest", f"{sc['id']} steps[{k}]", f"{kinds} kinds of change ({ids} elements) start "
                                                                    "at once; spread them over the words that "
                                                                    "introduce each one")


def print_report(notes: list[dict], log=print) -> None:
    if not notes:
        log("review: no findings (this is not a verdict on quality - watch the film)")
        return
    for n in notes:
        log(f"  {n['level'].upper():<8} {n['area']:<7} {n['where']:<10} {n['msg']}")
    log(f"review: {len(notes)} finding(s) - prompts to look, not failures")


def save(notes: list[dict], path: Path) -> None:
    path.write_text(json.dumps(notes, indent=1))
