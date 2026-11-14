"""Real image-generator mascots (opt-in): set OEX_REAL_MASCOTS to a folder that contains one sub-folder per mascot
(neutral.png, mouth-*.png, blink.png, pose-*.png, expr-*.png made with ChatGPT or another generator).

    OEX_REAL_MASCOTS=~/mascot-tests .venv/bin/python -m pytest tests/test_real_mascots.py -s

The images are personal likenesses: keep the folder OUTSIDE this repository. The test prepares each mascot, renders
a short demo film with it, and writes review.png + a contact sheet next to the images for a human to inspect.
Thresholds are the release criteria in docs/RELEASE-CHECKLIST.md.
"""
import json
import os
import shutil
from pathlib import Path

import pytest
from conftest import needs_ffmpeg

ROOT = os.environ.get("OEX_REAL_MASCOTS")
FOLDERS = sorted(p for p in Path(ROOT).expanduser().iterdir() if (p / "neutral.png").exists()) if ROOT else []

pytestmark = [needs_ffmpeg, pytest.mark.skipif(not FOLDERS, reason="set OEX_REAL_MASCOTS to run real-mascot tests")]


@pytest.mark.parametrize("folder", FOLDERS, ids=lambda p: p.name)
def test_real_mascot_prepares_and_renders(folder, tmp_path):
    from openexplainer.cli import main
    from openexplainer.mascot import prepare

    info = prepare(folder, log=print)
    errors = [c["msg"] for c in info["checks"] if c["level"] == "error"]
    assert not errors, errors
    assert info["mouths"].get("ah"), "no usable open mouth"
    for name, st in info["states"].items():
        assert st["score"] >= 0.6, f"{name}: registration {st['score']}"
    poses = [n for n in info["states"] if n.startswith("pose-")]
    assert all(info["states"][p]["talk"] for p in poses), "a gesture lost lip sync: its head differs from neutral"
    if info["mouth_box"]:
        x0, y0, x1, y1 = info["mouth_box"]
        assert (x1 - x0) * (y1 - y0) < 0.08 * info["canvas"][0] * info["canvas"][1], "mouth region too large"

    film = tmp_path / "film"
    assert main(["new", str(film), "--demo"]) == 0
    cfg = json.loads((film / "project.json").read_text())
    cfg["mascot"] = {"dir": str(folder), "position": "left"}
    (film / "project.json").write_text(json.dumps(cfg))
    sb = json.loads((film / "storyboard.json").read_text())
    if poses:
        sb["scenes"][1]["mascot"] = [{"at": "write the script", "pose": poses[0][5:], "for": 1.5}]
    (film / "storyboard.json").write_text(json.dumps(sb))
    assert main(["-C", str(film), "render", "--workers", "2"]) == 0
    check = json.loads((film / "build" / "mascot-check.json").read_text())
    assert check["talk_share"] >= 0.9
    shutil.copy(next((film / "renders").glob("*-sheet.png")), folder / "build" / "film-sheet.png")
    print(f"look at: {folder / 'build' / 'review.png'} and {folder / 'build' / 'film-sheet.png'}")
