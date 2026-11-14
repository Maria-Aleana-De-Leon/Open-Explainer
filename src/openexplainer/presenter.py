"""Presenter motion (spec S4): plans the mascot's per-frame state and draws it.

Planning (whole film, once):
  - mouth shapes from mouthtrack (24 Hz), mapped to the shapes the mascot has
  - pose/expression changes from storyboard cues, with optional "for" auto-return
  - emphasis nods on stressed words: words that follow a pause, or among the loudest tenth; >= 0.8 s apart
  - blinks at seeded pseudo-random intervals (2.5-6 s, occasional double blink), kept clear of state changes
Drawing (per frame, in the scene worker):
  - feet planted; idle sway from two slow sines of unrelated periods; nod = a short dip that decays
  - state changes cross-fade over XFADE seconds; the film opens with the presenter rising into place
  - a soft projected shadow made from the character's own silhouette
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from .mascot import compose, load_info
from .mouthtrack import SHAPES, track, word_coverage

RATE = 24.0
XFADE = 0.08
BLINK = 0.12
NOD_UP, NOD_DECAY, NOD_PX, NOD_GAP = 0.08, 0.22, 7.0, 0.8


def _stressed(words: list[tuple[float, float]], x: np.ndarray, sr: int = 16000) -> list[float]:
    if not words:
        return []
    loud = []
    for s, e in words:
        seg = x[int(s * sr): max(int(s * sr) + 1, int(e * sr))]
        loud.append(float(np.sqrt((seg ** 2).mean() + 1e-12)))
    cut = np.percentile(loud, 90)
    out, prev_e = [], -10.0
    for (s, e), l in zip(words, loud):
        if s - prev_e >= 0.25 or l >= cut:
            out.append(s)
        prev_e = e
    # never two nods closer than NOD_GAP
    kept = []
    for t in out:
        if not kept or t - kept[-1] >= NOD_GAP:
            kept.append(t)
    return kept


def _nod(t: float, onsets: list[float]) -> float:
    v = 0.0
    for o in onsets:
        d = t - o
        if d < 0:
            break
        if d < NOD_UP:
            v = max(v, d / NOD_UP)
        elif d < NOD_UP + 5 * NOD_DECAY:
            v = max(v, math.exp(-(d - NOD_UP) / NOD_DECAY))
    return v


def _blinks(seed: str, total: float, avoid: list[float]) -> list[float]:
    rnd = random.Random(int(hashlib.sha256(seed.encode()).hexdigest()[:12], 16))
    out, t = [], rnd.uniform(1.2, 2.5)
    while t < total - 0.5:
        if all(abs(t - a) > 0.25 and abs(t + BLINK - a) > 0.25 for a in avoid):
            out.append(round(t, 3))
            if rnd.random() < 0.15:
                out.append(round(t + BLINK + 0.12, 3))
        t += rnd.uniform(2.5, 6.0)
    return out


def plan(proj, tl: dict, log=print):
    from .errors import ValidationError
    from .media import decode_mono

    m = proj.cfg["mascot"]
    mdir = proj.path(m.get("dir") or "mascot")
    info, bdir = load_info(mdir)
    x = decode_mono(proj.path(proj.cfg["narration"]["audio"]))
    shapes = track(x, 16000, RATE)
    words = [(w[1], w[2]) for sc in tl["scenes"] for w in sc["words"]]
    talk, rest = word_coverage(shapes, words, RATE)
    log(f"mascot: mouth track - {talk:.0%} of words with an open mouth, {rest:.0%} of long pauses at rest")
    names = list(info["states"])
    problems, changes = [], [(0.0, "neutral")]
    for sc in tl["scenes"]:
        if sc.get("mascot") is False:
            continue
        for act in sc.get("mascot") or []:
            pose, expr = act.get("pose"), act.get("expression")
            cands = (["neutral"] if pose == "neutral" and not expr else
                     ([f"pose-{pose}-{expr}"] if pose and expr else []) + ([f"pose-{pose}"] if pose else [])
                     + ([f"expr-{expr}"] if expr else []))
            want = next((c for c in cands if c in info["states"]), None)
            if not want:
                # a missing gesture must not stop a film: the presenter stays as it is and the user is told which
                # image would add it (prompt 3 for expressions, prompt 5 for poses)
                need = f"pose-{pose}.png" if pose else f"expr-{expr}.png"
                log(f"  note: scene {sc['id']}: the mascot has no {need}; it keeps its current pose there "
                    f"(add {need} to the mascot folder to use it)")
                continue
            changes.append((act["t"], want))
            if act.get("for"):
                changes.append((act["t"] + act["for"], "neutral"))
    if problems:
        raise ValidationError("mascot actions", problems)
    changes.sort(key=lambda c: c[0])
    ends = [c[0] for c in changes[1:]] + [tl["duration"]]
    for (t0, nm), t1 in zip(changes, ends):
        if not info["states"][nm]["talk"]:
            spoken = sum(max(0.0, min(e, t1) - max(s, t0)) for s, e in words)
            if spoken > 2.0:
                log(f"  warning: '{nm}' has no lip sync but is held over {spoken:.1f}s of speech from {t0:.1f}s; "
                    "add \"for\": 1.5 to that action or switch back to a talking pose")
    swaps = [t for t, _ in changes[1:]]
    speech_end = words[-1][1] if words else 0.0
    blinks = _blinks(proj.cfg["title"], tl["duration"], swaps)
    nods = _stressed(words, x)
    log(f"mascot: {len(swaps)} pose/expression change(s), {len(blinks)} blinks, {len(nods)} emphasis nods")
    (proj.build / "mascot-check.json").write_text(json.dumps(
        {"talk_share": round(talk, 3), "rest_share": round(rest, 3), "changes": changes, "blinks": blinks,
         "nods": nods}, indent=1))

    def state_at(t):
        cur, prev, since = "neutral", "neutral", 0.0
        for ct, nm in changes:
            if ct <= t:
                prev, cur, since = cur, nm, ct
        return cur, prev, since

    def for_scene(sc: dict, fps: int):
        if sc.get("mascot") is False:
            return None
        f0 = round(sc["start"] * fps)
        n = round(sc["end"] * fps) - f0
        frames = []
        for f in range(f0, f0 + n):
            t = f / fps
            cur, prev, since = state_at(t)
            age = t - since if since > 0 else 99.0
            i = int(t * RATE)
            sh = shapes[i] if i < len(shapes) and t <= speech_end + 0.15 else "rest"   # at rest once the narration ends
            bl = any(b <= t < b + BLINK for b in blinks)
            nod = int(round(_nod(t, [o for o in nods if o <= t and t - o < 1.5]) * 100))
            frames.append([names.index(cur), names.index(prev), round(min(age, 9.0), 3), SHAPES.index(sh), int(bl), nod])
        return {"dir": str(bdir), "scale": m["scale"], "states": names, "start": sc["start"], "fps": fps,
                "frames": frames, "first": f0 == 0, "mirror": m["position"] in ("right", "bottom-right")}

    return for_scene


class Rig:
    def __init__(self, job: dict, R):
        self.job = job
        self.root = Path(job["dir"])
        self.info = json.loads((self.root / "mascot.json").read_text())
        self.k = R.mascot_h * job["scale"] / self.info["char_height"]
        self.feet = R.mascot_feet
        self.cache: dict = {}
        self.patches: dict = {}
        self.bases = {n: Image.open(self.root / st["file"]).convert("RGBA") for n, st in self.info["states"].items()}
        cw, ch = self.info["canvas"]
        self.size = (max(1, round(cw * self.k)), max(1, round(ch * self.k)))
        fx, fy = self.info["feet"]
        self.anchor = (self.size[0] - fx * self.k if job["mirror"] else fx * self.k, fy * self.k)
        sil = self.bases["neutral"].getchannel("A").resize(self.size, Image.BILINEAR)
        sh = sil.resize((self.size[0], max(4, int(self.size[1] * 0.10))), Image.BILINEAR).filter(ImageFilter.GaussianBlur(9))
        self.shadow = Image.new("RGBA", sh.size, (0, 0, 0, 0))
        self.shadow.putalpha(sh.point(lambda v: int(v * 0.22)))

    @classmethod
    def from_job(cls, job: dict, R) -> "Rig":
        return cls(job, R)

    def sprite(self, si: int, shape: str, bl: int) -> Image.Image:
        key = (si, shape, bl)
        if key not in self.cache:
            name = self.job["states"][si]
            im = compose(self.bases[name], self.info, self.root, name, shape, bool(bl), self.patches)
            im = im.resize(self.size, Image.LANCZOS)
            if self.job["mirror"]:
                im = im.transpose(Image.FLIP_LEFT_RIGHT)
            if len(self.cache) > 240:
                self.cache.clear()
            self.cache[key] = im
        return self.cache[key]

    def draw(self, canvas: Image.Image, t: float) -> None:
        from .scenes import ease_out_cubic, paste
        fr = self.job["frames"]
        if not fr:
            return
        i = max(0, min(len(fr) - 1, round((t - self.job["start"]) * self.job["fps"])))
        cur, prev, age, shi, bl, nod = fr[i]
        shape = SHAPES[shi]
        x = self.feet[0] - self.anchor[0] + 2.5 * math.sin(2 * math.pi * t / 4.1) + 1.2 * math.sin(2 * math.pi * t / 2.3 + 1.0)
        y = self.feet[1] - self.anchor[1] + 1.5 * math.sin(2 * math.pi * t / 3.3) + NOD_PX * nod / 100
        if self.job["first"] and t < 0.6:
            y += (1 - ease_out_cubic(t / 0.6)) * 160
        paste(canvas, self.shadow, self.feet[0] - self.shadow.width / 2, self.feet[1] - self.shadow.height * 0.6)
        if age < XFADE and prev != cur:      # dissolve the new state over the fully drawn old one (never see-through)
            paste(canvas, self.sprite(prev, shape, bl), x, y)
            paste(canvas, self.sprite(cur, shape, bl), x, y, age / XFADE)
        else:
            paste(canvas, self.sprite(cur, shape, bl), x, y)
