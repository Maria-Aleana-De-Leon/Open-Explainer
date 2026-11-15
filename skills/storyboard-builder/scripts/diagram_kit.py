"""Original explanatory diagrams for Open Explainer `image` scenes, drawn with Pillow only.

Use it from your own small script and run that with any Python that has Pillow 10.1+, for example:

    uv run --no-project --with pillow python make_wing.py

    import sys; sys.path.insert(0, "<this skill>/scripts")
    from diagram_kit import Diagram
    d = Diagram("midnight", "16:9")                 # transparent canvas sized for the stage
    d.box((100, 300, 500, 500), "Sun heats water")
    d.arrow((500, 400), (900, 400), label="evaporation")
    d.save("assets/water-cycle.png")                # inside the film project

Colours are the film style's palette (names: bg, card, ink, muted, accent, accent2, line, marker) or any "#RRGGBB".
Labels smaller than MIN_TEXT pixels raise an error: they are unreadable in a 1080p video.
"""
from __future__ import annotations

import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

MIN_TEXT = 36
SS = 2  # supersampling factor: draw at 2x, downscale on save for smooth edges

# Canvas sizes that fill the image scene's stage (with a heading) without being scaled up.
SIZES = {"16:9": (1580, 600), "16:9-mascot": (1170, 600), "9:16": (920, 1000), "9:16-mascot": (920, 640)}

# Same values as openexplainer/styles.py (a test keeps them in sync).
PALETTES = {
    "paper": {"bg": "#F6F1E7", "card": "#FFFFFF", "ink": "#1E1B16", "muted": "#6B6459", "accent": "#E4572E",
              "accent2": "#2E86AB", "line": "#D9CFBE", "marker": "#F2C14E"},
    "midnight": {"bg": "#0E1726", "card": "#1B2A45", "ink": "#F2F5FA", "muted": "#9AA8BF", "accent": "#3DDC97",
                 "accent2": "#5AA9FF", "line": "#2A3B5C", "marker": "#2F6FD0"},
    "chalk": {"bg": "#1F3B2D", "card": "#2A4D3F", "ink": "#F4F1E8", "muted": "#B9C4B5", "accent": "#FFD166",
              "accent2": "#F78C6B", "line": "#3E6352", "marker": "#B5733F"},
    "pop": {"bg": "#FFE14D", "card": "#FFFFFF", "ink": "#111111", "muted": "#3D3D3D", "accent": "#FF3D7F",
            "accent2": "#2B59FF", "line": "#111111", "marker": "#FFFFFF"},
    "white": {"bg": "#FFFFFF", "card": "#FFFFFF", "ink": "#121826", "muted": "#5B6474", "accent": "#0E9F6E",
              "accent2": "#2563EB", "line": "#D5DAE1", "marker": "#FDE68A"},
}


def _font_dir() -> Path | None:
    """The toolkit's Poppins fonts (SIL OFL 1.1), if they can be found; otherwise Pillow's built-in font is used."""
    env = os.environ.get("OEX_FONTS")
    candidates = [Path(env)] if env else []
    try:
        import openexplainer.styles as st  # available when run with the toolkit's own Python
        candidates.append(st.FONT_DIR)
    except ImportError:
        pass
    here = Path(__file__).resolve()
    candidates += [p / "src" / "openexplainer" / "assets" / "fonts" for p in here.parents]
    return next((c for c in candidates if (c / "Poppins-Bold.ttf").exists()), None)


