"""Spec S3/S7: mascot preparation."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from openexplainer.errors import OexError
from openexplainer.mascot import NORM_H, prepare, register
from openexplainer.mascot_io import _rgba, remove_background

ROOT = Path(__file__).resolve().parents[1]
QUIET = dict(log=lambda *_: None)


@pytest.fixture(scope="module")
def pip_src(tmp_path_factory):
    d = tmp_path_factory.mktemp("pip")
    subprocess.run([sys.executable, str(ROOT / "tools" / "make_demo_mascot.py"), str(d)], check=True, capture_output=True)
    return d


def test_prepare_drifting_generated_set(pip_src, tmp_path):
    info = prepare(pip_src, tmp_path / "out", **QUIET)
    assert info["ok"] and info["version"] == 2
    assert set(info["mouths"]) == {"mbp", "half", "ah", "ee", "oh", "oo", "fv"}
    st = info["states"]
    assert all(s["score"] >= 0.8 for s in st.values())                 # every image registered
    assert all(st[p]["talk"] and st[p]["blink"] for p in ("pose-point", "pose-present", "pose-wave"))
    assert not st["expr-surprised"]["talk"]                             # its own mouth is not overwritten
    x0, y0, x1, y1 = info["mouth_box"]
    assert (x1 - x0) * (y1 - y0) < 0.05 * info["canvas"][0] * info["canvas"][1]   # the mouth, not the face
    assert info["provenance"]["source_photo_stored"] is False


def test_patch_borders_have_no_visible_seam(pip_src, tmp_path):
    out = tmp_path / "out"
    info = prepare(pip_src, out, **QUIET)
    N = np.asarray(Image.open(out / "states" / "neutral.png").convert("RGBA")).astype(float)
    x0, y0, x1, y1 = info["mouth_box"]
    for shape, rel in info["mouths"].items():
        p = np.asarray(Image.open(out / rel).convert("RGBA")).astype(float)
        a = p[..., 3] / 255
        border = (a > 0.1) & (a < 0.6)
        err = np.abs(p[..., :3] - N[y0:y1, x0:x1, :3]).mean(-1)[border].mean()
        assert err <= 6, (shape, err)


@pytest.mark.parametrize("scale,dx,dy", [(1.0, 0, 0), (1.04, 9, -6), (0.97, -12, 7)])
def test_registration_recovers_known_transform(pip_src, scale, dx, dy):
    """Like a generated pose: the character at another scale/offset, plus a raised 'arm' outside the head, so the
    trimmed image's origin and height differ from the character's. Registration must still find the head."""
    from openexplainer.mascot_io import trim
    N0 = Image.open(pip_src / "neutral.png").convert("RGBA")
    N = _rgba(trim(N0.resize((round(N0.width * NORM_H / N0.height), NORM_H), Image.LANCZOS)))
    big = Image.new("RGBA", (int(N.shape[1] * 1.6), int(N.shape[0] * 1.4)), (0, 0, 0, 0))
    src = Image.fromarray(N.astype(np.uint8), "RGBA").resize((round(N.shape[1] * scale), round(N.shape[0] * scale)),
                                                              Image.LANCZOS)
    ox, oy = 120 + dx, 150 + dy
    big.alpha_composite(src, (ox, oy))
    big.paste((46, 134, 171, 255), (ox - 60, oy - 110, ox - 20, oy + 300))     # an arm raised beside the head
    A = _rgba(trim(big))
    cx, cy = 60, 110                                                            # character origin inside A
    r = register(N, A, np.arange(0.84, 1.17, 0.03))
    assert abs(r["k"] * scale - 1) < 0.02, r                   # canvas px per source px undoes the scale
    assert abs(r["dx"] + cx * r["k"]) <= 4 and abs(r["dy"] + cy * r["k"]) <= 4, r


def test_missing_mouth_shapes_are_reported_with_fallbacks(pip_src, tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    for n in ("neutral", "mouth-ah", "mouth-mbp"):
        shutil.copy(pip_src / f"{n}.png", src / f"{n}.png")
    info = prepare(src, **QUIET)
    msgs = " ".join(c["msg"] for c in info["checks"])
    assert "missing mouth shapes: half, ee, oh, oo, fv" in msgs
    assert info["shape_map"]["ee"] == "ah" and info["shape_map"]["fv"] == "mbp" and info["shape_map"]["oo"] == "ah"
    assert info["eyes"] is None


def test_unchanged_variant_is_an_error(pip_src, tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    shutil.copy(pip_src / "neutral.png", src / "neutral.png")
    shutil.copy(pip_src / "neutral.png", src / "mouth-ah.png")
    info = prepare(src, **QUIET)
    assert not info["ok"]
    assert any("nothing changed" in c["msg"] for c in info["checks"])


def test_no_neutral_is_a_clear_error(tmp_path):
    with pytest.raises(OexError) as e:
        prepare(tmp_path, **QUIET)
    assert "neutral.png" in str(e.value)


def test_busy_background_is_refused_not_guessed(tmp_path):
    noise = (np.random.default_rng(1).random((500, 400, 3)) * 255).astype("uint8")
    with pytest.raises(OexError) as e:
        remove_background(Image.fromarray(noise))
    assert "transparent background" in e.value.fix


def test_old_mascot_builds_must_be_prepared_again(tmp_path):
    from openexplainer.mascot import load_info
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "mascot.json").write_text(json.dumps({"version": 1, "ok": True}))
    with pytest.raises(OexError) as e:
        load_info(tmp_path)
    assert "prepare" in e.value.fix


def test_prompt_library_matches_the_validator():
    """Every importer message quoted in the repair prompt exists in the code, every file name the prompts ask for is
    one the importer accepts, and all seven shapes have a prompt row."""
    import re
    from openexplainer.mascot import SHAPES
    code = (ROOT / "src" / "openexplainer" / "mascot.py").read_text() + (ROOT / "src" / "openexplainer" / "mascot_io.py").read_text()
    repair = (ROOT / "prompts" / "06-repair-inconsistent.md").read_text()
    for msg in re.findall(r"^\| `([^`]+)`", repair, re.M):
        assert msg.split(" - ")[0].replace("...", "").strip() in code, f"prompt 6 quotes a message the code never prints: {msg}"
    names = set()
    for f in sorted((ROOT / "prompts").glob("0*.md")):
        names |= set(re.findall(r"`((?:mouth|pose|expr)-[a-z-]+|blink|neutral)\.png`", f.read_text()))
    for n in names:
        assert n in ("neutral", "blink") or n.startswith(("pose-", "expr-")) or n[6:] in SHAPES, n
    assert {f"mouth-{s}" for s in SHAPES} <= names
    assert len(sorted((ROOT / "prompts").glob("0*.md"))) == 7
