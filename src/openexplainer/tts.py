"""Optional text-to-speech providers. Recorded narration is the primary path; TTS is a convenience.

Providers:
    say         macOS built-in voices (local, free). Good for drafts and tests.
    elevenlabs  ElevenLabs API, with character timestamps (no transcription needed). Key from env
                ELEVENLABS_API_KEY only - never written to disk or project files.
    command     any local engine (e.g. Piper): a command template with {text_file} and {out} placeholders.

All providers read the storyboard's "say" text, join scenes with a pause, and write the project's narration file.
"""
from __future__ import annotations

import base64
import json
import os
import shlex
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from .errors import OexError
from .media import ffmpeg


def script_text(proj, pause_ms: int = 600) -> tuple[str, list[str]]:
    paras = [s["say"].strip() for s in proj.storyboard["scenes"]]
    return "\n\n".join(paras), paras


def say(proj, out: Path, voice: str | None, rate: int | None, pause_ms: int = 600) -> None:
    if not shutil.which("say"):
        raise OexError("the 'say' provider needs macOS", "use --provider elevenlabs or --provider command")
    _, paras = script_text(proj)
    text = f" [[slnc {pause_ms}]] ".join(paras)
    with tempfile.TemporaryDirectory() as td:
        aiff = Path(td) / "n.aiff"
        cmd = ["say", "-o", str(aiff)] + (["-v", voice] if voice else []) + (["-r", str(rate)] if rate else [])
        subprocess.run(cmd + [text], check=True)
        ffmpeg("-i", str(aiff), "-ar", "48000", "-ac", "1", str(out))


def elevenlabs(proj, out: Path, voice: str | None, model: str = "eleven_multilingual_v2",
               words_out: Path | None = None, _post=None) -> None:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise OexError("ELEVENLABS_API_KEY is not set",
                       "export ELEVENLABS_API_KEY=... in your shell (it is read from the environment only)")
    if not voice:
        raise OexError("--voice <voice_id> is required for ElevenLabs", "copy the voice id from your ElevenLabs voices")
    text, _ = script_text(proj)
    body = json.dumps({"text": text, "model_id": model}).encode()
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps?output_format=mp3_44100_128"
    if _post is None:
        req = urllib.request.Request(url, data=body, headers={"xi-api-key": key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                data = json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise OexError(f"ElevenLabs returned HTTP {e.code}: {e.read()[:300]!r}",
                           "check the key, the voice id and your character quota") from e
    else:
        data = _post(url, body)
    mp3 = out.with_suffix(".mp3")
    mp3.write_bytes(base64.b64decode(data["audio_base64"]))
    if out.suffix != ".mp3":
        ffmpeg("-i", str(mp3), "-ar", "48000", str(out))
        mp3.unlink()
    if words_out is not None:
        words_out.parent.mkdir(parents=True, exist_ok=True)
        words_out.write_text(json.dumps({"alignment": data.get("alignment") or data.get("normalized_alignment")}))


def command(proj, out: Path, template: str) -> None:
    if "{text_file}" not in template or "{out}" not in template:
        raise OexError("--command must contain {text_file} and {out}",
                       "e.g. --command \"piper -m en_US-amy-medium.onnx -f {out} < {text_file}\"")
    text, _ = script_text(proj)
    with tempfile.TemporaryDirectory() as td:
        tf = Path(td) / "script.txt"
        tf.write_text(text, encoding="utf-8")
        raw = Path(td) / "raw.wav"
        cmd = template.format(text_file=shlex.quote(str(tf)), out=shlex.quote(str(raw)))
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if r.returncode or not raw.exists():
            raise OexError(f"TTS command failed ({r.returncode}): {r.stderr[-300:]}")
        ffmpeg("-i", str(raw), "-ar", "48000", str(out))
