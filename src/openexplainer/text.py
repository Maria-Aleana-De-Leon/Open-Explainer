"""Text layout to RGBA sprites: auto-fit size, word wrap, *accent* runs, per-word boxes for highlights."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from .styles import FONTS, rgb

Run = tuple[str, bool]


@dataclass(frozen=True)
class RichWord:
    runs: tuple[Run, ...]

    @property
    def text(self) -> str:
        return "".join(r for r, _ in self.runs)

    @property
    def accent(self) -> bool:
        return any(a for _, a in self.runs)


@lru_cache(maxsize=256)
def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS[weight]), size)


def parse_rich(text: str) -> list[RichWord]:
    """'Why is the sky *blue*?' -> words; '*blue*?' stays ONE word with two colour runs (no space before '?')."""
    out, accent = [], False
    for raw in text.split():
        runs, buf = [], ""
        for ch in raw:
            if ch == "*":
                if buf:
                    runs.append((buf, accent))
                buf, accent = "", not accent
            else:
                buf += ch
        if buf:
            runs.append((buf, accent))
        if runs:
            out.append(RichWord(tuple(runs)))
    return out


@dataclass
class Layout:
    size: int
    lines: list[list[RichWord]]
    width: int
    height: int
    line_h: int
    weight: str = "regular"
    boxes: list[tuple[int, int, int, int, bool]] = field(default_factory=list)  # x0,y0,x1,y1,accent per word
    words: list[RichWord] = field(default_factory=list)


def _wrap(words: list[RichWord], f, max_w: float) -> list[list[RichWord]]:
    space = f.getlength(" ")
    lines, cur, cur_w = [], [], 0.0
    for w in words:
        ww = f.getlength(w.text)
        if cur and cur_w + space + ww > max_w:
            lines.append(cur)
            cur, cur_w = [], 0.0
        cur.append(w)
        cur_w += (space if len(cur) > 1 else 0) + ww
    if cur:
        lines.append(cur)
    return lines


def _balanced(words: list[RichWord], f, max_w: float, n_lines: int) -> list[list[RichWord]]:
    """The narrowest wrap with the same number of lines: no lone word on the last line of a centred headline."""
    lo = max(f.getlength(w.text) for w in words)
    hi = max_w
    for _ in range(14):
        mid = (lo + hi) / 2
        if len(_wrap(words, f, mid)) <= n_lines:
            hi = mid
        else:
            lo = mid
    return _wrap(words, f, hi)


def layout(text: str, weight: str, max_w: int, max_h: int, size: int, min_size: int = 18,
           leading: float = 1.18, align: str = "left", max_lines: int = 8) -> Layout:
    words = parse_rich(text)
    while True:
        f = font(weight, size)
        space = f.getlength(" ")
        lines = _wrap(words, f, max_w)
        if align == "center" and 1 < len(lines) <= 4:
            lines = _balanced(words, f, max_w, len(lines))
        asc, desc = f.getmetrics()
        line_h = int((asc + desc) * leading)
        widths = [sum(f.getlength(w.text) for w in ln) + space * (len(ln) - 1) for ln in lines]
        too_wide = any(f.getlength(w.text) > max_w for w in words)
        h = line_h * len(lines)
        if (h <= max_h and not too_wide and len(lines) <= max_lines) or size <= min_size:
            lay = Layout(size, lines, int(max(widths, default=0)) + 2, h, line_h, weight)
            y = 0
            for ln, lw in zip(lines, widths):
                x = {"left": 0, "center": (lay.width - lw) / 2, "right": lay.width - lw}[align]
                for w in ln:
                    ww = f.getlength(w.text)
                    lay.boxes.append((int(x), y, int(x + ww), y + line_h, w.accent))
                    lay.words.append(w)
                    x += ww + space
                y += line_h
            return lay
        size = max(min_size, int(size * 0.92))


def render(lay: Layout, ink: str, accent: str, pad: int = 4) -> Image.Image:
    im = Image.new("RGBA", (lay.width + pad * 2, lay.height + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = font(lay.weight, lay.size)
    asc, desc = f.getmetrics()
    off = (lay.line_h - (asc + desc)) // 2
    for (x0, y0, _, _, _), w in zip(lay.boxes, lay.words):
        x = x0 + pad
        for part, acc in w.runs:
            d.text((x, y0 + off + pad), part, font=f, fill=rgb(accent if acc else ink))
            x += f.getlength(part)
    return im


def accent_bars(lay: Layout, pad: int = 4) -> list[tuple[float, float, float, float]]:
    """Emphasis bars for the *accent* text of a layout drawn by `render` (sprite pixels, padding included).

    One continuous bar per line for each run of accented text: it spans the accented letters themselves (across the
    spaces between accented words, but not unaccented punctuation such as the "?" in "*fly*?") and sits just below
    the lowest ink of those letters, so it never touches descenders (g, p, y)."""
    f = font(lay.weight, lay.size)
    asc, desc = f.getmetrics()
    off = (lay.line_h - (asc + desc)) // 2
    gap, thick, ext = max(3, round(lay.size * 0.06)), max(5, round(lay.size * 0.1)), round(lay.size * 0.01)
    bars: list[list[float]] = []            # x0, x1, ink bottom, line top
    open_bar = False
    line = None
    for (x0, y0, _, _, _), w in zip(lay.boxes, lay.words):
        if y0 != line:                      # a new line closes any open bar
            line, open_bar = y0, False
        x = x0
        for part, acc in w.runs:
            if acc and part.strip():
                mask, (ox, oy) = f.getmask2(part, mode="L")      # real ink (getbbox ignores side bearings)
                bb = mask.getbbox() or (0, 0, int(f.getlength(part)), 0)
                left, right, bottom = ox + bb[0], ox + bb[2], oy + bb[3]
                if open_bar:
                    bars[-1][1] = x + right
                    bars[-1][2] = max(bars[-1][2], bottom)
                else:
                    bars.append([x + left, x + right, bottom, y0])
                open_bar = True
            elif part.strip():
                open_bar = False
            x += f.getlength(part)
    out = []
    for x0, x1, bottom, y0 in bars:
        top = y0 + off + pad + bottom + gap
        out.append((x0 + pad - ext, top, x1 + pad + ext, top + thick))
    return out


def sprite(text: str, weight: str, max_w: int, max_h: int, size: int, ink: str, accent: str,
           align: str = "left", min_size: int = 18) -> tuple[Image.Image, Layout]:
    lay = layout(text, weight, max_w, max_h, size, min_size=min_size, align=align)
    return render(lay, ink, accent), lay
