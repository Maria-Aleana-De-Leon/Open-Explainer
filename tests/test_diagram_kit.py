"""The storyboard-builder diagram kit: Pillow-only, the film styles' colours, legible text, canvases that fill the
image scene's stage, and output the renderer accepts."""
import importlib.util
from pathlib import Path

import pytest
from PIL import Image

from openexplainer import styles
from openexplainer.scenes import regions

KIT = Path(__file__).resolve().parents[1] / "skills" / "storyboard-builder" / "scripts" / "diagram_kit.py"
spec = importlib.util.spec_from_file_location("diagram_kit", KIT)
dk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dk)


def test_palettes_match_the_film_styles():
    assert set(dk.PALETTES) == set(styles.STYLES)
    for name, pal in dk.PALETTES.items():
        for key, value in pal.items():
            assert styles.STYLES[name][key] == value, (name, key)


@pytest.mark.parametrize("fmt, mascot", [("16:9", None), ("16:9-mascot", "left"), ("9:16", None),
                                         ("9:16-mascot", "left")])
def test_canvas_fills_the_stage_without_upscaling(fmt, mascot):
    w, h = dk.SIZES[fmt]
    W, H = (1080, 1920) if fmt.startswith("9:16") else (1920, 1080)
    R = regions(W, H, mascot)
    sw, sh = R.stage[2] - R.stage[0], R.stage[3] - R.stage[1]
    k = min(1.0, sw / w, (sh - 140) / h)          # 140 px: room for a heading, as in review.py
    assert k > 0.95                                # drawn at (nearly) the size it is shown: crisp labels
    assert (w * k) * (h * k) / (sw * sh) > 0.6     # and it fills most of the stage


def test_draws_a_transparent_png_with_readable_text(tmp_path):
    d = dk.Diagram("paper", "16:9")
    d.box((40, 40, 400, 200), "Sun heats water")
    d.arrow((400, 120), (800, 120), label="vapour rises")
    d.curve([(800, 120), (950, 200), (1000, 400)])
    d.ellipse((1000, 300, 1300, 500), outline="accent2")
    d.shape([(1350, 500), (1450, 300), (1550, 500)], fill="accent")
    out = d.save(tmp_path / "assets" / "d.png")
    im = Image.open(out)
    assert im.size == dk.SIZES["16:9"] and im.mode == "RGBA"
    assert im.getpixel((5, 590))[3] == 0                 # background stays transparent
    assert im.getextrema()[3][1] == 255                  # something was drawn
    with pytest.raises(ValueError, match="too small"):
        d.text((10, 10), "tiny", size=dk.MIN_TEXT - 1)
    with pytest.raises(ValueError, match="unknown style"):
        dk.Diagram("neon")


def _warn(d):
    return d.check()


def test_layout_checks_catch_real_problems():
    d = dk.Diagram("midnight", "16:9")
    d.shape([(400, 250), (1200, 250), (1200, 400), (400, 400)], name="wing")
    d.arrow((100, 320), (1500, 320), label=None, name="air")               # straight through the wing
    assert any("passes through 'wing'" in m for m in _warn(d))

    d = dk.Diagram("midnight", "16:9")
    d.text((700, 300), "Lift", size=60)
    d.text((740, 310), "Weight", size=60)                                   # on top of each other
    assert any("overlap" in m for m in _warn(d))

    d = dk.Diagram("midnight", "16:9")
    d.box((600, 250, 760, 350), "A label far too long for its box")         # spills over the edges
    assert any("crosses the edge" in m for m in _warn(d))

    d = dk.Diagram("midnight", "16:9")
    d.box((100, 100, 1480, 500), fill="card")
    d.text((790, 300), "Hard to read", size=48, color="line")               # line colour on a card
    assert any("low contrast" in m for m in _warn(d))

    d = dk.Diagram("midnight", "16:9")
    d.box((1300, 200, 1590, 400), "Cut off")                               # past the right edge
    assert any("canvas edge" in m for m in _warn(d))

    d = dk.Diagram("midnight", "16:9")
    d.box((740, 270, 840, 330))                                             # a speck in a big canvas
    assert any("uses only" in m for m in _warn(d))


def test_layout_checks_accept_legitimate_diagrams():
    d = dk.Diagram("midnight", "16:9")
    d.box((80, 200, 480, 400), "Sun heats water")
    d.box((1100, 200, 1500, 400), "Cloud forms")
    d.arrow((480, 300), (1100, 300), label="vapour rises")                 # edge to edge, label above the line
    d.shape([(500, 470), (1080, 470), (1080, 540), (500, 540)], name="sea")
    d.arrow((300, 520), (1300, 520), through=True, name="water level")     # an intended crossing
    d.text((790, 150), "Water cycle", size=56, weight="bold")
    d.arrow((700, 182), (600, 240), name="pointer")                        # pointer starting at its label's edge
    assert _warn(d) == []
