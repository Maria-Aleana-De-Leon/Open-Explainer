"""Isometric 3D drawing for animated diagrams (`"look": "3d"`): flat-shaded solids and illustrated objects.

Every face is one solid colour (lit top, mid right, darker left) with a thin darker edge: depth without gradients.
World units: a node stands on the unit square centred on its base point; x runs down-right, y down-left, z up.
`Iso` projects world points to screen pixels around a base point; the objects are original drawings built from
boxes, cylinders, plates and lines, so they stay crisp at any size and recolour with the film's style.
"""
from __future__ import annotations

import math

C = math.cos(math.radians(30))
TOP, RIGHT, LEFT = 1.0, 0.8, 0.64            # face brightness: top, right-facing (+x), left-facing (+y)

# fixed object colours (style colours are added per film: accent, accent2, good, bad)
WHITE, STEEL, DARK = (236, 240, 246), (150, 162, 182), (56, 64, 80)
GOLD, WOOD, WARN, RED, SKIN = (246, 196, 83), (186, 132, 84), (246, 196, 60), (214, 92, 70), (240, 214, 186)


def shade(c, k):
    return tuple(max(0, min(255, round(v * k))) for v in c[:3])


def mix(a, b, k):
    return tuple(round(x + (y - x) * k) for x, y in zip(a[:3], b[:3]))


def iso_size(u: float) -> tuple[float, float]:
    """Screen width and height of the unit footprint at `u` px per world unit."""
    return 2 * C * u, u


