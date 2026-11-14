"""Scene templates: a resolved scene dict + style + layout regions -> a frame-at-time-t drawing function.

Every visual change is a pure function of the global time t, so any frame can be rendered independently,
scenes can be rendered in parallel, and re-rendering is bit-for-bit reproducible.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFilter

from . import text as T
from .errors import OexError
from .styles import rgb

LEAD = 0.18      # arrivals start this long before their cue word and land on it
ENTER = 0.5      # arrival duration
EXIT = 0.28      # content fades out over the last EXIT seconds of a scene (not the last scene)


# ---------------- easing ----------------

def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ease_out_cubic(p):
    return 1 - (1 - p) ** 3


def ease_out_back(p, s=1.4):
    p -= 1
    return 1 + (s + 1) * p ** 3 + s * p ** 2


def ease_in_out(p):
    return 0.5 - 0.5 * math.cos(math.pi * p)


# ---------------- compositing helpers ----------------

_fade_cache: dict = {}


def faded(sprite: Image.Image, opacity: float) -> Image.Image:
    level = int(round(clamp(opacity) * 32))
    if level >= 32:
        return sprite
    key = (id(sprite), level)
    hit = _fade_cache.get(key)
    if hit is None or hit[0] is not sprite:
        im = sprite.copy()
        im.putalpha(sprite.getchannel("A").point(lambda v, k=level / 32: int(v * k)))
        if len(_fade_cache) > 4000:
            _fade_cache.clear()
        _fade_cache[key] = hit = (sprite, im)
    return hit[1]


def paste(canvas: Image.Image, sprite: Image.Image, x: float, y: float, opacity: float = 1.0) -> None:
    if opacity <= 0.004:
        return
    s = faded(sprite, opacity)
    x, y = int(round(x)), int(round(y))
    W, H = canvas.size
    x0, y0 = max(0, -x), max(0, -y)
    x1, y1 = min(s.width, W - x), min(s.height, H - y)
    if x1 <= x0 or y1 <= y0:
        return
    if (x0, y0, x1, y1) != (0, 0, s.width, s.height):
        s = s.crop((x0, y0, x1, y1))
    canvas.alpha_composite(s, (x + x0, y + y0))


def card(w: int, h: int, radius: int, fill: str, shadow: bool = True, outline: str | None = None) -> Image.Image:
    """Antialiased rounded card (drawn at 2x), with a soft drop shadow."""
    pad = 30 if shadow else 0
    big = Image.new("RGBA", ((w + pad * 2) * 2, (h + pad * 2) * 2), (0, 0, 0, 0))
    if shadow:
        sh = Image.new("RGBA", big.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle([pad * 2, pad * 2 + 14, (pad + w) * 2, (pad + h) * 2 + 14],
                                             radius * 2, fill=(0, 0, 0, 46))
        big = Image.alpha_composite(big, sh.filter(ImageFilter.GaussianBlur(22)))
    d = ImageDraw.Draw(big)
    d.rounded_rectangle([pad * 2, pad * 2, (pad + w) * 2, (pad + h) * 2], radius * 2, fill=rgb(fill) + (255,),
                        outline=(rgb(outline) + (255,)) if outline else None, width=6 if outline else 0)
    out = big.resize((w + pad * 2, h + pad * 2), Image.LANCZOS)
    out.info["pad"] = pad
    return out


def circle(d: int, fill: str) -> Image.Image:
    big = Image.new("RGBA", (d * 3, d * 3), (0, 0, 0, 0))
    ImageDraw.Draw(big).ellipse([0, 0, d * 3 - 1, d * 3 - 1], fill=rgb(fill) + (255,))
    return big.resize((d, d), Image.LANCZOS)


# ---------------- regions ----------------

@dataclass
class Regions:
    W: int
    H: int
    stage: tuple[int, int, int, int]
    captions: tuple[int, int, int, int]
    mascot_feet: tuple[int, int]
    mascot_h: int
    portrait: bool


def regions(W: int, H: int, mascot: str | None) -> Regions:
    portrait = H > W
    if not portrait:
        if mascot in ("left", "bottom-left"):
            stage = (640, 110, W - 110, H - 230)
            feet = (330, H - 30)
        elif mascot in ("right", "bottom-right"):
            stage = (110, 110, W - 640, H - 230)
            feet = (W - 330, H - 30)
        else:
            stage = (170, 120, W - 170, H - 230)
            feet = (W // 2, H + 999)
        cap = (stage[0], H - 200, stage[2], H - 70)
        return Regions(W, H, stage, cap, feet, 640, False)
    # bottom ~250 px stay clear for platform UI (captions/handles on TikTok, Reels, Shorts)
    if mascot:
        stage = (80, 190, W - 80, 995)          # >= 50 px clear of the caption band
        cap = (60, 1045, W - 60, 1205)
        # a larger presenter, set in from the edge, fills the lower third instead of hiding in its corner;
        # head top ~ y 1250, just under the caption band; feet clear of the platform UI at the very bottom
        feet = (380 if mascot in ("left", "bottom-left") else W - 380, H - 70)
        return Regions(W, H, stage, cap, feet, 600, True)
    stage = (80, 220, W - 80, 1360)
    cap = (60, 1420, W - 60, 1580)
    return Regions(W, H, stage, cap, (W // 2, H + 999), 620, True)


# ---------------- elements ----------------

@dataclass
class El:
    sprite: Image.Image | None
    x: float
    y: float
    t: float                      # global cue time the element lands on
    anim: str = "rise"            # rise | pop | slide | none
    dur: float = ENTER
    draw: Callable | None = None  # custom drawer(canvas, t, progress)
    z: int = 0

    def render(self, canvas: Image.Image, t: float) -> None:
        p = clamp((t - (self.t - LEAD)) / self.dur)
        if p <= 0:
            return
        if self.draw is not None:
            self.draw(canvas, t, p)
            return
        e = ease_out_cubic(p)
        if self.anim == "pop":
            k = max(0.01, 0.82 + 0.18 * ease_out_back(p))
            s = self.sprite
            if abs(k - 1) > 0.004:
                s = s.resize((max(1, int(s.width * k)), max(1, int(s.height * k))), Image.BILINEAR)
            paste(canvas, s, self.x + (self.sprite.width - s.width) / 2, self.y + (self.sprite.height - s.height) / 2,
                  min(1.0, p * 2.2))
        elif self.anim == "slide":
            paste(canvas, self.sprite, self.x + 70 * (1 - e), self.y, e)
        elif self.anim == "none":
            paste(canvas, self.sprite, self.x, self.y, 1.0)
        else:
            paste(canvas, self.sprite, self.x, self.y + 46 * (1 - e), e)


@dataclass
class Built:
    els: list[El] = field(default_factory=list)


# ---------------- templates ----------------

def _center_x(R: Regions, w: int) -> float:
    return (R.stage[0] + R.stage[2]) / 2 - w / 2


def _heading(sc: dict, st: dict, R: Regions, b: Built, y: int) -> int:
    if not sc.get("heading"):
        return y
    sw = R.stage[2] - R.stage[0]
    sp, lay = T.sprite(sc["heading"], "bold", sw, 220, 76 if not R.portrait else 72, st["ink"], st["accent"])
    b.els.append(El(sp, R.stage[0], y, sc["start"] + 0.12, "rise"))
    return y + sp.height + 36


def build_title(sc, st, R, root):
    b = Built()
    sw, sh = R.stage[2] - R.stage[0], R.stage[3] - R.stage[1]
    t_sp, t_lay = T.sprite(sc["title"], "bold", sw, int(sh * 0.5), 124 if not R.portrait else 104, st["ink"],
                           st["accent"], align="center")
    s_sp = None
    if sc.get("subtitle"):
        s_sp, _ = T.sprite(sc["subtitle"], "medium", int(sw * 0.9), int(sh * 0.3), 50, st["muted"], st["accent"],
                           align="center")
    total = t_sp.height + 50 + (s_sp.height if s_sp else 0)
    y_title = (R.stage[1] + R.stage[3]) / 2 - total / 2
    t0 = min(sc["t"], sc["start"] + 0.35)
    if sc.get("emphasis_t"):
        _highlight(b, st, t_lay, _center_x(R, t_sp.width), y_title, sc["emphasis_t"], t0)
    b.els.append(El(t_sp, _center_x(R, t_sp.width), y_title, t0, "rise"))
    below = y_title + t_sp.height + 12
    if not sc.get("emphasis_t"):    # the accent bar only when the emphasis highlight does not mark the title
        bar_w = 180

        def bar(canvas, t, p, cx=(R.stage[0] + R.stage[2]) / 2, bar_y=below):
            e = ease_out_cubic(clamp((t - t0 - 0.15) / 0.5))
            if e > 0:
                w = int(bar_w * e)
                ImageDraw.Draw(canvas).rounded_rectangle([cx - w / 2, bar_y, cx + w / 2, bar_y + 10], 5,
                                                         fill=rgb(st["accent"]))
        b.els.append(El(None, 0, 0, t0, draw=bar, dur=0.01))
    if s_sp:
        b.els.append(El(s_sp, _center_x(R, s_sp.width), below + 28, t0 + 0.35, "rise"))
    return b


def build_bullets(sc, st, R, root):
    b = Built()
    y = _heading(sc, st, R, b, R.stage[1])
    items = sc["items"]
    sw = R.stage[2] - R.stage[0]
    avail = R.stage[3] - y
    n = len(items)
    row_h = min(170, avail // max(1, n))
    size = 54 if not R.portrait else 58
    dot = 64
    y += max(0, (avail - row_h * n) * 0.4)  # sit the list in the stage, slightly above centre
    for k, it in enumerate(items):
        ry = y + k * row_h
        num = card(dot, dot, dot // 2, st["accent"], shadow=False)
        nd = ImageDraw.Draw(num)
        f = T.font("bold", 30)
        label = str(k + 1)
        nd.text((dot / 2, dot / 2), label, font=f, fill=rgb(st["bg"]), anchor="mm")
        tsp, _ = T.sprite(it["text"], "medium", sw - dot - 40, row_h - 16, size, st["ink"], st["accent"], min_size=26)
        cy = ry + row_h / 2
        b.els.append(El(num, R.stage[0], cy - dot / 2, it["t"], "pop"))
        b.els.append(El(tsp, R.stage[0] + dot + 32, cy - tsp.height / 2, it["t"] + 0.05, "slide"))
    return b


def build_statement(sc, st, R, root):
    b = Built()
    sw, sh = R.stage[2] - R.stage[0], R.stage[3] - R.stage[1]
    txt = sc["text"]
    sp, lay = T.sprite(txt, "bold", sw, sh, 96 if not R.portrait else 92, st["ink"], st["accent"], align="center")
    x, y = _center_x(R, sp.width), (R.stage[1] + R.stage[3]) / 2 - sp.height / 2
    t0 = min(sc["t"], sc["start"] + 0.35)
    _highlight(b, st, lay, x, y, sc.get("emphasis_t") or (t0 + 0.7), t0)
    b.els.append(El(sp, x, y, t0, "rise"))
    return b


def _highlight(b: Built, st: dict, lay, x: float, y: float, t_emph: float, t_el: float) -> None:
    """A marker that sweeps in under the *accent* text of a text sprite at x, y, on the emphasis word: one
    continuous bar per line of accented text, below the letters (see text.accent_bars)."""
    bars = T.accent_bars(lay)

    def marker(canvas, t, p):
        e = ease_out_cubic(clamp((t - t_emph) / 0.45))
        if e <= 0 or not bars:
            return
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for x0, y0, x1, y1 in bars:
            r = min(8, (y1 - y0) / 2)
            d.rounded_rectangle([x + x0, y + y0, x + x0 + max(2 * r, (x1 - x0) * e), y + y1], r,
                                fill=rgb(st["marker"]) + (170,))   # per-style colour
        canvas.alpha_composite(layer)
    b.els.append(El(None, 0, 0, t_el, draw=marker, dur=0.01, z=-1))


_NUM = re.compile(r"^(\D*?)(\d[\d,]*(?:\.\d+)?)(.*)$")


def build_number(sc, st, R, root):
    b = Built()
    sw, sh = R.stage[2] - R.stage[0], R.stage[3] - R.stage[1]
    val = sc["value"]
    lay = T.layout(val, "bold", sw, int(sh * 0.5), 220 if not R.portrait else 190, align="center", max_lines=2)
    f = T.font("bold", lay.size)
    m = _NUM.match(val)
    lbl = None
    if sc.get("label"):
        lbl, _ = T.sprite(sc["label"], "medium", int(sw * 0.85), int(sh * 0.3), 56, st["muted"], st["accent"],
                          align="center")
    total = lay.height + (lbl.height + 30 if lbl else 0)
    y = (R.stage[1] + R.stage[3]) / 2 - total / 2
    cx = (R.stage[0] + R.stage[2]) / 2
    t0 = sc["t"]

    def number(canvas, t, p):
        e = ease_out_cubic(p)
        # count up only a single plain number ("300 billion", "0.07 s"); a range or several numbers ("80-90%",
        # "1 in 3") is shown as written - counting its first number produced nonsense like "79-90%"
        if m and len(lay.lines) == 1 and not re.search(r"\d", m.group(3)):
            pre, num, suf = m.groups()
            target = float(num.replace(",", ""))
            k = ease_out_cubic(clamp((t - (t0 - LEAD)) / 0.9))
            decimals = len(num.split(".")[1]) if "." in num else 0
            cur = target * k
            s = f"{cur:,.{decimals}f}" if "," in num else f"{cur:.{decimals}f}"
            shown = pre + s + suf
        else:
            shown = val
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((cx, y + 30 * (1 - e) + lay.height / 2), shown, font=f, fill=rgb(st["accent"]),
                                   anchor="mm")
        paste(canvas, layer, 0, 0, e)
    b.els.append(El(None, 0, 0, t0, draw=number, dur=ENTER))
    if lbl:
        ly = y + lay.height + 30
        if t0 - sc["start"] > 0.6:
            # a number is usually said at the END of its sentence: the label sets up the context first, centred on
            # the stage, then glides down to make room as the number lands on its word
            t_lbl = sc["start"] + 0.35
            mid = (R.stage[1] + R.stage[3]) / 2 - lbl.height / 2

            def label(canvas, t, p, t_lbl=t_lbl, mid=mid, ly=ly):
                e_in = ease_out_cubic(clamp((t - t_lbl) / ENTER))
                mv = ease_in_out(clamp((t - (t0 - LEAD - 0.45)) / 0.4))   # clears the space before the number arrives
                paste(canvas, lbl, cx - lbl.width / 2, mid + (ly - mid) * mv + 30 * (1 - e_in), e_in)
            b.els.append(El(None, 0, 0, t_lbl, draw=label, dur=0.01))
        else:
            b.els.append(El(lbl, cx - lbl.width / 2, ly, t0 + 0.4, "rise"))
    return b


def build_cycle(sc, st, R, root):
    """A loop: nodes around an ellipse, arrows between neighbours, and a closing arrow back to the first node that
    draws once the last node has landed (the 'and repeat' beat)."""
    b = Built()
    y0 = _heading(sc, st, R, b, R.stage[1])
    items = sc["items"]
    n = len(items)
    x0, x1, y1 = R.stage[0], R.stage[2], R.stage[3]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 + 10
    nw, nh = (340, 136) if not R.portrait else (380, 140)
    rx = min((x1 - x0) / 2 - nw / 2 - 20, 520)
    ry = min((y1 - y0) / 2 - nh / 2 - 10, 260 if not R.portrait else 330)
    cy = min(cy, y1 - 40 - nh / 2 - ry)          # bottom node stays clear of the caption band
    pos = [(cx + rx * math.sin(2 * math.pi * k / n), cy - ry * math.cos(2 * math.pi * k / n)) for k in range(n)]
    col = st["muted"]

    def edge(a, z, margin=14):
        """Start and end on the cards' borders (not at a fixed fraction), so arrowheads are never hidden."""
        (ax, ay), (zx, zy) = a, z
        dx, dy = zx - ax, zy - ay
        L = math.hypot(dx, dy) or 1.0
        ux, uy = dx / L, dy / L
        out = min((nw / 2 + margin) / abs(ux) if ux else 1e9, (nh / 2 + margin) / abs(uy) if uy else 1e9)
        return (ax + ux * out, ay + uy * out), (zx - ux * out, zy - uy * out)

    def arrow_el(a, z, t_draw):
        p0, p1 = edge(a, z)

        def draw(canvas, t, p, p0=p0, p1=p1, t_draw=t_draw):
            e = ease_in_out(clamp((t - t_draw) / 0.32))
            if e <= 0:
                return
            ex, ey = p0[0] + (p1[0] - p0[0]) * e, p0[1] + (p1[1] - p0[1]) * e
            d = ImageDraw.Draw(canvas)
            d.line([p0, (ex, ey)], fill=rgb(col), width=9)
            if e > 0.9:
                ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
                L = 30
                d.polygon([(ex, ey), (ex - L * math.cos(ang - 0.5), ey - L * math.sin(ang - 0.5)),
                           (ex - L * math.cos(ang + 0.5), ey - L * math.sin(ang + 0.5))], fill=rgb(col))
        return El(None, 0, 0, t_draw, draw=draw, dur=0.01, z=-1)

    for k, it in enumerate(items):
        c = card(nw, nh, st["radius"], st["card"], outline=st["accent"] if k == 0 else None)
        pad = c.info["pad"]
        tsp, _ = T.sprite(it["text"], "bold", nw - 36, nh - 24, 58, st["card_ink"], st["accent"], align="center",
                          min_size=24)
        c.alpha_composite(tsp, (int(pad + nw / 2 - tsp.width / 2), int(pad + nh / 2 - tsp.height / 2)))
        px, py = pos[k]
        b.els.append(El(c, px - nw / 2 - pad, py - nh / 2 - pad, it["t"], "pop"))
        if k:
            b.els.append(arrow_el(pos[k - 1], pos[k], it["t"] - LEAD - 0.32))
    if n > 2:
        b.els.append(arrow_el(pos[-1], pos[0], items[-1]["t"] + 0.45))
    return b


