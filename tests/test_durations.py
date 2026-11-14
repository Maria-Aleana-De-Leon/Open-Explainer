"""Duration planning: predictions match real takes; targets turn into word counts; nothing slows speech."""

from conftest import make_project, words_for

from openexplainer import durations as D


def test_estimate_matches_measured_takes():
    # (script words, measured effective wpm, real film length incl. 1.2 s tail) from the example takes
    for words, wpm, real in ((67, 152, 27.93), (415, 155, 161.9), (757, 148, 307.83)):
        e = D.estimate(["w " * words], wpm)
        assert abs(e["seconds"] - real) < 2.0, (words, e["seconds"], real)


def test_words_for_target_round_trip():
    n = D.words_for(180, 20, 150)
    assert abs(D.estimate(["w " * n], 150)["seconds"] - 180) < 1.0
    assert D.parse_target("3:00") == 180 and D.parse_target("90s") == 90 and D.parse_target("5m") == 300


def test_report_says_how_many_words_to_add_or_cut():
    short = D.report(["word " * 300], 180, 150, "x")
    assert "add about" in short[1]
    long = D.report(["word " * 600], 180, 150, "x")
    assert "cut about" in long[1]


def test_measured_pace_from_a_take(tmp_path):
    ws = words_for(" ".join(["word"] * 50), start=0.0, per=0.4)          # 50 words over 20 s = 150 wpm
    make_project(tmp_path, [{"id": "s01", "type": "end", "say": " ".join(["word"] * 50), "title": "x"}], ws, 21)
    assert abs(D.measured_wpm(tmp_path / "build" / "words.json", 50) - 150) < 5
