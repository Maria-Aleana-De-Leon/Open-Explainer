"""`oex review` visual-storytelling and music-level prompts: they fire on text-only films, lonely short lines,
thumbnail-sized diagrams and inaudible or competing music, and stay quiet when the film is balanced."""
import wave

import numpy as np
import pytest
from conftest import make_project, needs_ffmpeg, words_for
from PIL import Image

from openexplainer import review
from openexplainer.config import load_project
from openexplainer.pipeline import plan

LINE = "the wing turns the passing air downward and the air pushes the wing up in return"  # 16 words


def _film(root, scenes, gap=0.6):
    """scenes: list of (scene dict without 'say', number of narration words). Word timings are synthetic."""
    full, words, t = [], [], 0.2
    for sc, n in scenes:
        text = " ".join((LINE.split() * 20)[:n])
        ws = words_for(text, start=t)
        words += ws
        t = ws[-1]["e"] + gap
        full.append(dict(sc, say=text))
    make_project(root, full, words, total=t + 1.0)
    proj = load_project(root)
    return proj, plan(proj, log=lambda *a: None)


def _areas(notes, area):
    return [n for n in notes if n["area"] == area]


@needs_ffmpeg
def test_text_only_film_is_prompted_to_use_pictures(tmp_path):
    proj, tl = _film(tmp_path, [
        ({"id": "s01", "type": "title", "title": "Why planes fly"}, 22),
        ({"id": "s02", "type": "statement", "text": "Air goes *down*"}, 30),
        ({"id": "s03", "type": "bullets", "heading": "Forces", "items": ["Lift", "Weight", "Thrust"]}, 30),
        ({"id": "s04", "type": "statement", "text": "Speed makes *lift*"}, 30),
        ({"id": "s05", "type": "end", "title": "Thanks"}, 16),
    ])
    msgs = [n["msg"] for n in _areas(review.run(proj, tl), "visuals")]
    assert any(m.startswith("no pictures") for m in msgs)
    assert any("three text-only scenes in a row" in m for m in msgs)
    assert any("alone on stage" in m for m in msgs)          # "Air goes down", 3 words for ~9 s


@needs_ffmpeg
@pytest.mark.parametrize("size, small", [((300, 150), True), ((1580, 600), False)])
def test_diagram_size_against_the_stage(tmp_path, size, small):
    (tmp_path / "assets").mkdir(parents=True)
    Image.new("RGBA", size, (40, 60, 90, 255)).save(tmp_path / "assets" / "wing.png")
    proj, tl = _film(tmp_path, [
        ({"id": "s01", "type": "title", "title": "Why planes fly", "subtitle": "in one minute"}, 22),
        ({"id": "s02", "type": "image", "image": "assets/wing.png", "heading": "Air down, wing up"}, 30),
        ({"id": "s03", "type": "flow", "heading": "How", "items": ["Wing", "Air down", "Lift"]}, 30),
        ({"id": "s04", "type": "end", "title": "Thanks"}, 16),
    ])
    notes = _areas(review.run(proj, tl), "visuals")
    assert not any(n["msg"].startswith("no pictures") for n in notes)
    assert any("covers only" in n["msg"] for n in notes) == small


def _wav(path, x, sr=16000):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


@needs_ffmpeg
@pytest.mark.parametrize("pause_db, speech_db, expect", [
    (-45, -55, "barely audible"),     # music ~27 dB under the voice in pauses: inaudible
    (-33, -40, None),                 # ~15 dB under in pauses, ~22 dB under speech: the toolkit default
    (-33, -24, "competes"),           # ducking missing: music only ~6 dB under the voice while it speaks
])
def test_music_level_prompts(tmp_path, pause_db, speech_db, expect):
    proj, tl = _film(tmp_path, [({"id": "s01", "type": "flow", "heading": "How", "items": ["A", "B", "C"]}, 40),
                                ({"id": "s02", "type": "end", "title": "Thanks"}, 20)])
    sr, secs = 16000, 24
    t = np.arange(sr * secs) / sr
    talking = (t % 2.0) < 1.0                                  # 1 s of speech, 1 s of pause
    voice = np.where(talking, 10 ** (-18 / 20) * np.sqrt(2) * np.sin(2 * np.pi * 220 * t), 0.0)
    rng = np.random.default_rng(0)
    level = np.where(talking, 10 ** (speech_db / 20), 10 ** (pause_db / 20))
    music = rng.standard_normal(len(t)) * level
    _wav(proj.build / "audio" / "voice.wav", voice)
    _wav(proj.build / "audio" / "music.wav", music)
    msgs = [n["msg"] for n in _areas(review.run(proj, tl), "sound")]
    if expect:
        assert any(expect in m for m in msgs), msgs
    else:
        assert not any("barely audible" in m or "competes" in m or "close to the voice" in m for m in msgs), msgs


@needs_ffmpeg
def test_a_sequence_of_different_diagrams_is_not_flagged_as_repetition(tmp_path):
    (tmp_path / "assets").mkdir(parents=True)
    for k in range(4):
        Image.new("RGBA", (1580, 600), (40, 60 + k * 30, 90, 255)).save(tmp_path / "assets" / f"d{k}.png")
    proj, tl = _film(tmp_path, [({"id": "s01", "type": "number", "value": "400 tonnes", "label": "a jumbo jet"}, 20)]
                     + [({"id": f"s0{k + 2}", "type": "image", "image": f"assets/d{k}.png", "heading": f"Step {k}"}, 22)
                        for k in range(4)]
                     + [({"id": "s06", "type": "flow", "heading": "Speed", "items": ["Speed", "Lift", "Climb"]}, 20),
                        ({"id": "s07", "type": "end", "title": "Thanks"}, 12)])
    msgs = [n["msg"] for n in review.run(proj, tl) if n["area"] == "layout"]
    assert not any("'image'" in m for m in msgs), msgs