def build_flow(sc, st, R, root):
    if sc.get("layout") == "cycle":
        return build_cycle(sc, st, R, root)
    b = Built()
    y0 = _heading(sc, st, R, b, R.stage[1])
    items = sc["items"]
    n = len(items)
    x0, x1, y1 = R.stage[0], R.stage[2], R.stage[3]
    vertical = R.portrait or n > 5
    gap = 64 if R.portrait else (50 if n >= 4 else 90)     # 4+ nodes in a row: tighter gaps, wider nodes
    if vertical:
        # on a phone the column is the whole layout: tall nodes, nearly full width, the set centred in the stage
        nh = min(210 if R.portrait else 170, int((y1 - y0 - gap * (n - 1)) / max(1, n)))
        nw = min(860 if R.portrait else 720, x1 - x0)
        y0 += max(0, (y1 - y0 - (nh * n + gap * (n - 1))) * 0.4)
        boxes = [((x0 + x1) / 2 - nw / 2, y0 + k * (nh + gap), nw, nh) for k in range(n)]
    else:
        nw = int((x1 - x0 - gap * (n - 1)) / max(1, n))
        nh = min(260, y1 - y0)
        cy = (y0 + y1) / 2
        boxes = [(x0 + k * (nw + gap), cy - nh / 2, nw, nh) for k in range(n)]
    col = st["accent"]
    for k, (it, (bx, by, bw, bh)) in enumerate(zip(items, boxes)):
        c = card(int(bw), int(bh), st["radius"], st["card"], outline=col if k == n - 1 else None)
        pad = c.info["pad"]
        tsp, _ = T.sprite(it["text"], "bold", int(bw) - 36, int(bh) - 30,
                          60 if R.portrait else (46 if n >= 4 else 52), st["card_ink"],
                          st["accent"],
                          align="center", min_size=24)
        c.alpha_composite(tsp, (int(pad + bw / 2 - tsp.width / 2), int(pad + bh / 2 - tsp.height / 2)))
        b.els.append(El(c, bx - pad, by - pad, it["t"], "pop"))
        if k:
            px, py, pw, ph = boxes[k - 1]
            if vertical:
                a, z = (px + pw / 2, py + ph + 10), (bx + bw / 2, by - 12)
            else:
                a, z = (px + pw + 10, py + ph / 2), (bx - 12, by + bh / 2)

            def arrow(canvas, t, p, a=a, z=z, tk=it["t"]):
                e = ease_in_out(clamp((t - (tk - LEAD - 0.32)) / 0.32))
                if e <= 0:
                    return
                ex, ey = a[0] + (z[0] - a[0]) * e, a[1] + (z[1] - a[1]) * e
                d = ImageDraw.Draw(canvas)
                d.line([a, (ex, ey)], fill=rgb(st["muted"]), width=8)
                if e > 0.9:
                    ang = math.atan2(z[1] - a[1], z[0] - a[0])
                    L = 26
                    pts = [(ex, ey), (ex - L * math.cos(ang - 0.5), ey - L * math.sin(ang - 0.5)),
                           (ex - L * math.cos(ang + 0.5), ey - L * math.sin(ang + 0.5))]
                    d.polygon(pts, fill=rgb(st["muted"]))
            b.els.append(El(None, 0, 0, it["t"] - 0.32, draw=arrow, dur=0.01, z=-1))
    return b


