"""Splitting generated sprite sheets: irregular cells, art past the cell line, touching neighbours, sparkles, alpha
noise, the 4+3 mouth layout, checks and the review sheet; and the end-to-end path into the mascot importer with the
bundled demo mascot (MIT), so no private artwork is needed."""
import json
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from openexplainer.errors import OexError
from openexplainer.mascot import prepare
from openexplainer.sheets import KINDS, clean_alpha, find_cells, place_mouths, split

ROOT = Path(__file__).resolve().parents[1]
QUIET = dict(log=lambda *_: None)


def _sheet(rows, cell=(200, 520), jitter=18, alpha=253, noise=True, seed=1, extra=None, item=(60, 210)):
    """Items as solid ellipses in distinct colours (identity), placed off-grid, slightly see-through, with specks."""
    rnd = random.Random(seed)
    W, H = max(rows) * cell[0], len(rows) * cell[1]
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    k, colours = 0, []
    for r, count in enumerate(rows):
        x_off = (W - count * cell[0]) // 2
        for c in range(count):
            col = (40 + 8 * k, 200 - 6 * k, 90 + 5 * k)
            colours.append(col)
            cx = x_off + c * cell[0] + cell[0] // 2 + rnd.randint(-jitter, jitter)
            cy = r * cell[1] + cell[1] // 2 + rnd.randint(-jitter, jitter)
            d.ellipse([cx - item[0], cy - item[1], cx + item[0], cy + item[1]], fill=col + (alpha,))
            if extra:
                extra(d, k, cx, cy, col)
            k += 1
    if noise:
        a = np.asarray(im).copy()
        specks = np.random.default_rng(seed).random(a.shape[:2]) < 0.03
        a[specks & (a[..., 3] == 0), 3] = 4
        im = Image.fromarray(a, "RGBA")
    return im, colours


def _colour(path):
    a = np.asarray(Image.open(path))
    m = a[..., 3] == 255
    return tuple(int(v) for v in np.median(a[m][:, :3], axis=0))


def test_alpha_is_cleaned_art_opaque_background_clear():
    im, _ = _sheet([3, 3, 3])
    a = np.asarray(clean_alpha(im))[..., 3]
    assert set(np.unique(a)) <= {0, 255} | set(range(9, 240))
    assert (a == 255).any() and not ((a > 0) & (a <= 8)).any()


def test_a_3x3_sheet_splits_into_nine_items_in_reading_order(tmp_path):
    im, colours = _sheet([3, 3, 3])
    im.save(tmp_path / "s.png")
    m = split(tmp_path / "s.png", "poses", tmp_path / "out")
    assert m["ok"] and len([i for i in m["items"] if "file" in i]) == 9
    for it, col in zip(m["items"], colours):
        assert max(abs(a - b) for a, b in zip(_colour(tmp_path / "out" / it["file"]), col)) <= 2, it["name"]
    sizes = {tuple(it["size"]) for it in m["items"]}
    assert len(sizes) == 1                                           # one shared canvas: the set stays aligned
    assert (tmp_path / "out" / "split" / "review.png").exists()
    assert json.loads((tmp_path / "out" / "split" / "manifest.json").read_text())["kind"] == "poses"
    assert not list((tmp_path / "out").glob("review.png"))          # the mascot folder holds only mascot images


def test_art_reaching_past_the_regular_cell_line_stays_with_its_item(tmp_path):
    def arm(d, k, cx, cy, col):
        if k == 2:                                                   # a pointing arm towards the next row's space
            d.rectangle([cx + 50, cy - 10, cx + 95, cy + 4], fill=col + (253,))
    im, colours = _sheet([3, 3, 3], jitter=0, extra=arm)
    im.save(tmp_path / "s.png")
    m = split(tmp_path / "s.png", "poses", tmp_path / "out")
    it = m["items"][2]
    w = it["art"][2] - it["art"][0]
    assert w > 150 and not it["warnings"]                            # the whole arm, in one piece, no cut


