"""Spec S4: presenter scheduling."""
import numpy as np

from openexplainer.presenter import BLINK, _blinks, _nod, _stressed


def test_blinks_are_seeded_spaced_and_avoid_state_changes():
    a = _blinks("My film", 120.0, [10.0, 30.0])
    assert a == _blinks("My film", 120.0, [10.0, 30.0])            # deterministic per title
    assert a != _blinks("Another film", 120.0, [10.0, 30.0])
    singles = [t for i, t in enumerate(a) if not (i and t - a[i - 1] < 0.5)]
    gaps = np.diff(singles)
    assert gaps.min() >= 2.5 - 1e-6 and gaps.max() <= 6.0 + 0.5
    assert all(abs(t - s) > 0.25 and abs(t + BLINK - s) > 0.25 for t in a for s in (10.0, 30.0))


def test_nods_follow_stressed_words_and_decay():
    sr = 16000
    x = np.zeros(sr * 4, np.float32)
    x[int(0.5 * sr): int(0.8 * sr)] = 0.1
    x[int(0.85 * sr): int(1.1 * sr)] = 0.1
    x[int(2.0 * sr): int(2.3 * sr)] = 0.8            # loud word after a pause
    words = [(0.5, 0.8), (0.85, 1.1), (2.0, 2.3)]
    on = _stressed(words, x)
    assert 0.5 in on and 2.0 in on and 0.85 not in on   # mid-phrase quiet word gets no nod
    assert all(b - a >= 0.8 for a, b in zip(on, on[1:]))
    assert _nod(2.0 + 0.08, on) > 0.95 and _nod(2.0 + 1.2, on) < 0.02 and _nod(1.9, [2.0]) == 0
