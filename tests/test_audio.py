"""Spec S2: ducking depth, recovery in pauses, lookahead, limiter."""
import numpy as np
from conftest import needs_ffmpeg, tone_wav

from openexplainer import audio as A
from openexplainer.media import decode_mono


def _music(path, total):
    t = np.arange(int(total * A.SR)) / A.SR
    A._write_wav(path, np.stack([0.5 * np.sin(2 * np.pi * 330 * t)] * 2, 1))


def _db(x):
    return 20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-12)


@needs_ffmpeg
def test_duck_depth_recovery_and_lookahead(tmp_path):
    total = 6.0
    tone_wav(tmp_path / "v.wav", [(1.0, 2.5), (4.0, 5.0)], total)       # speech 1.0-2.5 s and 4.0-5.0 s
    _music(tmp_path / "m.wav", total)
    rep = A.music_bed(tmp_path / "m.wav", tmp_path / "v.wav", tmp_path / "bed.wav", total, gain_db=-20, duck_db=10,
                      fade_out=0.0)
    bed = decode_mono(tmp_path / "bed.wav", A.SR)
    seg = lambda a, b: bed[int(a * A.SR): int(b * A.SR)]
    base = _db(seg(3.2, 3.8))                         # long pause: back at base level
    under = _db(seg(1.5, 2.2))                        # under speech
    assert abs((base - under) - 10) <= 1.5, (base, under)
    before = _db(seg(0.96, 1.0))                      # just before speech starts: already going down (lookahead)
    assert before < _db(seg(0.6, 0.8)) - 1.0
    assert rep["speech_share"] > 0.3


@needs_ffmpeg
def test_final_mix_respects_true_peak(tmp_path):
    total = 2.0
    t = np.arange(int(total * A.SR)) / A.SR
    A._write_wav(tmp_path / "v.wav", np.stack([0.99 * np.sign(np.sin(2 * np.pi * 220 * t))] * 2, 1))
    A._write_wav(tmp_path / "m.wav", np.stack([0.9 * np.sin(2 * np.pi * 110 * t)] * 2, 1))
    A.final_mix(tmp_path / "v.wav", tmp_path / "m.wav", None, tmp_path / "mix.wav", total, tp=-1.5)
    from openexplainer.media import loudness
    assert loudness(tmp_path / "mix.wav")["true_peak_db"] <= -1.0