class Diagram:
    """Draws with Pillow and remembers what it drew, so `check()` can point out layout problems before you render.

    `save()` prints the warnings (it never refuses to save): a line through a shape, labels overlapping each other,
    a line or a shape edge, low-contrast text, elements cut off at the canvas edge, and a drawing too small for
    its canvas. Intentional crossings (a reference line drawn through a wing, say) are declared with
    `through=True` and are not reported. Drawing done directly on `self.d` is not tracked."""

    def __init__(self, style: str = "midnight", fmt: str = "16:9", size: tuple[int, int] | None = None,
                 background: str | None = None):
        if style not in PALETTES:
            raise ValueError(f"unknown style {style!r}; use one of {sorted(PALETTES)}")
        self.pal = PALETTES[style]
        self.w, self.h = size or SIZES[fmt]
        self.bg = background or "bg"            # what the drawing is seen against (transparent shows the film's bg)
        fill = (0, 0, 0, 0) if background is None else self._rgba(background)
        self.im = Image.new("RGBA", (self.w * SS, self.h * SS), fill)
        self.d = ImageDraw.Draw(self.im)
        self.fonts = _font_dir()
        self.solids: list[dict] = []            # {name, poly, fill}
        self.lines: list[dict] = []             # {name, pts, width, through}
        self.labels: list[dict] = []            # {text, box, color}
        self.warnings: list[str] = []

    # ---- helpers ----
    def _rgba(self, c: str, alpha: int = 255) -> tuple[int, int, int, int]:
        h = self.pal.get(c, c).lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha

    def font(self, size: int, weight: str = "medium") -> ImageFont.FreeTypeFont:
        if size < MIN_TEXT:
            raise ValueError(f"text size {size}px is too small to read in a 1080p video (min {MIN_TEXT}px)")
        if self.fonts:
            return ImageFont.truetype(str(self.fonts / f"Poppins-{weight.capitalize()}.ttf"), size * SS)
        return ImageFont.load_default(size * SS)

    @staticmethod
    def _p(pt):
        return pt[0] * SS, pt[1] * SS

    # ---- drawing ----
    def text(self, xy, s: str, size: int = 44, color: str = "ink", weight: str = "medium", anchor: str = "mm"):
        f = self.font(size, weight)
        self.d.text(self._p(xy), s, font=f, fill=self._rgba(color), anchor=anchor, align="center")
        x0, y0, x1, y1 = self.d.textbbox(self._p(xy), s, font=f, anchor=anchor, align="center")
        self.labels.append({"text": s, "box": (x0 / SS, y0 / SS, x1 / SS, y1 / SS), "color": color})

    def box(self, xyxy, label: str | None = None, fill: str = "card", outline: str | None = "line",
            radius: int = 24, size: int = 44, color: str = "ink", name: str | None = None):
        x0, y0, x1, y1 = xyxy
        self.d.rounded_rectangle([x0 * SS, y0 * SS, x1 * SS, y1 * SS], radius * SS, fill=self._rgba(fill),
                                 outline=self._rgba(outline) if outline else None, width=3 * SS)
        self.solids.append({"name": name or label or f"box {len(self.solids) + 1}", "fill": fill,
                            "poly": [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]})
        if label:
            self.text(((x0 + x1) / 2, (y0 + y1) / 2), label, size=size, color=color)

    def shape(self, points, fill: str = "card", outline: str | None = None, width: int = 4, name: str | None = None):
        self.d.polygon([self._p(p) for p in points], fill=self._rgba(fill),
                       outline=self._rgba(outline) if outline else None, width=width * SS)
        self.solids.append({"name": name or f"shape {len(self.solids) + 1}", "fill": fill, "poly": list(points)})

    def ellipse(self, xyxy, fill: str = "card", outline: str | None = None, width: int = 4, name: str | None = None):
        x0, y0, x1, y1 = xyxy
        self.d.ellipse([x0 * SS, y0 * SS, x1 * SS, y1 * SS], fill=self._rgba(fill),
                       outline=self._rgba(outline) if outline else None, width=width * SS)
        cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
        poly = [(cx + rx * math.cos(2 * math.pi * k / 48), cy + ry * math.sin(2 * math.pi * k / 48)) for k in range(48)]
        self.solids.append({"name": name or f"ellipse {len(self.solids) + 1}", "fill": fill, "poly": poly})

    def _head(self, tip, angle, color, size):
        a = math.radians(28)
        pts = [tip] + [(tip[0] - size * math.cos(angle + s * a), tip[1] - size * math.sin(angle + s * a))
                       for s in (1, -1)]
        self.d.polygon([self._p(p) for p in pts], fill=self._rgba(color))

    def arrow(self, start, end, color: str = "accent", width: int = 10, head: int = 30, label: str | None = None,
              label_size: int = 40, label_color: str | None = None, label_offset: int = -16, through: bool = False,
              name: str | None = None):
        ang = math.atan2(end[1] - start[1], end[0] - start[0])
        stop = (end[0] - head * 0.8 * math.cos(ang), end[1] - head * 0.8 * math.sin(ang))
        self.d.line([self._p(start), self._p(stop)], fill=self._rgba(color), width=width * SS)
        self._head(end, ang, color, head)
        self.lines.append({"name": name or label or f"arrow {len(self.lines) + 1}", "pts": [start, end],
                           "width": width, "through": through})
        if label:
            mid = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2 + label_offset - width / 2)
            self.text(mid, label, size=label_size, color=label_color or color, anchor="mb")   # sits above the line

    def curve(self, points, color: str = "accent2", width: int = 8, arrow: bool = True, head: int = 30,
              through: bool = False, name: str | None = None):
        """A smooth line through `points` (Catmull-Rom), optionally ending in an arrowhead: flows, paths, air."""
        pts = [points[0]] + list(points) + [points[-1]]
        out = []
        for i in range(1, len(pts) - 2):
            p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
            for k in range(48):
                t = k / 48
                out.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j])
                                        * t * t + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t ** 3) for j in (0, 1)))
        out.append(points[-1])
        self.d.line([self._p(p) for p in out], fill=self._rgba(color), width=width * SS, joint="curve")
        if arrow:
            a, b = out[-3], out[-1]
            self._head(b, math.atan2(b[1] - a[1], b[0] - a[0]), color, head)
        self.lines.append({"name": name or f"curve {len(self.lines) + 1}", "pts": out, "width": width,
                           "through": through})

    # ---- checks ----
    def check(self) -> list[str]:
        """Layout warnings for everything drawn through the kit. Prompts to look, not proof of a problem."""
        w: list[str] = []
        for ln in self.lines:
            if ln["through"]:
                continue
            for so in self.solids:
                inside = _length_inside(ln["pts"], so["poly"], margin=max(6.0, ln["width"]))
                if inside > 12:
                    w.append(f"line '{ln['name']}' passes through '{so['name']}' for {inside:.0f}px; route it around "
                             "the shape, or pass through=True if the crossing is intended")
        for i, a in enumerate(self.labels):
            for b in self.labels[i + 1:]:
                if _overlap(_pad(a["box"], 4), _pad(b["box"], 4)):
                    w.append(f"labels '{a['text']}' and '{b['text']}' overlap; move one of them")
            for ln in self.lines:          # the ends are skipped: a pointer arrow may start right next to its label
                if any(_in_box(p, _pad(a["box"], 4)) for p in _samples(ln["pts"], skip_ends=24)):
                    w.append(f"label '{a['text']}' sits on line '{ln['name']}'; move the label clear of it")
            corners = _corners(a["box"])
            holder = None
            for so in self.solids:
                n_in = sum(_in_poly(c, so["poly"]) for c in corners)
                if n_in == 4:
                    holder = so
                elif n_in or _in_poly(_centre(a["box"]), so["poly"]):
                    w.append(f"label '{a['text']}' crosses the edge of '{so['name']}'; put it fully inside or outside")
            behind = holder["fill"] if holder else self.bg
            ratio = _contrast(self._rgba(a["color"]), self._rgba(behind))
            if ratio < 3.0:
                w.append(f"label '{a['text']}' has low contrast ({ratio:.1f}:1) against its background; use "
                         f"'ink' or 'accent' instead of '{a['color']}'")
        boxes = [x["box"] for x in self.labels] + [_bounds(x["poly"]) for x in self.solids] + \
                [_bounds(x["pts"]) for x in self.lines]
        for bx in boxes:
            if bx[0] < 16 or bx[1] < 16 or bx[2] > self.w - 16 or bx[3] > self.h - 16:
                w.append(f"something at {tuple(round(v) for v in bx)} is cut off or touches the canvas edge "
                         f"({self.w}x{self.h}); keep ~40px clear")
                break
        if boxes:
            u = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
            used = (u[2] - u[0]) * (u[3] - u[1]) / (self.w * self.h)
            if used < 0.3:
                w.append(f"the drawing uses only {used:.0%} of the canvas, so it will look small on screen; "
                         "spread it out or draw it larger")
        self.warnings = list(dict.fromkeys(w))
        return self.warnings

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.im.resize((self.w, self.h), Image.LANCZOS).save(path)
        warnings = self.check()
        print(f"diagram -> {path} ({self.w}x{self.h}), {len(warnings)} layout warning(s)")
        for msg in warnings:
            print(f"  check: {msg}")
        return path


