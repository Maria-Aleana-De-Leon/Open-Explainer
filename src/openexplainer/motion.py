"""Animated diagrams for the `diagram` scene type: nodes, groups and connectors that a scene's steps animate on the
narration's words.

Storyboard data (full guide: storyboard-builder skill, references/motion.md):

    nodes    {id, label, x?, y?, shape?: box|pill|circle|diamond, sub?}    x, y: 0..1 of the diagram area
    layout   manual (default) | row | column | cycle | hub (+ center)      positions for nodes without x, y
    groups   {id, label?, nodes: [...]}                                     a labelled frame around related nodes
    edges    {id?, from, to, route?: straight|curve|elbow, label?}
    steps    {at, show, hide, draw, activate, deactivate, done, error, dim, undim, focus, unfocus, label, move, flow,
              ease?, stagger?}
    continue true: carry on from the previous diagram scene (shared ids keep their state and glide to new positions)

Every frame is a pure function of t. `state(t)` collects every parameter the drawing depends on (entrance progress,
colours mid-transition, positions mid-move, token positions...) and `layer(state)` draws exactly that state at 2x and
box-filters it down. Equal states give identical pixels, so a settled stretch is drawn once and reused, and frames
are the same in any order, on any number of workers, with or without the cache.
"""
from __future__ import annotations

import bisect
import math
from collections import OrderedDict, namedtuple
from dataclasses import dataclass, field

from PIL import Image, ImageDraw

from . import text as T
from .styles import rgb

SS = 2                      # supersampling factor
ENTER_S = 0.45              # node / group entrance
EXIT_S = 0.3                # hide
DRAW_S = 0.6                # connector drawing
TRANS_S = 0.3               # colour, dim and label transitions
MOVE_S = 0.7                # a node gliding to a new position
HOLD_S = 0.25               # pause at the far end before a token returns
PULSE_S = 0.6               # activation / arrival pulse
STAGGER_S = 0.12            # default delay between several ids in one step
CACHE_LAYERS = 8            # finished layers kept per diagram

STATES = ("idle", "active", "done", "error")
SHAPES = ("box", "pill", "circle", "diamond")
LAYOUTS = ("manual", "row", "column", "cycle", "hub")
ROUTES = ("straight", "curve", "elbow")


def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


EASE = {
    "linear": lambda p: p,
    "in_out_sine": lambda p: 0.5 - 0.5 * math.cos(math.pi * p),
    "out_sine": lambda p: math.sin(math.pi * p / 2),
    "out_cubic": lambda p: 1 - (1 - p) ** 3,
    "in_out_cubic": lambda p: 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2,
    "out_quint": lambda p: 1 - (1 - p) ** 5,
    "in_out_quint": lambda p: 16 * p ** 5 if p < 0.5 else 1 - (-2 * p + 2) ** 5 / 2,
    "out_expo": lambda p: 1.0 if p >= 1 else 1 - 2 ** (-10 * p),
    "out_back": lambda p: 1 + 2.2 * (p - 1) ** 3 + 1.2 * (p - 1) ** 2,
    "spring": lambda p: 1.0 if p >= 1 else 1 - math.exp(-6 * p) * math.cos(9 * p),
}


def _mix(c1, c2, k):
    return tuple(round(a + (b - a) * k) for a, b in zip(c1, c2))


def _lit(s0, s1, k):
    """How far an element is out of the idle state (0 idle .. 1 lit), mid-transition included."""
    return (s1 != 0) * k + (s0 != 0) * (1 - k)


class Track:
    """A discrete value that changes at given times, each change blending in over a short transition."""

    def __init__(self, initial):
        self.initial, self.times, self.values = initial, [], []

    def set(self, t: float, value):
        i = bisect.bisect_right(self.times, t)
        self.times.insert(i, t)
        self.values.insert(i, value)

    def at(self, t: float, dur: float = TRANS_S):
        """(previous value, current value, progress of the change 0..1)."""
        i = bisect.bisect_right(self.times, t) - 1
        if i < 0:
            return self.initial, self.initial, 1.0
        prev = self.values[i - 1] if i else self.initial
        return prev, self.values[i], clamp((t - self.times[i]) / dur)

    def last(self):
        return self.values[-1] if self.values else self.initial

    def blend(self, t: float) -> float:
        a, b, k = self.at(t)
        return a + (b - a) * k


Box = namedtuple("Box", "shape w h")


