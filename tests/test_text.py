from openexplainer.text import layout, parse_rich


def test_accent_inside_a_word_keeps_punctuation_attached():
    ws = parse_rich("Why is the sky *blue*?")
    assert [w.text for w in ws] == ["Why", "is", "the", "sky", "blue?"]
    assert ws[-1].runs == (("blue", True), ("?", False))


def test_accent_spanning_words_and_same_text_different_runs_do_not_collide():
    a = parse_rich("*blue?*")[0]
    b = parse_rich("*blue*?")[0]
    assert a.text == b.text and a.runs != b.runs


def test_layout_shrinks_to_fit_and_wraps():
    lay = layout("a very long headline that cannot possibly fit on one line at this size", "bold", 600, 200, 120)
    assert lay.width <= 602 and lay.height <= 200 and len(lay.lines) > 1