class Iso:
    """Draws world-space shapes around a base point (bx, by) in screen px, `u` px per world unit."""

    def __init__(self, d, bx: float, by: float, u: float, lw: float):
        self.d, self.bx, self.by, self.u, self.lw = d, bx, by, u, max(1, round(lw))

    def P(self, x, y, z=0.0):
        return self.bx + (x - y) * C * self.u, self.by + (x + y) * 0.5 * self.u - z * self.u

    def poly(self, pts, col, edge=True):
        self.d.polygon([self.P(*p) for p in pts], fill=col, outline=shade(col, 0.55) if edge else None,
                       width=self.lw if edge else 0)

    def line(self, pts, col, w):
        self.d.line([self.P(*p) for p in pts], fill=col, width=max(1, round(w * self.u)), joint="curve")

    def dot(self, x, y, z, r, col):
        X, Y = self.P(x, y, z)
        R = r * self.u
        self.d.ellipse([X - R, Y - R, X + R, Y + R], fill=col)

    def box(self, x0, y0, z0, x1, y1, z1, col, top=None):
        self.poly([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], shade(col, LEFT))
        self.poly([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], shade(col, RIGHT))
        self.poly([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], top or col)

    def _ring(self, cx, cy, z, r, a0, a1, n=24):
        return [(cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + r * math.sin(a0 + (a1 - a0) * i / n), z)
                for i in range(n + 1)]

    def cylinder(self, cx, cy, r, z0, z1, col, top=None):
        """Upright cylinder: two flat side tones split at the front, a flat top."""
        q = math.pi / 4
        for a0, a1, k in ((3 * q, q, LEFT), (q, -q, RIGHT)):        # front-left and front-right halves
            self.poly(self._ring(cx, cy, z0, r, a0, a1) + self._ring(cx, cy, z1, r, a1, a0), shade(col, k))
        self.poly(self._ring(cx, cy, z1, r, 0, 2 * math.pi, 48), top or col)

    def plate(self, pts_xz, y, col, t=0.05):
        """A flat shape standing upright in the plane y (facing the viewer's left), `t` thick."""
        if t:
            self.poly([(x, y - t, z) for x, z in pts_xz], shade(col, 0.5))
        self.poly([(x, y, z) for x, z in pts_xz], col)

    def flat(self, pts_xy, z, col):
        """A flat shape lying in the horizontal plane z."""
        self.poly([(x, y, z) for x, y in pts_xy], col)

    def vcircle(self, cx, y, cz, r, n=40):
        return [(cx + r * math.cos(2 * math.pi * i / n), cz + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


# ---------- illustrated objects: f(g, pal) drawn on a tile whose top is at z = 0.1; returns nothing ----------

def _robot(g, p):
    g.box(-0.3, -0.3, 0.1, 0.3, 0.3, 0.55, STEEL)
    g.poly([(-0.13, 0.3, 0.24), (0.13, 0.3, 0.24), (0.13, 0.3, 0.42), (-0.13, 0.3, 0.42)], p["accent2"])
    g.box(-0.25, -0.25, 0.6, 0.25, 0.25, 0.98, WHITE)
    for x in (-0.12, 0.1):
        g.dot(x, 0.25, 0.8, 0.065, DARK)
    g.line([(0, 0, 0.98), (0, 0, 1.16)], DARK, 0.04)
    g.dot(0, 0, 1.2, 0.07, p["accent"])


def _person(g, p):
    g.cylinder(0, 0, 0.2, 0.1, 0.72, p["accent2"])
    g.dot(0, 0, 0.94, 0.19, SKIN)
    X, Y = g.P(0, 0, 0.94)
    R = 0.19 * g.u
    g.d.chord([X - R, Y - R, X + R, Y + R], 180, 360, fill=DARK)          # hair: the top half of the head


def _flag(g, p):
    g.cylinder(0, 0, 0.3, 0.1, 0.2, STEEL)
    g.line([(0, 0, 0.2), (0, 0, 1.25)], WHITE, 0.045)
    g.plate([(0, 1.25), (0.52, 1.1), (0, 0.94)], 0, p["accent"], t=0)


def _magnifier(g, p):
    g.line([(0.1, 0, 0.5), (0.36, 0, 0.12)], DARK, 0.11)
    ring = g.vcircle(-0.08, 0, 0.74, 0.38)
    g.plate(ring, 0, STEEL, t=0.08)
    g.plate(g.vcircle(-0.08, 0, 0.74, 0.28), 0.002, mix(p["accent2"], WHITE, 0.45), t=0)
    g.plate(g.vcircle(-0.18, 0, 0.84, 0.08), 0.004, WHITE, t=0)


def _clipboard(g, p):
    g.plate([(-0.3, 0.1), (0.3, 0.1), (0.3, 1.04), (-0.3, 1.04)], 0.05, WOOD, t=0.06)
    g.plate([(-0.24, 0.16), (0.24, 0.16), (0.24, 0.92), (-0.24, 0.92)], 0.052, WHITE, t=0)
    for k, z in enumerate((0.78, 0.66, 0.54, 0.42, 0.3)):
        g.line([(-0.16, 0.054, z), (0.16 if k else 0.04, 0.054, z)], STEEL, 0.035)
    g.box(-0.12, 0.02, 0.98, 0.12, 0.1, 1.1, STEEL)


def _toolbox(g, p):
    g.box(-0.42, -0.26, 0.1, 0.42, 0.26, 0.42, RED)
    g.box(-0.44, -0.28, 0.42, 0.44, 0.28, 0.52, shade(RED, 0.85))
    g.poly([(-0.07, 0.28, 0.36), (0.07, 0.28, 0.36), (0.07, 0.28, 0.46), (-0.07, 0.28, 0.46)], WHITE)
    g.line([(-0.16, 0, 0.52), (-0.16, 0, 0.68), (0.16, 0, 0.68), (0.16, 0, 0.52)], DARK, 0.06)


def _gear(g, p):
    teeth, pts = 8, []
    for i in range(teeth * 4):
        a = 2 * math.pi * i / (teeth * 4)
        r = 0.4 if (i % 4) in (1, 2) else 0.31
        pts.append((r * math.cos(a), 0.62 + r * math.sin(a)))
    g.box(-0.08, -0.08, 0.1, 0.08, 0.08, 0.26, DARK)
    g.plate(pts, 0, STEEL, t=0.1)
    g.plate(g.vcircle(0, 0, 0.62, 0.12), 0.002, DARK, t=0)


def _shield(g, p):
    g.plate([(-0.44, 1.04), (0.44, 1.04), (0.44, 0.62), (0.31, 0.36), (0, 0.13), (-0.31, 0.36), (-0.44, 0.62)],
            0.04, p["accent2"], t=0.08)
    g.line([(-0.2, 0.042, 0.62), (-0.04, 0.042, 0.47), (0.24, 0.042, 0.82)], WHITE, 0.085)


def _plane(g, p):
    g.line([(0, 0, 0.1), (0, 0, 0.5)], STEEL, 0.05)
    g.flat([(-0.14, 0), (0.14, 0), (0.0, -0.64), (-0.2, -0.64)], 0.56, p["accent2"])        # far wing
    g.flat([(-0.62, -0.2), (-0.5, -0.2), (-0.5, 0), (-0.62, 0)], 0.62, p["accent2"])
    g.plate([(-0.62, 0.62), (-0.44, 0.62), (-0.56, 0.92), (-0.66, 0.92)], 0, p["accent"], t=0.03)
    g.box(-0.62, -0.09, 0.5, 0.4, 0.09, 0.68, WHITE)
    g.poly([(0.4, -0.09, 0.68), (0.4, 0.09, 0.68), (0.62, 0, 0.58)], WHITE)                     # nose
    g.poly([(0.4, 0.09, 0.5), (0.4, 0.09, 0.68), (0.62, 0, 0.58)], shade(WHITE, LEFT))
    for x in (-0.36, -0.2, -0.04, 0.12):
        g.dot(x, 0.09, 0.61, 0.03, p["accent2"])
    g.flat([(-0.14, 0), (0.14, 0), (0.0, 0.64), (-0.2, 0.64)], 0.56, p["accent2"])          # near wing
    g.flat([(-0.62, 0), (-0.5, 0), (-0.5, 0.2), (-0.62, 0.2)], 0.62, p["accent2"])


def _document(g, p):
    g.plate([(-0.28, 0.1), (0.28, 0.1), (0.28, 0.86), (0.14, 1.0), (-0.28, 1.0)], 0.03, WHITE, t=0.04)
    g.plate([(0.14, 1.0), (0.14, 0.86), (0.28, 0.86)], 0.032, STEEL, t=0)
    for k, z in enumerate((0.8, 0.68, 0.56, 0.44, 0.32)):
        g.line([(-0.18, 0.034, z), (0.06 if k == 0 else 0.18, 0.034, z)], STEEL, 0.035)


def _files(g, p):
    g.box(-0.42, -0.44, 0.1, 0.42, 0.44, 0.16, GOLD)
    g.box(-0.42, -0.44, 0.16, 0.42, -0.32, 0.42, shade(GOLD, 0.9))      # the folder's back cover, behind the sheets
    for k, z in enumerate((0.17, 0.23)):
        o = 0.04 * k
        g.box(-0.34 + o, -0.38 - o, z, 0.34 + o, 0.38 - o, z + 0.04, WHITE)
    for y in (-0.22, -0.08, 0.06, 0.2):
        g.line([(-0.2, y - 0.04, 0.27), (0.24, y - 0.04, 0.27)], STEEL, 0.03)


def _coins(g, p):
    for x, y, h in sorted(((0.2, -0.16, 0.22), (-0.18, 0.06, 0.4), (0.16, 0.26, 0.12)), key=lambda c: c[0] + c[1]):
        g.cylinder(x, y, 0.17, 0.1, 0.1 + h, GOLD)
        for z in [0.1 + 0.06 * i for i in range(1, int(h / 0.06))]:
            g.line(g._ring(x, y, z, 0.17, math.pi * 0.75, -math.pi * 0.25, 12), shade(GOLD, 0.5), 0.012)


def _trash(g, p):
    g.cylinder(0, 0, 0.28, 0.1, 0.72, STEEL)
    for a in (-0.3, 0.3, 0.8, 1.3):
        g.line([(0.2 * math.cos(a + 0.4), 0.2 * math.sin(a + 0.4), 0.2),
                (0.26 * math.cos(a + 0.4), 0.26 * math.sin(a + 0.4), 0.64)], shade(STEEL, 0.55), 0.03)
    g.cylinder(0, 0, 0.32, 0.72, 0.8, DARK)
    g.line([(-0.1, 0, 0.8), (-0.1, 0, 0.88), (0.1, 0, 0.88), (0.1, 0, 0.8)], DARK, 0.05)


def _warning(g, p):
    g.line([(0, 0, 0.1), (0, 0, 0.4)], STEEL, 0.06)
    g.plate([(-0.52, 0.34), (0.52, 0.34), (0, 1.1)], 0.02, WARN, t=0.05)
    g.line([(0, 0.024, 0.84), (0, 0.024, 0.6)], DARK, 0.075)
    g.dot(0, 0.024, 0.48, 0.045, DARK)


def _calendar(g, p):
    g.plate([(-0.32, 0.1), (0.32, 0.1), (0.32, 0.94), (-0.32, 0.94)], 0.05, WHITE, t=0.08)
    g.plate([(-0.32, 0.74), (0.32, 0.74), (0.32, 0.94), (-0.32, 0.94)], 0.052, RED, t=0)
    for x in (-0.16, 0.16):
        g.line([(x, 0.054, 0.88), (x, 0.054, 1.02)], DARK, 0.05)
    for r, z in enumerate((0.6, 0.44, 0.28)):
        for c, x in enumerate((-0.2, -0.07, 0.07, 0.2)):
            col = p["accent"] if (r, c) == (1, 2) else STEEL
            g.plate([(x - 0.045, z - 0.045), (x + 0.045, z - 0.045), (x + 0.045, z + 0.045), (x - 0.045, z + 0.045)],
                    0.054, col, t=0)


def _server(g, p):
    for z in (0.1, 0.38, 0.66):
        g.box(-0.32, -0.3, z, 0.32, 0.3, z + 0.25, DARK, top=shade(DARK, 1.35))
        g.dot(0.2, 0.3, z + 0.125, 0.035, p["good"])
        g.line([(-0.22, 0.3, z + 0.125), (0.05, 0.3, z + 0.125)], STEEL, 0.03)


def _globe(g, p):
    g.cylinder(0, 0, 0.22, 0.1, 0.18, STEEL)
    g.line([(0, 0, 0.18), (0, 0, 0.3)], STEEL, 0.05)
    X, Y = g.P(0, 0, 0.66)
    R = 0.36 * g.u
    g.d.ellipse([X - R, Y - R, X + R, Y + R], fill=p["accent2"], outline=shade(p["accent2"], 0.55), width=g.lw)
    land = shade(p["good"], 0.9)
    g.d.polygon([(X - R * 0.55, Y - R * 0.5), (X - R * 0.05, Y - R * 0.7), (X + R * 0.1, Y - R * 0.2),
                 (X - R * 0.3, Y + R * 0.05), (X - R * 0.6, Y - R * 0.1)], fill=land)
    g.d.polygon([(X + R * 0.25, Y + R * 0.1), (X + R * 0.7, Y + R * 0.0), (X + R * 0.5, Y + R * 0.6),
                 (X + R * 0.2, Y + R * 0.45)], fill=land)


ICONS = {
    "robot": (_robot, 1.29), "person": (_person, 1.15), "flag": (_flag, 1.27), "magnifier": (_magnifier, 1.27),
    "clipboard": (_clipboard, 1.22), "toolbox": (_toolbox, 0.9), "gear": (_gear, 1.14), "shield": (_shield, 1.3),
    "plane": (_plane, 1.29), "document": (_document, 1.17), "files": (_files, 0.87), "coins": (_coins, 0.71),
    "trash": (_trash, 1.05), "warning": (_warning, 1.14), "calendar": (_calendar, 1.14), "server": (_server, 1.24),
    "globe": (_globe, 1.04),
}
"""name -> (draw function, how far it rises above its base point on screen, in world units)."""

SHAPE_HEIGHT = {"box": 0.55, "pill": 0.3, "circle": 0.5, "diamond": 0.95}


def solid(g: Iso, shape: str, col):
    """A plain node as a solid: box -> block, pill -> low slab, circle -> cylinder, diamond -> block with a
    pyramid roof (a decision)."""
    if shape == "circle":
        g.cylinder(0, 0, 0.5, 0, 0.5, col)
    elif shape == "diamond":
        g.box(-0.5, -0.5, 0, 0.5, 0.5, 0.3, col)
        roof = mix(col, WHITE, 0.12)
        g.poly([(-0.5, -0.5, 0.3), (0.5, -0.5, 0.3), (0, 0, 0.95)], roof)                # back faces first
        g.poly([(-0.5, -0.5, 0.3), (-0.5, 0.5, 0.3), (0, 0, 0.95)], roof)
        g.poly([(0.5, -0.5, 0.3), (0.5, 0.5, 0.3), (0, 0, 0.95)], shade(roof, RIGHT))
        g.poly([(-0.5, 0.5, 0.3), (0.5, 0.5, 0.3), (0, 0, 0.95)], shade(roof, LEFT))
    else:
        g.box(-0.5, -0.5, 0, 0.5, 0.5, SHAPE_HEIGHT.get(shape, 0.55), col)


def floor_grid(d, W: int, H: int, step: float, col):
    """An isometric floor grid (two families of lines at +-30 degrees), flat and uniform."""
    k = math.tan(math.radians(30))
    span = W + H / k
    n = int(span / step) + 2
    for i in range(-n, n + 1):
        x = i * step
        d.line([(x, 0), (x + H / k, H)], fill=col, width=1)
        d.line([(x, 0), (x - H / k, H)], fill=col, width=1)