@dataclass
class Node:
    id: str
    label: str
    shape: str
    x: float                      # centre before any move (canvas px)
    y: float
    w: float                      # the largest size it takes (layout, spacing checks)
    h: float
    sub: str = ""
    measure: object = None        # label -> (w, h): the node's size for that label
    show: float | None = None     # entrance start; -inf: already there (carried over from the previous scene)
    hide: float | None = None
    state: Track = field(default_factory=lambda: Track("idle"))
    dim: Track = field(default_factory=lambda: Track(0))
    text: Track = field(default_factory=lambda: Track(""))
    moves: list = field(default_factory=list)      # (t, x, y, ease)
    pulses: list = field(default_factory=list)     # pulse start times (activation, a token arriving)

    def pos(self, t: float):
        x, y = self.x, self.y
        for t0, nx, ny, ease in self.moves:
            if t <= t0:
                break
            k = EASE[ease](clamp((t - t0) / MOVE_S))
            x, y = x + (nx - x) * k, y + (ny - y) * k
        return x, y

    def size(self, t: float):
        """The node's size at t: it fits its label, and grows or shrinks smoothly while a new label crossfades in."""
        l0, l1, k = self.text.at(t)
        w1, h1 = self.measure(l1)
        if l0 == l1 or k >= 1:
            return w1, h1
        w0, h0 = self.measure(l0)
        e = EASE["in_out_cubic"](k)
        return w0 + (w1 - w0) * e, h0 + (h1 - h0) * e

    def box(self, t: float) -> Box:
        return Box(self.shape, *self.size(t))


@dataclass
class Edge:
    id: str
    a: str
    b: str
    route: str
    label: str = ""
    draw: float | None = None
    hide: float | None = None
    state: Track = field(default_factory=lambda: Track("idle"))
    dim: Track = field(default_factory=lambda: Track(0))


@dataclass
class Group:
    id: str
    label: str
    members: list
    show: float | None = None
    hide: float | None = None
    dim: Track = field(default_factory=lambda: Track(0))


class Path:
    """A polyline with arc-length lookup."""

    def __init__(self, pts):
        self.pts = pts
        self.cum = [0.0]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            self.cum.append(self.cum[-1] + math.hypot(bx - ax, by - ay))

    @property
    def length(self):
        return self.cum[-1]

    def point_at(self, s):
        s = clamp(s, 0, self.length)
        i = min(max(1, bisect.bisect_left(self.cum, s)), len(self.pts) - 1)
        (x0, y0), (x1, y1) = self.pts[i - 1], self.pts[i]
        seg = (self.cum[i] - self.cum[i - 1]) or 1e-9
        k = (s - self.cum[i - 1]) / seg
        return x0 + (x1 - x0) * k, y0 + (y1 - y0) * k, math.atan2(y1 - y0, x1 - x0)

    def upto(self, s):
        i = bisect.bisect_left(self.cum, s)
        x, y, _ = self.point_at(s)
        return self.pts[:max(1, i)] + [(x, y)]


def _border(shape, cx, cy, w, h, tx, ty, gap=10.0):
    """Where the line from a node's centre towards (tx, ty) leaves its outline, plus a gap."""
    dx, dy = tx - cx, ty - cy
    d = math.hypot(dx, dy)
    if d < 1e-6:
        return cx, cy
    ux, uy = dx / d, dy / d
    if shape == "circle":
        r = w / 2
    elif shape == "diamond":
        r = 1 / (abs(ux) / (w / 2) + abs(uy) / (h / 2))
    else:
        r = min((w / 2) / abs(ux) if ux else math.inf, (h / 2) / abs(uy) if uy else math.inf)
    return cx + ux * (r + gap), cy + uy * (r + gap)


def _quad(p0, c, p1, n):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * c[0] + t * t * p1[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * c[1] + t * t * p1[1]) for t in (i / n for i in range(n + 1))]


def _round_corners(pts, r):
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        (ax, ay), (bx, by), (cx, cy) = pts[i - 1], pts[i], pts[i + 1]
        d1, d2 = math.hypot(bx - ax, by - ay), math.hypot(cx - bx, cy - by)
        rr = min(r, d1 / 2, d2 / 2)
        if rr < 1:
            out.append((bx, by))
            continue
        s = (bx - (bx - ax) / d1 * rr, by - (by - ay) / d1 * rr)
        e = (bx + (cx - bx) / d2 * rr, by + (cy - by) / d2 * rr)
        out += _quad(s, (bx, by), e, 8)
    out.append(pts[-1])
    return out


def route_points(route: str, a, pa, b, pb) -> list:
    """The connector's polyline between two nodes (anything with shape, w, h) centred at pa and pb, border to
    border."""
    if route == "elbow":
        if abs(pb[0] - pa[0]) >= abs(pb[1] - pa[1]):          # leave and enter through the sides
            sx = 1 if pb[0] > pa[0] else -1
            p0, p1 = (pa[0] + sx * (a.w / 2 + 10), pa[1]), (pb[0] - sx * (b.w / 2 + 10), pb[1])
            mid = (p0[0] + p1[0]) / 2
            return _round_corners([p0, (mid, p0[1]), (mid, p1[1]), p1], 26)
        sy = 1 if pb[1] > pa[1] else -1                          # through top and bottom
        p0, p1 = (pa[0], pa[1] + sy * (a.h / 2 + 10)), (pb[0], pb[1] - sy * (b.h / 2 + 10))
        mid = (p0[1] + p1[1]) / 2
        return _round_corners([p0, (p0[0], mid), (p1[0], mid), p1], 26)
    p0 = _border(a.shape, *pa, a.w, a.h, *pb)
    p1 = _border(b.shape, *pb, b.w, b.h, *pa)
    if route == "curve":
        mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        return _quad(p0, (mx - (p1[1] - p0[1]) * 0.18, my + (p1[0] - p0[0]) * 0.18), p1, 40)
    return [p0, p1]


