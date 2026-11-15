"""The white style and project colour overrides: nothing behind text (labels, captions, call to action), other styles
keep their boxes, and `colors` in project.json replaces any style colour by name."""
import numpy as np

from openexplainer.config import PROJECT
from openexplainer.motion import Diagram
from openexplainer.render import SceneFrames
from openexplainer.schema import check
from openexplainer.styles import get as style

from test_iso import AREA, JOB, SCENE, ST, layer


def test_white_style_draws_no_boxes_behind_text_and_other_styles_keep_theirs():
    from openexplainer.captions import Burner, chunks
    cs = chunks([("Look", 0.0, 0.3), ("plan", 0.3, 0.6)], 6)
    box = (170, 880, 1750, 1010)
    white = Burner(cs, box, style("white"), False)._sprite(0, 0)
    paper = Burner(cs, box, style("paper"), False)._sprite(0, 0)
    assert np.asarray(white)[2, white.width // 2, 3] == 0            # transparent around the words: no pill
    assert np.asarray(paper)[2, paper.width // 2, 3] > 200           # the pill is still there in other styles
    d = Diagram(dict(SCENE), style("white"), AREA)
    assert d.boxes is False and Diagram(dict(SCENE), ST, AREA).boxes is True
    a = layer(d, 8.5)
    lab = d.nodes["plan"]
    x, y = int(lab.x), int(lab.y - lab.h / 2 + 30)                    # around the label text: background shows through
    patch = a[y - 30:y + 30, x - 70:x + 70]
    assert (patch[..., 3] == 0).mean() > 0.3


def test_white_style_exists_with_every_colour_the_renderer_needs():
    w, m = style("white"), style("midnight")
    assert w["bg"] == "#FFFFFF" and set(m) <= set(w)


def test_project_colours_override_the_style(tmp_path):
    st = style("white", "#EA580C", {"good": "#F97316"})
    assert st["accent"] == "#EA580C" and st["good"] == "#F97316" and st["bad"] == style("white")["bad"]
    assert check({"title": "t", "narration": {"audio": "a.wav"}, "colors": {"good": "#F97316"}}, PROJECT) == []
    assert any("green" in p for p in check({"title": "t", "narration": {"audio": "a.wav"},
                                            "colors": {"green": "#00FF00"}}, PROJECT))
    job = dict(JOB, style="white", accent="#EA580C", colors={"good": "#F97316"})
    sf = SceneFrames(dict(SCENE), job)
    assert sf.st["good"] == "#F97316"