def test_sparkles_and_rays_belong_to_their_sticker(tmp_path):
    def sparkle(d, k, cx, cy, col):
        d.ellipse([cx + 66, cy - 80, cx + 78, cy - 68], fill=col + (253,))    # a separate little shape
    im, colours = _sheet([5] * 5, cell=(180, 180), jitter=4, extra=sparkle, item=(60, 60))
    im = im.resize((900, 900))
    im.save(tmp_path / "s.png")
    m = split(tmp_path / "s.png", "stickers", tmp_path / "out")
    assert m["ok"] and len(m["items"]) == 25
    assert [i["name"] for i in m["items"]][:3] == ["lightbulb", "question", "brain"]
    for it in m["items"]:
        a = np.asarray(Image.open(tmp_path / "out" / it["file"]))[..., 3]
        ys, xs = np.nonzero(a)
        assert xs.max() - xs.min() > 60                              # body and sparkle together


def test_the_irregular_4_plus_3_mouth_layout(tmp_path):
    im, colours = _sheet([4, 3], cell=(240, 220), item=(80, 60))
    im.save(tmp_path / "m.png")
    m = split(tmp_path / "m.png", "mouths", tmp_path / "out")
    assert m["ok"] and [i["name"] for i in m["items"]] == KINDS["mouths"]["names"]
    for it, col in zip(m["items"], colours):
        assert max(abs(a - b) for a, b in zip(_colour(tmp_path / "out" / it["file"]), col)) <= 2


def test_touching_neighbours_are_reported(tmp_path):
    def bridge(d, k, cx, cy, col):
        if k == 0:
            d.rectangle([cx, cy - 5, cx + 200, cy + 5], fill=col + (253,))   # joins item 0 to item 1
    im, _ = _sheet([3, 3, 3], jitter=0, extra=bridge)
    im.save(tmp_path / "s.png")
    m = split(tmp_path / "s.png", "poses", tmp_path / "out")
    assert any("touches its neighbour" in w for w in m["warnings"])


def test_missing_items_alpha_and_size_are_errors(tmp_path):
    im, _ = _sheet([3, 3])                                           # only six items for a 3x3 kind
    im.save(tmp_path / "six.png")
    assert not split(tmp_path / "six.png", "poses", tmp_path / "a")["ok"]
    im, _ = _sheet([3, 3, 3])
    im.convert("RGB").save(tmp_path / "rgb.png")
    with pytest.raises(OexError):
        split(tmp_path / "rgb.png", "poses", tmp_path / "b")         # no alpha: nothing to split on
    small, _ = _sheet([3, 3, 3])
    small.resize((300, 600)).save(tmp_path / "small.png")
    m = split(tmp_path / "small.png", "poses", tmp_path / "c")
    assert not m["ok"] and any("tall" in p for p in m["problems"])
    with pytest.raises(OexError, match="names"):
        split(tmp_path / "small.png", "poses", tmp_path / "d", names=["a", "b"])


def test_a_shared_canvas_lines_up_two_sheets(tmp_path):
    im, _ = _sheet([3, 3, 3])
    im.save(tmp_path / "s.png")
    a = split(tmp_path / "s.png", "expressions", tmp_path / "e", canvas=(200, 460))
    b = split(tmp_path / "s.png", "mouthless", tmp_path / "m", canvas=(200, 460))
    assert {tuple(i["size"]) for i in a["items"] + b["items"]} == {(200, 460)}
    with pytest.raises(OexError, match="smaller"):
        split(tmp_path / "s.png", "expressions", tmp_path / "f", canvas=(50, 50))


def test_cells_follow_the_gaps_not_a_fixed_grid():
    a = np.zeros((300, 600), np.uint8)
    a[100:200, 10:140] = 255                                         # unequal items and gaps
    a[100:200, 260:300] = 255
    a[100:200, 330:590] = 255
    cells = find_cells(a, [3])
    xs = [c["box"][0] for c in cells] + [cells[-1]["box"][2]]
    assert 140 <= xs[1] <= 260 and 300 <= xs[2] <= 330 and all(c["crossed"] == 0 for c in cells)


# ---------- end to end with the demo mascot (MIT) ----------

@pytest.fixture(scope="module")
def pip(tmp_path_factory):
    d = tmp_path_factory.mktemp("pip")
    subprocess.run([sys.executable, str(ROOT / "tools" / "make_demo_mascot.py"), str(d)], check=True, capture_output=True)
    return d


