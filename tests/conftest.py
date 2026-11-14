import json
import math
import shutil
import struct
import subprocess
import wave
from pathlib import Path

import pytest

HAS_FFMPEG = shutil.which("ffmpeg") is not None
needs_ffmpeg = pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed")


def tone_wav(path: Path, segments: list[tuple[float, float]], total: float, rate: int = 48000, freq: float = 220.0):
    """A WAV with a 220 Hz buzz (voice stand-in) inside each (start, end) segment and silence elsewhere."""
    n = int(total * rate)
    frames = bytearray()
    for i in range(n):
        t = i / rate
        on = any(a <= t < b for a, b in segments)
        v = 0.3 * math.sin(2 * math.pi * freq * t) * (1 + 0.5 * math.sin(2 * math.pi * 3 * t)) if on else 0.0
        frames += struct.pack("<h", int(max(-1, min(1, v)) * 32767))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))


def make_project(root: Path, scenes: list[dict], words: list[dict], total: float, segments=None, **cfg) -> Path:
    """A project whose 'narration' is synthetic and whose word timings are given (no recogniser needed)."""
    (root / "audio").mkdir(parents=True, exist_ok=True)
    segs = segments or [(w["s"], w["e"]) for w in words]
    tone_wav(root / "audio" / "narration.wav", segs, total)
    base = {"title": "Test film", "narration": {"audio": "audio/narration.wav", "language": "en"},
            "captions": {"burn_in": True}}
    base.update(cfg)
    (root / "project.json").write_text(json.dumps(base))
    (root / "storyboard.json").write_text(json.dumps({"scenes": scenes}))
    (root / "build").mkdir(exist_ok=True)
    (root / "build" / "words.json").write_text(json.dumps({"language": "en", "words": words}))
    return root


def words_for(text: str, start: float = 0.2, per: float = 0.3, gap: float = 0.0) -> list[dict]:
    out, t = [], start
    for w in text.split():
        out.append({"w": w, "s": round(t, 3), "e": round(t + per - 0.05, 3)})
        t += per
    return out


def ffprobe_json(path: Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
                       capture_output=True, text=True, check=True)
    return json.loads(r.stdout)