# ---- geometry (canvas pixels) ----
def _pad(b, m):
    return b[0] - m, b[1] - m, b[2] + m, b[3] + m


def _overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _in_box(p, b) -> bool:
    return b[0] <= p[0] <= b[2] and b[1] <= p[1] <= b[3]


def _corners(b):
    return [(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])]


def _centre(b):
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def _bounds(pts):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _in_poly(p, poly) -> bool:
    x, y, inside = p[0], p[1], False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def _dist_to_edges(p, poly) -> float:
    best = float("inf")
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        dx, dy = x2 - x1, y2 - y1
        t = max(0.0, min(1.0, ((p[0] - x1) * dx + (p[1] - y1) * dy) / (dx * dx + dy * dy or 1)))
        best = min(best, math.hypot(p[0] - x1 - t * dx, p[1] - y1 - t * dy))
    return best


def _samples(pts, step: float = 4.0, skip_ends: float = 0.0):
    out = []
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / step))
        out += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n)]
    out.append(tuple(pts[-1]))
    k = int(skip_ends / step)
    return out[k:len(out) - k] if k and len(out) > 2 * k else out


def _length_inside(pts, poly, margin: float, step: float = 4.0) -> float:
    """How much of a line runs well inside a shape (touching or ending at its edge does not count)."""
    return step * sum(1 for p in _samples(pts, step) if _in_poly(p, poly) and _dist_to_edges(p, poly) > margin)


def _contrast(c1, c2) -> float:
    def lum(c):
        ch = [v / 255 for v in c[:3]]
        ch = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in ch]
        return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]
    a, b = sorted((lum(c1), lum(c2)), reverse=True)
    return (a + 0.05) / (b + 0.05)
