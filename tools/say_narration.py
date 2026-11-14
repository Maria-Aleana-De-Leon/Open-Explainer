"""Generate a TEST narration from a storyboard with macOS `say` (local, offline).

Only for testing the pipeline. The output is not committed or distributed (Apple's macOS licence allows its system
voices for personal, non-commercial use only, not for publishing or public sharing). Real films use the creator's own
recording or their own TTS account.

usage: python tools/say_narration.py <project_dir> [--voice Samantha] [--rate 175] [--pause 450]
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("project")
ap.add_argument("--voice", default="Samantha")
ap.add_argument("--rate", type=int, default=175)
ap.add_argument("--pause", type=int, default=450, help="ms of silence between scenes")
ap.add_argument("--out", default=None)
a = ap.parse_args()
if not shutil.which("say"):
    sys.exit("macOS `say` not found: record the narration yourself or use your TTS provider")
root = Path(a.project)
cfg = json.loads((root / "project.json").read_text())
sb = json.loads((root / cfg.get("storyboard", "storyboard.json")).read_text())
text = f" [[slnc {a.pause}]] ".join(s["say"] for s in sb["scenes"])
out = Path(a.out) if a.out else root / cfg["narration"]["audio"]
out.parent.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as td:
    aiff = Path(td) / "n.aiff"
    subprocess.run(["say", "-v", a.voice, "-r", str(a.rate), "-o", str(aiff), text], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(aiff), "-ar", "48000", "-ac", "1", str(out)], check=True)
print(f"wrote {out}")
