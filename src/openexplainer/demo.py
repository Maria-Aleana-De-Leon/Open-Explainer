"""`oex new --demo`: a starter project that renders on any machine without a microphone, TTS or speech model.

The "narration" is a synthetic voice-like buzz whose bursts follow the storyboard's words, and the word timings are
written directly, so the whole pipeline (alignment, scenes, captions, mixing, QA) runs offline in seconds.
"""
from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np

SCENES = [
    {"id": "s01", "type": "title", "say": "This is a demo film made without a microphone.",
     "title": "Your first *explainer*", "subtitle": "Rendered offline by oex"},
    {"id": "s02", "type": "flow", "say": "You write the script, record it, and the toolkit times every scene.",
     "heading": "How it works", "items": [{"text": "Script", "at": "write the script"},
                                          {"text": "Record", "at": "record it"},
                                          {"text": "Render", "at": "times every scene"}]},
    {"id": "s03", "type": "end", "say": "Replace this demo with your own voice.", "title": "Now it is your turn",
     "cta": "oex new my-film"},
]


def write(root: Path, rate: int = 48000) -> None:
    words, t = [], 0.4
    for sc in SCENES:
        for w in sc["say"].split():
            d = 0.12 + 0.045 * len(w.strip(".,"))
            words.append({"w": w, "s": round(t, 3), "e": round(t + d, 3)})
            t += d + 0.06
        t += 0.6
    total = t + 0.3
    n = int(total * rate)
    tt = np.arange(n) / rate
    sig = np.zeros(n, np.float32)
    for w in words:
        a, b = int(w["s"] * rate), int(w["e"] * rate)
        seg = tt[a:b]
        env = np.clip(np.sin(np.pi * (seg - seg[0]) / max(seg[-1] - seg[0], 1e-3)), 0, 1) ** 0.5
        sig[a:b] = 0.25 * env * (np.sin(2 * np.pi * 140 * seg) + 0.4 * np.sin(2 * np.pi * 560 * seg))
    (root / "audio").mkdir(parents=True, exist_ok=True)
    with wave.open(str(root / "audio" / "narration.wav"), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes((sig * 32767).astype("<i2").tobytes())
    (root / "build").mkdir(exist_ok=True)
    (root / "build" / "words.json").write_text(json.dumps({"language": "en", "source": "demo (synthetic)",
                                                           "duration": total, "words": words}))
    (root / "storyboard.json").write_text(json.dumps({"scenes": SCENES}, indent=2) + "\n")
