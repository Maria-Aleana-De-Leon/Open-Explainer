"""Split generated sprite sheets into individual transparent PNGs, deterministically, and check the results.

Image generators rarely place a grid exactly: cells drift, a pointing arm reaches past the cell line, hair touches
the neighbour, and "transparent" art comes back slightly see-through (opaque pixels at alpha ~253) with faint
alpha noise around it. So nothing here assumes equal cells:

1. alpha is cleaned (noise <= 8 -> 0, >= 240 -> 255) so the art is fully opaque and the background fully clear;
2. rows are found where the sheet's alpha profile is lowest near the expected row lines, then, row by row, the
   cuts between items are found the same way (each cut is searched in a window around its expected place);
3. every item is cropped to its own artwork, and either trimmed (stickers, mouth sprites) or placed on one shared
   canvas, centred horizontally and standing on the same bottom line (poses, expressions), so a set stays aligned;
4. every result is checked (count, size, alpha, empty or cut-off art, cuts through artwork) and written with a
   manifest and a labelled review sheet for a person to approve.

Kinds and the names they write (the mascot kinds use the mascot file-name contract, docs/mascot/ASSETS.md):

    poses        3x3 -> neutral, pose-wave, pose-point-right, pose-point-left, pose-present, pose-think,
                        pose-walk-1, pose-walk-2, pose-walk-3          (a full-body mascot folder)
    expressions  3x3 -> neutral, expr-happy, expr-excited, expr-surprised, expr-thinking, expr-confused,
                        expr-worried, expr-sad, expr-frustrated        (a head-and-shoulders mascot folder)
    mouthless    3x3 -> base-neutral ... base-frustrated               (mouthless bases; not used by the renderer)
    mouths       4+3 -> sprite-ah, sprite-ee, sprite-oh, sprite-closed, sprite-fv, sprite-l, sprite-m
                        (isolated mouths, provisional names: verify each one by eye)
    stickers     5x5 -> lightbulb ... star                             (overlay pictures)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .errors import OexError

NOISE, SOLID = 8, 240        # alpha at or below NOISE is background; at or above SOLID is fully opaque artwork
EXPR = ["neutral", "happy", "excited", "surprised", "thinking", "confused", "worried", "sad", "frustrated"]
KINDS = {
    "poses": {"rows": [3, 3, 3], "fit": "aligned", "names": [
        "neutral", "pose-wave", "pose-point-right", "pose-point-left", "pose-present", "pose-think",
        "pose-walk-1", "pose-walk-2", "pose-walk-3"], "min_height": 400},
    "expressions": {"rows": [3, 3, 3], "fit": "aligned", "names": ["neutral"] + [f"expr-{e}" for e in EXPR[1:]],
                    "min_height": 400},
    "mouthless": {"rows": [3, 3, 3], "fit": "aligned", "names": [f"base-{e}" for e in EXPR], "min_height": 400},
    "mouths": {"rows": [4, 3], "fit": "trim", "names": [
        "sprite-ah", "sprite-ee", "sprite-oh", "sprite-closed", "sprite-fv", "sprite-l", "sprite-m"]},
    "stickers": {"rows": [5] * 5, "fit": "trim", "names": [
        "lightbulb", "question", "brain", "lightning", "magnifier", "check", "cross", "warning", "trophy", "target",
        "book", "clock", "calendar", "checklist", "laptop", "heart", "thumbs-up", "bell", "speech-bubble", "play",
        "arrow-right", "arrow-left", "arrow-down", "exclamation", "star"]},
}
# isolated mouth sprite -> mascot mouth file (docs/mascot/ASSETS.md). "closed" is the neutral mouth itself; there is
# no rounded "oo" sprite in the sheet, so the mascot falls back for it.
MOUTH_MAP = {"sprite-ah": "mouth-ah", "sprite-ee": "mouth-ee", "sprite-oh": "mouth-oh", "sprite-fv": "mouth-fv",
             "sprite-l": "mouth-half", "sprite-m": "mouth-mbp"}


def clean_alpha(im: Image.Image) -> Image.Image:
    """Fully clear background and fully opaque artwork; anti-aliased edges keep their in-between alpha."""
    a = np.asarray(im.convert("RGBA")).copy()
    al = a[..., 3]
    al[al <= NOISE] = 0
    al[al >= SOLID] = 255
    a[al == 0, :3] = 0
    return Image.fromarray(a, "RGBA")


def _cuts(profile: np.ndarray, n: int, lo: int, hi: int, window: float = 0.3) -> list[tuple[int, float]]:
    """n-1 cut positions in [lo, hi), with how much artwork each crosses (relative to the profile's peak).

    Real empty gaps come first: of all the gaps in the profile, the n-1 that best match the expected boundaries, in
    order (so unequal items and art that reaches past the regular cell line are handled). If there are fewer gaps
    than boundaries (items touch), the rest are cut where the profile is lowest near their expected place."""
    peak, cell = float(profile.max()) or 1.0, (hi - lo) / n
    expected = [lo + cell * k for k in range(1, n)]
    empty = profile[lo:hi] <= peak * 0.002
    gaps, i = [], 0
    while i < len(empty):
        if empty[i]:
            j = i
            while j < len(empty) and empty[j]:
                j += 1
            gaps.append((lo + i, lo + j))
            i = j
        else:
            i += 1
    gaps = [g for g in gaps if g[0] > lo and g[1] < hi]              # inner gaps only
    m, G = len(expected), len(gaps)
    if G >= m:                                                       # pick m gaps in order, closest to expected
        INF = float("inf")
        cost = [[INF] * (G + 1) for _ in range(m + 1)]
        cost[0] = [0.0] * (G + 1)
        for k in range(1, m + 1):
            for g in range(k, G + 1):
                centre = (gaps[g - 1][0] + gaps[g - 1][1]) / 2
                cost[k][g] = min(cost[k][g - 1], cost[k - 1][g - 1] + abs(centre - expected[k - 1]))
        out, g = [], G
        for k in range(m, 0, -1):
            while cost[k][g] == cost[k][g - 1]:
                g -= 1
            out.append((int((gaps[g - 1][0] + gaps[g - 1][1]) / 2), 0.0))
            g -= 1
        chosen = sorted(out)
        if all(abs(c - e) < cell * 0.75 for (c, _), e in zip(chosen, expected)):
            return chosen
    out = []
    for c in expected:                                               # touching items: the emptiest place nearby
        a, b = int(max(lo + 1, c - cell * window)), int(min(hi - 1, c + cell * window))
        seg = profile[a:b]
        mn = seg.min()
        idx = np.nonzero(seg <= mn + peak * 0.002)[0]
        runs = np.split(idx, np.nonzero(np.diff(idx) > 1)[0] + 1)
        best = max(runs, key=lambda r: (len(r), -abs(a + r.mean() - c)))
        out.append((int(a + best.mean()), float(mn) / peak))
    return out


def _extent(profile: np.ndarray) -> tuple[int, int]:
    nz = np.nonzero(profile > 0)[0]
    if not len(nz):
        raise OexError("the sheet is empty (fully transparent)", "check that the PNG has artwork and an alpha channel")
    return int(nz[0]), int(nz[-1]) + 1


def find_cells(alpha: np.ndarray, rows: list[int]) -> list[dict]:
    """Cell boxes (x0, y0, x1, y1) in reading order, with how much artwork each cut had to cross."""
    solid = (alpha > NOISE).astype(np.float64)
    y_lo, y_hi = _extent(solid.sum(1))
    ycuts = _cuts(solid.sum(1), len(rows), y_lo, y_hi)
    ys = [y_lo] + [c for c, _ in ycuts] + [y_hi]
    cells = []
    for r, count in enumerate(rows):
        band = solid[ys[r]:ys[r + 1]]
        x_lo, x_hi = _extent(band.sum(0))
        xcuts = _cuts(band.sum(0), count, x_lo, x_hi)
        xs = [x_lo] + [c for c, _ in xcuts] + [x_hi]
        crossed_y = max([ycuts[r - 1][1] if r else 0.0, ycuts[r][1] if r < len(ycuts) else 0.0])
        for i in range(count):
            crossed_x = max([xcuts[i - 1][1] if i else 0.0, xcuts[i][1] if i < len(xcuts) else 0.0])
            cells.append({"box": (xs[i], ys[r], xs[i + 1], ys[r + 1]), "crossed": round(max(crossed_x, crossed_y), 4)})
    return cells


def split(sheet: Path, kind: str, out: Path, names: list[str] | None = None, pad: int = 12,
          canvas: tuple[int, int] | None = None) -> dict:
    """Split one sheet into named PNGs in `out`, with split/manifest.json and split/review.png (in a subfolder, so
    a mascot folder holds only mascot images). `canvas` (w, h) fixes the shared canvas of an aligned kind, so two
    sheets of the same character (e.g. expressions and their mouthless bases) line up. Returns the manifest."""
    if kind not in KINDS:
        raise OexError(f"unknown kind '{kind}'", f"use one of: {', '.join(KINDS)}")
    spec = KINDS[kind]
    names = names or spec["names"]
    if len(names) != sum(spec["rows"]):
        raise OexError(f"{len(names)} names for {sum(spec['rows'])} items", "give one name per item, in reading order")
    src = Image.open(sheet)
    problems, warnings = [], []
    if src.mode not in ("RGBA", "LA", "PA") and "transparency" not in src.info:
        raise OexError(f"{sheet.name} has no transparency (alpha channel), so items cannot be told from the background",
                       "ask the image generator for a transparent PNG, or remove the background first")
    im = clean_alpha(src)
    a = np.asarray(im)[..., 3]
    cells = find_cells(a, spec["rows"])
    items = []
    for name, cell in zip(names, cells):
        x0, y0, x1, y1 = cell["box"]
        crop = im.crop((x0, y0, x1, y1))
        ca = np.asarray(crop)[..., 3]
        ys, xs = np.nonzero(ca > NOISE)
        it = {"name": name, "cell": [x0, y0, x1, y1], "crossed": cell["crossed"], "warnings": []}
        if not len(xs):
            it["warnings"].append("empty cell")
            problems.append(f"{name}: empty cell - the sheet has fewer items than expected or a different layout")
            items.append(it)
            continue
        bx0, by0, bx1, by1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
        it["art"] = [x0 + bx0, y0 + by0, x0 + bx1, y0 + by1]
        it["image"] = crop.crop((bx0, by0, bx1, by1))
        if cell["crossed"] > 0.25:
            problems.append(f"{name}: a cut goes through the middle of artwork - the sheet does not have the "
                            f"{'+'.join(map(str, spec['rows']))} layout of a '{kind}' sheet")
        elif cell["crossed"] > 0.01:
            it["warnings"].append("a cut crosses artwork: it touches its neighbour; check its edges")
        edges = [bx0 == 0 and x0 > 0, by0 == 0 and y0 > 0, bx1 == crop.width and x1 < im.width,
                 by1 == crop.height and y1 < im.height]
        if any(edges) and cell["crossed"] > 0:
            it["warnings"].append("artwork runs into the cell edge: it may be cut off")
        it["opaque"] = round(float((ca >= SOLID).sum()) / max(1, (ca > NOISE).sum()), 3)
        items.append(it)
    present = [it for it in items if "image" in it]
    if spec["fit"] == "aligned" and present:              # one shared canvas: centred, standing on one line
        W = max(it["image"].width for it in present) + 2 * pad
        H = max(it["image"].height for it in present) + 2 * pad
        if canvas:
            if canvas[0] < W or canvas[1] < H:
                raise OexError(f"--canvas {canvas[0]}x{canvas[1]} is smaller than the artwork ({W}x{H})",
                               f"use at least {W}x{H}")
            W, H = canvas
        for it in present:
            c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            c.alpha_composite(it["image"], ((W - it["image"].width) // 2, H - pad - it["image"].height))
            it["image"] = c
        heights = [it["art"][3] - it["art"][1] for it in present]
        if max(heights) > 1.08 * min(heights):
            warnings.append(f"item heights differ by {100 * (max(heights) / min(heights) - 1):.0f}%: the character "
                            "may have changed size between cells; the mascot importer corrects small differences")
        if H < spec.get("min_height", 0):
            problems.append(f"items are only {H} px tall (need {spec['min_height']}+): generate the sheet larger")
    else:
        for it in present:
            w, h = it["image"].size
            c = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
            c.alpha_composite(it["image"], (pad, pad))
            it["image"] = c
    out.mkdir(parents=True, exist_ok=True)
    for it in present:
        it["file"] = f"{it['name']}.png"
        it["size"] = list(it["image"].size)
        it["image"].save(out / it["file"])
        warnings += [f"{it['name']}: {w}" for w in it["warnings"]]
    manifest = {"sheet": sheet.name, "kind": kind, "layout": "+".join(map(str, spec["rows"])),
                "sheet_size": list(src.size), "items": [{k: v for k, v in it.items() if k != "image"} for it in items],
                "problems": problems, "warnings": warnings, "ok": not problems}
    (out / "split").mkdir(exist_ok=True)
    (out / "split" / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    review(present, out / "split" / "review.png", kind)
    return manifest


def review(items: list[dict], path: Path, kind: str) -> None:
    """A labelled contact sheet on a checkerboard, so missing transparency or cut-off art is easy to see."""
    if not items:
        return
    cols = 5 if len(items) > 9 else (4 if len(items) == 7 else 3)
    tw = 240
    th = max(round(tw * it["image"].height / it["image"].width) for it in items)
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (tw + 16) + 16, rows * (th + 46) + 16), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    for k, it in enumerate(items):
        x, y = 16 + (k % cols) * (tw + 16), 16 + (k // cols) * (th + 46)
        img = it["image"]
        s = min(tw / img.width, th / img.height)
        img = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)
        bg = Image.new("RGBA", (tw, th), (236, 236, 236, 255))
        bd = ImageDraw.Draw(bg)
        for yy in range(0, th, 12):
            for xx in range(0, tw, 12):
                if (xx // 12 + yy // 12) % 2:
                    bd.rectangle([xx, yy, xx + 11, yy + 11], fill=(214, 214, 214, 255))
        bg.alpha_composite(img, ((tw - img.width) // 2, (th - img.height) // 2))
        sheet.paste(bg.convert("RGB"), (x, y))
        flag = " !" if it["warnings"] else ""
        d.text((x, y + th + 8), f"{it['name']}{flag}", fill=(200, 40, 40) if flag else (30, 30, 30))
    sheet.save(path)


def place_mouths(mascot: Path, sprites: Path, box: tuple[int, int, int], base: Path | None = None,
                 mapping: dict | None = None) -> list[str]:
    """Paint isolated mouth sprites onto a face to make the mascot's mouth images (`neutral.png` with only the
    mouth changed, as the importer expects). `box` = (centre x, centre y, width) of the mouth, in pixels of the
    face image, measured by a person.

    With `base` (a mouthless face, e.g. `base-neutral.png` from the mouthless sheet, on the same canvas as
    neutral.png), every image is painted on that base: neutral.png = base + the closed mouth, mouth-*.png = base +
    each sprite, so they differ only at the mouth. Without it, sprites are painted over neutral.png's own mouth and
    must cover it completely. Either way a person checks the results (review.png from `oex mascot prepare`)."""
    neutral = mascot / "neutral.png"
    face = base or neutral
    if not face.exists():
        raise OexError(f"{face} not found", "split the expression or pose sheet first (it writes neutral.png)")
    img0 = clean_alpha(Image.open(face))
    cx, cy, width = box
    if not (0 < cx < img0.width and 0 < cy < img0.height and 4 <= width < img0.width):
        raise OexError(f"mouth box {box} is outside {face.name} ({img0.width}x{img0.height})",
                       "give the centre x, centre y and width of the mouth in that image's pixels")
    if base and neutral.exists() and Image.open(neutral).size != img0.size:
        raise OexError(f"{base.name} is {img0.size}, neutral.png is {Image.open(neutral).size}",
                       "split both sheets with the same kind so they share one canvas size")

    def paint(sprite: str):
        f = sprites / f"{sprite}.png"
        if not f.exists():
            return None
        sp = clean_alpha(Image.open(f))
        sa = np.asarray(sp)[..., 3]
        ys, xs = np.nonzero(sa > NOISE)
        sp = sp.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
        s = width / sp.width
        sp = sp.resize((max(1, round(sp.width * s)), max(1, round(sp.height * s))), Image.LANCZOS)
        img = img0.copy()
        img.alpha_composite(sp, (round(cx - sp.width / 2), round(cy - sp.height / 2)))
        return img

    written = []
    if base:
        closed = paint("sprite-closed")
        if closed is None:
            raise OexError("sprite-closed.png not found", "the closed mouth makes neutral.png on a mouthless base")
        closed.save(neutral)
        written.append("neutral.png")
    for sprite, target in (mapping or MOUTH_MAP).items():
        img = paint(sprite)
        if img is not None:
            img.save(mascot / f"{target}.png")
            written.append(f"{target}.png")
    if len(written) <= (1 if base else 0):
        raise OexError(f"no mouth sprites found in {sprites}", "split the mouth sheet first: oex assets split --kind mouths")
    return written
