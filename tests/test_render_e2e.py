"""End-to-end: real frames, real ffmpeg encode, real QA on the output file."""
import json

import pytest
from conftest import ffprobe_json, make_project, needs_ffmpeg, words_for
from PIL import Image

from openexplainer.config import load_project
from openexplainer.errors import OexError
from openexplainer.pipeline import render

A = "Here is a picture of the system."
B = "And that is the whole idea."


def _film(tmp_path, fmt="16:9"):
    wa = words_for(A, start=0.2)
    wb = words_for(B, start=wa[-1]["e"] + 0.8)
    scenes = [{"id": "s01", "type": "image", "say": A, "image": "pic.png", "heading": "The system"},
              {"id": "s02", "type": "end", "say": B, "title": "That's it", "cta": "Follow"}]
    make_project(tmp_path, scenes, wa + wb, total=wb[-1]["e"] + 0.3, fps=12, format=fmt)
    return tmp_path


@needs_ffmpeg
def test_failed_scene_then_partial_regeneration(tmp_path, capsys):
    root = _film(tmp_path)
    # 1) the image is missing: s01 fails, s02 still renders, nothing is assembled
    with pytest.raises(OexError) as e:
        render(load_project(root), workers=2)
    assert "s01" in str(e.value) and "oex render --only s01" in str(e.value)
    state = json.loads((root / "build" / "render-state.json").read_text())["results"]
    assert {r["id"]: r["ok"] for r in state} == {"s01": False, "s02": True}

    # 2) fix the cause; re-render: only s01 is rendered, s02 comes from the cache
    Image.new("RGB", (800, 450), (40, 120, 200)).save(root / "pic.png")
    capsys.readouterr()
    rep = render(load_project(root), workers=2)
    out = capsys.readouterr().out
    assert "1 scene(s) to render, 1 cached" in out
    assert rep["ok"], [c for c in rep["checks"] if not c["ok"]]
    film = root / "renders" / "test-film-16x9.mp4"
    info = ffprobe_json(film)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (1920, 1080)
    assert (root / "renders" / "test-film-16x9.srt").exists()
    assert (root / "renders" / "test-film-16x9-stems" / "voice.wav").exists()


@needs_ffmpeg
def test_vertical_format_renders_1080x1920(tmp_path):
    root = _film(tmp_path, fmt="9:16")
    Image.new("RGB", (600, 600), (200, 80, 40)).save(root / "pic.png")
    rep = render(load_project(root), workers=2)
    assert rep["ok"], [c for c in rep["checks"] if not c["ok"]]
    v = next(s for s in ffprobe_json(root / "renders" / "test-film-9x16.mp4")["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (1080, 1920)


@needs_ffmpeg
def test_demo_starter_preflight_render_and_evidence(tmp_path):
    from openexplainer.cli import main
    d = tmp_path / "demo"
    assert main(["new", str(d), "--demo"]) == 0
    assert main(["-C", str(d), "preflight"]) == 0
    assert main(["-C", str(d), "render", "--workers", "2"]) == 0
    out = d / "renders"
    verify = (out / "demo-16x9.VERIFY.md").read_text()
    assert "## Checks on the rendered file (PASS)" in verify and "publish-safe assets | yes" in verify
    assert (out / "demo-16x9-sheet.png").exists()


@needs_ffmpeg
def test_preflight_fails_on_missing_timings(tmp_path):
    from openexplainer.cli import main
    d = tmp_path / "demo"
    main(["new", str(d), "--demo"])
    (d / "build" / "words.json").unlink()
    assert main(["-C", str(d), "preflight"]) == 2


@needs_ffmpeg
def test_visual_checks_can_fail(tmp_path, monkeypatch):
    """The cue and film-match checks are not rubber stamps: break what they look at and they fail."""
    import json as _j

    from PIL import Image as _I

    from openexplainer import qa, render, scenes
    from openexplainer.cli import main
    d = tmp_path / "demo"
    main(["new", str(d), "--demo"])
    assert main(["-C", str(d), "render", "--workers", "2"]) == 0
    proj = load_project(d)
    tl = _j.loads((d / "build" / "timeline.json").read_text())
    film = next((d / "renders").glob("*[0-9].mp4"))
    ok = {c["check"]: c["ok"] for c in qa.run(proj, tl, film)["checks"]}
    assert ok["visual cues"] and ok["film = model"]
    monkeypatch.setattr(scenes.El, "render", lambda self, canvas, t: None)          # elements never appear
    monkeypatch.setattr(render.SceneFrames, "frame", lambda self, t: _I.new("RGBA", (1920, 1080), (255, 0, 255, 255)))
    ok = {c["check"]: c["ok"] for c in qa.run(proj, tl, film)["checks"]}
    assert not ok["visual cues"] and not ok["film = model"]
