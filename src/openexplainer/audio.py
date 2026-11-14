"""Audio (spec S2): voice mastering, ducked music, SFX placement, true-peak limiting, stems, loudness report.

Voice: FFmpeg's two-pass EBU R128 `loudnorm` (measure, then linear normalisation) to the target LUFS / true peak.
The voice is never time-stretched or edited; visuals move to the words, never the reverse.
Music: looped/trimmed to the film and faded; ducked under the voice by a gain curve computed here from a
speech-presence measure of the mastered voice (lookahead, attack, release) - see `speech_presence`.
SFX: each cue placed at its time with its gain. Final: voice + music + SFX -> limiter -> 48 kHz stereo WAV.
"""
from __future__ import annotations

import json
import re
import subprocess
import wave
from pathlib import Path

import numpy as np

from .errors import OexError
from .media import ffmpeg, loudness, require_tool

SR = 48000


def _loudnorm_measure(src: Path, target: float, tp: float) -> dict:
    r = subprocess.run([require_tool("ffmpeg"), "-hide_banner", "-nostdin", "-i", str(src), "-af",
                        f"loudnorm=I={target}:TP={tp}:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    if not m:
        raise OexError(f"could not measure loudness of {src}", "check the narration file plays and is not silent")
    return json.loads(m.group(0))


def master_voice(src: Path, out: Path, total: float, target: float = -16.0, tp: float = -1.5) -> dict:
    meas = _loudnorm_measure(src, target, tp)
    if meas["input_i"] in ("-inf", "inf") or float(meas["input_i"]) < -70:
        raise OexError(f"narration {src} is silent (measured {meas['input_i']} LUFS)", "check you exported the right take")
    flt = (f"loudnorm=I={target}:TP={tp}:LRA=11:measured_I={meas['input_i']}:measured_TP={meas['input_tp']}:"
           f"measured_LRA={meas['input_lra']}:measured_thresh={meas['input_thresh']}:offset={meas['target_offset']}:"
           f"linear=true,aresample={SR},aformat=channel_layouts=stereo,apad=whole_dur={total:.4f},"
           f"atrim=end={total:.4f}")
    ffmpeg("-i", str(src), "-af", flt, "-ar", str(SR), "-c:a", "pcm_s16le", str(out))
    return {"input_lufs": float(meas["input_i"]), "input_tp": float(meas["input_tp"])}


FRAME = 0.02        # speech-presence analysis frame (s)
ATTACK = 0.06       # duck reaches depth within this time
RELEASE = 0.40      # and recovers over this time
LOOKAHEAD = 0.08    # the duck starts this long before speech


def _decode(src: Path, total: float, loop: bool) -> np.ndarray:
    """(n, 2) float32 at SR, exactly `total` seconds (looped or padded)."""
    args = [require_tool("ffmpeg"), "-v", "error", "-nostdin"] + (["-stream_loop", "-1"] if loop else []) + \
           ["-i", str(src), "-t", f"{total:.4f}", "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"]
    r = subprocess.run(args, capture_output=True)
    if r.returncode:
        raise OexError(f"cannot decode {src}: {r.stderr.decode(errors='replace')[-300:]}")
    a = np.frombuffer(r.stdout, np.float32).reshape(-1, 2)
    n = int(round(total * SR))
    return np.pad(a, ((0, max(0, n - len(a))), (0, 0)))[:n]


def _write_wav(path: Path, a: np.ndarray) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(a, -1, 1) * 32767).astype("<i2").tobytes())


def speech_presence(voice: np.ndarray, sr: int = SR) -> np.ndarray:
    """0..1 per FRAME: how much speech is present, with lookahead and attack/release smoothing."""
    hop = int(sr * FRAME)
    n = len(voice) // hop
    mono = voice[: n * hop].mean(1) if voice.ndim == 2 else voice[: n * hop]
    db = 10 * np.log10((mono.reshape(n, hop) ** 2).mean(1) + 1e-12)
    loud = db[db > db.max() - 50]
    ref = np.percentile(loud, 95) if len(loud) else db.max()
    raw = np.clip((db - (ref - 30)) / 8, 0, 1)                      # fully "speech" within ~22 dB of the peaks
    look = int(round(LOOKAHEAD / FRAME))
    if look:   # each frame sees the speech coming in the next LOOKAHEAD seconds
        raw = np.lib.stride_tricks.sliding_window_view(np.pad(raw, (0, look)), look + 1).max(1)
    up, down = np.exp(-FRAME / ATTACK), np.exp(-FRAME / RELEASE)
    out = np.zeros_like(raw)
    v = 0.0
    for i, x in enumerate(raw):
        k = up if x > v else down
        v = k * v + (1 - k) * x
        out[i] = v
    return out


