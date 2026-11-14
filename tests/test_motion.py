"""Animated `diagram` scenes: steps happen on their words, connectors draw progressively, tokens travel (one hop or
a chain) and come back, states and labels transition, nodes glide, scenes continue seamlessly, stationary parts stay
pixel-identical, bad ids are clear errors, and caching never changes a pixel."""
import math
import random

import numpy as np
import pytest
from PIL import Image

from openexplainer.errors import OexError
from openexplainer.motion import (DRAW_S, EASE, ENTER_S, HOLD_S, MOVE_S, Diagram, auto_layout, route_points)
from openexplainer.render import SceneFrames
from openexplainer.scenes import build_diagram, regions
from openexplainer.styles import get as style
from openexplainer.timeline import _link_continued

NODES = [{"id": "model", "label": "AI model", "x": 0.3, "y": 0.5}, {"id": "tool", "label": "Search", "x": 0.8, "y": 0.5}]
EDGES = [{"id": "call", "from": "model", "to": "tool"}]
STEPS = [{"t": 1.0, "show": ["model"]}, {"t": 2.0, "show": ["tool"], "draw": ["call"]}, {"t": 3.0, "activate": ["model"]},
         {"t": 4.0, "flow": {"edge": "call", "label": "request", "back": "result"}}]
SCENE = {"id": "d", "type": "diagram", "say": "x", "start": 0.0, "end": 9.0, "t": 0.5, "nodes": NODES, "edges": EDGES,
         "steps": STEPS, "words": [], "caption_words": []}
JOB = {"width": 1920, "height": 1080, "fps": 30, "style": "midnight", "accent": None, "mascot_pos": None,
       "captions": False, "caption_words": 6, "is_last": True, "root": ".", "mascot": None, "camera": "still"}
AREA = (170, 200, 1750, 850)
ST = style("midnight")

# a richer scene that uses every feature: shapes, auto layout, groups, routes, labels, states, moves, chains
RICH = dict(SCENE, layout="row", nodes=[
    {"id": "user", "label": "You", "shape": "circle"}, {"id": "app", "label": "App", "sub": "browser"},
    {"id": "api", "label": "API", "shape": "pill"}, {"id": "db", "label": "Database", "shape": "diamond"}],
    groups=[{"id": "server", "label": "Server", "nodes": ["api", "db"]}],
    edges=[{"id": "a", "from": "user", "to": "app"}, {"id": "b", "from": "app", "to": "api", "route": "curve",
                                                      "label": "HTTPS"},
           {"id": "c", "from": "api", "to": "db", "route": "elbow"}],
    steps=[{"t": 0.6, "show": ["user", "app", "api", "db"], "stagger": 0.15},
           {"t": 1.8, "flow": {"path": ["a", "b", "c"], "label": "query", "back": "rows"}},
           {"t": 6.0, "done": ["db"], "error": ["api"], "label": {"app": "Page ready"}},
           {"t": 6.6, "move": {"user": {"x": 0.1, "y": 0.2, "ease": "out_cubic"}}, "focus": ["user", "app"]},
           {"t": 7.6, "unfocus": True, "hide": ["c"]}])


def frame(t, sc=SCENE, job=JOB):
    return np.asarray(SceneFrames(sc, job).frame(t).convert("RGB")).astype(int)


def layer(d, t):
    c = Image.new("RGBA", (1920, 1080))
    d.draw(c, t)
    return np.asarray(c).astype(int)


def edge_pts(d, eid, t=99.0):
    e = d.edges[eid]
    A, B = d.nodes[e.a], d.nodes[e.b]
    return route_points(e.route, A.box(t), A.pos(t), B.box(t), B.pos(t))


# ---------- the basics ----------

def test_elements_arrive_on_their_steps():
    before, after = frame(0.95), frame(1.5)
    assert (np.abs(after - before).max(-1) > 20).mean() > 0.002          # the model appears at its step, not before
    assert (np.abs(frame(1.95) - frame(1.5)).max(-1) > 20).mean() < 1e-4  # and nothing else changes until the next


