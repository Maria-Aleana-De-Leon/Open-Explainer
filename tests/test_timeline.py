import json

import pytest
from conftest import make_project, words_for

from openexplainer import timeline as TL
from openexplainer.config import load_project
from openexplainer.errors import ValidationError
from openexplainer.words import Word


def _proj(tmp_path, scenes, words, total, **cfg):
    make_project(tmp_path, scenes, words, total, **cfg)
    return load_project(tmp_path)


S1 = "Email is old. It started in the sixties."
S2 = "Today it moves billions of messages every single day."


def _words():
    a = words_for(S1, start=0.3)
    b = words_for(S2, start=a[-1]["e"] + 1.0)
    return a + b


def test_scenes_cut_inside_the_pause_and_cover_the_film(tmp_path):
    ws = _words()
    scenes = [{"id": "s01", "type": "statement", "say": S1, "text": "Email is *old*", "emphasis": "old"},
              {"id": "s02", "type": "number", "say": S2, "value": "300 billion", "at": "billions"}]
    p = _proj(tmp_path, scenes, ws, total=ws[-1]["e"] + 0.5)
    tl = TL.build(p, [Word(w["w"], w["s"], w["e"]) for w in ws], ws[-1]["e"] + 0.5)
    s1, s2 = tl["scenes"]
    last_s1, first_s2 = ws[len(S1.split()) - 1]["e"], ws[len(S1.split())]["s"]
    assert last_s1 < s2["start"] < first_s2                     # cut lands in the pause
    assert first_s2 - s2["start"] <= TL.LEAD_MAX + 1 / 30        # never too early
    assert s1["frames"] + s2["frames"] == tl["frames"]           # whole frames, no gaps
    assert s2["t"] == next(w["s"] for w in ws if w["w"] == "billions")
    assert s1["emphasis_t"] == next(w["s"] for w in ws if w["w"] == "old.")


def test_missing_cue_phrase_is_reported_with_scene_and_phrase(tmp_path):
    ws = _words()
    scenes = [{"id": "s01", "type": "bullets", "say": S1, "items": [{"text": "x", "at": "nineteen seventies"}]},
              {"id": "s02", "type": "end", "say": S2, "title": "Bye"}]
    p = _proj(tmp_path, scenes, ws, total=ws[-1]["e"] + 0.5)
    with pytest.raises(ValidationError) as e:
        TL.build(p, [Word(w["w"], w["s"], w["e"]) for w in ws], ws[-1]["e"] + 0.5)
    assert "s01" in str(e.value) and "nineteen seventies" in str(e.value)


def test_misrecognised_words_are_interpolated_not_fatal(tmp_path):
    ws = _words()
    ws[2]["w"] = "olde"  # the recogniser misheard "old."
    scenes = [{"id": "s01", "type": "statement", "say": S1, "text": "x", "emphasis": "old"},
              {"id": "s02", "type": "end", "say": S2, "title": "Bye"}]
    p = _proj(tmp_path, scenes, ws, total=ws[-1]["e"] + 0.5)
    tl = TL.build(p, [Word(w["w"], w["s"], w["e"]) for w in ws], ws[-1]["e"] + 0.5)
    assert ws[1]["e"] <= tl["scenes"][0]["emphasis_t"] <= ws[3]["s"]
    assert any("interpolated" in w for w in tl["warnings"])


def test_captions_use_the_script_spelling_with_recording_times(tmp_path):
    ws = _words()
    ws[2]["w"] = "olde"  # misheard
    scenes = [{"id": "s01", "type": "statement", "say": S1, "text": "x"},
              {"id": "s02", "type": "end", "say": S2, "title": "Bye"}]
    p = _proj(tmp_path, scenes, ws, total=ws[-1]["e"] + 0.5)
    tl = TL.build(p, [Word(w["w"], w["s"], w["e"]) for w in ws], ws[-1]["e"] + 0.5)
    cap = tl["scenes"][0]["caption_words"]
    assert [c[0] for c in cap] == S1.split()                       # script spelling, punctuation kept
    assert cap[0][1] == ws[0]["s"] and cap[3][1] == ws[3]["s"]     # matched words keep recording times
    assert ws[1]["e"] <= cap[2][1] <= ws[3]["s"]                   # misheard word interpolated


def test_wrong_take_is_rejected(tmp_path):
    ws = words_for("completely different words were recorded for this take today")
    scenes = [{"id": "s01", "type": "end", "say": S1, "title": "x"}]
    p = _proj(tmp_path, scenes, ws, total=ws[-1]["e"] + 0.5)
    with pytest.raises(Exception) as e:
        TL.build(p, [Word(w["w"], w["s"], w["e"]) for w in ws], ws[-1]["e"] + 0.5)
    assert "does not match" in str(e.value) or "found in the recording" in str(e.value)


def test_config_reports_every_problem_at_once(tmp_path):
    make_project(tmp_path, [{"id": "s01", "type": "title", "say": "hi"}], words_for("hi"), 1.0)
    cfg = json.loads((tmp_path / "project.json").read_text())
    cfg.update(fps=500, format="4:3", colour="red")
    (tmp_path / "project.json").write_text(json.dumps(cfg))
    with pytest.raises(ValidationError) as e:
        load_project(tmp_path)
    msg = str(e.value)
    assert "fps" in msg and "4:3" in msg and "colour" in msg


def test_scene_missing_required_content(tmp_path):
    make_project(tmp_path, [{"id": "s01", "type": "bullets", "say": "hi"},
                            {"id": "s01", "type": "flow", "say": "x", "items": []}], words_for("hi x"), 2.0)
    with pytest.raises(ValidationError) as e:
        load_project(tmp_path)
    assert "needs 'items'" in str(e.value) and "duplicate scene id" in str(e.value)