def build_compare(sc, st, R, root):
    b = Built()
    y0 = _heading(sc, st, R, b, R.stage[1])
    x0, x1, y1 = R.stage[0], R.stage[2], R.stage[3]
    gap = 50
    rows = max(len(sc["left"].get("items", [])), len(sc["right"].get("items", [])), 1)
    if R.portrait:
        cw = x1 - x0
        ch = min(int((y1 - y0 - gap) / 2), 150 + rows * 100)
        top = y0 + max(0, (y1 - y0 - 2 * ch - gap) * 0.4)
        slots = [(x0, top), (x0, top + ch + gap)]
    else:
        cw = int((x1 - x0 - gap) / 2)
        ch = min(y1 - y0, 170 + rows * 120)
        top = y0 + max(0, (y1 - y0 - ch) * 0.4)
        slots = [(x0, top), (x0 + cw + gap, top)]
    # one item size for both cards (the largest that fits every item), so neighbours never differ in size
    all_items = sc["left"].get("items", []) + sc["right"].get("items", [])
    item_size = min([T.layout("• " + it["text"], "medium", cw - 90, 110, 52, min_size=24).size for it in all_items]
                    or [52])
    for side, (sx, sy), accent in (("left", slots[0], st["accent2"]), ("right", slots[1], st["accent"])):
        spec = sc[side]
        c = card(cw, ch, st["radius"], st["card"])
        pad = c.info["pad"]
        y = pad + 36
        if spec.get("title"):
            tsp, _ = T.sprite(spec["title"], "bold", cw - 72, 140, 60, accent, accent)
            c.alpha_composite(tsp, (pad + 36, y))
            y += tsp.height + 24
        b.els.append(El(c, sx - pad, sy - pad, spec["t"], "rise"))
        items = spec.get("items", [])
        row_h = min(120, int((ch - (y - pad) - 30) / max(1, len(items))))
        for k, it in enumerate(items):
            isp = T.render(T.layout("• " + it["text"], "medium", cw - 90, row_h, item_size, min_size=item_size),
                           st["card_ink"], accent)
            b.els.append(El(isp, sx + 40, sy + (y - pad) + k * row_h, spec["t"] + 0.25 + 0.18 * k, "slide", z=1))
    return b