def auto_layout(layout: str, nodes: list, center: str | None = None) -> dict:
    """Positions (0..1 of the diagram area) for the nodes that have no x, y of their own."""
    free = [n["id"] for n in nodes if "x" not in n or "y" not in n]
    n, pos = len(free), {}
    if layout == "row":
        for i, nid in enumerate(free):
            pos[nid] = (0.1 + 0.8 * i / (n - 1) if n > 1 else 0.5, 0.5)
    elif layout == "column":
        for i, nid in enumerate(free):
            pos[nid] = (0.5, 0.12 + 0.76 * i / (n - 1) if n > 1 else 0.5)
    elif layout == "cycle":
        for i, nid in enumerate(free):
            a = -math.pi / 2 + 2 * math.pi * i / n
            pos[nid] = (0.5 + 0.30 * math.cos(a), 0.5 + 0.38 * math.sin(a))
    elif layout == "hub" and free:
        hub = center if center in free else free[0]
        rest = [x for x in free if x != hub]
        pos[hub] = (0.5, 0.5)
        for i, nid in enumerate(rest):
            a = -math.pi / 2 + 2 * math.pi * i / len(rest)
            pos[nid] = (0.5 + 0.36 * math.cos(a), 0.5 + 0.38 * math.sin(a))
    return pos


def _flows_of(step: dict) -> list:
    f = step.get("flow")
    return [f] if isinstance(f, dict) else (f or [])


