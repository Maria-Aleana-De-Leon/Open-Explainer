"""Spec S1: mouth-shape track from audio."""
import numpy as np

from openexplainer.mouthtrack import OPEN, track, word_coverage

SR = 16000


def _tone(f, d, amp=0.3):
    t = np.arange(int(d * SR)) / SR
    return amp * np.sin(2 * np.pi * f * t) * (1 + 0.3 * np.sin(2 * np.pi * 4 * t))


def _vowel(f1, f2, d, amp=0.3, f2_gain=0.8):
    return _tone(f1, d, amp) + _tone(f2, d, amp * f2_gain)


def _sil(d):
    return np.zeros(int(d * SR))


def runs(seq):
    out, i = [], 0
    while i < len(seq):
        j = i
        while j < len(seq) and seq[j] == seq[i]:
            j += 1
        out.append((seq[i], j - i))
        i = j
    return out


def test_silence_is_rest_and_is_deterministic():
    x = np.concatenate([_sil(0.5), _vowel(500, 1200, 0.6), _sil(0.6)])
    a, b = track(x), track(x)
    assert a == b
    assert a[0] == "rest" and a[-1] == "rest"
    assert any(s in OPEN for s in a)


def test_short_gaps_close_the_mouth_long_pauses_rest():
    x = np.concatenate([_vowel(600, 1100, 0.5), _sil(0.1), _vowel(600, 1100, 0.5), _sil(0.6), _vowel(600, 1100, 0.5)])
    s = track(x)
    mid_short = s[int(0.55 * 24)]
    mid_long = s[int((1.1 + 0.3) * 24)]
    assert mid_short == "mbp" and mid_long == "rest"


def test_hiss_gives_fv_and_formant_balance_gives_spread_vs_round():
    rng = np.random.default_rng(0)
    hiss = np.fft.irfft(np.fft.rfft(rng.standard_normal(int(0.4 * SR))) * (np.fft.rfftfreq(int(0.4 * SR), 1 / SR) > 4000))
    x = np.concatenate([_vowel(700, 1150, 0.5), _sil(0.05), 0.25 * hiss / np.abs(hiss).max(), _sil(0.05),
                        _vowel(300, 2300, 0.5, 0.3, 1.5), _sil(0.05), _vowel(350, 700, 0.5, 0.3)])
    # stand-ins with real vowel acoustics: "ee" has a strong second formant above 900 Hz, rounded vowels keep both
    # formants low (here below 900 Hz), "ah" sits in between
    s = track(x)
    seg = lambda a, b: s[int(a * 24): int(b * 24)]
    assert "fv" in seg(0.6, 0.95)
    spread = seg(1.05, 1.45)
    rounded = seg(1.6, 2.0)
    assert spread.count("ee") > spread.count("oh") + spread.count("oo")
    assert rounded.count("oh") + rounded.count("oo") > rounded.count("ee")


def test_open_shapes_hold_at_least_two_frames_unless_the_mouth_closes():
    rng = np.random.default_rng(3)
    parts = []
    for _ in range(40):
        parts.append(_vowel(rng.uniform(250, 800), rng.uniform(700, 2600), rng.uniform(0.04, 0.3), rng.uniform(0.05, 0.4)))
        if rng.random() < 0.3:
            parts.append(_sil(rng.uniform(0.03, 0.15)))
    r = runs(track(np.concatenate(parts)))
    bad = [k for k, (lab, n) in enumerate(r) if lab in OPEN and n < 2 and k + 1 < len(r) and r[k + 1][0] in OPEN]
    assert not bad


def test_word_coverage():
    shapes = ["rest"] * 24 + ["ah"] * 12 + ["rest"] * 24 + ["ee"] * 12
    talk, rest = word_coverage(shapes, [(1.0, 1.5), (2.5, 3.0)])
    assert talk == 1.0 and rest == 1.0
