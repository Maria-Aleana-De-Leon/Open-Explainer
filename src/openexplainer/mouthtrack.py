"""Mouth-shape track from narration audio (spec S1, docs/specs/COMPONENTS.md).

Language-independent: no phoneme recogniser. Each analysis frame is described by three features,
normalised against the take itself:

    openness  how loud the frame is relative to the take's typical speech level      (0..1)
    spread    log energy ratio of the 900-2600 Hz band to the 250-900 Hz band        (z-score)
              high = spread lips (ee), low = rounded lips (oh, oo)
    hiss      share of energy above 3.5 kHz                                          (z-score)

Every shape has a prototype in that feature space. A dynamic-programming pass over the whole take chooses the label
sequence that best fits the frames while paying a cost for every change, with a hard minimum duration of
MIN_HOLD frames for open shapes. Silent frames become `rest` (long pauses) or `mbp` (short gaps).
"""
from __future__ import annotations

import numpy as np

SHAPES = ["rest", "mbp", "half", "ah", "ee", "oh", "oo", "fv"]
SPOKEN = ["mbp", "half", "ah", "ee", "oh", "oo", "fv"]           # labels the DP chooses between ("mbp" = gap)
OPEN = {"half", "ah", "ee", "oh", "oo", "fv"}

# prototypes: (openness, spread, hiss)
PROTO = {
    "half": (0.20, 0.0, -0.3),
    "ah":   (0.80, 0.0, -0.3),
    "ee":   (0.60, 1.4, 0.0),
    "oh":   (0.75, -1.4, -0.3),
    "oo":   (0.35, -1.7, -0.3),
    "fv":   (0.35, 0.0, 2.3),
}
WEIGHT = np.array([3.0, 0.8, 0.9])
SWITCH = 1.2          # cost of changing shape
MIN_HOLD = 2          # frames an open shape is held at least
REST_GAP = 0.25       # silence at least this long (s) shows the resting mouth


def _features(x: np.ndarray, sr: int, rate: float):
    hop = sr / rate
    n = int(len(x) / hop)
    if n == 0:
        return None
    nfft = 1024
    win = np.hanning(nfft).astype(np.float32)
    f = np.fft.rfftfreq(nfft, 1 / sr)
    b1, b2, b3 = (f >= 250) & (f < 900), (f >= 900) & (f < 2600), f >= 3500
    centers = (np.arange(n) * hop + hop / 2).astype(int)
    pad = np.pad(x, (nfft // 2, nfft // 2))
    frames = np.stack([pad[c: c + nfft] for c in centers]) * win
    p = np.abs(np.fft.rfft(frames, axis=1)) ** 2
    e1, e2, e3 = p[:, b1].sum(1) + 1e-10, p[:, b2].sum(1) + 1e-10, p[:, b3].sum(1) + 1e-10
    tot = p.sum(1) + 1e-10
    level = 10 * np.log10(tot)
    return level, np.log(e2 / e1), e3 / tot


def track(x: np.ndarray, sr: int = 16000, rate: float = 24.0) -> list[str]:
    """One shape label per 1/rate seconds."""
    feats = _features(x, sr, rate)
    if feats is None:
        return []
    level, spread, hiss = feats
    ref = np.percentile(level, 90)
    voiced = level > ref - 32
    if not voiced.any():
        return ["rest"] * len(level)
    # openness = rank of the frame's level among this take's voiced frames (0 quietest .. 1 loudest), so every take
    # uses the full range of mouth sizes whatever its recording level or dynamics
    order = np.sort(level[voiced])
    openness = np.searchsorted(order, level) / max(1, len(order))
    # spread: robust z-score (the band ratio is roughly symmetric); hiss: absolute share, saturating at 35 %
    m = np.median(spread[voiced])
    s = np.subtract(*np.percentile(spread[voiced], [75, 25])) / 1.35 + 1e-6
    spread_z = np.clip((spread - m) / s, -2.5, 2.5)
    hiss_n = np.clip(hiss / 0.35, 0, 1) * 3.0 - 0.3

    feat = np.stack([openness, spread_z, hiss_n], 1)
    labels = SPOKEN
    proto = np.array([PROTO.get(l, (0.0, 0.0, 0.0)) for l in labels])
    emit = (((feat[:, None, :] - proto[None, :, :]) ** 2) * WEIGHT).sum(-1)       # (n, L)
    gap = labels.index("mbp")
    emit[:, gap] = np.where(voiced, 6.0, 0.0)                                     # gaps only where it is quiet
    emit[~voiced] += np.where(np.arange(len(labels)) == gap, 0.0, 8.0)
    return _postprocess(_decode(emit, labels), voiced, rate)


def _decode(emit: np.ndarray, labels: list[str]) -> list[str]:
    """Viterbi over (label, held) states; open labels must be held MIN_HOLD frames before changing."""
    n, L = emit.shape
    H = MIN_HOLD                       # age index 0..H-1; H-1 means "held long enough"
    gap = labels.index("mbp")
    INF = float("inf")
    cost = np.full((L, H), INF)
    cost[:, 0] = emit[0]
    back = np.zeros((n, L, H, 2), np.int16)
    for t in range(1, n):
        new = np.full((L, H), INF)
        ptr = np.zeros((L, H, 2), np.int16)
        for i in range(L):                         # stay on the same shape: age advances
            for h in range(H):
                nh = min(h + 1, H - 1)
                if cost[i, h] < new[i, nh]:
                    new[i, nh] = cost[i, h]
                    ptr[i, nh] = (i, h)
        for j in range(L):                         # change to shape j (starts at age 0)
            for i in range(L):
                if i == j:
                    continue
                for h in range(H):
                    # an open shape may only end once held, unless the mouth closes (j is a gap) or i is a gap
                    if h < H - 1 and i != gap and j != gap:
                        continue
                    c = cost[i, h] + SWITCH
                    if c < new[j, 0]:
                        new[j, 0] = c
                        ptr[j, 0] = (i, h)
        cost = new + emit[t][:, None]
        back[t] = ptr
    j, h = np.unravel_index(int(np.argmin(cost)), cost.shape)
    out = [labels[j]]
    for t in range(n - 1, 0, -1):
        j, h = back[t, j, h]
        out.append(labels[j])
    return out[::-1]


def _postprocess(seq: list[str], voiced: np.ndarray, rate: float) -> list[str]:
    out = list(seq)
    i, n = 0, len(out)
    min_rest = int(round(REST_GAP * rate))
    while i < n:
        if not voiced[i]:
            j = i
            while j < n and not voiced[j]:
                j += 1
            label = "rest" if (j - i) >= min_rest or i == 0 or j == n else "mbp"
            for k in range(i, j):
                out[k] = label
            i = j
        else:
            i += 1
    return out


def word_coverage(shapes: list[str], words: list[tuple[float, float]], rate: float = 24.0) -> tuple[float, float]:
    """(share of words during which the mouth opens, share of pauses >= 0.6 s that show the resting mouth)."""
    if not words:
        return 0.0, 1.0
    talking = sum(1 for s, e in words if any(x in OPEN for x in shapes[int(s * rate): max(int(s * rate) + 1, int(e * rate))]))
    pauses = [(a[1], b[0]) for a, b in zip(words, words[1:]) if b[0] - a[1] >= 0.6]
    resting = sum(1 for a, b in pauses if 0 <= int((a + b) / 2 * rate) < len(shapes)
                  and shapes[int((a + b) / 2 * rate)] == "rest")
    return talking / len(words), (resting / len(pauses)) if pauses else 1.0
