"""Optional text-to-speech providers. Recorded narration is the primary path; TTS is a convenience.

Providers:
    say         macOS built-in voices (local, free). Private drafts and tests only: Apple's macOS licence allows
                its system voices for personal, non-commercial use and not for publishing or public sharing.
    elevenlabs  ElevenLabs API, with character timestamps (no transcription needed). Key from env
                ELEVENLABS_API_KEY only - never written to disk or project files.
    command     any local engine (e.g. Piper): a command template with {text_file} and {out} placeholders.

All providers read the storyboard's "say" text, join scenes with a pause, and write the project's narration file.
`synthesize` runs a provider into a temporary file and only replaces the narration after `check_speech` has
confirmed real, audible audio of a plausible length. A failure is reported as an error; there is no silent fallback
to another provider.
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
from .media import decode_mono, duration, ffmpeg

MIN_SPEECH_S = 0.5          # shorter than this is not narration
SILENCE_DBFS = -60.0        # peak below this is silence
MAX_WORDS_PER_S = 8.0       # faster than ~480 words/min means the audio stops early (truncated or partly failed)

FIXES = {
    "say": "macOS `say` exits without error when it cannot reach the speech service, which happens inside some "
           "sandboxes (for example an AI agent's sandboxed shell). Run `oex tts --provider say` in a normal "
           "Terminal, or let the agent run it outside its sandbox; or record the narration yourself",
    "command": "run your TTS command by hand on a short text and check that it writes audio to {out}",
    "elevenlabs": "check your ElevenLabs voice id and character quota, then run `oex tts` again",
}


def check_speech(path: Path, provider: str, words: int) -> float:
    """Raise OexError unless `path` holds real, audible audio of a plausible length for `words` words.

    Returns the duration in seconds."""
    fix = FIXES.get(provider, "record the narration yourself")
    if not path.exists() or path.stat().st_size == 0:
        raise OexError(f"{provider} produced no audio file", fix)
    try:
        d = duration(path)
    except OexError:
        raise OexError(f"{provider} produced a file with no playable audio ({path.name})", fix) from None
    if d < MIN_SPEECH_S:
        raise OexError(f"{provider} produced only {d:.2f}s of audio for a {words}-word script", fix)
    x = decode_mono(path, 16000)
    peak = float(abs(x).max()) if len(x) else 0.0
    if peak <= 10 ** (SILENCE_DBFS / 20):
        raise OexError(f"{provider} produced {d:.1f}s of silence, not speech", fix)
    if words >= 10 and d < words / MAX_WORDS_PER_S:
        raise OexError(f"{provider} produced only {d:.1f}s of audio for a {words}-word script "
                       f"(at least {words / MAX_WORDS_PER_S:.0f}s expected); the speech stopped early", fix)
    return d


def synthesize(proj, out: Path, provider: str, voice: str | None = None, rate: int | None = None,
               template: str | None = None, words_out: Path | None = None) -> float:
    """Make narration with `provider` and write it to `out` only if it is real speech. Returns its duration."""
    text, _ = script_text(proj)
    words = len(text.split())
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(f"{out.stem}.tts-new{out.suffix}")
    tmp.unlink(missing_ok=True)
    try:
        if provider == "say":
            say(proj, tmp, voice, rate)
        elif provider == "elevenlabs":
            elevenlabs(proj, tmp, voice, words_out=words_out)
        elif provider == "command":
            command(proj, tmp, template or "")
        else:
            raise OexError(f"unknown TTS provider {provider!r}", "use --provider say, elevenlabs or command")
        d = check_speech(tmp, provider, words)
        os.replace(tmp, out)
        return d
    finally:
        tmp.unlink(missing_ok=True)


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
        r = subprocess.run(cmd + [text], capture_output=True, text=True)
        if r.returncode:
            raise OexError(f"`say` failed (exit {r.returncode}): {r.stderr.strip()[-300:]}",
                           "check the voice name with `say -v '?'`")
        # `say` can exit 0 and leave an empty or header-only file; check_speech catches that after conversion
        if aiff.exists() and aiff.stat().st_size > 0:
            try:
                ffmpeg("-i", str(aiff), "-ar", "48000", "-ac", "1", str(out))
            except OexError:
                pass


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
            raise OexError(f"TTS command failed ({r.returncode}): {r.stderr[-300:]}", FIXES["command"])
        if raw.stat().st_size > 0:
            try:
                ffmpeg("-i", str(raw), "-ar", "48000", str(out))
            except OexError:
                pass                # unreadable output: check_speech reports it with the provider's fix