class Diagram:
    def __init__(self, sc: dict, st: dict, area, prev_area=None):
        self.st = st
        x0, y0, x1, y1 = area
        self.area = (int(x0), int(y0), int(math.ceil(x1)), int(math.ceil(y1)))
        self.font = T.font("medium", 46 * SS)
        self.sub_font = T.font("medium", 32 * SS)
        self.small = T.font("bold", 34 * SS)
        self._cache: OrderedDict = OrderedDict()
        good, bad = rgb(st.get("good", st["accent"])), rgb(st.get("bad", st["accent2"]))
        self.hot = {"idle": rgb(st["muted"]), "active": rgb(st["accent"]), "done": good, "error": bad}
        card = rgb(st["card"])
        self.colours = {"idle": (card, rgb(st["line"])), "active": (_mix(card, self.hot["active"], 0.18), self.hot["active"]),
                        "done": (_mix(card, good, 0.18), good), "error": (_mix(card, bad, 0.18), bad)}
        labels = {nd["id"]: [nd["label"]] for nd in sc["nodes"]}       # every label each node will show
        for step in sc.get("steps", []):
            for i, text in (step.get("label") or {}).items():
                labels.setdefault(i, []).append(text)
        auto = auto_layout(sc.get("layout", "manual"), sc["nodes"], sc.get("center"))
        W, H = x1 - x0, y1 - y0
        self.nodes: dict[str, Node] = {}
        for nd in sc["nodes"]:
            fx, fy = (nd["x"], nd["y"]) if "x" in nd and "y" in nd else auto.get(nd["id"], (0.5, 0.5))
            shape, sub = nd.get("shape", "box"), nd.get("sub", "")
            measure = self._measurer(shape, sub)
            sizes = [measure(text) for text in labels[nd["id"]]]
            node = Node(nd["id"], nd["label"], shape, x0 + fx * W, y0 + fy * H, max(w for w, _ in sizes),
                        max(h for _, h in sizes), sub, measure)
            node.text = Track(nd["label"])
            self.nodes[nd["id"]] = node
        self.groups = {g["id"]: Group(g["id"], g.get("label", ""), list(g["nodes"])) for g in sc.get("groups", [])}
        self._fit(sc, auto)
        self.edges: dict[str, Edge] = {}
        for ed in sc.get("edges", []):
            eid = ed.get("id") or f"{ed['from']}-{ed['to']}"
            self.edges[eid] = Edge(eid, ed["from"], ed["to"], ed.get("route", "straight"), ed.get("label", ""))
        self.flows: list[dict] = []
        carried = self._carry_over(sc["prev"], st, prev_area or area) if sc.get("prev") else set()
        self._apply_steps(sc)
        for n in self.nodes.values():
            n.moves.sort(key=lambda m: m[0])
            if n.show is None:                          # never shown explicitly: there from the scene's start
                n.show = sc["t"]
        for g in self.groups.values():                  # a group appears just before its first member
            if g.show is None:
                g.show = min(self.nodes[m].show for m in g.members) - 0.1
        for e in self.edges.values():                   # never drawn explicitly: once both ends are there
            if e.draw is None:
                e.draw = max(self.nodes[e.a].show, self.nodes[e.b].show) + 0.1
                if e.draw == -math.inf and e.id not in carried:
                    e.draw = sc["t"]                    # a new connector between two carried-over nodes
        for f in self.flows:
            self._plan_flow(f)

    def _measurer(self, shape: str, sub: str):
        cache = {}

        def measure(text: str):
            if text not in cache:
                lines = text.split("\n")
                tw = max(self.font.getlength(line) for line in lines) / SS
                sw = self.sub_font.getlength(sub) / SS if sub else 0
                w, h = max(200.0, tw + 72, sw + 60), 104.0 + 54 * (len(lines) - 1) + (40 if sub else 0)
                if shape == "circle":
                    w = h = max(w, h + 40, 170.0)
                elif shape == "diamond":
                    w, h = w * 1.4, h * 1.6
                cache[text] = (w, h)
            return cache[text]
        return measure

    def _fit(self, sc: dict, auto: dict):
        """Row and column layouts space nodes by their real sizes (equal gaps), and every node, with room for its
        group's frame, is kept inside the diagram area."""
        x0, y0, x1, y1 = self.area
        free = [self.nodes[i] for i in auto]
        layout = sc.get("layout", "manual")
        if layout in ("row", "column") and len(free) > 1:
            horiz = layout == "row"
            sizes = [n.w if horiz else n.h for n in free]
            span = (x1 - x0) if horiz else (y1 - y0)
            group_of = {m: g["id"] for g in sc.get("groups", []) for m in g["nodes"]}
            labels = {frozenset((e["from"], e["to"])): e.get("label", "") for e in sc.get("edges", [])}
            need = []                                   # the least room between neighbours: arrow, label, frames
            for a, b in zip(free, free[1:]):
                label = labels.get(frozenset((a.id, b.id)), "")
                room = 90 + (self.small.getlength(label) / SS + 70 if label and horiz else 0)
                room += 70 if label and not horiz else 0
                room += 40 * ((a.id in group_of) + (b.id in group_of)) if group_of.get(a.id) != group_of.get(b.id) else 0
                need.append(room)
            extra = clamp((span * 0.94 - sum(sizes) - sum(need)) / len(need), 0, 200)
            pos = (x0 if horiz else y0) + (span - sum(sizes) - sum(need) - extra * len(need)) / 2
            for k, (n, size) in enumerate(zip(free, sizes)):
                if horiz:
                    n.x = pos + size / 2
                else:
                    n.y = pos + size / 2
                pos += size + (need[k] + extra if k < len(need) else 0)
        grouped = {m: g for g in self.groups.values() for m in g.members}
        for n in self.nodes.values():
            side, top = (34, 70 if grouped[n.id].label else 34) if n.id in grouped else (8, 8)
            n.x = clamp(n.x, x0 + n.w / 2 + side, max(x0 + n.w / 2 + side, x1 - n.w / 2 - side))
            n.y = clamp(n.y, y0 + n.h / 2 + top, max(y0 + n.h / 2 + top, y1 - n.h / 2 - side))

    def extent(self) -> tuple[float, float, float, float]:
        """The settled diagram's bounding box (final node positions, group frames included), canvas px."""
        boxes = []
        for n in self.nodes.values():
            x, y = n.pos(math.inf)
            boxes.append((x - n.w / 2, y - n.h / 2, x + n.w / 2, y + n.h / 2))
        for g in self.groups.values():
            mb = [boxes[list(self.nodes).index(m)] for m in g.members]
            boxes.append((min(b[0] for b in mb) - 30, min(b[1] for b in mb) - (64 if g.label else 30),
                          max(b[2] for b in mb) + 30, max(b[3] for b in mb) + 30))
        return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))

    def crowded(self, gap: float = 16.0) -> list[tuple[str, str]]:
        """Pairs of nodes closer than `gap` px (bounding boxes) at any position they take: placed or moved there."""
        spots = {nid: [(n.x, n.y)] + [(m[1], m[2]) for m in n.moves] for nid, n in self.nodes.items()}
        ids, out = list(self.nodes), []

        def shown(n):
            return (n.show if n.show is not None else -math.inf, n.hide + EXIT_S if n.hide is not None else math.inf)
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                A, B = self.nodes[a], self.nodes[b]
                (a0, a1), (b0, b1) = shown(A), shown(B)
                if min(a1, b1) - max(a0, b0) < ENTER_S + EXIT_S:     # never together, or one crossfades into the other
                    continue
                for ax, ay in spots[a]:
                    if any(abs(ax - bx) < (A.w + B.w) / 2 + gap and abs(ay - by) < (A.h + B.h) / 2 + gap
                           for bx, by in spots[b]):
                        out.append((a, b))
                        break
        return out

    # ---------- building the timelines ----------
    def _carry_over(self, prev: dict, st: dict, prev_area) -> set:
        """Elements shared with the previous diagram scene continue: already there, in their final state, gliding
        from their old position to their new one as this scene starts. Returns the carried-over ids."""
        old, end, carried = Diagram(prev, st, prev_area), prev["end"], set()
        for nid, n in self.nodes.items():
            o = old.nodes.get(nid)
            if not o or (o.hide is not None and o.hide <= end):
                continue
            carried.add(nid)
            n.show = -math.inf
            n.state, n.dim, n.text = Track(o.state.last()), Track(o.dim.last()), Track(o.text.last())
            cw, ch = n.measure(o.text.last())
            n.w, n.h = max(n.w, cw), max(n.h, ch)
            ox, oy = o.pos(end)
            if abs(ox - n.x) > 0.5 or abs(oy - n.y) > 0.5:
                n.moves.append((end, n.x, n.y, "in_out_cubic"))
                n.x, n.y = ox, oy
        for eid, e in self.edges.items():
            o = old.edges.get(eid)
            if o and (o.hide is None or o.hide > end) and e.a in carried and e.b in carried:
                carried.add(eid)
                e.draw, e.state, e.dim = -math.inf, Track(o.state.last()), Track(o.dim.last())
        for gid, g in self.groups.items():
            if gid in old.groups and (old.groups[gid].hide is None or old.groups[gid].hide > end):
                carried.add(gid)
                g.show, g.dim = -math.inf, Track(old.groups[gid].dim.last())
        return carried

    def _el(self, i):
        return self.nodes.get(i) or self.edges.get(i) or self.groups[i]

    def _apply_steps(self, sc: dict):
        everything = list(self.nodes) + list(self.edges) + list(self.groups)
        for step in sc.get("steps", []):
            t, gap, ease = step["t"], step.get("stagger", STAGGER_S), step.get("ease", "in_out_cubic")
            for k, i in enumerate(step.get("show", []) + step.get("draw", [])):
                el, tt = self._el(i), t + k * gap
                if isinstance(el, Edge):
                    el.draw = tt if el.draw is None else el.draw
                else:
                    el.show = tt if el.show is None else el.show
            for k, i in enumerate(step.get("hide", [])):
                self._el(i).hide = t + k * gap
            for key, value in (("activate", "active"), ("deactivate", "idle"), ("done", "done"), ("error", "error")):
                for k, i in enumerate(step.get(key, [])):
                    el = self._el(i)
                    el.state.set(t + k * gap, value)
                    if isinstance(el, Node) and value != "idle":
                        el.pulses.append(t + k * gap)
            for key, value in (("dim", 1), ("undim", 0)):
                for k, i in enumerate(step.get(key, [])):
                    self._el(i).dim.set(t + k * gap, value)
            if step.get("focus"):                       # everything else steps back; links among the focus stay
                keep = set(step["focus"])
                keep |= {e.id for e in self.edges.values() if e.a in keep and e.b in keep}
                keep |= {g.id for g in self.groups.values() if set(g.members) & keep}
                for i in everything:
                    self._el(i).dim.set(t, 0 if i in keep else 1)
            if step.get("unfocus"):
                for i in everything:
                    self._el(i).dim.set(t, 0)
            for i, text in (step.get("label") or {}).items():
                self.nodes[i].text.set(t, text)
            x0, y0, x1, y1 = self.area
            for i, to in (step.get("move") or {}).items():
                self.nodes[i].moves.append((t, x0 + to["x"] * (x1 - x0), y0 + to["y"] * (y1 - y0),
                                            to.get("ease", ease)))
            for k, f in enumerate(_flows_of(step)):
                self.flows.append(dict(f, t=t + k * gap))

    def _plan_flow(self, f: dict):
        """A token's route (one connector, or a chain of connectors through nodes), its trip time, and a pulse on
        every node it reaches."""
        f["chain"] = f.get("path") or [f["edge"]]
        hops = [self.edges[c] for c in f["chain"]]
        f["nodes"] = [hops[0].a] + [h.b for h in hops]
        legs = [math.dist(self.nodes[h.a].pos(f["t"]), self.nodes[h.b].pos(f["t"])) for h in hops]
        if f.get("reverse"):                            # travel the chain backwards, from its last node
            f["nodes"], legs = f["nodes"][::-1], legs[::-1]
        f["dur"] = f.get("dur") or round(clamp(sum(legs) / 800, 0.8, 0.75 * len(hops) + 0.4), 3)
        f["ease"] = "in_out_sine" if len(hops) > 1 else "in_out_cubic"
        ease, total, acc = EASE[f["ease"]], sum(legs) or 1.0, 0.0
        for leg, nid in zip(legs, f["nodes"][1:]):
            acc += leg
            k = next((i / 400 for i in range(401) if ease(i / 400) >= acc / total - 1e-9), 1.0)
            self.nodes[nid].pulses.append(f["t"] + k * f["dur"])
        if f.get("back"):
            self.nodes[f["nodes"][0]].pulses.append(f["t"] + 2 * f["dur"] + HOLD_S)

    # ---------- the state at time t ----------
    @staticmethod
    def _appear(start, end, t, dur):
        if start is None or t < start:
            return 0.0
        p = 1.0 if start == -math.inf else clamp((t - start) / dur)
        if end is not None and t >= end:
            p *= 1 - clamp((t - end) / EXIT_S)
        return p

    @staticmethod
    def _pulse(n: Node, t: float) -> float:
        return max((math.sin(math.pi * (t - p0) / PULSE_S) for p0 in n.pulses if 0 <= t - p0 < PULSE_S), default=0.0)

    def state(self, t: float) -> tuple:
        """Every parameter the drawing depends on, as a pure function of t (rounded, so equal states compare equal
        and settled stretches share one cached layer)."""
        r = lambda v: round(v, 4)                                        # noqa: E731
        nodes = []
        for n in self.nodes.values():
            appear = self._appear(n.show, n.hide, t, ENTER_S)
            if appear <= 0:
                nodes.append(None)
                continue
            s0, s1, sk = n.state.at(t)
            l0, l1, lk = n.text.at(t)
            entering = n.show != -math.inf and t - n.show < ENTER_S
            nodes.append((r(appear), entering, *map(r, n.pos(t)), STATES.index(s0), STATES.index(s1), r(sk),
                          r(n.dim.blend(t)), l0, l1, r(lk), r(self._pulse(n, t)), *map(r, n.size(t))))
        edges = []
        for e in self.edges.values():
            p = self._appear(e.draw, e.hide, t, DRAW_S)
            if p <= 0:
                edges.append(None)
                continue
            s0, s1, sk = e.state.at(t)
            label = 1.0 if e.draw == -math.inf else clamp((t - e.draw - DRAW_S + 0.15) / 0.3)
            edges.append((r(p), e.hide is not None and t >= e.hide, STATES.index(s0), STATES.index(s1), r(sk),
                          r(e.dim.blend(t)), r(label), *map(r, self.nodes[e.a].pos(t)),
                          *map(r, self.nodes[e.b].pos(t)), *map(r, self.nodes[e.a].size(t)),
                          *map(r, self.nodes[e.b].size(t))))
        groups = []
        for g in self.groups.values():
            p = self._appear(g.show, g.hide, t, ENTER_S)
            groups.append(None if p <= 0 else (r(p), r(g.dim.blend(t)),
                                               tuple(r(v) for m in g.members
                                                     for v in (*self.nodes[m].pos(t), *self.nodes[m].size(t)))))
        flows = []
        for f in self.flows:
            out = (t - f["t"]) / f["dur"]
            back = (t - f["t"] - f["dur"] - HOLD_S) / f["dur"] if f.get("back") else -1.0
            flows.append((r(out) if 0 <= out <= 1 else -1.0, r(back) if 0 <= back <= 1 else -1.0))
        return tuple(groups), tuple(edges), tuple(nodes), tuple(flows)

    # ---------- drawing (2x local coordinates) ----------
    def _xy(self, x, y):
        return (x - self.area[0]) * SS, (y - self.area[1]) * SS

    def _group(self, d, g: Group, s):
        p, dim, centres = s
        a = EASE["out_cubic"](p) * (1 - 0.65 * dim)
        boxes = []
        for k in range(len(g.members)):
            cx, cy, w, h = centres[4 * k:4 * k + 4]
            boxes.append((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))
        pad, top = 30, (64 if g.label else 30)
        X0, Y0 = self._xy(min(b[0] for b in boxes) - pad, min(b[1] for b in boxes) - top)
        X1, Y1 = self._xy(max(b[2] for b in boxes) + pad, max(b[3] for b in boxes) + pad)
        st = self.st
        d.rounded_rectangle([X0, Y0, X1, Y1], 30 * SS, fill=rgb(st["bg2"]) + (round(170 * a),),
                            outline=rgb(st["line"]) + (round(255 * a),), width=3 * SS)
        if g.label:
            d.text((X0 + 26 * SS, Y0 + 32 * SS), g.label, font=self.small, fill=rgb(st["muted"]) + (round(255 * a),),
                   anchor="lm")

    def _edge(self, d, e: Edge, s):
        p, hiding, s0, s1, sk, dim, label, ax, ay, bx, by, aw, ah, bw, bh = s
        path = Path(route_points(e.route, Box(self.nodes[e.a].shape, aw, ah), (ax, ay),
                                 Box(self.nodes[e.b].shape, bw, bh), (bx, by)))
        frac = 1.0 if hiding else EASE["in_out_sine"](p)
        fade = (p if hiding else 1.0) * (1 - 0.7 * dim)
        col = _mix(self.hot[STATES[s0]], self.hot[STATES[s1]], sk) + (round(255 * fade),)
        L = path.length * frac
        pts = [self._xy(x, y) for x, y in path.upto(max(L - 14, 0.5))]        # stop short of the arrowhead
        if len(pts) >= 2:
            d.line(pts, fill=col, width=round((5 + 2 * _lit(s0, s1, sk)) * SS), joint="curve")
        x, y, ang = path.point_at(L)
        hx, hy = self._xy(x, y)
        A = 24 * SS
        d.polygon([(hx, hy), (hx - A * math.cos(ang - 0.45), hy - A * math.sin(ang - 0.45)),
                   (hx - A * math.cos(ang + 0.45), hy - A * math.sin(ang + 0.45))], fill=col)
        la = label * fade
        if e.label and la > 0:
            self._edge_label(d, e.label, path, la)

    def _edge_label(self, d, label, path: Path, alpha: float):
        """Beside the connector's midpoint, below a horizontal line or right of a vertical one: token labels ride
        above their token, so the two never collide."""
        mx, my, ang = path.point_at(path.length / 2)
        nx, ny = -math.sin(ang), math.cos(ang)
        if ny < -1e-6 or (abs(ny) <= 1e-6 and nx < 0):
            nx, ny = -nx, -ny
        tw = self.small.getlength(label) / SS
        off = abs(nx) * (tw / 2 + 14) + abs(ny) * 22 + 22         # clear of a passing token's glow
        X, Y = self._xy(mx + nx * off, my + ny * off)
        a = round(255 * alpha)
        d.rounded_rectangle([X - (tw / 2 + 14) * SS, Y - 22 * SS, X + (tw / 2 + 14) * SS, Y + 22 * SS], 22 * SS,
                            fill=rgb(self.st["bg"]) + (round(220 * alpha),))
        d.text((X, Y), label, font=self.small, fill=rgb(self.st["muted"]) + (a,), anchor="mm")

    @staticmethod
    def _shape(d, shape, cx, cy, w, h, fill, outline=None, width=0):
        box = [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]
        if shape == "circle":
            d.ellipse(box, fill=fill, outline=outline, width=width)
        elif shape == "diamond":
            d.polygon([(cx, cy - h / 2), (cx + w / 2, cy), (cx, cy + h / 2), (cx - w / 2, cy)], fill=fill,
                      outline=outline, width=width)
        else:
            d.rounded_rectangle(box, h / 2 if shape == "pill" else 22 * SS, fill=fill, outline=outline, width=width)

    def _node(self, d, n: Node, s):
        appear, entering, x, y, s0, s1, sk, dim, l0, l1, lk, pulse, nw, nh = s
        st = self.st
        a = EASE["out_cubic"](appear) * (1 - 0.68 * dim)
        scale = (0.86 + 0.14 * EASE["out_back"](appear) if entering else 1.0) * (1 + 0.04 * pulse)
        w, h = nw * scale * SS, nh * scale * SS
        cx, cy = self._xy(x, y)
        (f0, o0), (f1, o1) = self.colours[STATES[s0]], self.colours[STATES[s1]]
        if pulse > 0:                                   # soft halo while a pulse runs
            g = 14 * SS * pulse
            self._shape(d, n.shape, cx, cy, w + 2 * g, h + 2 * g, o1 + (round(60 * pulse * a),))
        self._shape(d, n.shape, cx, cy, w, h, _mix(f0, f1, sk) + (round(255 * a),),
                    _mix(o0, o1, sk) + (round(255 * a),), round((3 + 2 * _lit(s0, s1, sk)) * SS))
        ty = cy - (20 * SS if n.sub else 0)
        for text, k in (((l0, 1 - lk), (l1, lk)) if l0 != l1 else ((l1, 1.0),)):
            if k > 0:                                   # a changed label crossfades in place
                d.multiline_text((cx, ty), text, font=self.font, fill=rgb(st["card_ink"]) + (round(255 * a * k),),
                                 anchor="mm", align="center", spacing=10 * SS)
        if n.sub:
            d.text((cx, cy + 32 * SS), n.sub, font=self.sub_font, fill=rgb(st["muted"]) + (round(255 * a),),
                   anchor="mm")
        if s1 in (2, 3) or (s0 in (2, 3) and sk < 1):   # a small check / cross badge for done / error
            which, k = (s1, sk) if s1 in (2, 3) else (s0, 1 - sk)
            col = o1 if which == s1 else o0
            R = 20 * SS
            if n.shape in ("box", "pill"):
                bx, by = cx + w / 2 - 6 * SS, cy - h / 2 + 6 * SS
            else:
                bx, by = cx + w * 0.3, cy - h * 0.3
            d.ellipse([bx - R, by - R, bx + R, by + R], fill=col + (round(255 * k * a),))
            ink = rgb(st["bg"]) + (round(255 * k * a),)
            if which == 2:
                d.line([(bx - 9 * SS, by), (bx - 2 * SS, by + 7 * SS), (bx + 10 * SS, by - 8 * SS)], fill=ink,
                       width=5 * SS, joint="curve")
            else:
                for sy in (-1, 1):
                    d.line([(bx - 8 * SS, by - 8 * SS * sy), (bx + 8 * SS, by + 8 * SS * sy)], fill=ink, width=5 * SS)

    def _flow_path(self, f: dict, reverse=False) -> Path:
        pts = []
        for c in f["chain"]:
            e = self.edges[c]
            A, B = self.nodes[e.a], self.nodes[e.b]
            pts += route_points(e.route, A.box(f["t"]), A.pos(f["t"]), B.box(f["t"]), B.pos(f["t"]))
        return Path(pts[::-1] if reverse else pts)

    def _token(self, d, f: dict, k: float, reverse: bool, part: str):
        colour = rgb(self.st["accent" if reverse else "accent2"])
        label = f.get("back") if reverse else f.get("label")
        path = self._flow_path(f, reverse != bool(f.get("reverse")))
        pos = EASE[f["ease"]](k)
        x, y, ang = path.point_at(pos * path.length)
        X, Y = self._xy(x, y)
        fade = min(1.0, k * 6, (1 - k) * 6 + 0.4)
        r = 16 * SS
        if part == "dot":                               # under the nodes: it passes through them
            d.ellipse([X - r * 1.9, Y - r * 1.9, X + r * 1.9, Y + r * 1.9], fill=colour + (round(55 * fade),))
            d.ellipse([X - r, Y - r, X + r, Y + r], fill=colour + (round(255 * fade),))
            return
        if not label:
            return
        if len(f["chain"]) > 1:                         # long trips: the label rides along, fading at the ends
            a = clamp(min(pos / 0.06, (1 - pos) / 0.06)) * fade
        else:                                           # one hop: only mid-trip, never over a node
            a = clamp(min((pos - 0.15) / 0.12, (0.85 - pos) / 0.12)) * fade
        if a > 0:
            A = round(255 * a)
            tw = self.small.getlength(label)
            if abs(math.sin(ang)) > 0.7:                # travelling up or down: beside the token (left; connector
                bx0, by0 = X - r - 12 * SS - tw - 32 * SS, Y - 24 * SS     # labels sit on the right)
            else:                                       # otherwise above it
                bx0, by0 = X - tw / 2 - 16 * SS, Y - r - 60 * SS
            d.rounded_rectangle([bx0, by0, bx0 + tw + 32 * SS, by0 + 48 * SS], 24 * SS,
                                fill=rgb(self.st["card"]) + (A,), outline=colour + (A,), width=2 * SS)
            d.text((bx0 + tw / 2 + 16 * SS, by0 + 24 * SS), label, font=self.small, fill=colour + (A,), anchor="mm")

    def layer(self, state: tuple) -> Image.Image:
        """The finished diagram layer for a state. Depends only on the state, never on what was drawn before."""
        if state in self._cache:
            self._cache.move_to_end(state)
            return self._cache[state]
        groups, edges, nodes, flows = state
        x0, y0, x1, y1 = self.area
        big = Image.new("RGBA", ((x1 - x0) * SS, (y1 - y0) * SS), (0, 0, 0, 0))
        d = ImageDraw.Draw(big, "RGBA")             # blend translucent fills (halos, frames) instead of replacing
        for g, s in zip(self.groups.values(), groups):
            if s:
                self._group(d, g, s)
        for e, s in zip(self.edges.values(), edges):
            if s:
                self._edge(d, e, s)
        tokens = [(f, k, rev) for f, (out, back) in zip(self.flows, flows) for k, rev in ((out, False), (back, True))
                  if k >= 0]
        for f, k, rev in tokens:
            self._token(d, f, k, rev, "dot")
        for n, s in zip(self.nodes.values(), nodes):
            if s:
                self._node(d, n, s)
        for f, k, rev in tokens:
            self._token(d, f, k, rev, "label")
        small = big.reduce(SS)                      # 2x2 box average: the exact supersampling filter, no ringing
        self._cache[state] = small
        if len(self._cache) > CACHE_LAYERS:
            self._cache.popitem(last=False)
        return small

    def draw(self, canvas: Image.Image, t: float, p: float = 1.0) -> None:
        canvas.alpha_composite(self.layer(self.state(t)), self.area[:2])
