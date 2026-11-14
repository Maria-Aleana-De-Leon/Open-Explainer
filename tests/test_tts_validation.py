"""TTS output is checked before it replaces the narration: an empty, silent or truncated result is an error with a
fix, the previous narration is kept, and no other provider is tried instead.

Regression: macOS `say` can exit 0 and leave an empty file (for example inside an agent's sandboxed shell); `oex tts`
used to report success and the failure only surfaced later in `oex transcribe`."""
import json
import os
import subprocess
import sys

import pytest
from conftest import make_project, needs_ffmpeg, words_for

from openexplainer import tts
from openexplainer.config import load_project
from openexplainer.errors import OexError

SAY_TEXT = ("Airplanes fly because their wings push air down and the air pushes back up on the wings. "
            "Faster air means more lift.")      # 21 words

FAKE_SAY = r'''#!{python}
import os, subprocess, sys
args = sys.argv[1:]
out = args[args.index("-o") + 1]
mode = os.environ.get("FAKE_SAY_MODE", "tone")
def lavfi(src, secs=None, frames=None):
    limit = ["-frames:a", str(frames)] if frames is not None else ["-t", str(secs)]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", src] + limit + [out], check=True)
if mode == "empty":
    open(out, "wb").close()
elif mode == "header":                  # what `say` leaves in a sandbox: a valid header, zero samples
    lavfi("anullsrc=r=22050:cl=mono", frames=0)
elif mode == "silent":
    lavfi("anullsrc=r=22050:cl=mono", 3)
elif mode == "short":
    lavfi("sine=frequency=220:sample_rate=22050", 1)
else:
    lavfi("sine=frequency=220:sample_rate=22050", 5)
'''


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "film"
    make_project(root, [{"id": "s01", "type": "statement", "say": SAY_TEXT, "text": "Lift"}],
                 words_for(SAY_TEXT), total=8.0)
    return root


@pytest.fixture
def fake_say(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "say"
    exe.write_text(FAKE_SAY.replace("{python}", sys.executable))
    exe.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    return monkeypatch


@needs_ffmpeg
@pytest.mark.parametrize("mode, message", [
    ("empty", "no audio file"),
    ("header", "no playable audio"),
    ("silent", "silence"),
    ("short", "stopped early"),
])
def test_failed_say_output_is_an_error_and_keeps_the_old_narration(project, fake_say, mode, message):
    fake_say.setenv("FAKE_SAY_MODE", mode)
    out = project / "audio" / "narration.wav"
    before = out.read_bytes()
    with pytest.raises(OexError) as e:
        tts.synthesize(load_project(project), out, "say")
    assert message in str(e.value) and "say" in str(e.value)
    assert "sandbox" in e.value.fix and "record" in e.value.fix
    assert out.read_bytes() == before                       # nothing was overwritten
    assert not list((project / "audio").glob("*.tts-new*"))  # no half-written file left behind


@needs_ffmpeg
def test_real_audio_replaces_the_narration(project, fake_say):
    fake_say.setenv("FAKE_SAY_MODE", "tone")
    out = project / "audio" / "narration.wav"
    d = tts.synthesize(load_project(project), out, "say")
    assert 4.5 < d < 5.5
    assert not list((project / "audio").glob("*.tts-new*"))


@needs_ffmpeg
def test_command_provider_with_empty_output_is_an_error(project):
    out = project / "audio" / "narration.wav"
    before = out.read_bytes()
    with pytest.raises(OexError) as e:
        tts.synthesize(load_project(project), out, "command", template="touch {out} # {text_file}")
    assert "command produced" in str(e.value)
    assert out.read_bytes() == before


@needs_ffmpeg
def test_cli_reports_failed_say_without_traceback(project, fake_say, tmp_path):
    env = dict(os.environ, FAKE_SAY_MODE="header")
    r = subprocess.run([sys.executable, "-m", "openexplainer.cli", "-C", str(project), "tts", "--provider", "say",
                        "--overwrite"], capture_output=True, text=True, env=env)
    assert r.returncode != 0
    assert "error:" in r.stderr and "fix:" in r.stderr and "Traceback" not in r.stderr
    assert "narration ->" not in r.stdout                   # no false success message
    assert json.loads((project / "project.json").read_text())["narration"]["audio"] == "audio/narration.wav"