def test_connector_draws_progressively_from_its_start():
    d = Diagram(dict(SCENE), ST, AREA)
    (x0, y0), (x1, _) = edge_pts(d, "call")[0], edge_pts(d, "call")[-1]
    lit = []
    for k in range(6):
        a = layer(d, 2.0 + DRAW_S * k / 5)[..., 3]
        lit.append(int((a[int(y0) - 2:int(y0) + 3, int(x0):int(x1)].max(0) > 0).sum()))
    assert lit == sorted(lit) and lit[0] < lit[-1] * 0.2 and lit[-1] > (x1 - x0) * 0.9


def _token_x(d, t, y):
    a = layer(d, t)
    blue = (a[..., 2] > 200) & (a[..., 0] < 140) & (a[..., 3] > 200)        # accent2 (request)
    green = (a[..., 1] > 180) & (a[..., 0] < 120) & (a[..., 2] < 190) & (a[..., 3] > 200)
    band = slice(int(y) - 20, int(y) + 20)
    xs_b, xs_g = np.nonzero(blue[band])[1], np.nonzero(green[band])[1]
    return (xs_b.mean() if len(xs_b) else None), (xs_g.mean() if len(xs_g) else None)


def test_token_goes_out_and_comes_back():
    d = Diagram(dict(SCENE), ST, AREA)
    y, dur = edge_pts(d, "call")[0][1], d.flows[0]["dur"]
    out = [_token_x(d, 4.0 + dur * k, y)[0] for k in (0.2, 0.5, 0.8)]
    assert out[0] < out[1] < out[2]                                          # request travels model -> tool
    back0 = 4.0 + dur + HOLD_S
    ret = [_token_x(d, back0 + dur * k, y)[1] for k in (0.2, 0.5, 0.8)]
    assert ret[0] > ret[1] > ret[2]                                          # result travels tool -> model


def test_stationary_parts_are_pixel_identical_while_a_token_moves():
    R = regions(1920, 1080, None)
    n = Diagram(dict(SCENE), ST, R.stage).nodes["model"]
    box = (slice(int(n.y - n.h / 2) + 4, int(n.y + n.h / 2) - 4), slice(int(n.x - n.w / 2) + 4, int(n.x + n.w / 2) - 4))
    a, b = frame(4.3), frame(4.5)                                              # token in flight, next to the node
    assert not (a == b).all()                                                  # something is moving...
    assert (a[box] == b[box]).all()                                            # ...but the node and its label are not


# ---------- shapes, layouts, routes ----------

@pytest.mark.parametrize("layout", ["row", "column", "cycle", "hub"])
def test_auto_layouts_place_every_node_inside_the_area_without_overlap(layout):
    nodes = [{"id": f"n{i}", "label": f"Node {i}"} for i in range(5)]
    pos = auto_layout(layout, nodes, "n2")
    assert set(pos) == {n["id"] for n in nodes}
    assert all(0.05 <= x <= 0.95 and 0.05 <= y <= 0.95 for x, y in pos.values())
    assert min(math.dist(p, q) for i, p in enumerate(pos.values()) for q in list(pos.values())[i + 1:]) > 0.15
    if layout == "hub":
        assert pos["n2"] == (0.5, 0.5)


def test_manual_nodes_keep_their_position_in_an_auto_layout():
    nodes = [{"id": "a", "label": "A", "x": 0.2, "y": 0.9}, {"id": "b", "label": "B"}, {"id": "c", "label": "C"}]
    assert set(auto_layout("row", nodes)) == {"b", "c"}