def test_a_pose_sheet_becomes_a_prepared_mascot(pip, tmp_path):
    names = ["neutral", "pose-point", "pose-present", "pose-wave", "expr-happy", "expr-thinking", "expr-confused",
             "expr-surprised", "blink"]
    tiles = [Image.open(pip / f"{n}.png").convert("RGBA") for n in names]
    tw, th = 520, 750
    sheet = Image.new("RGBA", (3 * tw, 3 * th), (0, 0, 0, 0))
    rnd = random.Random(3)
    for k, t in enumerate(tiles):
        t = t.resize((round(t.width * 0.55), round(t.height * 0.55)), Image.LANCZOS)
        x = (k % 3) * tw + (tw - t.width) // 2 + rnd.randint(-12, 12)
        y = (k // 3) * th + (th - t.height) // 2 + rnd.randint(-12, 12)
        sheet.alpha_composite(t, (x, y))
    sheet.save(tmp_path / "sheet.png")
    m = split(tmp_path / "sheet.png", "poses", tmp_path / "mascot", names=names)
    assert m["ok"], m["problems"]
    info = prepare(tmp_path / "mascot", **QUIET)
    assert info["ok"]
    assert all(s["score"] >= 0.8 for s in info["states"].values()), info["states"]


def test_mouth_sprites_placed_on_a_mouthless_face_give_working_mouths(pip, tmp_path):
    ref = prepare(pip, tmp_path / "ref", **QUIET)                    # where Pip's mouth is, from the real set
    x0, y0, x1, y1 = ref["mouth_box"]
    canvas = ref["canvas"]
    neutral = Image.open(tmp_path / "ref" / "states" / "neutral.png").convert("RGBA")
    assert list(neutral.size) == list(canvas)
    face = neutral.copy()                                             # a mouthless base: the mouth painted over
    skin = neutral.getpixel((int((x0 + x1) / 2), int(y0) - 6))
    ImageDraw.Draw(face).rectangle([x0, y0, x1, y1], fill=skin)
    sprites = tmp_path / "sprites"
    sprites.mkdir()
    for name, src in (("sprite-closed", "neutral"), ("sprite-ah", "mouth-ah"), ("sprite-ee", "mouth-ee"),
                      ("sprite-m", "mouth-mbp")):
        img = Image.open(tmp_path / "ref" / "states" / "neutral.png").convert("RGBA") if src == "neutral" else None
        if img is None:
            # Pip's mouth artwork for that sound, cut from its prepared patch
            img = Image.open(tmp_path / "ref" / "mouths" / f"{src.split('-')[1]}.png").convert("RGBA")
            sprite = img
        else:
            sprite = img.crop((x0, y0, x1, y1))
        sprite.save(sprites / f"{name}.png")
    mascot = tmp_path / "bust"
    mascot.mkdir()
    face.save(mascot / "base.png")
    written = place_mouths(mascot, sprites, (int((x0 + x1) / 2), int((y0 + y1) / 2), int(x1 - x0)),
                           base=mascot / "base.png")
    assert {"neutral.png", "mouth-ah.png", "mouth-ee.png", "mouth-mbp.png"} <= set(written)
    (mascot / "base.png").unlink()
    n = np.asarray(Image.open(mascot / "neutral.png")).astype(int)
    a = np.asarray(Image.open(mascot / "mouth-ah.png")).astype(int)
    ys, xs = np.nonzero(np.abs(a - n).max(-1) > 0)
    assert xs.min() >= x0 - 4 and xs.max() <= x1 + 4 and ys.min() >= y0 - 40 and ys.max() <= y1 + 40   # mouth only
    info = prepare(mascot, **QUIET)
    assert info["ok"] and {"ah", "ee", "mbp"} <= set(info["mouths"])
    with pytest.raises(OexError, match="outside"):
        place_mouths(mascot, sprites, (99999, 10, 40))


def test_the_assets_command(tmp_path):
    im, _ = _sheet([5] * 5, cell=(180, 180), jitter=4, item=(60, 60))
    im.save(tmp_path / "st.png")
    r = subprocess.run([sys.executable, "-m", "openexplainer.cli", "assets", "split", str(tmp_path / "st.png"),
                        "--kind", "stickers", "--out", str(tmp_path / "o")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert len(list((tmp_path / "o").glob("*.png"))) == 25 and "OK" in r.stdout
