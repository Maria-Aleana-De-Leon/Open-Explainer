import numpy as np

from openexplainer.words import Word, norm, parse, refine, speech_onsets, tokens, validate


def test_norm_keeps_tagalog_and_strips_punctuation():
    assert norm("Ñino,") == "ñino"
    assert norm("'Yung") == "yung"
    assert tokens("Kasi, 'yung email — mabilis!") == ["kasi", "yung", "email", "mabilis"]


def test_recogniser_fragments_are_merged():
    from openexplainer.words import merge_fragments
    ws = [Word("carry", 0.0, 0.3), Word("400", 0.3, 0.6), Word(",000", 0.6, 0.9), Word("long", 1.0, 1.2),
          Word("-distance", 1.2, 1.6), Word("-", 2.5, 2.6)]
    assert [w.w for w in merge_fragments(ws)] == ["carry", "400,000", "long-distance", "-"]
    assert tokens("four hundred thousand") == ["400000"]


def test_number_words_match_recogniser_digits():
    assert tokens("about thirty one satellites") == ["about", "31", "satellites"]
    assert tokens("three hundred metres, four distances") == ["300", "metres", "4", "distances"]
    assert tokens("twenty thousand kilometres") == ["20000", "kilometres"]
    assert tokens("a hundred ways") == ["a", "hundred", "ways"]


def test_parse_elevenlabs_tts_alignment():
    chars = list("Hi there")
    starts = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
    ends = [s + 0.1 for s in starts]
    data = {"alignment": {"characters": chars, "character_start_times_seconds": starts,
                          "character_end_times_seconds": ends}}
    words, _ = parse(data)
    assert [(w.w, w.s, w.e) for w in words] == [("Hi", 0.0, 0.2), ("there", 0.3, 0.8)]


def test_parse_elevenlabs_scribe_skips_spacing_and_events():
    data = {"language_code": "tgl", "words": [
        {"text": "Kumusta", "start": 0.1, "end": 0.5, "type": "word"},
        {"text": " ", "start": 0.5, "end": 0.6, "type": "spacing"},
        {"text": "(laughs)", "start": 0.6, "end": 0.9, "type": "audio_event"},
        {"text": "po", "start": 0.9, "end": 1.0, "type": "word"}]}
    words, lang = parse(data)
    assert [w.w for w in words] == ["Kumusta", "po"]
    assert lang == "tgl"


def test_parse_segment_list_from_whisper_dump():
    data = [{"s": 0, "e": 1, "text": "a b", "words": [{"w": " a", "s": 0.0, "e": 0.4}, {"w": " b", "s": 0.5, "e": 1}]}]
    words, _ = parse(data)
    assert [w.w for w in words] == ["a", "b"]


def test_validate_reports_disorder_and_wrong_take():
    ws = [Word("a", 1.0, 1.2), Word("b", 0.2, 0.4), Word("c", 2.0, 1.5)]
    problems = validate(ws, audio_duration=1.0)
    assert any("not in order" in p for p in problems)
    assert any("ends before it starts" in p for p in problems)
    assert any("different take" in p for p in problems)


def _signal(segments, total, rate=16000):
    t = np.arange(int(total * rate)) / rate
    x = np.zeros_like(t, dtype=np.float32)
    for a, b in segments:
        m = (t >= a) & (t < b)
        x[m] = 0.3 * np.sin(2 * np.pi * 200 * t[m])
    return x


def test_speech_onsets_counts_speech_at_time_zero():
    on = speech_onsets(_signal([(0.0, 0.5), (1.0, 1.5)], 2.0))
    assert abs(on[0]) < 0.011 and abs(on[1] - 1.0) < 0.011


def test_refine_moves_early_pause_words_to_the_real_onset():
    x = _signal([(0.0, 0.8), (1.5, 2.2)], 3.0)
    words = [Word("one", 0.0, 0.4), Word("two", 0.4, 0.8), Word("three", 1.3, 1.8), Word("four", 1.8, 2.2)]
    out, moved = refine(words, x)
    assert moved == 1
    assert abs(out[2].s - 1.5) < 0.011       # was 0.2 s early, snapped to the onset
    assert out[3].s == 1.8                   # mid-phrase word untouched
