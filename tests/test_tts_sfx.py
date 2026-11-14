import base64
import json
import shutil
import subprocess

import pytest
from conftest import make_project, needs_ffmpeg, tone_wav, words_for

from openexplainer import sfx as X
from openexplainer import tts
from openexplainer.config import load_project
from openexplainer.pipeline import import_words
from openexplainer.words import load


@needs_ffmpeg
def test_elevenlabs_response_becomes_narration_and_word_timings(tmp_path, monkeypatch):
    """The live API is not called (no key in CI); the response handling is tested with a recorded-shape reply."""
    make_project(tmp_path, [{"id": "s01", "type": "end", "say": "Hi there", "title": "x"}], words_for("Hi there"), 1.0)
    (tmp_path / "audio" / "narration.wav").unlink()
    mp3 = tmp_path / "t.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=f=220:d=1.0", str(mp3)], check=True)
    chars = list("Hi there")
    reply = {"audio_base64": base64.b64encode(mp3.read_bytes()).decode(),
             "alignment": {"characters": chars, "character_start_times_seconds": [i * 0.1 for i in range(8)],
                           "character_end_times_seconds": [i * 0.1 + 0.1 for i in range(8)]}}
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test")
    (tmp_path / "audio" / "narration.wav").touch()
    p = load_project(tmp_path)
    (tmp_path / "audio" / "narration.wav").unlink()
    out = tmp_path / "audio" / "narration.wav"
    al = tmp_path / "build" / "al.json"
    tts.elevenlabs(p, out, "voice123", words_out=al, _post=lambda url, body: reply)
    assert out.exists()
    import_words(load_project(tmp_path), al)
    assert [w.w for w in load(tmp_path / "build" / "words.json")] == ["Hi", "there"]


def test_elevenlabs_requires_key_from_environment(tmp_path, monkeypatch):
    make_project(tmp_path, [{"id": "s01", "type": "end", "say": "Hi", "title": "x"}], words_for("Hi"), 1.0)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(Exception) as e:
        tts.elevenlabs(load_project(tmp_path), tmp_path / "x.wav", "v")
    assert "ELEVENLABS_API_KEY" in str(e.value)


@needs_ffmpeg
def test_sfx_add_dedupe_query_rotation_and_check(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    for i, name in enumerate(("whoosh-a", "whoosh-b", "pop-1", "ding-ok")):
        tone_wav(lib / f"{name}.wav", [(0.05, 0.3 + 0.1 * i)], 0.4 + 0.1 * i, freq=200 + 50 * i)
    shutil.copy(lib / "pop-1.wav", lib / "pop-copy.wav")                # same audio under another name
    cat = tmp_path / "catalog.json"
    quiet = dict(log=lambda *_: None)
    assert X.add_folder(cat, lib, "licensed", "CC0-1.0", "me", **quiet) == 4
    assert X.add_folder(cat, lib, "licensed", "CC0-1.0", "me", **quiet) == 0
    c = X.load(cat)
    assert c["schema"] == "oex-sfx-2"
    assert {s["kind"] for s in c["sounds"]} == {"transition", "pop", "chime"}
    assert all(not s["file"].startswith("/") for s in c["sounds"])      # portable relative paths
    assert [s["id"] for s in X.query(c, "whoosh")] == ["whoosh-a", "whoosh-b"]          # shorter first
    assert [s["id"] for s in X.query(c, "kind:transition max:0.45")] == ["whoosh-a"]
    assert X.query(c, "rights:unknown") == [] and len(X.query(c, "rights:safe")) == 4
    assert X.choose(c, "transition", 0)["id"] != X.choose(c, "transition", 1)["id"]
    with pytest.raises(Exception):
        X.add_folder(cat, lib, "licensed", None, **quiet)               # licensed needs a licence
    shutil.copy(lib / "pop-1.wav", lib / "whoosh-a.wav")
    assert any("whoosh-a" in p for p in X.verify(cat))
    out = X.cut(cat, "pop-1", tmp_path / "cue.wav", 0.0, 0.2, -6)
    assert out.exists()
    with pytest.raises(Exception):
        X.cut(cat, "pop-1", tmp_path / "cue.wav")                        # never overwrites


@needs_ffmpeg
def test_sfx_map_any_json_catalog(tmp_path):
    other = tmp_path / "other"
    (other / "sounds").mkdir(parents=True)
    tone_wav(other / "sounds" / "a.wav", [(0.0, 0.2)], 0.3)
    tone_wav(other / "sounds" / "b.wav", [(0.0, 0.5)], 0.6, freq=500)
    (other / "index.json").write_text(json.dumps({"items": [
        {"path": "sounds/a.wav", "title": "Soft swoosh", "cat": "transition", "lic": {"state": "cleared", "name": "CC0"}},
        {"path": "sounds/b.wav", "title": "Mystery", "cat": "other", "lic": {"state": "?"}},
        {"path": "sounds/missing.wav", "title": "Gone"}]}))
    mapping = {"records": "items", "file": "path", "name": "title", "kind": "cat", "status": "lic.state",
               "licence": "lic.name", "status_values": {"cleared": "licensed"}}
    cat = tmp_path / "cat.json"
    assert X.add_mapped(cat, other / "index.json", mapping, log=lambda *_: None) == 2
    by = {s["name"]: s for s in X.load(cat)["sounds"]}
    assert by["Soft swoosh"]["rights"] == {"status": "licensed", "licence": "CC0", "holder": None, "source": None,
                                           "credit_line": None}
    assert by["Mystery"]["rights"]["status"] == "unknown"


@needs_ffmpeg
def test_automatic_cues_are_varied_not_a_whoosh_on_every_cut(tmp_path):
    from types import SimpleNamespace
    lib = tmp_path / "lib"
    lib.mkdir()
    for i, n in enumerate(("whoosh-a", "pop-a", "ding-a", "impact-a")):
        tone_wav(lib / f"{n}.wav", [(0.0, 0.3)], 0.4, freq=200 + 60 * i)
    cat = tmp_path / "c.json"
    X.add_folder(cat, lib, "own", **dict(log=lambda *_: None))
    scenes = []
    for k in range(20):                                   # 20 scenes, 6 s each, every one with an emphasis beat
        s = k * 6.0
        scenes.append({"id": f"s{k}", "type": "statement", "start": s, "end": s + 6, "t": s + 0.5,
                       "emphasis_t": s + 3.0, "words": []})
    tl = {"scenes": scenes, "duration": 120.0}
    proj = SimpleNamespace(cfg={"sfx": {"catalog": str(cat), "auto": True, "gain_db": -12, "max_per_minute": 6,
                                        "min_gap": 3.0}}, path=lambda p: tmp_path / p)
    ev = X.plan_cues(proj, tl, log=lambda *_: None)
    roles = [e["role"] for e in ev]
    assert len(ev) <= 12                                                   # 6/min budget
    assert roles.count("transition") <= len(ev) // 2 + 1                   # at most half are whooshes
    tr = sorted(e["event_t"] for e in ev if e["role"] == "transition")
    assert all(b - a >= X.TRANSITION_GAP for a, b in zip(tr, tr[1:]))
    assert "emphasis" in roles
