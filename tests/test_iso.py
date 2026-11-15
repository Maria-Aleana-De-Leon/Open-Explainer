"""The 3d look for animated diagrams: flat-shaded solids and illustrated objects that stay inside their footprint,
faces of one solid colour, the same pixels in any frame order, objects that drop in and hop on their words, icon
swaps, tokens travelling on the floor, clear validation, and flat diagrams left exactly as they were."""
import random

import numpy as np
import pytest
from PIL import Image, ImageDraw

from openexplainer import iso as I
from openexplainer.config import ICONS, STORYBOARD
from openexplainer.schema import check
from openexplainer.errors import OexError
from openexplainer.motion import ENTER_S, U3D, Diagram
from openexplainer.render import SceneFrames
from openexplainer.scenes import background, check_diagram
from openexplainer.styles import get as style
from openexplainer.timeline import _link_continued

ST = style("midnight")
AREA = (170, 290, 1750, 850)
PAL = {"accent": (61, 220, 151), "accent2": (90, 169, 255), "good": (79, 209, 139), "bad": (255, 107, 107)}
NODES = [{"id": "agent", "label": "Agent", "icon": "robot", "x": 0.15, "y": 0.5},
         {"id": "plan", "label": "Plan", "x": 0.5, "y": 0.0},
         {"id": "tool", "label": "Search", "icon": "magnifier", "x": 0.85, "y": 0.5},
         {"id": "ok", "label": "OK?", "shape": "diamond", "x": 0.5, "y": 1.0}]
EDGES = [{"id": "a", "from": "agent", "to": "plan"}, {"id": "b", "from": "plan", "to": "tool"},
         {"id": "c", "from": "agent", "to": "ok", "route": "curve", "label": "check"}]
STEPS = [{"t": 1.0, "show": ["agent"]}, {"t": 1.8, "show": ["plan", "tool", "ok"], "stagger": 0.2},
         {"t": 3.0, "flow": {"path": ["a", "b"], "label": "query", "back": "result"}},
         {"t": 6.0, "icon": {"tool": "plane"}, "label": {"tool": "Flights"}, "done": ["tool"]},
         {"t": 7.0, "error": ["ok"], "activate": ["agent"]}]
SCENE = {"id": "d", "type": "diagram", "look": "3d", "say": "x", "start": 0.0, "end": 9.0, "t": 0.5, "nodes": NODES,
         "edges": EDGES, "steps": STEPS, "words": [], "caption_words": []}
JOB = {"width": 1920, "height": 1080, "fps": 30, "style": "midnight", "accent": None, "mascot_pos": None,
       "captions": False, "caption_words": 6, "is_last": True, "root": ".", "mascot": None, "camera": "still"}


def layer(d, t):
    c = Image.new("RGBA", (1920, 1080))
    d.draw(c, t)
    return np.asarray(c).astype(int)


@pytest.mark.parametrize("name", sorted(I.ICONS))
def test_every_object_draws_inside_its_footprint_and_height(name):
    u, bx, by = 100, 300, 400
    im = Image.new("RGBA", (600, 600))
    g = I.Iso(ImageDraw.Draw(im, "RGBA"), bx, by, u, 2)
    I.ICONS[name][0](g, PAL)
    a = np.asarray(im)[..., 3]
    ys, xs = np.nonzero(a)
    assert len(xs) > 500, f"{name} drew almost nothing"
    height = I.ICONS[name][1]
    assert ys.min() >= by - (height + 0.01) * u, f"{name} is taller than its declared height"
    assert xs.min() >= bx - 1.25 * u and xs.max() <= bx + 1.25 * u and ys.max() <= by + 0.75 * u


def test_icon_names_agree_between_schema_and_drawing():
    assert sorted(ICONS) == sorted(I.ICONS)


def test_faces_are_flat_single_colours_no_gradients():
    im = Image.new("RGB", (400, 400))
    g = I.Iso(ImageDraw.Draw(im), 200, 250, 100, 0)
    g.box(-0.5, -0.5, 0, 0.5, 0.5, 0.6, (90, 120, 200))
    a = np.asarray(im).astype(int)
    for x, y in (g.P(0.0, 0.0, 0.6), g.P(0.5, 0.0, 0.3), g.P(0.0, 0.5, 0.3)):        # top, right and left faces
        patch = a[int(y) - 6:int(y) + 7, int(x) - 6:int(x) + 7].reshape(-1, 3)
        assert len({tuple(p) for p in patch}) == 1
    tops = {tuple(a[int(y), int(x)]) for x, y in (g.P(0, 0, 0.6), g.P(0.5, 0, 0.3), g.P(0, 0.5, 0.3))}
    assert len(tops) == 3                                                           # three distinct face tones


