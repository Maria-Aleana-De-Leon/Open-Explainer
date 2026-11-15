"""Align the storyboard's narration text to the word timings and resolve every cue to a global time.

Nobody types timestamps. Each scene carries the narration it covers ("say"); each animated element names a phrase
from that text ("at"). This module:
  1. aligns script tokens to transcript tokens (difflib; unmatched tokens are interpolated),
  2. cuts scenes inside the pause between paragraphs, on whole frames, so scene lengths always sum to the film,
  3. resolves every "at" (phrase or scene-relative seconds) to global seconds,
  4. reports problems (missing phrases, scenes that do not match the recording) all at once.
"""
from __future__ import annotations

import copy
import re
from difflib import SequenceMatcher

from .config import Project
from .errors import OexError, ValidationError
from .words import Word, tokens, word_key

MIN_SCENE = 0.8      # seconds; shorter scenes are an authoring error
LEAD_MAX = 0.45      # a new scene appears at most this long before its first word
MATCH_MIN = 0.3      # per-scene share of narration words that must be found in the recording


class Aligner:
    """raw=False: tokens for cue finding (number words merged). raw=True: one key per written word of the script,
    so captions can show the script's own spelling with the recording's timing."""

    def __init__(self, scenes: list[dict], words: list[Word], raw: bool = False):
        self.words = words
        self.script: list[str] = []
        self.owner: list[int] = []
        self.raw: list[str] = []
        for i, s in enumerate(scenes):
            if raw:
                ws = [w for w in s["say"].split() if word_key(w)]
                t = [word_key(w) for w in ws]
                self.raw += ws
            else:
                t = tokens(s["say"])
            self.script += t
            self.owner += [i] * len(t)
        trans = [word_key(w.w) for w in words]
        self.match: list[int | None] = [None] * len(self.script)
        sm = SequenceMatcher(None, self.script, trans, autojunk=False)
        for b in sm.get_matching_blocks():
            for k in range(b.size):
                self.match[b.a + k] = b.b + k
        self.scene_range = {}
        for p, i in enumerate(self.owner):
            a, _ = self.scene_range.get(i, (p, p))
            self.scene_range[i] = (a, p + 1)

    def coverage(self, i: int) -> float:
        a, b = self.scene_range.get(i, (0, 0))
        return sum(self.match[p] is not None for p in range(a, b)) / max(1, b - a)

    def _anchor(self, p: int, step: int) -> int | None:
        while 0 <= p < len(self.match):
            if self.match[p] is not None:
                return p
            p += step
        return None

    def start(self, p: int) -> float:
        """Start time of script token p (interpolated if the recogniser missed it)."""
        if self.match[p] is not None:
            return self.words[self.match[p]].s
        a, b = self._anchor(p, -1), self._anchor(p, +1)
        if a is None and b is None:
            return 0.0
        if a is None:
            return max(0.0, self.words[self.match[b]].s - 0.25 * (b - p))
        if b is None:
            return self.words[self.match[a]].e + 0.25 * (p - a - 1)
        ta, tb = self.words[self.match[a]].e, self.words[self.match[b]].s
        return ta + (tb - ta) * (p - a) / (b - a)

    def end(self, p: int) -> float:
        if self.match[p] is not None:
            return self.words[self.match[p]].e
        return self.start(p) + 0.25

    def find(self, i: int, phrase: str) -> int | None:
        """Script position of `phrase` inside scene i ("phrase#2" = second occurrence)."""
        m = re.fullmatch(r"(.*?)#(\d+)", phrase)
        nth = int(m.group(2)) if m else 1
        want = tokens(m.group(1) if m else phrase)
        if not want:
            return None
        a, b = self.scene_range[i]
        seen = 0
        for p in range(a, b - len(want) + 1):
            if self.script[p:p + len(want)] == want:
                seen += 1
                if seen == nth:
                    return p
        return None


def _items(raw) -> list[dict]:
    return [{"text": it} if isinstance(it, str) else dict(it) for it in (raw or [])]


