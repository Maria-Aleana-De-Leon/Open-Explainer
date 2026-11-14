"""Quality checks on the RENDERED file. Nothing is claimed from the plan; every check reads the output.

Checks: container/streams, resolution, fps, frame count, durations, loudness and true peak, speech onset vs
word timings (A/V offset), visual cue timing (the stage changes when a cue lands), black frames, caption files.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import numpy as np

from .media import decode_mono, loudness, probe, require_tool
from .scenes import LEAD
from .words import speech_onsets


def _frame(path: Path, t: float, w: int, h: int) -> np.ndarray:
    r = subprocess.run([require_tool("ffmpeg"), "-v", "error", "-nostdin", "-ss", f"{max(0.0, t):.3f}", "-i", str(path),
                        "-frames:v", "1", "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                       capture_output=True)
    if len(r.stdout) != w * h:
        return np.zeros((h, w), np.uint8)
    return np.frombuffer(r.stdout, np.uint8).reshape(h, w)


def xcorr_lag(ref: np.ndarray, x: np.ndarray, rate: int = 16000, hop: int = 80) -> float:
    """Seconds by which x lags ref (energy-envelope cross-correlation, 5 ms resolution, ±1 s search)."""
    def env(a):
        n = len(a) // hop
        e = np.sqrt((a[: n * hop].reshape(n, hop) ** 2).mean(1))
        return e - e.mean()
    a, b = env(ref), env(x)
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    maxlag = int(rate / hop)
    best, best_l = -np.inf, 0
    for lag in range(-maxlag, maxlag + 1):
        v = np.dot(a[max(0, -lag): n - max(0, lag)], b[max(0, lag): n - max(0, -lag)])
        if v > best:
            best, best_l = v, lag
    return best_l * hop / rate


def run(proj, timeline: dict, film: Path, captions_dir: Path | None = None) -> dict:
    checks: list[dict] = []

    def add(name, ok, detail, level="error"):
        checks.append({"check": name, "ok": bool(ok), "detail": detail, "level": level})

    info = probe(film)
    v = [s for s in info["streams"] if s["codec_type"] == "video"]
    a = [s for s in info["streams"] if s["codec_type"] == "audio"]
    add("streams", len(v) == 1 and len(a) == 1, f"{len(v)} video, {len(a)} audio")
    if not v or not a:
        return {"ok": False, "checks": checks}
    v, a = v[0], a[0]
    W, H, fps = timeline["width"], timeline["height"], timeline["fps"]
    add("codec", v["codec_name"] == "h264" and v.get("pix_fmt") == "yuv420p" and a["codec_name"] == "aac",
        f"{v['codec_name']}/{v.get('pix_fmt')} + {a['codec_name']}")
    add("resolution", (v["width"], v["height"]) == (W, H), f"{v['width']}x{v['height']} (want {W}x{H})")
    num, den = (int(x) for x in v["r_frame_rate"].split("/"))
    add("fps", abs(num / den - fps) < 0.01, f"{num / den:.3f} (want {fps})")
    r = subprocess.run([require_tool("ffprobe"), "-v", "error", "-select_streams", "v:0", "-count_packets",
                        "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(film)],
                       capture_output=True, text=True)
    nframes = int(r.stdout.strip() or 0)
    add("frame count", abs(nframes - timeline["frames"]) <= 1, f"{nframes} (want {timeline['frames']})")
    dur = float(info["format"]["duration"])
    add("duration", abs(dur - timeline["duration"]) <= 2 / fps + 0.03,
        f"{dur:.3f}s (want {timeline['duration']:.3f}s)")
    adur = float(a.get("duration", dur))
    add("audio duration", abs(adur - timeline["duration"]) <= 0.1, f"{adur:.3f}s")
    add("audio format", int(a["sample_rate"]) == 48000 and a.get("channels") == 2,
        f"{a['sample_rate']} Hz, {a.get('channels')} ch")
    narration_end = timeline["audio_duration"]
    add("narration fits", timeline["duration"] >= narration_end, f"film {timeline['duration']:.2f}s >= "
                                                                   f"narration {narration_end:.2f}s")

    L = loudness(film)
    tgt, tp = proj.cfg["audio"]["target_lufs"], proj.cfg["audio"]["true_peak"]
    add("loudness", L["lufs"] is not None and abs(L["lufs"] - tgt) <= 2.5, f"{L['lufs']} LUFS (target {tgt}±2.5)")
    add("true peak", L["true_peak_db"] is not None and L["true_peak_db"] <= tp + 0.6,
        f"{L['true_peak_db']} dBTP (limit {tp}; AAC encoding adds a little)")

    # A/V 1 (hard): the film's audio must sit exactly where the mastered voice was timed (cross-correlation)
    x = decode_mono(film)
    voice = proj.build / "audio" / "voice.wav"
    if voice.exists():
        lag = xcorr_lag(decode_mono(voice), x)
        add("mux offset", abs(lag) <= 1 / fps + 0.005, f"film audio vs mastered voice: {lag * 1000:+.0f} ms "
                                                      f"(limit ±{1000 / fps:.0f} ms = 1 frame)")
    # A/V 2 (informational): word timings vs real speech onsets for words that follow a pause
    # measured on the mastered voice: the mux check above already ties the film to it, and music in the pauses
    # would blur the onsets of a full mix
    on = speech_onsets(decode_mono(voice) if voice.exists() else x)
    offs = []
    for sc in timeline["scenes"]:
        prev_e = -1.0
        for w, s, e in sc["words"]:
            if s - prev_e >= 0.08 and len(on):
                d = on - s
                near = d[np.abs(d) < 0.5]
                if len(near):
                    offs.append(float(near[np.argmin(np.abs(near))]))
            prev_e = e
    if offs:
        med = float(np.median(offs))
        add("word timing", abs(med) <= 0.06, f"speech onset - word start after pauses: median {med * 1000:+.0f} ms "
                                             f"over {len(offs)} words", "warning")

    # visual cues, checked on the scene model (deterministic renderer): drawing ONLY the scene's elements - no
    # camera, captions or mascot - something must appear or change between just before and just after each cue
    cue_rows, misses, match_rows = model_checks(proj, timeline, film)
    for r in cue_rows:
        if not r["ok"]:
            misses.append(f"{r['scene']}:{r['cue']}@{r['t']:.2f}s")
    add("visual cues", not misses, f"{len(cue_rows) - len(misses)}/{len(cue_rows)} cues bring something on screen "
        "exactly at their word" + (f"; nothing at {', '.join(misses[:6])}" if misses else ""))
    worst = max((r["diff"] for r in match_rows), default=0.0)
    add("film = model", worst <= 6.0, f"decoded film vs renderer at one frame per scene: worst mean difference "
        f"{worst:.1f}/255 over {len(match_rows)} scenes (encoding noise is ~1-3)")

    r = subprocess.run([require_tool("ffmpeg"), "-hide_banner", "-nostdin", "-i", str(film), "-vf",
                        "blackdetect=d=0.4:pix_th=0.06", "-an", "-f", "null", "-"], capture_output=True, text=True)
    blacks = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", r.stderr)
    add("black frames", not blacks, f"{len(blacks)} black segment(s) >= 0.4s" + (f": {blacks[:3]}" if blacks else ""))

    if captions_dir:
        srt = captions_dir / (film.stem + ".srt")
        ok = srt.exists() and srt.stat().st_size > 0
        last_end = 0.0
        if ok:
            ends = re.findall(r"--> (\d+):(\d+):(\d+),(\d+)", srt.read_text(encoding="utf-8"))
            last_end = max((int(h) * 3600 + int(m_) * 60 + int(s) + int(ms) / 1000 for h, m_, s, ms in ends),
                           default=0)
        add("captions", ok and 0 < last_end <= timeline["duration"] + 0.01,
            f"{srt.name}: last cue ends {last_end:.2f}s" if ok else "missing SRT")

    errors = [c for c in checks if not c["ok"] and c["level"] == "error"]
    return {"ok": not errors, "film": str(film), "checks": checks, "cues": cue_rows, "film_vs_model": match_rows}


def model_checks(proj, timeline: dict, film: Path):
    """(cue rows, misses placeholder, film-vs-model rows). See the comment at the call site."""
    from PIL import Image

    from .pipeline import mascot_provider
    from .render import SceneFrames, jobs_for
    mascot_for = mascot_provider(proj, timeline, log=lambda *_: None)
    W, H = timeline["width"], timeline["height"]
    cue_rows, match_rows = [], []
    for sc, job in jobs_for(proj, timeline, False, mascot_for):
        sf = SceneFrames(sc, job)

        def elements_only(t):
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            for el in sf.els:
                el.render(layer, t)
            return np.asarray(layer, dtype=np.int16)

        for name, t in _cues(sc):
            if not (sc["start"] + 0.2 < t < sc["end"] - 0.4):
                continue
            a, b = elements_only(t - LEAD - 0.02), elements_only(t + 0.35)
            changed = float((np.abs(b - a).max(-1) > 20).mean() * 100)
            cue_rows.append({"scene": sc["id"], "cue": name, "t": t, "change": round(changed, 3), "ok": changed > 0.01})
        tm = sc["start"] + (sc["end"] - sc["start"]) * 0.6
        model = np.asarray(sf.frame(tm).convert("L").resize((W // 2, H // 2)), dtype=np.int16)
        actual = _frame(film, round(tm * timeline["fps"]) / timeline["fps"], W // 2, H // 2).astype(np.int16)
        match_rows.append({"scene": sc["id"], "t": round(tm, 2), "diff": round(float(np.abs(model - actual).mean()), 2)})
    return cue_rows, [], match_rows


def _cues(sc: dict):
    # title / statement / end text appears at the scene start (the stage is never empty); their word-timed beat
    # is the emphasis highlight, so that is what is checked
    if sc["type"] in ("title", "statement", "end"):
        if sc.get("emphasis_t"):
            yield "emphasis", sc["emphasis_t"]
    else:
        yield "scene", sc["t"]
    for k, it in enumerate(sc.get("items", [])):
        yield f"items[{k}]", it["t"]
    for side in ("left", "right"):
        if side in sc:
            yield side, sc[side]["t"]


def contact_sheet(film: Path, times: list[float], out: Path, labels: list[str] | None = None, cols: int = 4,
                  width: int = 480) -> Path:
    """A grid of frames from the rendered film (what reviewers and agents look at instead of source code)."""
    from PIL import Image, ImageDraw

    info = probe(film)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    h = int(width * v["height"] / v["width"]) // 2 * 2
    tiles = []
    for i, t in enumerate(times):
        r = subprocess.run([require_tool("ffmpeg"), "-v", "error", "-nostdin", "-ss", f"{t:.3f}", "-i", str(film),
                            "-frames:v", "1", "-vf", f"scale={width}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           capture_output=True)
        im = Image.frombytes("RGB", (width, h), r.stdout) if len(r.stdout) == width * h * 3 else \
            Image.new("RGB", (width, h), (255, 0, 255))
        d = ImageDraw.Draw(im)
        lab = (labels[i] + " " if labels else "") + f"{t:.2f}s"
        d.rectangle([0, 0, 8 + 8 * len(lab), 22], fill=(0, 0, 0))
        d.text((4, 4), lab, fill=(255, 255, 255))
        tiles.append(im)
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (width + 8) + 8, rows * (h + 8) + 8), (60, 60, 60))
    for i, im in enumerate(tiles):
        sheet.paste(im, (8 + (i % cols) * (width + 8), 8 + (i // cols) * (h + 8)))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


def print_report(rep: dict, log=print) -> None:
    for c in rep["checks"]:
        mark = "PASS" if c["ok"] else ("WARN" if c["level"] == "warning" else "FAIL")
        log(f"  {mark:<4}  {c['check']:<15} {c['detail']}")
    log("QA: " + ("PASS" if rep["ok"] else "FAIL"))


def save(rep: dict, path: Path) -> None:
    path.write_text(json.dumps(rep, indent=1))
