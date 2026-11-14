"""Text stability: stationary text never moves between frames, and the optional camera push is a smooth, monotonic
drift. Regression: the push used to resize to a truncated integer size and crop at a truncated offset every frame, so
"stationary" text jumped back and forth by about a pixel (measured on a real film: 29 direction changes in 52 frames).
New projects use a still camera; projects without a `camera` setting keep their style's camera."""
import json
import subprocess
import sys

import numpy as np
import pytest
from PIL import Image

from openexplainer.captions import Burner, chunks
from openexplainer.render import SceneFrames
from openexplainer.styles import get as style

SCENE = {"id": "s1", "type": "statement", "say": "x", "text": "Look, plan, act, check. Repeat until it works.",
         "start": 0.0, "end": 6.0, "t": 0.2, "words": [], "caption_words": [], "items": []}


def _job(style_name="midnight", camera=None):
    return {"width": 1920, "height": 1080, "fps": 30, "style": style_name, "accent": None, "mascot_pos": None,
            "captions": False, "caption_words": 6, "is_last": True, "root": ".", "mascot": None, "camera": camera}


def _moments(frames: SceneFrames, times):
    """Intensity-weighted horizontal centre and spread of everything drawn over the background, per frame."""
    bg = np.asarray(frames.frame(0.0).convert("L")).astype(float)       # nothing has appeared yet
    xs = np.arange(1920)[None, :]
    cx, sx = [], []
    for t in times:
        w = np.abs(np.asarray(frames.frame(t).convert("L")).astype(float) - bg)      # dark or light text alike
        s = w.sum()
        m = (w * xs).sum() / s
        cx.append(m)
        sx.append(np.sqrt((w * (xs - m) ** 2).sum() / s))
    return np.array(cx), np.array(sx)


SETTLED = [1.0 + k / 30 for k in range(60)]                              # after the entrance, only the camera acts


def test_stationary_text_does_not_move_with_a_still_camera():
    cx, sx = _moments(SceneFrames(dict(SCENE, camera="still"), _job()), SETTLED)
    assert np.abs(np.diff(cx)).max() == 0 and np.abs(np.diff(sx)).max() == 0


def test_camera_push_is_a_smooth_monotonic_drift():
    cx, sx = _moments(SceneFrames(dict(SCENE, camera="push"), _job()), SETTLED)
    assert (np.diff(sx) > 0).all()                     # the text only ever grows (it used to shrink back on some frames)
    assert np.abs(np.diff(cx)).max() < 0.25            # centred text: no lurching (it used to jump ~0.55 px per frame)
    assert 1.005 < sx[-1] / sx[0] < 1.04               # a gentle push, not a zoom


def test_slide_transition_moves_monotonically():
    f = SceneFrames(dict(SCENE, camera="still", transition="slide"), _job("paper"))
    cx, _ = _moments(f, [0.25 + k / 30 for k in range(10)])
    assert (np.diff(cx) <= 0.01).all() and cx[0] - cx[-1] > 5   # glides left into place, never back


def test_camera_transform_adds_no_dark_halos():
    """Filtering is done on premultiplied alpha: no pixel ends up darker than the background or the text."""
    f = SceneFrames(dict(SCENE, camera="push"), _job("midnight"))
    bg = np.asarray(f.frame(0.0).convert("L")).astype(int)
    g = np.asarray(f.frame(3.0).convert("L")).astype(int)
    assert (g >= bg - 2).all()


def test_captions_stay_put_while_the_highlight_moves():
    words = [(w, 1.0 + i * 0.3, 1.25 + i * 0.3) for i, w in enumerate("Checking catches a mistake before".split())]
    cs = chunks(words, 6)
    b = Burner(cs, (170, 880, 1750, 1010), style("midnight"), False)

    def letters(t):
        c = Image.new("RGBA", (1920, 1080), (14, 23, 38, 255))
        b.draw(c, t)
        a = np.asarray(c.convert("RGB")).astype(float)[880:1010]
        return np.clip((np.linalg.norm(a - np.array([27, 42, 69]), axis=2) - 40) / 80, 0, 1)   # colour-blind

    ref = letters(cs[0].words[0][1] + 0.05)
    for _, s, _ in cs[0].words[1:]:
        m = letters(s + 0.05)
        r = np.fft.ifft2(np.fft.fft2(ref) * np.conj(np.fft.fft2(m))).real
        assert np.unravel_index(r.argmax(), r.shape) == (0, 0)                 # zero shift


@pytest.mark.parametrize("scene_cam, project_cam, expected", [
    (None, None, "push"),          # existing project without a setting: the style's camera, as before
    (None, "still", "still"),      # project setting wins over the style
    ("push", "still", "push"),     # a scene can still ask for a push
])
def test_camera_setting_precedence(scene_cam, project_cam, expected):
    sc = dict(SCENE, **({"camera": scene_cam} if scene_cam else {}))
    assert SceneFrames(sc, _job("midnight", project_cam)).camera == expected


@pytest.mark.parametrize("demo", [False, True])
def test_new_projects_use_a_still_camera(tmp_path, demo):
    d = tmp_path / "film"
    subprocess.run([sys.executable, "-m", "openexplainer.cli", "new", str(d)] + (["--demo"] if demo else []),
                   check=True, capture_output=True)
    assert json.loads((d / "project.json").read_text())["camera"] == "still"


def test_render_cache_key_covers_every_module_that_draws():
    """A change to any module the renderer draws with must invalidate cached scenes (motion.py was once missed)."""
    import re
    from pathlib import Path

    from openexplainer import render
    pkg = Path(render.__file__).parent
    seen, todo = set(), ["render.py"]
    while todo:
        name = todo.pop()
        if name in seen or not (pkg / name).exists():
            continue
        seen.add(name)
        todo += [m + ".py" for m in re.findall(r"from \.(\w+) import|from \. import (\w+)", (pkg / name).read_text())
                 for m in m if m]
    drawing = seen - {"config.py", "errors.py", "media.py", "schema.py", "timeline.py", "words.py", "audio.py",
                      "pipeline.py", "qa.py", "review.py", "sfx.py", "tts.py", "cli.py", "durations.py", "demo.py",
                      "__init__.py"}
    assert drawing <= set(render.PIXEL_MODULES), drawing - set(render.PIXEL_MODULES)
