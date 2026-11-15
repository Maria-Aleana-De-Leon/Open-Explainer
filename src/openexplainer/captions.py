"""Captions from word timings: SRT/VTT export and burned-in karaoke-style captions."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from . import text as T
from .styles import rgb

GAP_BREAK = 0.45   # a pause this long starts a new caption
HOLD = 0.5         # a caption stays this long after its last word (unless the next one starts)


@dataclass
class Chunk:
    words: list[tuple[str, float, float]]
    start: float
    end: float

    @property
    def text(self) -> str:
        return " ".join(w for w, _, _ in self.words)


def chunks(words: list[tuple[str, float, float]], max_words: int = 6, max_chars: int = 42) -> list[Chunk]:
    out: list[Chunk] = []
    cur: list = []
    for i, (w, s, e) in enumerate(words):
        if cur:
            gap = s - cur[-1][2]
            chars = len(" ".join(x[0] for x in cur)) + 1 + len(w)
            ends_sentence = cur[-1][0].rstrip()[-1:] in ".?!"
            if len(cur) >= max_words or chars > max_chars or gap > GAP_BREAK or ends_sentence:
                out.append(Chunk(cur, cur[0][1], cur[-1][2]))
                cur = []
        cur.append((w, s, e))
    if cur:
        out.append(Chunk(cur, cur[0][1], cur[-1][2]))
    for a, b in zip(out, out[1:]):
        a.end = min(a.end + HOLD, b.start)
    if out:
        out[-1].end += HOLD
    return out


def _ts(t: float, sep: str) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def write_srt(path: Path, cs: list[Chunk]) -> None:
    path.write_text("".join(f"{i}\n{_ts(c.start, ',')} --> {_ts(c.end, ',')}\n{c.text}\n\n"
                            for i, c in enumerate(cs, 1)), encoding="utf-8")


def write_vtt(path: Path, cs: list[Chunk]) -> None:
    path.write_text("WEBVTT\n\n" + "".join(f"{_ts(c.start, '.')} --> {_ts(c.end, '.')}\n{c.text}\n\n" for c in cs),
                    encoding="utf-8")


class Burner:
    """Draws the active caption with the current word in the accent colour."""

    def __init__(self, cs: list[Chunk], box: tuple[int, int, int, int], st: dict, portrait: bool):
        self.cs, self.box, self.st = cs, box, st
        self.size = 50 if portrait else 44
        self.cache: dict = {}

    def _sprite(self, ci: int, wi: int) -> Image.Image:
        key = (ci, wi)
        if key not in self.cache:
            c = self.cs[ci]
            x0, y0, x1, y1 = self.box
            words = [w for w, _, _ in c.words]
            rich = " ".join(f"*{w}*" if k == wi else w for k, w in enumerate(words))
            lay = T.layout(rich, "bold", x1 - x0 - 80, y1 - y0 - 30, self.size, min_size=24, align="center",
                           max_lines=2)
            txt = T.render(lay, self.st["ink"], self.st["accent"])
            pad_x, pad_y = 34, 16
            pill = Image.new("RGBA", (txt.width + pad_x * 2, txt.height + pad_y * 2), (0, 0, 0, 0))
            if self.st.get("boxes", True):              # styles without boxes: the caption is plain text
                ImageDraw.Draw(pill).rounded_rectangle([0, 0, pill.width - 1, pill.height - 1], 22,
                                                       fill=rgb(self.st["card"]) + (232,))
            pill.alpha_composite(txt, (pad_x, pad_y))
            if len(self.cache) > 600:
                self.cache.clear()
            self.cache[key] = pill
        return self.cache[key]

    def draw(self, canvas: Image.Image, t: float) -> None:
        for ci, c in enumerate(self.cs):
            if c.start - 0.05 <= t < c.end:
                wi = 0
                for k, (_, s, _) in enumerate(c.words):
                    if s <= t + 0.03:
                        wi = k
                sp = self._sprite(ci, wi)
                x0, y0, x1, y1 = self.box
                from .scenes import paste
                paste(canvas, sp, (x0 + x1) / 2 - sp.width / 2, (y0 + y1) / 2 - sp.height / 2)
                return
