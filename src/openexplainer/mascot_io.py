"""Image helpers for mascot preparation: alpha handling, background removal, trimming, small-mask labelling."""
from __future__ import annotations

from collections import deque

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .errors import OexError


def _rgba(im: Image.Image) -> np.ndarray:
    return np.asarray(im.convert("RGBA")).astype(np.float32)


def _on_white(a: np.ndarray) -> np.ndarray:
    al = a[..., 3:4] / 255.0
    return a[..., :3] * al + 255 * (1 - al)


def _gray(a: np.ndarray) -> np.ndarray:
    return _on_white(a).mean(-1)


def _label(mask: np.ndarray) -> tuple[np.ndarray, int]:
    """4-connected component labelling (small masks only; analysis resolution)."""
    lab = np.zeros(mask.shape, np.int32)
    h, w = mask.shape
    n = 0
    for y0, x0 in zip(*np.nonzero(mask)):
        if lab[y0, x0]:
            continue
        n += 1
        lab[y0, x0] = n
        q = deque([(y0, x0)])
        while q:
            y, x = q.popleft()
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = n
                    q.append((yy, xx))
    return lab, n


def _clean(mask: np.ndarray, k: int = 3) -> np.ndarray:
    im = Image.fromarray((mask * 255).astype(np.uint8))
    im = im.filter(ImageFilter.MinFilter(k)).filter(ImageFilter.MaxFilter(k))
    return np.asarray(im) > 127


def has_real_alpha(im: Image.Image) -> bool:
    if im.mode not in ("RGBA", "LA", "PA") and "transparency" not in im.info:
        return False
    a = np.asarray(im.convert("RGBA"))[..., 3]
    return (a < 16).mean() > 0.03


def remove_background(im: Image.Image, tol: int = 40) -> tuple[Image.Image, str]:
    """Flood-fill the background from the border. Handles plain backgrounds and the fake 'transparency'
    checkerboard image generators sometimes paint. Returns (RGBA image, description)."""
    rgb = im.convert("RGB")
    a = np.asarray(rgb).astype(np.int16)
    border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    light = (border.min(1) > 150).mean()
    kind = "checkerboard" if (border.std(0).mean() > 8 and light > 0.9) else "plain"
    if border.std(0).mean() > 40 and light < 0.9:
        raise OexError("background is not plain or transparent; cannot remove it reliably",
                       "re-export the image with a transparent background (prompt 7 in prompts/), or remove it in "
                       "an editor, then run `oex mascot prepare` again")
    sentinel = (255, 0, 254)
    work = rgb.copy()
    h, w = a.shape[:2]
    if kind == "checkerboard":
        # the two checker colours alternate, so a seeded flood fill stops at every square: flatten them first
        flat = border.reshape(-1, 3)
        cols = np.unique((flat // 8) * 8, axis=0, return_counts=True)
        top = cols[0][np.argsort(-cols[1])[:2]].astype(np.int16) + 4
        near = np.zeros(a.shape[:2], bool)
        for c in top:
            near |= np.abs(a - c).max(-1) <= 14
        arr = np.asarray(work).copy()
        arr[near] = (255, 255, 255)
        work = Image.fromarray(arr)
        kind = "checkerboard"
    step = max(1, min(w, h) // 64)
    pts = [(x, 0) for x in range(0, w, step)] + [(x, h - 1) for x in range(0, w, step)] + \
          [(0, y) for y in range(0, h, step)] + [(w - 1, y) for y in range(0, h, step)]
    for p in pts:
        if work.getpixel(p) != sentinel:
            ImageDraw.floodfill(work, p, sentinel, thresh=tol)
    bg = np.all(np.asarray(work) == sentinel, axis=-1)
    alpha = Image.fromarray(((~bg) * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)) \
        .filter(ImageFilter.GaussianBlur(0.8))
    out = rgb.convert("RGBA")
    out.putalpha(alpha)
    return out, f"{kind} background removed ({bg.mean():.0%} of pixels)"


def trim(im: Image.Image) -> Image.Image:
    a = np.asarray(im)[..., 3]
    ys, xs = np.nonzero(a > 20)
    if not len(ys):
        raise OexError("image is fully transparent")
    return im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
