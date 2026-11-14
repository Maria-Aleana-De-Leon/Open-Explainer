"""Thin, checked wrappers around ffmpeg / ffprobe."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from .errors import OexError


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise OexError(f"{name} not found on PATH",
                       "install FFmpeg (macOS: brew install ffmpeg, Windows: winget install Gyan.FFmpeg, "
                       "Linux: apt install ffmpeg) and re-run `oex doctor`")
    return path


def ffmpeg(*args: str, quiet: bool = True) -> None:
    cmd = [require_tool("ffmpeg"), "-hide_banner", "-nostdin", "-y"]
    if quiet:
        cmd += ["-v", "error"]
    cmd += list(args)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        tail = "\n".join(r.stderr.strip().splitlines()[-8:])
        raise OexError(f"ffmpeg failed (exit {r.returncode}):\n{tail}", "check the input file named above exists and plays")


def probe(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        raise OexError(f"file not found: {p}")
    r = subprocess.run([require_tool("ffprobe"), "-v", "error", "-print_format", "json", "-show_format",
                        "-show_streams", str(p)], capture_output=True, text=True)
    if r.returncode != 0:
        raise OexError(f"ffprobe cannot read {p}: {r.stderr.strip()[:300]}", "the file may be corrupt or not media")
    return json.loads(r.stdout)


def duration(path: str | Path) -> float:
    info = probe(path)
    d = info.get("format", {}).get("duration")
    if d is None:
        raise OexError(f"no duration in {path}")
    return float(d)


def decode_mono(path: str | Path, rate: int = 16000):
    """Decode any audio/video file to a float32 mono numpy array at `rate`."""
    import numpy as np

    r = subprocess.run([require_tool("ffmpeg"), "-v", "error", "-nostdin", "-i", str(path), "-vn", "-ac", "1",
                        "-ar", str(rate), "-f", "s16le", "-"], capture_output=True)
    if r.returncode != 0:
        raise OexError(f"cannot decode audio from {path}: {r.stderr.decode(errors='replace')[-300:]}")
    return np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768.0


def loudness(path: str | Path) -> dict:
    """EBU R128 integrated loudness (LUFS) and true peak (dBTP) of a file's audio."""
    r = subprocess.run([require_tool("ffmpeg"), "-hide_banner", "-nostdin", "-nostats", "-i", str(path),
                        "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True)
    summary = r.stderr.split("Summary:")[-1]
    i = re.search(r"I:\s+(-?[\d.]+|-inf) LUFS", summary)
    pk = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summary)

    def num(m):
        if not m:
            return None
        return float("-inf") if m.group(1) == "-inf" else float(m.group(1))

    return {"lufs": num(i), "true_peak_db": num(pk)}
