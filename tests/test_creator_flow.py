"""Creator workflow: prompts at hand, swapping in your own mascot and narration, the title hook and the loop diagram."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import make_project, needs_ffmpeg, words_for

ROOT = Path(__file__).resolve().parents[1]
OEX = [sys.executable, "-m", "openexplainer.cli"]


def run(*a):
    return subprocess.run(OEX + list(a), capture_output=True, text=True)


def test_prompts_are_one_command_away():
    r = run("prompts")
    assert r.returncode == 0 and r.stdout.count("Prompt ") == 7 and "oex use-mascot" in r.stdout
    four = run("prompts", "4").stdout
    assert all(f"mouth-{s}.png" in four for s in ("ah", "half", "ee", "oh", "oo", "fv", "mbp"))


@needs_ffmpeg
def test_use_mascot_backs_up_prepares_and_reports_missing_gestures(tmp_path):
    src = tmp_path / "mine"
    subprocess.run([sys.executable, str(ROOT / "tools" / "make_demo_mascot.py"), str(src)], check=True,
                   capture_output=True)
    (src / "pose-wave.png").unlink()                      # a set without one gesture the storyboard uses
    d = tmp_path / "film"
    run("new", str(d), "--demo")
    sb = json.loads((d / "storyboard.json").read_text())
    sb["scenes"][0]["mascot"] = [{"at": "demo film", "pose": "wave"}]
    (d / "storyboard.json").write_text(json.dumps(sb))
    (d / "mascot").mkdir()
    (d / "mascot" / "old.txt").write_text("previous")
    r = run("-C", str(d), "use-mascot", str(src))
    assert r.returncode == 0, r.stdout + r.stderr
    assert (d / "mascot-previous" / "old.txt").exists()
    assert (d / "mascot" / "build" / "mascot.json").exists()
    assert json.loads((d / "project.json").read_text())["mascot"]["dir"] == "mascot"
    assert "pose-wave.png" in r.stdout and "READY" in r.stdout
    r = run("-C", str(d), "render", "--workers", "2")      # missing gesture: a note, not a failure
    assert r.returncode == 0, r.stdout[-800:] + r.stderr[-800:]
    assert "has no pose-wave.png" in r.stdout


@needs_ffmpeg
@pytest.mark.skipif(not shutil.which("say"), reason="needs macOS `say` to make a speech recording")
def test_use_narration_copies_retimes_and_reports(tmp_path):
    pytest.importorskip("faster_whisper")
    d = tmp_path / "film"
    run("new", str(d), "--demo")
    sb = json.loads((d / "storyboard.json").read_text())
    text = " [[slnc 400]] ".join(s["say"] for s in sb["scenes"])
    aiff = tmp_path / "take.aiff"
    subprocess.run(["say", "-o", str(aiff), text], check=True)
    mp3 = tmp_path / "my take.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(aiff), str(mp3)], check=True)
    r = run("-C", str(d), "use-narration", str(mp3))
    assert r.returncode == 0, r.stdout[-800:] + r.stderr[-800:]
    assert json.loads((d / "project.json").read_text())["narration"]["audio"] == "audio/narration.mp3"
    assert (d / "audio" / "narration.previous.wav").exists()         # the old take is kept
    assert "your pace:" in r.stdout and "film length" in r.stdout


@needs_ffmpeg
def test_title_hook_and_loop_diagram_land_on_their_words(tmp_path):
    from openexplainer.config import load_project
    from openexplainer.pipeline import render
    a = "Imagine asking for a trip plan and it does it."
    b = "It looks then plans then acts then checks."
    wa = words_for(a, start=0.2)
    wb = words_for(b, start=wa[-1]["e"] + 0.8)
    scenes = [{"id": "hook", "type": "title", "say": a, "title": "It *does it*", "emphasis": "it does it"},
              {"id": "loop", "type": "flow", "layout": "cycle", "say": b,
               "items": [{"text": "Look", "at": "looks"}, {"text": "Plan", "at": "plans"},
                         {"text": "Act", "at": "acts"}, {"text": "Check", "at": "checks"}]}]
    make_project(tmp_path, scenes, wa + wb, total=wb[-1]["e"] + 0.4, fps=12)
    rep = render(load_project(tmp_path), workers=2)
    ok = {c["check"]: c for c in rep["checks"]}
    assert ok["visual cues"]["ok"] and ok["film = model"]["ok"], ok["visual cues"]["detail"]
    cues = {(c["scene"], c["cue"]) for c in rep["cues"]}
    assert ("hook", "emphasis") in cues and ("loop", "items[3]") in cues