def build_end(sc, st, R, root):
    b = Built()
    sw, sh = R.stage[2] - R.stage[0], R.stage[3] - R.stage[1]
    t_sp, _ = T.sprite(sc["title"], "bold", sw, int(sh * 0.45), 110, st["ink"], st["accent"], align="center")
    y = (R.stage[1] + R.stage[3]) / 2 - t_sp.height / 2 - (60 if sc.get("cta") else 0)
    t0 = min(sc["t"], sc["start"] + 0.3)
    b.els.append(El(t_sp, _center_x(R, t_sp.width), y, t0, "rise"))
    if sc.get("cta"):
        lay = T.layout(sc["cta"], "bold", sw - 120, 120, 48, align="center", max_lines=1)
        pill = card(lay.width + 90, lay.height + 44, (lay.height + 44) // 2, st["accent"])
        pad = pill.info["pad"]
        tsp = T.render(lay, st["bg"], st["bg"])
        pill.alpha_composite(tsp, (pad + 45 - 4, pad + 22 - 4))
        b.els.append(El(pill, _center_x(R, pill.width), y + t_sp.height + 40, t0 + 0.5, "pop"))
    return b


def build_image(sc, st, R, root: Path):
    b = Built()
    y0 = _heading(sc, st, R, b, R.stage[1])
    src = Path(sc["image"]) if Path(sc["image"]).is_absolute() else root / sc["image"]
    if not src.exists():
        raise OexError(f"scene {sc['id']}: image not found: {src}", "add the file or fix the 'image' path, then "
                       f"re-render just this scene: oex render --only {sc['id']}")
    try:
        im = Image.open(src).convert("RGBA")
    except Exception as e:  # noqa: BLE001 - PIL raises many types for bad files
        raise OexError(f"scene {sc['id']}: cannot read image {src}: {e}") from e
    bw, bh = R.stage[2] - R.stage[0], R.stage[3] - y0
    im.thumbnail((bw, bh), Image.LANCZOS)
    mask = Image.new("L", (im.width * 2, im.height * 2), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, mask.width - 1, mask.height - 1], st["radius"] * 2, fill=255)
    im.putalpha(Image.composite(im.getchannel("A"), Image.new("L", im.size, 0),
                                mask.resize(im.size, Image.LANCZOS)))
    b.els.append(El(im, _center_x(R, im.width), y0 + (bh - im.height) / 2, sc["t"], "rise"))
    return b


BUILDERS = {
    "title": build_title, "bullets": build_bullets, "statement": build_statement, "number": build_number,
    "flow": build_flow, "compare": build_compare, "end": build_end, "image": build_image,
}


# ---------------- background ----------------

def background(W: int, H: int, st: dict) -> Image.Image:
    im = Image.new("RGBA", (W, H), rgb(st["bg"]) + (255,))
    d = ImageDraw.Draw(im)
    c2 = rgb(st["bg2"])
    if st["decor"] == "dots":
        for y in range(40, H, 48):
            for x in range(40, W, 48):
                d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=c2)
    elif st["decor"] == "grid":
        for x in range(0, W, 80):
            d.line([(x, 0), (x, H)], fill=c2, width=1)
        for y in range(0, H, 80):
            d.line([(0, y), (W, y)], fill=c2, width=1)
    elif st["decor"] == "circles":
        r = int(min(W, H) * 0.35)
        d.ellipse([W - r, -r, W + r, r], fill=c2)
        d.ellipse([-r // 2, H - r, r * 1.5, H + r], fill=c2)
    return im
