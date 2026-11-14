from openexplainer.captions import chunks, write_srt, write_vtt


def test_chunks_break_on_sentences_pauses_and_length():
    ws = [("Hello", 0.0, 0.3), ("there.", 0.3, 0.6), ("This", 0.7, 0.9), ("is", 0.9, 1.0), ("a", 1.0, 1.1),
          ("test", 1.1, 1.3), ("after", 2.5, 2.8), ("pause", 2.8, 3.0)]
    cs = chunks(ws, max_words=6)
    assert [c.text for c in cs] == ["Hello there.", "This is a test", "after pause"]
    assert cs[0].end <= cs[1].start  # holds never overlap the next caption


def test_srt_and_vtt_timestamps(tmp_path):
    cs = chunks([("Kumusta", 0.0, 0.5), ("po.", 0.5, 1.234)])
    write_srt(tmp_path / "a.srt", cs)
    write_vtt(tmp_path / "a.vtt", cs)
    assert "00:00:00,000 --> 00:00:01,734\nKumusta po." in (tmp_path / "a.srt").read_text()
    assert (tmp_path / "a.vtt").read_text().startswith("WEBVTT")