def music_bed(src: Path, voice: Path, out: Path, total: float, gain_db: float, duck_db: float,
              fade_out: float) -> dict:
    """Loop/trim the music to the film, fade it, and duck it under the voice (gain curve computed here)."""
    music = _decode(src, total, loop=True)
    v = _decode(voice, total, loop=False)
    pres = speech_presence(v)
    t_frames = (np.arange(len(pres)) + 0.5) * FRAME
    t = np.arange(len(music)) / SR
    gain_db_curve = gain_db - duck_db * np.interp(t, t_frames, pres)
    fo = max(0.0, min(fade_out, total / 3))
    fade = np.minimum(np.clip(t / 0.6, 0, 1), np.clip((total - t) / max(fo, 1e-3), 0, 1))
    music = music * (10 ** (gain_db_curve / 20) * fade)[:, None]
    _write_wav(out, music)
    return {"duck_db": duck_db, "speech_share": round(float((pres > 0.5).mean()), 3)}


def sfx_track(events: list[dict], out: Path, total: float) -> int:
    """events: [{"file": path, "t": seconds, "gain_db": -12, "start": 0, "duration": None}]"""
    events = [e for e in events if 0 <= e["t"] < total - 0.05]
    if not events:
        ffmpeg("-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=stereo", "-t", f"{total:.4f}", "-c:a", "pcm_s16le", str(out))
        return 0
    args, parts = [], []
    for i, e in enumerate(events):
        if not Path(e["file"]).exists():
            raise OexError(f"sound effect file missing: {e['file']}", "run `oex sfx verify` or re-import the sound")
        args += ["-i", str(e["file"])]
        trim = f"atrim=start={e.get('start', 0):.3f}" + (f":duration={e['duration']:.3f}" if e.get("duration") else "")
        ms = int(round(e["t"] * 1000))
        parts.append(f"[{i}:a]aresample={SR},aformat=channel_layouts=stereo,{trim},asetpts=N/SR/TB,"
                     f"afade=t=out:st={max(0.0, (e.get('duration') or 30) - 0.03):.3f}:d=0.03,"
                     f"volume={e.get('gain_db', -12)}dB,adelay={ms}|{ms}[s{i}]")
    mix = "".join(f"[s{i}]" for i in range(len(events)))
    flt = ";".join(parts) + f";{mix}amix=inputs={len(events)}:normalize=0:dropout_transition=0," \
                            f"apad=whole_dur={total:.4f},atrim=end={total:.4f}[o]"
    ffmpeg(*args, "-filter_complex", flt, "-map", "[o]", "-ar", str(SR), "-c:a", "pcm_s16le", str(out))
    return len(events)


def final_mix(voice: Path, music: Path | None, sfx: Path | None, out: Path, total: float, tp: float = -1.5) -> None:
    ins = [voice] + [p for p in (music, sfx) if p]
    args = []
    for p in ins:
        args += ["-i", str(p)]
    limit = 10 ** (tp / 20)
    flt = (f"{''.join(f'[{i}:a]' for i in range(len(ins)))}amix=inputs={len(ins)}:normalize=0:duration=longest,"
           f"aresample={SR * 4},alimiter=limit={limit:.4f}:level=false:attack=5:release=60,"
           f"aresample={SR},atrim=end={total:.4f}[o]")   # 4x oversampled: the limiter sees inter-sample peaks
    ffmpeg(*args, "-filter_complex", flt, "-map", "[o]", "-ar", str(SR), "-c:a", "pcm_s16le", str(out))


def build_mix(proj, timeline: dict, sfx_events: list[dict], log=print) -> dict:
    d = proj.build / "audio"
    d.mkdir(parents=True, exist_ok=True)
    total = timeline["duration"]
    a = proj.cfg["audio"]
    voice = d / "voice.wav"
    vm = master_voice(proj.path(proj.cfg["narration"]["audio"]), voice, total, a["target_lufs"], a["true_peak"])
    music = None
    if proj.cfg["music"]:
        m = proj.cfg["music"]
        src = proj.path(m["file"])
        if not src.exists():
            raise OexError(f"music file not found: {src}", "fix music.file in project.json or set \"music\": null")
        music = d / "music.wav"
        music_bed(src, voice, music, total, m["gain_db"], m["duck_db"], m["fade_out"])
    sfx = d / "sfx.wav"
    n = sfx_track(sfx_events, sfx, total)
    mix = d / "mix.wav"
    final_mix(voice, music, sfx if n else None, mix, total, a["true_peak"])
    rep = {"voice_in": vm, "voice": loudness(voice), "mix": loudness(mix), "sfx_cues": n,
           "music": bool(music)}
    if music:
        rep["music_bed"] = loudness(music)
    log(f"audio: voice {rep['voice']['lufs']} LUFS, mix {rep['mix']['lufs']} LUFS / peak "
        f"{rep['mix']['true_peak_db']} dBTP, {n} sfx cue(s), music {'on' if music else 'off'}")
    return rep
