"""Emphasis highlight: one continuous bar per line of *accent* text, as wide as the accented letters, below their
lowest ink (never on descenders), at any font size; the sweep animation and its timing are unchanged.

Regression: the marker used to be one bar per word (gaps between words), covered whole words including unaccented
punctuation ("fly?"), and sat at 74-97% of the line height, right on top of descenders."""
import numpy as np
import pytest
from PIL import Image

from openexplainer import scenes
from openexplainer import text as T

INK, ACCENT = "#FFFFFF", "#FF0000"


def _render(txt, size=96, width=1580):
    sp, lay = T.sprite(txt, "bold", width, 900, size, INK, ACCENT, align="center")
    return np.asarray(sp), lay, T.accent_bars(lay)


def _ink(a, colour):
    """(x0, y0, x1, y1) of the pixels drawn in `colour` (red = accent, white = ink), or None."""
    r, g, b, al = (a[..., k].astype(int) for k in range(4))
    m = (al > 140) & ((r > 200) & (g < 90) & (b < 90) if colour == "accent" else (r > 200) & (g > 200) & (b > 200))
    ys, xs = np.nonzero(m)
    return (xs.min(), ys.min(), xs.max(), ys.max()) if len(xs) else None


def _ext(lay):
    return round(lay.size * 0.01) + 2


@pytest.mark.parametrize("txt", ["Why is the sky *blue*?", "*Lift*"])
def test_single_word_bar_follows_the_word(txt):
    a, lay, bars = _render(txt)
    ink = _ink(a, "accent")
    assert len(bars) == 1
    x0, y0, x1, _ = bars[0]
    assert abs(x0 - ink[0]) <= _ext(lay) and abs(x1 - ink[2]) <= _ext(lay)     # as wide as the letters
    assert y0 > ink[3]                                                          # below them


@pytest.mark.parametrize("txt", ["Faster air = *more lift*", "Good agents *ask first*", "It *does it all*."])
def test_multiword_phrase_is_one_continuous_bar(txt):
    a, lay, bars = _render(txt)
    ink = _ink(a, "accent")
    assert len(bars) == 1                                                       # no gaps between the words
    assert bars[0][0] <= ink[0] + 1 and bars[0][2] >= ink[2] - 1


def test_unaccented_punctuation_is_not_underlined():
    a, lay, bars = _render("How does it *fly*?", size=124)
    accent, words = _ink(a, "accent"), _ink(a, "ink")
    question_mark_left = min(x for x in range(accent[2] + 1, a.shape[1])
                             if (a[:, x, 3] > 140).any() and (a[:, x, 1] > 200).any())
    assert bars[0][2] < question_mark_left                                      # stops before the "?"
    assert words is not None


def test_separate_accents_get_separate_bars():
    _, _, bars = _render("*more* air, *more* lift")
    assert len(bars) == 2 and bars[0][2] < bars[1][0]


@pytest.mark.parametrize("size", [40, 72, 96, 124, 180])
@pytest.mark.parametrize("txt", ["*typography* matters", "a *gyp* jump", "*Speed* = *lift*"])
def test_bar_never_touches_descenders_at_any_size(txt, size):
    a, lay, bars = _render(txt, size=size)
    for x0, y0, x1, y1 in bars:
        ink_bottom = _ink(a[:, int(x0):int(x1) + 1], "accent")[3]              # the letters above this bar
        assert y0 > ink_bottom                                                  # clear of g, p, y
        assert y0 - ink_bottom < 0.15 * lay.size                               # but close enough to belong
        assert 4 <= y1 - y0 <= 0.15 * lay.size


def test_wrapped_accent_gets_one_bar_per_line_below_each_line():
    a, lay, bars = _render("The secret is *a wing that pushes a lot of air down every second*", size=96,
                           width=700)
    assert len(lay.lines) >= 2 and len(bars) >= 2
    tops = [b[1] for b in bars]
    assert tops == sorted(tops) and len(set(round(t) for t in tops)) == len(tops)   # one per line, in order


def test_extra_spaces_inside_the_accent_do_not_widen_the_bar():
    a, lay, bars = _render("Fly *on   air*")
    ink = _ink(a, "accent")
    assert len(bars) == 1 and bars[0][2] <= ink[2] + _ext(lay)


def test_no_accent_no_bar():
    assert _render("Plain text, no accent")[2] == []


def test_sweep_animation_and_timing_are_unchanged():
    class B:
        els = []
    _, lay = T.sprite("Planes *ride* the air", "bold", 1580, 600, 96, INK, ACCENT, align="center")
    st = {"marker": "#2F6FD0"}
    b = B()
    scenes._highlight(b, st, lay, 100, 100, t_emph=2.0, t_el=1.0)
    el = b.els[-1]
    assert el.t == 1.0 and el.z == -1                                          # same element timing and layer

    def width(t):
        c = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
        el.draw(c, t, 0.0)
        cols = np.nonzero(np.asarray(c)[..., 3].max(axis=0) > 0)[0]
        return 0 if len(cols) == 0 else cols.max() - cols.min()

    full = T.accent_bars(lay)[0][2] - T.accent_bars(lay)[0][0]
    assert width(1.99) == 0                                                    # nothing before the emphasis word
    assert 0 < width(2.1) < full - 5                                           # sweeping in
    assert abs(width(2.6) - full) <= 2                                         # complete after 0.45 s