def test_same_pixels_in_any_order_and_with_a_fresh_diagram():
    times = [0.4, 1.1, 1.9, 2.3, 3.2, 3.6, 4.4, 6.1, 6.3, 7.2, 8.5]
    seq = Diagram(dict(SCENE), ST, AREA)
    ref = {t: layer(seq, t) for t in times}
    shuffled = times[:]
    random.Random(4).shuffle(shuffled)
    other = Diagram(dict(SCENE), ST, AREA)
    for t in shuffled:
        assert np.array_equal(layer(other, t), ref[t]), t


def _top_y(a, x0, x1):
    ys = np.nonzero(a[:, x0:x1, 3].max(1) > 40)[0]
    return ys.min() if len(ys) else None


def test_objects_drop_in_on_their_step_and_settle():
    d = Diagram(dict(SCENE), ST, AREA)
    n = d.nodes["agent"]
    x0, x1 = int(n.x - 60), int(n.x + 60)
    assert layer(d, 0.95)[:, x0:x1, 3].max() == 0                                 # not there before its step
    falling, settled = layer(d, 1.0 + ENTER_S * 0.3), layer(d, 2.5)
    assert falling[:, x0:x1, 3].max() > 0
    assert _top_y(falling, x0, x1) < _top_y(settled, x0, x1)                     # dropping in from above
    assert np.array_equal(layer(d, 2.6)[:, x0:x1], settled[:, x0:x1])            # then still: steady pixels


def test_an_icon_swap_replaces_the_object_on_its_step():
    d = Diagram(dict(SCENE), ST, AREA)
    n = d.nodes["tool"]
    box = (slice(int(n.y - n.h / 2), int(n.y + n.h / 2)), slice(int(n.x - n.w / 2), int(n.x + n.w / 2)))
    before, after = layer(d, 5.9)[box], layer(d, 8.0)[box]
    assert (np.abs(after - before).max(-1) > 40).mean() > 0.02
    assert d.nodes["tool"].icon.last() == "plane"


def test_a_token_travels_along_the_floor():
    d = Diagram(dict(SCENE), ST, AREA)
    xs = []
    for k in range(1, 5):                                  # the outward trip (the answer comes back later)
        a = layer(d, 3.0 + k * 0.25)
        blue = (a[..., 2] > 200) & (a[..., 0] < 140) & (a[..., 3] > 200)
        xs.append(np.nonzero(blue)[1].mean() if blue.any() else None)
    xs = [x for x in xs if x is not None]
    assert len(xs) >= 3 and xs == sorted(xs) and xs[-1] - xs[0] > 150, xs


def test_3d_scenes_stand_on_an_isometric_floor_and_flat_ones_keep_their_grid():
    flat, iso = np.asarray(background(1920, 1080, ST)), np.asarray(background(1920, 1080, ST, iso=True))
    assert not np.array_equal(flat, iso)
    assert np.array_equal(np.asarray(SceneFrames(dict(SCENE, look="flat", nodes=[
        {k: v for k, v in n.items() if k != "icon"} for n in NODES], steps=[
        {k: v for k, v in s.items() if k != "icon"} for s in STEPS]), JOB).bg), flat)


def test_flat_is_the_default_and_unchanged_by_the_3d_code():
    plain = [{k: v for k, v in n.items() if k != "icon"} for n in NODES]
    steps = [{k: v for k, v in s.items() if k != "icon"} for s in STEPS]
    a = Diagram(dict(SCENE, look="flat", nodes=plain, steps=steps), ST, AREA)
    b = Diagram({k: v for k, v in dict(SCENE, nodes=plain, steps=steps).items() if k != "look"}, ST, AREA)
    for t in (1.5, 3.4, 7.5):
        assert np.array_equal(layer(a, t), layer(b, t))


def test_icons_need_the_3d_look_and_known_nodes():
    with pytest.raises(OexError, match="need the 3d look"):
        check_diagram(dict(SCENE, look="flat"))
    with pytest.raises(OexError, match="unknown id"):
        check_diagram(dict(SCENE, steps=[{"t": 1, "icon": {"nope": "plane"}}]))
    sb = {"scenes": [{"id": "s1", "type": "diagram", "say": "x", "look": "3d",
                      "nodes": [{"id": "a", "label": "A", "x": 0.5, "y": 0.5, "icon": "unicorn"}]}]}
    assert any("unicorn" in p for p in check(sb, STORYBOARD))


def test_continue_needs_the_same_look():
    problems = []
    _link_continued([dict(SCENE, id="a"), dict(SCENE, id="b", look="flat", **{"continue": True})], problems)
    assert any("same \"look\"" in p for p in problems)


def test_crowded_3d_nodes_are_reported():
    close = [dict(NODES[0], x=0.3, y=0.5), dict(NODES[2], x=0.36, y=0.5)]
    d = Diagram(dict(SCENE, nodes=close, edges=[], steps=[]), ST, AREA)
    assert ("agent", "tool") in d.crowded()


def test_the_unit_is_large_enough_to_read():
    assert U3D >= 80