def build(proj: Project, words: list[Word], audio_duration: float) -> dict:
    scenes = proj.storyboard["scenes"]
    fps = proj.fps
    al = Aligner(scenes, words)
    raw_al = Aligner(scenes, words, raw=True)
    problems, warnings = [], []

    total_cov = sum(m is not None for m in al.match) / max(1, len(al.match))
    if total_cov < 0.5:
        raise OexError(f"only {total_cov:.0%} of the storyboard narration was found in the recording",
                       "the take does not match the storyboard 'say' text: re-transcribe the right take, or update "
                       "each scene's 'say' to what was actually recorded")
    for i, s in enumerate(scenes):
        if i not in al.scene_range:
            problems.append(f"scene {s['id']}: 'say' has no words")
            continue
        cov = al.coverage(i)
        if cov < MATCH_MIN:
            problems.append(f"scene {s['id']}: only {cov:.0%} of its 'say' text was heard in the recording")
        elif cov < 0.8:
            warnings.append(f"scene {s['id']}: {cov:.0%} of its words matched the transcript; times are interpolated")
    if problems:
        raise ValidationError("storyboard vs recording", problems)

    # ---- scene cuts, in seconds, then snapped to frames ----
    first = [al.start(al.scene_range[i][0]) for i in range(len(scenes))]
    last = [al.end(al.scene_range[i][1] - 1) for i in range(len(scenes))]
    cuts = [0.0]
    for i in range(1, len(scenes)):
        gap_mid = (last[i - 1] + first[i]) / 2
        cut = max(gap_mid, first[i] - LEAD_MAX)
        cut = min(cut, first[i] - 0.04) if first[i] - 0.04 > last[i - 1] else gap_mid
        cuts.append(cut)
    end = max(audio_duration, last[-1]) + proj.cfg["tail"]
    frames_at = [round(c * fps) for c in cuts] + [round(end * fps)]
    out_scenes = []
    for i, s in enumerate(scenes):
        f0, f1 = frames_at[i], frames_at[i + 1]
        start, stop = f0 / fps, f1 / fps
        if stop - start < MIN_SCENE:
            problems.append(f"scene {s['id']}: only {stop - start:.2f}s long (min {MIN_SCENE}s); merge it with a "
                            "neighbour or give it more narration")
        r = copy.deepcopy(s)
        r.update(start=round(start, 4), end=round(stop, 4), start_frame=f0, frames=f1 - f0,
                 say_start=round(first[i], 3), say_end=round(last[i], 3))

        def resolve(at, where: str, default: float | None = None):
            if at is None:
                return default
            if isinstance(at, (int, float)):
                if not 0 <= at <= stop - start:
                    problems.append(f"scene {s['id']} {where}: at={at}s is outside the scene (0-{stop - start:.2f}s)")
                return round(start + float(at), 3)
            p = al.find(i, at)
            if p is None:
                problems.append(f"scene {s['id']} {where}: cue phrase \"{at}\" is not in this scene's 'say' text")
                return default
            if al.match[p] is None:
                warnings.append(f"scene {s['id']} {where}: \"{at}\" was not recognised in the audio; time interpolated")
            return round(al.start(p), 3)

        span0, span1 = first[i], max(first[i] + 0.5, last[i] - 0.3)
        if "steps" in r:                                       # diagram steps: on their words, else spread evenly
            steps = [dict(s) for s in r["steps"]]
            for k, s in enumerate(steps):
                s["t"] = resolve(s.pop("at", None), f"steps[{k}]", round(span0 + (span1 - span0) * k / max(1, len(steps)), 3))
            r["steps"] = steps
        for key in ("items",):
            if key in r:
                its = _items(r[key])
                n = len(its)
                for k, it in enumerate(its):
                    even = span0 + (span1 - span0) * k / max(1, n)
                    it["t"] = resolve(it.pop("at", None), f"{key}[{k}]", round(even, 3))
                r[key] = its
        for side in ("left", "right"):
            if side in r:
                r[side] = dict(r[side])
                r[side]["t"] = resolve(r[side].pop("at", None), side, round(span0 if side == "left" else
                                                                           (span0 + span1) / 2, 3))
                r[side]["items"] = _items(r[side].get("items"))
        r["t"] = resolve(r.pop("at", None), "at", round(span0, 3))
        if r.get("emphasis"):
            r["emphasis_t"] = resolve(r["emphasis"], "emphasis", None)
        if isinstance(r.get("mascot"), list):
            for k, act in enumerate(r["mascot"]):
                act["t"] = resolve(act.pop("at"), f"mascot[{k}]", round(start, 3))
        for k, cue in enumerate(r.get("sfx", [])):
            cue["t"] = resolve(cue.pop("at"), f"sfx[{k}]", None)
        r["words"] = [[w.w, w.s, w.e] for w in words if start <= w.s < stop]
        if proj.cfg["captions"]["source"] == "script":
            a, b = raw_al.scene_range.get(i, (0, 0))
            r["caption_words"] = [[raw_al.raw[p], round(raw_al.start(p), 3), round(raw_al.end(p), 3)]
                                  for p in range(a, b)]
        else:
            r["caption_words"] = r["words"]
        out_scenes.append(r)
    _link_continued(out_scenes, problems)
    if problems:
        raise ValidationError("storyboard cues", problems)
    w, h = proj.size
    return {"fps": fps, "width": w, "height": h, "duration": round(frames_at[-1] / fps, 4),
            "frames": frames_at[-1], "audio_duration": round(audio_duration, 3),
            "scenes": out_scenes, "warnings": warnings}


def _link_continued(scenes: list, problems: list) -> None:
    """A diagram scene with `"continue": true` carries on from the diagram before it: shared nodes, connectors and
    groups stay where they are (moving if their position changed), the cut between the two scenes is invisible
    (no exit fade, no entrance transition, a still camera) and an unchanged heading stays put."""
    for i, sc in enumerate(scenes):
        if not sc.get("continue"):
            continue
        prev = scenes[i - 1] if i else None
        if sc.get("type") != "diagram" or not prev or prev.get("type") != "diagram":
            problems.append(f"scene {sc['id']}: \"continue\" needs a diagram scene right after another diagram scene")
            continue
        if sc.get("look", "flat") != prev.get("look", "flat"):
            problems.append(f"scene {sc['id']}: \"continue\" needs the same \"look\" as the scene before it")
            continue
        prev["hold_exit"] = True
        prev["camera"] = sc["camera"] = "still"
        sc["transition"] = "none"
        sc["prev"] = {k: v for k, v in prev.items() if k not in ("words", "caption_words", "sfx", "mascot")}