@pytest.mark.parametrize("shape", ["box", "pill", "circle", "diamond"])
def test_connectors_start_just_outside_every_shape(shape):
    sc = dict(SCENE, nodes=[dict(NODES[0], shape=shape), dict(NODES[1], shape=shape)], steps=[])
    d = Diagram(sc, ST, AREA)
    a = layer(d, 5.0)
    for nid, end in (("model", 0), ("tool", -1)):
        x, y = edge_pts(d, "call")[end]
        n = d.nodes[nid]
        assert 0 < abs(x - n.x) - n.w / 2 <= 12                               # a small gap, never inside the node
        assert a[int(y), int(x) + (3 if end == 0 else -3), 3] > 0             # and the line is drawn there


def test_every_route_and_shape_renders_cleanly():
    d = Diagram(dict(RICH), ST, AREA)
    a = layer(d, 1.79)                                                         # everything in, before the token
    assert a[..., 3].max() == 255
    for eid in ("a", "b", "c"):
        pts = edge_pts(d, eid, 1.79)
        mid = pts[len(pts) // 2]
        assert a[int(mid[1]) - 3:int(mid[1]) + 4, int(mid[0]) - 3:int(mid[0]) + 4, 3].max() > 0
    c = edge_pts(d, "c", 1.79)                                                     # an elbow: axis-aligned ends
    assert abs(c[0][1] - c[1][1]) < 1e-6 and abs(c[-1][1] - c[-2][1]) < 1e-6


# ---------- states, labels, moves, stagger, focus, hide ----------

def _colour_at(d, t, nid):
    n = d.nodes[nid]
    x, y = n.pos(t)
    a = layer(d, t)
    return a[int(y - n.h / 2) + 1, int(x), :3]                               # on the outline


def test_states_change_colour_smoothly():
    d = Diagram(dict(RICH), ST, AREA)
    good, bad = np.array([0x4F, 0xD1, 0x8B]), np.array([0xFF, 0x6B, 0x6B])
    before, mid, after = (_colour_at(d, t, "db") for t in (5.9, 6.15, 6.5))
    assert np.abs(after - good).max() < 40 and np.abs(before - good).max() > 80
    assert np.abs(mid - before).sum() > 20 and np.abs(mid - after).sum() > 20    # a transition, not a cut
    assert np.abs(_colour_at(d, 6.5, "api") - bad).max() < 40


def test_a_relabelled_node_crossfades_in_place():
    d = Diagram(dict(RICH), ST, AREA)
    n = d.nodes["app"]
    s_mid = d.state(6.15)[2][1]
    assert s_mid[8:11] == ("App", "Page ready", 0.5)                          # both labels, half way
    w0, w1, wm = n.size(5.9)[0], n.size(7.0)[0], n.size(6.15)[0]
    assert w1 >= d.font.getlength("Page ready") / 2 + 60 > w0                  # the node fits each label...
    assert w0 < wm < w1                                                        # ...and grows smoothly between


def test_moved_node_glides_and_its_connector_follows():
    d = Diagram(dict(RICH), ST, AREA)
    n = d.nodes["user"]
    ys = [n.pos(6.6 + MOVE_S * k / 10)[1] for k in range(11)]
    assert all(b < a for a, b in zip(ys, ys[1:])) and ys[0] - ys[-1] > 100     # monotonic, no overshoot
    assert edge_pts(d, "a", 6.6)[0] != edge_pts(d, "a", 9.0)[0]               # the connector's end moved with it


def test_stagger_spaces_entrances():
    d = Diagram(dict(RICH), ST, AREA)
    assert [round(d.nodes[i].show, 3) for i in ("user", "app", "api", "db")] == [0.6, 0.75, 0.9, 1.05]
    assert d.groups["server"].show == pytest.approx(0.8)                        # just before its first member


def test_focus_dims_everything_else_and_unfocus_restores():
    d = Diagram(dict(RICH), ST, AREA)
    groups, edges, nodes, _ = d.state(7.2)
    dims = {i: s[7] for i, s in zip(d.nodes, nodes)}
    assert dims == {"user": 0, "app": 0, "api": 1, "db": 1}
    assert edges[0][5] == 0 and edges[1][5] == 1 and groups[0][1] == 1      # the user-app link stays
    assert all(s[7] == 0 for s in d.state(8.5)[2])


def test_hidden_connector_fades_out():
    d = Diagram(dict(RICH), ST, AREA)
    assert d.state(7.7)[1][2][0] < 1 and d.state(8.5)[1][2] is None


# ---------- multi-hop tokens ----------

def test_a_chained_token_visits_each_node_in_order_and_each_one_reacts():
    d = Diagram(dict(RICH), ST, AREA)
    f = d.flows[0]
    assert f["nodes"] == ["user", "app", "api", "db"]
    arrivals = [min(p for p in d.nodes[n].pulses if p > 1.8) for n in ("app", "api", "db")]
    assert arrivals == sorted(arrivals) and arrivals[-1] == pytest.approx(1.8 + f["dur"], abs=0.01)
    assert d.nodes["user"].pulses[-1] == pytest.approx(1.8 + 2 * f["dur"] + HOLD_S)   # the answer gets home
    xs = []
    for k in range(1, 10):
        a = layer(d, 1.8 + f["dur"] * k / 10)
        tok = (a[..., 2] > 200) & (a[..., 0] < 140) & (a[..., 3] > 100)
        xs.append(np.nonzero(tok)[1].mean())
    assert all(b > a for a, b in zip(xs, xs[1:]))                              # always forward along the chain


# ---------- continuity across scenes ----------

def _continued(move=False):
    a = dict(SCENE, id="a", end=6.0, steps=STEPS[:3], heading="How it works")
    b = dict(SCENE, id="b", start=6.0, end=10.0, t=6.2, heading="How it works", **{"continue": True},
             nodes=NODES + [{"id": "files", "label": "Files", "x": 0.8, "y": 0.85}],
             edges=EDGES + [{"id": "read", "from": "model", "to": "files"}],
             steps=[{"t": 7.0, "show": ["files"]}])
    if move:
        b["nodes"] = [dict(NODES[0], y=0.3)] + b["nodes"][1:]
    scenes, problems = [dict(a), dict(b)], []
    _link_continued(scenes, problems)
    assert not problems
    return scenes, dict(JOB, is_last=False)


def test_continued_scene_starts_exactly_where_the_previous_one_ended():
    (a, b), job = _continued()
    assert a["hold_exit"] and b["transition"] == "none" and a["camera"] == b["camera"] == "still"
    last_a = frame(a["end"] - 1 / 30, a, job)
    first_b = frame(b["start"], b, job)
    assert np.abs(last_a - first_b).max() <= 1                                 # an invisible cut
    assert (np.abs(frame(6.9, b, job) - first_b).max(-1) > 20).mean() < 1e-4   # nothing re-enters
    assert (np.abs(frame(7.6, b, job) - first_b).max(-1) > 20).mean() > 0.001  # the new node does


def test_carried_state_is_kept_and_a_moved_node_glides_from_its_old_place():
    (a, b), job = _continued(move=True)
    d = SceneFrames(b, job).els[-1].draw.__self__
    model = d.nodes["model"]
    assert d.state(6.0)[2][0][4:6] == (1, 1)                                   # still active, no re-activation
    y0, y1 = model.pos(6.0)[1], model.pos(6.0 + MOVE_S)[1]
    assert y1 < y0 and model.pos(6.0 + MOVE_S / 2)[1] == pytest.approx((y0 + y1) / 2, abs=2)


def test_continue_needs_a_diagram_before_it():
    scenes = [dict(SCENE, id="a", type="statement"), dict(SCENE, id="b", **{"continue": True})]
    problems = []
    _link_continued(scenes, problems)
    assert problems and "continue" in problems[0]


# ---------- errors ----------

@pytest.mark.parametrize("bad, msg", [
    ({"edges": [{"from": "model", "to": "ghost"}]}, "unknown node 'ghost'"),
    ({"steps": [{"t": 1.0, "show": ["nope"]}]}, "unknown id"),
    ({"steps": [{"t": 1.0, "draw": ["model"]}]}, "unknown id"),                 # a node is not a connector
    ({"steps": [{"t": 1.0, "flow": {"edge": "nope"}}]}, "unknown connector"),
    ({"steps": [{"t": 1.0, "flow": {"label": "x"}}]}, "needs an \"edge\" or a \"path\""),
    ({"steps": [{"t": 1.0, "move": {"nope": {"x": 0.1, "y": 0.1}}}]}, "unknown id"),
    ({"nodes": NODES + [{"id": "z", "label": "Z"}]}, "have no x, y"),
    ({"nodes": NODES + [dict(NODES[0])]}, "duplicate"),
    ({"groups": [{"id": "g", "nodes": ["ghost"]}]}, "needs existing nodes"),
])
def test_bad_diagrams_are_clear_errors(bad, msg):
    with pytest.raises(OexError, match=msg):
        build_diagram(dict(SCENE, **bad), ST, regions(1920, 1080, None), None)


def test_broken_flow_path_is_a_clear_error():
    sc = dict(RICH, steps=[{"t": 1.0, "flow": {"path": ["a", "c"]}}])
    with pytest.raises(OexError, match="breaks between a and c"):
        build_diagram(sc, ST, regions(1920, 1080, None), None)


def test_storyboard_schema_accepts_the_motion_fields():
    from openexplainer.config import SCENE as SPEC
    from openexplainer.schema import check
    sc = {k: v for k, v in RICH.items() if k not in ("start", "end", "t", "words", "caption_words")}
    sc["steps"] = [dict({k: v for k, v in s.items() if k != "t"}, at=s["t"]) for s in RICH["steps"]]
    assert check(sc, SPEC) == []
    sc["steps"][0]["move"] = {"user": {"x": 2, "y": 0.5}}
    assert check(sc, SPEC)                                                     # out-of-range move is caught


# ---------- determinism and caching ----------

def _fresh(sc, t):
    """Uncached: a new diagram (empty cache) for every frame."""
    d = Diagram(dict(sc), ST, AREA)
    return d.layer(d.state(t)).tobytes()


@pytest.mark.parametrize("sc", [SCENE, RICH], ids=["simple", "rich"])
def test_cached_frames_are_identical_to_uncached_in_any_order_and_split(sc):
    times = [k / 15 for k in range(int(sc["end"] * 15))]
    reference = {t: _fresh(sc, t) for t in times}
    shared = Diagram(dict(sc), ST, AREA)
    assert all(shared.layer(shared.state(t)).tobytes() == reference[t] for t in times)          # in order, cached
    shuffled = times[:]
    random.Random(7).shuffle(shuffled)
    other = Diagram(dict(sc), ST, AREA)
    assert all(other.layer(other.state(t)).tobytes() == reference[t] for t in shuffled)          # random order
    w1, w2 = Diagram(dict(sc), ST, AREA), Diagram(dict(sc), ST, AREA)
    half = len(times) // 2
    assert all((w1 if k < half else w2).layer((w1 if k < half else w2).state(t)).tobytes() == reference[t]
               for k, t in enumerate(times))                                                    # two workers


def test_settled_stretches_reuse_one_layer():
    d = Diagram(dict(SCENE), ST, AREA)
    settled = [7.5 + k / 30 for k in range(30)]                     # every step finished
    assert len({d.state(t) for t in settled}) == 1
    assert d.layer(d.state(settled[0])) is d.layer(d.state(settled[-1]))


def test_every_easing_starts_at_0_and_ends_at_1():
    for name, f in EASE.items():
        assert f(0) == pytest.approx(0, abs=1e-9) and f(1) == pytest.approx(1, abs=1e-9), name
    assert ENTER_S < DRAW_S < MOVE_S


def test_a_reversed_flow_travels_from_the_connector_end_and_pulses_its_start():
    sc = dict(SCENE, steps=[{"t": 1.0, "flow": {"edge": "call", "reverse": True, "label": "answer"}}])
    d = Diagram(sc, ST, AREA)
    f, y = d.flows[0], edge_pts(d, "call")[0][1]
    xs = [_token_x(d, 1.0 + f["dur"] * k, y)[0] for k in (0.2, 0.5, 0.8)]
    assert xs[0] > xs[1] > xs[2]                                             # tool -> model
    assert f["nodes"] == ["tool", "model"] and d.nodes["model"].pulses == [pytest.approx(1.0 + f["dur"], abs=0.01)]


def test_validate_reports_diagram_id_problems_before_rendering():
    from openexplainer.config import _scene_content_problems as storyboard_problems
    sb = {"scenes": [{"id": "s1", "type": "diagram", "say": "x", "nodes": NODES, "edges": EDGES,
                      "steps": [{"at": "x", "draw": ["ghost"]}]}]}
    problems = storyboard_problems(sb)
    assert any("unknown id(s) ['ghost']" in p for p in problems)


def test_qa_checks_a_diagram_scene_cue_only_when_something_appears_on_it():
    from openexplainer.qa import _cues

    def cues(sc):
        return [c for c, _ in _cues(sc)]
    assert "scene" in cues(dict(SCENE, steps=[]))                              # nodes appear on the scene cue
    assert "scene" not in cues(SCENE)                                           # every node has its own step
    (_, b), _ = _continued()
    assert "scene" not in cues(b)                                               # carried over or stepped: nothing new
    assert "scene" in cues(dict(b, steps=[]))                                   # "files" would appear on it


def test_extent_covers_nodes_and_group_frames():
    d = Diagram(dict(RICH), ST, AREA)
    x0, y0, x1, y1 = d.extent()
    assert x0 >= AREA[0] and x1 <= AREA[2] and y0 >= AREA[1] and y1 <= AREA[3]
    db = d.nodes["db"]
    assert x1 >= db.x + db.w / 2 + 30                                             # the group's frame counts


def test_a_node_that_replaces_another_in_place_is_not_crowding():
    sc = dict(SCENE, nodes=NODES + [{"id": "new", "label": "Flight search", "x": 0.8, "y": 0.5}],
              steps=[{"t": 1.0, "hide": ["tool"], "show": ["new"]}])
    assert Diagram(sc, ST, AREA).crowded() == []
    assert Diagram(dict(sc, steps=[]), ST, AREA).crowded() == [("tool", "new")]


def test_a_relabelled_node_keeps_its_size_across_a_continued_cut():
    (a, b), job = _continued()
    a["steps"] = a["steps"] + [{"t": 4.0, "label": {"tool": "Flight search"}}]
    scenes, problems = [dict(a), dict(SCENE, id="b", start=6.0, end=10.0, t=6.2, heading=a["heading"], steps=[],
                                      **{"continue": True})], []
    _link_continued(scenes, problems)
    last_a = frame(5.95, scenes[0], job)
    first_b = frame(6.0, scenes[1], job)
    assert np.abs(last_a - first_b).max() <= 1                                 # same label, same size: no jump


def test_a_token_label_on_a_vertical_connector_sits_beside_the_token():
    sc = dict(SCENE, nodes=[dict(NODES[0], x=0.5, y=0.9), dict(NODES[1], x=0.5, y=0.1)],
              steps=[{"t": 1.0, "flow": {"edge": "call", "label": "request"}}])
    d = Diagram(sc, ST, AREA)
    a = layer(d, 1.0 + d.flows[0]["dur"] / 2)
    x = int(d.nodes["model"].x)
    tok = (a[..., 2] > 200) & (a[..., 0] < 140) & (a[..., 3] > 200)
    rows = np.nonzero(tok[:, x])[0]
    y_tok = int(rows.mean())
    left = tok[y_tok - 20:y_tok + 20, x - 400:x - 30].sum()                    # label outline/text, left of it
    above = tok[y_tok - 120:y_tok - 40, x - 20:x + 20].sum()
    assert left > 0 and above == 0
