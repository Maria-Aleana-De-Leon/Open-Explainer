"""Mascot preparation (spec S3/S7, docs/specs/COMPONENTS.md).

Input folder (file names are the contract, docs/mascot/ASSETS.md):
    neutral.png                REQUIRED: front-facing, mouth closed, eyes open
    mouth-<shape>.png          neutral with ONLY the mouth changed; shapes: mbp half ah ee oh oo fv
    blink.png                  neutral with ONLY the eyes closed
    pose-<name>.png            gestures             expr-<name>.png   expressions
    pose-<name>-<expr>.png     optional combinations

Pipeline:
  1. alpha: keep real transparency, else remove a plain/checkerboard background (mascot_io)
  2. registration: every image -> neutral's frame by scale + translation. Scale is searched over a small set; for
     each scale the translation comes from FFT phase correlation of edge maps of the upper silhouette; the best
     peak wins; a full-resolution phase-correlation pass removes the residual offset. Quality = NCC of the upper
     region after registration (0..1).
  3. changed region of each mouth/blink variant: colour difference to neutral above a threshold, inside the face
     area, cleaned; the union over all mouth variants is the mouth region (its real shape, not a box)
  4. patch = variant pixels under a mask grown from that region and feathered by distance to its edge,
     colour-corrected to neutral by a least-squares gain/offset per channel fitted on unchanged pixels around it
  5. per state: talk/blink only where its mouth/eye area matches neutral; drift and missing shapes reported
Outputs in <folder>/build/: states/*.png (one shared canvas), mouths/*.png, eyes/closed.png, mascot.json,
review.png. The creator's photo is never needed or stored.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .errors import OexError
from .mascot_io import _clean, _gray, _label, _on_white, _rgba, has_real_alpha, remove_background, trim

SHAPES = ["mbp", "half", "ah", "ee", "oh", "oo", "fv"]
FALLBACK = {"half": ["ah"], "ee": ["ah"], "oh": ["ah"], "oo": ["oh", "half", "ah"], "fv": ["mbp"],
            "mbp": [], "ah": ["oh", "half", "ee"]}
NORM_H = 1000          # neutral character height on the canvas (px)
WORK_H = 300           # registration analysis height
MIN_SRC_H = 400
DIFF_T = 42            # colour distance (0..441) that counts as "changed"
UPPER = 0.42           # share of the neutral height used for registration (head and shoulders)
FACE = 0.75            # share of the neutral height in which face edits may live


# ---------------- registration ----------------

def _edges(g: np.ndarray) -> np.ndarray:
    gy, gx = np.gradient(g)
    return np.hypot(gx, gy)


def _phase_corr(a: np.ndarray, b: np.ndarray) -> tuple[float, int, int]:
    """Shift (dy, dx) such that b shifted by it best matches a, and the normalised peak height."""
    H, W = a.shape[0] + b.shape[0], a.shape[1] + b.shape[1]
    A = np.fft.rfft2(a - a.mean(), (H, W))
    B = np.fft.rfft2(b - b.mean(), (H, W))
    R = A * np.conj(B)
    R /= np.abs(R) + 1e-9
    r = np.fft.irfft2(R, (H, W))
    i = int(np.argmax(r))
    dy, dx = divmod(i, W)
    if dy > H // 2:
        dy -= H
    if dx > W // 2:
        dx -= W
    return float(r.flat[i]), dy, dx


def _resize(a: np.ndarray, k: float, resample=Image.BILINEAR) -> np.ndarray:
    im = Image.fromarray(a.astype(np.uint8), "RGBA")
    return _rgba(im.resize((max(2, round(im.width * k)), max(2, round(im.height * k))), resample))


def _ncc(a: np.ndarray, b: np.ndarray) -> float:
    a = a - a.mean()
    b = b - b.mean()
    d = float(np.sqrt((a * a).sum() * (b * b).sum())) + 1e-9
    return float((a * b).sum() / d)


def _soft(a: np.ndarray) -> np.ndarray:
    """Grey image blurred by ~3 px: comparisons of thin line art tolerate a pixel or two of residual offset."""
    g = Image.fromarray(_gray(a).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3))
    return np.asarray(g, np.float32)


def register(N: np.ndarray, A: np.ndarray, scales) -> dict:
    """Similarity (scale + translation) placing source image A (RGBA, any size) in neutral's canvas frame N.
    Returns {"k": canvas px per source px, "dx", "dy": canvas offset of A's origin, "peak": phase-corr peak}."""
    wk = WORK_H / N.shape[0]
    Nw = _resize(N, wk)
    up = int(Nw.shape[0] * UPPER)
    ref = _edges(_gray(Nw[:up]))
    base = N.shape[0] / A.shape[0]           # same character height as a first guess
    def trial(s):
        Aw = _resize(A, wk * base * s)
        cand = _edges(_gray(Aw[: int(Aw.shape[0] * min(1.0, UPPER * 1.6))]))
        return (*_phase_corr(ref, cand), s)

    best = max((trial(s) for s in scales), key=lambda r: r[0])
    step = (scales[1] - scales[0]) if len(scales) > 1 else 0.01
    for s in np.arange(best[3] - step, best[3] + step + 1e-9, step / 6):   # fine pass around the coarse best
        r = trial(float(s))
        if r[0] > best[0]:
            best = r
    peak, dy, dx, s = best
    k = base * s
    return {"k": k, "dx": dx / wk, "dy": dy / wk, "peak": peak}


# ---------------- prepare ----------------

def _collect(src: Path) -> dict:
    files = {p.stem.lower(): p for p in sorted(src.glob("*.png"))}
    if "neutral" not in files:
        raise OexError(f"no neutral.png in {src}",
                       "the first image must be named neutral.png (front-facing, mouth closed, eyes open); "
                       "see docs/mascot/ASSETS.md")
    mouths = {n[6:]: p for n, p in files.items() if n.startswith("mouth-")}
    unknown = [n for n in files if not (n in ("neutral", "blink") or n.startswith(("mouth-", "pose-", "expr-")))]
    unknown += [f"mouth-{s}" for s in mouths if s not in SHAPES]
    return {"neutral": files["neutral"], "blink": files.get("blink"),
            "mouths": {s: p for s, p in mouths.items() if s in SHAPES},
            "states": {n: p for n, p in files.items() if n.startswith(("pose-", "expr-"))}, "unknown": unknown}


def _blur(mask: np.ndarray, r: float) -> np.ndarray:
    im = Image.fromarray((mask.astype(np.float32) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))
    return np.asarray(im, np.float32) / 255


def _grow(mask: np.ndarray, px: int) -> np.ndarray:
    """Round (isotropic) growth by about `px` pixels."""
    return _blur(mask, max(1.0, px / 2)) > 0.02 if px > 0 else mask


def _feather(mask: np.ndarray, px: int) -> np.ndarray:
    """0..1 alpha: 1 well inside the mask, falling smoothly to 0 at its edge over about `px` pixels."""
    inner = _blur(mask, max(1.0, px / 3))
    return np.clip((inner - 0.5) * 2.2 + 0.5, 0, 1) * mask


def _colour_fit(src: np.ndarray, dst: np.ndarray, where: np.ndarray) -> list[list[float]] | None:
    """Per-channel colour correction mapping src onto dst, fitted on the `where` pixels.
    Gain + offset by least squares when the sample has real colour range; offset only (median difference) when it
    is nearly uniform (skin around a mouth), where a gain is not determined by the data."""
    if where.sum() < 40:
        return None
    out = []
    for c in range(3):
        x, y = src[..., c][where], dst[..., c][where]
        if x.std() < 12:
            out.append([1.0, round(float(np.clip(np.median(y - x), -60, 60)), 2)])
            continue
        A = np.stack([x, np.ones_like(x)], 1)
        (g, o), *_ = np.linalg.lstsq(A, y, rcond=None)
        out.append([round(float(np.clip(g, 0.8, 1.25)), 4), round(float(np.clip(o, -60, 60)), 2)])
    return out


def _apply_colour(a: np.ndarray, fit) -> np.ndarray:
    if not fit:
        return a
    b = a.copy()
    for c, (g, o) in enumerate(fit):
        b[..., c] = np.clip(a[..., c] * g + o, 0, 255)
    return b


def prepare(src: Path, out: Path | None = None, meta: dict | None = None, log=print) -> dict:
    src = Path(src)
    out = Path(out) if out else src / "build"
    files = _collect(src)
    checks: list[dict] = []

    def chk(level, msg):
        checks.append({"level": level, "msg": msg})
        log(f"  {level.upper():<5} {msg}")

    for n in files["unknown"]:
        chk("warn", f"{n}.png ignored: name not recognised (use neutral, blink, mouth-<{'|'.join(SHAPES)}>, "
                    "pose-<name>, expr-<name>)")

    def load(p: Path) -> np.ndarray:
        im = Image.open(p)
        if im.height < MIN_SRC_H:
            chk("error", f"{p.name}: only {im.height}px tall (need >= {MIN_SRC_H}px); export at a higher resolution")
        if not has_real_alpha(im):
            im, how = remove_background(im)
            chk("warn", f"{p.name}: no transparency - {how}; check the edges in review.png "
                        "(transparent PNG exports are more reliable)")
        return _rgba(trim(im.convert("RGBA")))

    N0 = load(files["neutral"])
    N = _resize(N0, NORM_H / N0.shape[0], Image.LANCZOS)
    regs = {"neutral": (N, {"k": 1.0, "dx": 0.0, "dy": 0.0, "peak": 1.0})}
    wide, narrow = np.arange(0.84, 1.17, 0.03), np.arange(0.95, 1.06, 0.01)
    for name, p in files["states"].items():
        A = load(p)
        regs[name] = (A, register(N, A, wide))
    for shape, p in files["mouths"].items():
        A = load(p)
        regs[f"mouth-{shape}"] = (A, register(N, A, narrow))
    if files["blink"]:
        A = load(files["blink"])
        regs["blink"] = (A, register(N, A, narrow))

    # shared canvas
    boxes = [(r["dx"], r["dy"], r["dx"] + A.shape[1] * r["k"], r["dy"] + A.shape[0] * r["k"]) for A, r in regs.values()]
    pad = 24
    X0, Y0 = int(np.floor(min(b[0] for b in boxes))) - pad, int(np.floor(min(b[1] for b in boxes))) - pad
    CW = int(np.ceil(max(b[2] for b in boxes))) + pad - X0
    CH = int(np.ceil(max(b[3] for b in boxes))) + pad - Y0

    def place(A, r, ox=0, oy=0) -> np.ndarray:
        im = Image.fromarray(A.astype(np.uint8), "RGBA")
        if abs(r["k"] - 1) > 1e-4:
            im = im.resize((max(1, round(im.width * r["k"])), max(1, round(im.height * r["k"]))), Image.LANCZOS)
        c = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        c.alpha_composite(im, (round(r["dx"] - X0 + ox), round(r["dy"] - Y0 + oy)))
        return _rgba(c)

    Nc = place(N, regs["neutral"][1])
    up = (slice(-Y0, -Y0 + int(NORM_H * UPPER)), slice(-X0, -X0 + N.shape[1]))
    ref_full = _edges(_gray(Nc[up]))
    canvas, quality = {}, {}
    for name, (A, r) in regs.items():
        if name == "neutral":
            canvas[name], quality[name] = Nc, 1.0
            continue
        C = place(A, r)
        _, dy, dx = _phase_corr(ref_full, _edges(_gray(C[up])))   # residual offset at full resolution
        if abs(dy) <= 12 and abs(dx) <= 12 and (dy or dx):
            C = place(A, r, dx, dy)
        canvas[name] = C
        quality[name] = round(max(0.0, _ncc(_gray(C[up]), _gray(Nc[up]))), 3)

    for name in files["states"]:
        q = quality[name]
        if q >= 0.6:
            chk("ok", f"{name}: registered to neutral (quality {q:.2f})")
        else:
            chk("warn", f"{name}: does not register well to neutral (quality {q:.2f}) - the character may have "
                        "changed; regenerate from neutral.png (prompt 6) or accept that this state may jump")

    feet = (round(-X0 + N.shape[1] / 2), round(-Y0 + NORM_H))
    face = np.zeros((CH, CW), bool)
    face[-Y0: -Y0 + int(NORM_H * FACE), max(0, -X0 - 10): -X0 + N.shape[1] + 10] = True
    body = Nc[..., 3] > 128

    Nw = _on_white(Nc)

    def changed(V: np.ndarray) -> tuple[np.ndarray, float, bool]:
        """(changed-region mask, drift share outside the face, anything changed at all).
        Displacement-tolerant: a pixel is 'changed' only if no neutral pixel within +-TOL px has its colour, so
        outlines that moved by a pixel or two (residual registration error, generator drift) are not changes."""
        Vw = _on_white(V)
        raw = np.sqrt(((Vw - Nw) ** 2).sum(-1)) > DIFF_T
        tol = np.full(raw.shape, np.inf, np.float32)
        T = 2
        for dy in range(-T, T + 1):
            for dx in range(-T, T + 1):
                sh = np.roll(np.roll(Nw, dy, 0), dx, 1)
                tol = np.minimum(tol, np.sqrt(((Vw - sh) ** 2).sum(-1)))
        m = tol > DIFF_T
        drift = float((m & ~face & body).sum() / max(1, body.sum()))
        return _clean(m & face, 3), drift, bool((raw & face).any())

    def keep_main(m: np.ndarray, frac: float) -> np.ndarray:
        small = m[::4, ::4]
        lab, n = _label(small)
        if not n:
            return np.zeros_like(m)
        sizes = np.bincount(lab.ravel())[1:]
        keep = [i + 1 for i, s in enumerate(sizes) if s >= frac * sizes.max()]
        big = np.kron(np.isin(lab, keep), np.ones((4, 4), bool))[: m.shape[0], : m.shape[1]]
        return m & _grow(big, 6)

    mouth_region = np.zeros((CH, CW), bool)
    eye_region = None
    for name in [n for n in canvas if n.startswith("mouth-") or n == "blink"]:
        m, drift, any_change = changed(canvas[name])
        if drift > 0.02:
            chk("warn", f"{name}: {drift:.1%} of the character also changed outside the face - ignored, only the "
                        "changed face region is used (prompt 6 can repair drift)")
        if not any_change:
            chk("error", f"{name}: nothing changed compared with neutral.png - is it the same image?")
            continue
        if not m.any():
            continue   # only a thin line changed (e.g. a closed mouth): it is covered by the other shapes' region
        if name == "blink":
            eye_region = keep_main(m, 0.25)
        else:
            mouth_region |= keep_main(m, 0.2)
        if quality[name] < 0.75:
            chk("warn", f"{name}: registration quality {quality[name]:.2f}; check its row in review.png")

    (out / "states").mkdir(parents=True, exist_ok=True)
    (out / "mouths").mkdir(exist_ok=True)
    (out / "eyes").mkdir(exist_ok=True)

    def patch_geometry(region: np.ndarray):
        if region is None or not region.any():
            return None
        ys, xs = np.nonzero(region)
        h = ys.max() - ys.min() + 1
        margin = max(6, int(h * 0.25))
        grown = _grow(region, margin)
        alpha = _feather(grown, margin)
        ys, xs = np.nonzero(grown)
        box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
        ring = _grow(grown, margin) & ~grown & body
        inside = float(body[box[1]:box[3], box[0]:box[2]][grown[box[1]:box[3], box[0]:box[2]]].mean())
        return {"box": box, "alpha": alpha, "ring": ring, "inside": inside}

    mouth = patch_geometry(mouth_region if mouth_region.any() else None)
    eyes = patch_geometry(eye_region)
    for nm, g in (("mouth", mouth), ("eyes", eyes)):
        if g and g["inside"] < 0.85:
            chk("warn", f"{nm} region extends outside the character ({g['inside']:.0%} inside); the variants changed "
                        f"more than the {nm} (outline, hair) - check review.png, or repair with prompt 6")

    def save_patch(V: np.ndarray, g: dict, path: Path):
        x0, y0, x1, y1 = g["box"]
        unchanged = g["ring"] & (V[..., 3] > 250) & (Nc[..., 3] > 250) & (np.abs(V[..., :3] - Nc[..., :3]).max(-1) < 30)
        fit = _colour_fit(V[..., :3], Nc[..., :3], unchanged)
        p = _apply_colour(V, fit)[y0:y1, x0:x1].copy()
        p[..., 3] = np.minimum(p[..., 3], 255 * g["alpha"][y0:y1, x0:x1])
        Image.fromarray(p.round().astype(np.uint8), "RGBA").save(path)

    mouths = {}
    if mouth:
        for shape in SHAPES:
            if f"mouth-{shape}" in canvas:
                save_patch(canvas[f"mouth-{shape}"], mouth, out / "mouths" / f"{shape}.png")
                mouths[shape] = f"mouths/{shape}.png"
    have = set(mouths)
    resolve = {s: (s if s in have else next((a for a in FALLBACK[s] if a in have), None)) for s in SHAPES}
    missing = [s for s in SHAPES if s not in have]
    if not have:
        chk("warn", "no mouth-*.png shapes: the mascot will not lip-sync (it still gestures and blinks)")
    elif "ah" not in have and not resolve["ah"]:
        chk("error", "mouth-ah.png (open mouth) is needed for talking")
    elif missing:
        chk("warn", f"missing mouth shapes: {', '.join(missing)} - using fallbacks "
                    + ", ".join(f"{m}->{resolve[m] or 'own mouth'}" for m in missing)
                    + " (generate them with prompt 4 for better lip sync)")
    eyes_rel = None
    if eyes and "blink" in canvas:
        save_patch(canvas["blink"], eyes, out / "eyes" / "closed.png")
        eyes_rel = "eyes/closed.png"
    elif files["blink"]:
        chk("warn", "blink.png: could not find the eyes - blinking disabled")

    states = {}
    for n in ["neutral"] + list(files["states"]):
        C = canvas[n]
        Image.fromarray(C.round().astype(np.uint8), "RGBA").save(out / "states" / f"{n}.png")
        st = {"file": f"states/{n}.png", "score": quality[n], "talk": False, "blink": False, "colour": None}
        for key, g, flag in (("mouth", mouth, "talk"), ("eyes", eyes, "blink")):
            if not g:
                continue
            x0, y0, x1, y1 = g["box"]
            s = 1.0 if n == "neutral" else max(0.0, _ncc(_soft(C[y0:y1, x0:x1]), _soft(Nc[y0:y1, x0:x1])))
            st[f"{key}_score"] = round(s, 3)
            st[flag] = s >= 0.5
            if n != "neutral" and not st[flag]:
                chk("warn", f"{n}: its {key} area differs from neutral (score {s:.2f}) - "
                            f"{'no lip sync' if key == 'mouth' else 'no blinks'} in this state")
        if n != "neutral" and mouth and st["talk"]:
            unchanged = mouth["ring"] & (C[..., 3] > 250) & (Nc[..., 3] > 250) & (np.abs(C[..., :3] - Nc[..., :3]).max(-1) < 30)
            st["colour"] = _colour_fit(Nc[..., :3], C[..., :3], unchanged)   # neutral-made patches -> this state
        states[n] = st

    info = {"version": 2, "canvas": [CW, CH], "feet": list(feet), "char_height": NORM_H,
            "mouth_box": list(mouth["box"]) if mouth else None, "eye_box": list(eyes["box"]) if eyes else None,
            "mouths": mouths, "shape_map": resolve, "eyes": eyes_rel, "states": states,
            "checks": checks, "ok": not any(c["level"] == "error" for c in checks),
            "provenance": {**(meta or {}), "source_photo_stored": False}}
    (out / "mascot.json").write_text(json.dumps(info, indent=1))
    review(out, info)
    log(f"mascot: {len(states)} state(s), mouths {sorted(have) or 'none'}, blink {'yes' if eyes_rel else 'no'} "
        f"-> {out / 'mascot.json'}; review: {out / 'review.png'}")
    return info


# ---------------- composition (review + presenter) ----------------

def compose(base: Image.Image, info: dict, root: Path, state: str, shape: str | None, blink: bool,
            cache: dict | None = None) -> Image.Image:
    st = info["states"][state]
    im = base.copy()
    if shape and shape != "rest" and st["talk"] and info["mouth_box"]:
        use = info["shape_map"].get(shape)
        if use:
            im.alpha_composite(_patch(root, info["mouths"][use], st.get("colour"), cache), tuple(info["mouth_box"][:2]))
    if blink and st["blink"] and info["eyes"]:
        im.alpha_composite(_patch(root, info["eyes"], st.get("colour"), cache), tuple(info["eye_box"][:2]))
    return im


def _patch(root: Path, rel: str, colour, cache):
    key = (rel, json.dumps(colour))
    if cache is not None and key in cache:
        return cache[key]
    p = Image.open(root / rel).convert("RGBA")
    if colour:
        p = Image.fromarray(_apply_colour(_rgba(p), colour).round().astype(np.uint8), "RGBA")
    if cache is not None:
        cache[key] = p
    return p


def review(out: Path, info: dict) -> Path:
    """review.png: every state (mouth/eye areas outlined, scores) + neutral with every mouth shape and the blink."""
    tile_h = 360
    cw, ch = info["canvas"]
    k = tile_h / ch
    tw = int(cw * k)
    states = list(info["states"])
    shapes = ["rest"] + SHAPES + ["blink"]
    cols = max(len(states), len(shapes))
    sheet = Image.new("RGB", (cols * (tw + 10) + 10, 2 * (tile_h + 40) + 20), (236, 236, 236))
    d = ImageDraw.Draw(sheet)
    cache: dict = {}

    def tile(im, col, row, label, colour=(0, 0, 0)):
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        for y in range(0, im.height, 24):
            for x in range(0, im.width, 24):
                if (x // 24 + y // 24) % 2:
                    bg.paste((228, 228, 228, 255), (x, y, x + 24, y + 24))
        bg.alpha_composite(im)
        x, y = 10 + col * (tw + 10), 10 + row * (tile_h + 40)
        sheet.paste(bg.convert("RGB").resize((tw, tile_h), Image.LANCZOS), (x, y))
        d.text((x, y + tile_h + 6), label, fill=colour)
        return x, y

    for i, n in enumerate(states):
        st = info["states"][n]
        x, y = tile(Image.open(out / st["file"]).convert("RGBA"), i, 0,
                    f"{n}  reg {st['score']:.2f}  talk {'Y' if st['talk'] else 'n'}  blink {'Y' if st['blink'] else 'n'}",
                    (0, 0, 0) if st["score"] >= 0.6 else (200, 0, 0))
        for box, col in ((info["mouth_box"], (220, 30, 30)), (info["eye_box"], (30, 90, 220))):
            if box:
                d.rectangle([x + box[0] * k, y + box[1] * k, x + box[2] * k, y + box[3] * k], outline=col, width=2)
    base = Image.open(out / info["states"]["neutral"]["file"]).convert("RGBA")
    for i, s in enumerate(shapes):
        if s == "blink":
            im, lab = compose(base, info, out, "neutral", None, True, cache), ("blink" if info["eyes"] else "blink (missing)")
        else:
            im = compose(base, info, out, "neutral", s, False, cache)
            use = info["shape_map"].get(s) if s != "rest" else "own mouth"
            lab = s if use == s or s == "rest" else (f"{s} -> {use}" if use else f"{s} (missing)")
        tile(im, i, 1, lab, (0, 0, 0) if "missing" not in lab and "->" not in lab else (200, 0, 0))
    sheet.save(out / "review.png")
    return out / "review.png"


def load_info(mdir: Path) -> tuple[dict, Path]:
    b = mdir / "build"
    f = b / "mascot.json"
    if not f.exists():
        raise OexError(f"mascot in {mdir} is not prepared", f"run `oex mascot prepare {mdir}` and check review.png")
    info = json.loads(f.read_text())
    if info.get("version") != 2:
        raise OexError(f"mascot in {mdir} was prepared by an older version", f"run `oex mascot prepare {mdir}` again")
    if not info.get("ok"):
        errs = "; ".join(c["msg"] for c in info["checks"] if c["level"] == "error")
        raise OexError(f"mascot in {mdir} has errors: {errs}", "fix the images and run `oex mascot prepare` again")
    return info, b
