"""Render: scenes in parallel -> cached MP4 segments -> concat -> mux the mastered mix -> final MP4.

Each scene segment is cached under build/cache/ by a hash of everything that affects its pixels. A failed scene
does not stop the others; the final film is assembled only when every scene succeeded, and the error names the
scenes to fix and the command that re-renders only them.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from PIL import Image

from . import __version__
from .captions import Burner, chunks
from .errors import OexError
from .media import ffmpeg, require_tool
from .scenes import BUILDERS, EXIT, background, clamp, ease_in_out, ease_out_cubic, regions
from .styles import get as get_style
from .styles import rgb

def _code_hash() -> str:
    """Hash of every module that affects pixels, plus the fonts: a code change invalidates cached scenes."""
    here = Path(__file__).parent
    h = hashlib.sha256()
    for name in ("render.py", "scenes.py", "text.py", "styles.py", "captions.py", "mascot.py", "mascot_io.py", "presenter.py",
                 "mouthtrack.py"):
        h.update((here / name).read_bytes())
    for f in sorted((here / "assets" / "fonts").glob("*.ttf")):
        h.update(f.read_bytes())
    return h.hexdigest()[:12]


RENDERER = f"oex-{__version__}-{_code_hash()}"


def _layer_opacity(layer: Image.Image, k: float) -> Image.Image:
    if k >= 0.999:
        return layer
    a = layer.getchannel("A").point(lambda v: int(v * k))
    layer.putalpha(a)
    return layer


class SceneFrames:
    """Draws any frame of one scene at a given global time."""

    def __init__(self, sc: dict, job: dict):
        self.sc = sc
        self.W, self.H = job["width"], job["height"]
        self.st = get_style(job["style"], job.get("accent"))
        self.R = regions(self.W, self.H, job["mascot_pos"])
        self.bg = background(self.W, self.H, self.st)
        self.built = BUILDERS[sc["type"]](sc, self.st, self.R, Path(job["root"]))
        self.els = sorted(self.built.els, key=lambda e: e.z)
        self.last = job["is_last"]
        self.transition = sc.get("transition") or self.st["transition"]
        self.camera = sc.get("camera") or self.st["camera"]
        self.burner = None
        if job["captions"]:
            cs = chunks([tuple(w) for w in sc["caption_words"]], job["caption_words"])
            self.burner = Burner(cs, self.R.captions, self.st, self.R.portrait)
        self.mascot = None
        if job.get("mascot"):
            from .presenter import Rig
            self.mascot = Rig.from_job(job["mascot"], self.R)

    def frame(self, t: float) -> Image.Image:
        sc, W, H = self.sc, self.W, self.H
        local, dur = t - sc["start"], sc["end"] - sc["start"]
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for el in self.els:
            el.render(layer, t)
        k = 1.0 if self.last else clamp((dur - local) / EXIT)
        ein = ease_out_cubic(clamp(local / 0.42))
        scale, dx = 1.0, 0.0
        if self.camera == "push":
            scale *= 1.0 + 0.035 * ease_in_out(clamp(local / max(dur, 0.01)))
        if self.transition == "slide":
            dx = 90 * (1 - ein)
        elif self.transition == "zoom":
            scale *= 0.93 + 0.07 * ein
            k *= ein
        elif self.transition == "fade":
            k *= ein
        if abs(scale - 1) > 0.0005:
            sw, sh = int(W * scale), int(H * scale)
            big = layer.resize((sw, sh), Image.BILINEAR)
            cx, cy = (self.R.stage[0] + self.R.stage[2]) / 2, (self.R.stage[1] + self.R.stage[3]) / 2
            ox, oy = cx * scale - cx, cy * scale - cy
            layer = big.crop((int(ox), int(oy), int(ox) + W, int(oy) + H))
        canvas = self.bg.copy()
        canvas.alpha_composite(_layer_opacity(layer, k), (int(dx), 0) if dx >= 0 else (0, 0))
        if self.transition == "wipe" and local < 0.5:
            e = ease_in_out(clamp(local / 0.5))
            x0 = int(W * e)
            if x0 < W:
                canvas.paste(Image.new("RGBA", (W - x0, H), rgb(self.st["accent"]) + (255,)), (x0, 0))
        if self.mascot:
            self.mascot.draw(canvas, t)
        if self.burner:
            self.burner.draw(canvas, t)
        return canvas


def scene_hash(sc: dict, job: dict) -> str:
    h = hashlib.sha256()
    payload = {k: v for k, v in job.items() if k not in ("out", "root")}
    h.update(json.dumps({"scene": sc, "job": payload, "renderer": RENDERER}, sort_keys=True, default=str).encode())
    if sc.get("image"):
        p = Path(sc["image"]) if Path(sc["image"]).is_absolute() else Path(job["root"]) / sc["image"]
        h.update(p.read_bytes() if p.exists() else b"missing")
    return h.hexdigest()[:16]


def render_scene(sc: dict, job: dict) -> dict:
    """Worker entry point (runs in a child process). Never raises: returns a status dict."""
    t0 = time.time()
    out = Path(job["out"])
    tmp = out.with_suffix(".part.mp4")
    try:
        sf = SceneFrames(sc, job)
        fps, scale = job["fps"], job.get("preview_scale", 1.0)
        W, H = job["width"], job["height"]
        ow, oh = int(W * scale) // 2 * 2, int(H * scale) // 2 * 2
        f0 = round(sc["start"] * fps)
        n = round(sc["end"] * fps) - f0
        cmd = [require_tool("ffmpeg"), "-v", "error", "-nostdin", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{W}x{H}", "-r", str(fps), "-i", "-"]
        if scale != 1.0:
            cmd += ["-vf", f"scale={ow}:{oh}:flags=bilinear"]
        cmd += ["-c:v", "libx264", "-preset", job.get("preset", "medium"), "-crf", str(job.get("crf", 18)),
                "-pix_fmt", "yuv420p", "-g", str(fps * 2), "-video_track_timescale", str(fps * 1000),
                "-movflags", "+faststart", str(tmp)]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for i in range(n):
                p.stdin.write(sf.frame((f0 + i) / fps).convert("RGB").tobytes())
            p.stdin.close()
        except BrokenPipeError:
            pass
        err = p.stderr.read().decode(errors="replace")
        if p.wait() != 0:
            raise OexError(f"ffmpeg encode failed: {err[-400:]}")
        os.replace(tmp, out)
        return {"id": sc["id"], "ok": True, "file": str(out), "frames": n, "seconds": round(time.time() - t0, 2)}
    except Exception as e:  # noqa: BLE001 - reported per scene, never kills the batch
        tmp.unlink(missing_ok=True)
        detail = str(e) if isinstance(e, OexError) else traceback.format_exc(limit=6)
        return {"id": sc["id"], "ok": False, "error": detail, "seconds": round(time.time() - t0, 2)}


def jobs_for(proj, timeline: dict, preview: bool, mascot_for=None) -> list[tuple[dict, dict]]:
    """mascot_for(scene, fps) -> serialisable mascot data for that scene, or None (hidden in that scene).
    When the film has a mascot, every scene keeps its space reserved so layouts stay consistent."""
    cache = proj.build / "cache" / ("preview" if preview else "final")
    cache.mkdir(parents=True, exist_ok=True)
    m = proj.cfg["mascot"]
    pos = m["position"] if (m and m["enabled"] and mascot_for) else None
    out = []
    scenes = timeline["scenes"]
    for i, sc in enumerate(scenes):
        fps = 12 if preview else timeline["fps"]
        job = {"width": timeline["width"], "height": timeline["height"], "fps": fps,
               "style": proj.cfg["style"], "accent": proj.cfg.get("accent"), "mascot_pos": pos,
               "captions": proj.cfg["captions"]["burn_in"], "caption_words": proj.cfg["captions"]["max_words"],
               "is_last": i == len(scenes) - 1, "root": str(proj.root),
               "preview_scale": 0.5 if preview else 1.0, "preset": "veryfast" if preview else "medium",
               "crf": 26 if preview else 18,
               "mascot": mascot_for(sc, fps) if mascot_for else None}
        key = scene_hash(sc, job)
        job["out"] = str(cache / f"{sc['id']}.{key}.mp4")
        out.append((sc, job))
    return out


def render_all(proj, timeline: dict, *, preview: bool = False, only: list[str] | None = None, force: bool = False,
               workers: int | None = None, mascot_for=None, log=print) -> list[dict]:
    jobs = jobs_for(proj, timeline, preview, mascot_for)
    known = {sc["id"] for sc, _ in jobs}
    if only:
        bad = [o for o in only if o not in known]
        if bad:
            raise OexError(f"unknown scene id(s): {', '.join(bad)}", f"scene ids are: {', '.join(sorted(known))}")
    todo, results = [], []
    for sc, job in jobs:
        cached = Path(job["out"]).exists()
        wanted = (only is None or sc["id"] in only)
        if cached and not (force and wanted):
            results.append({"id": sc["id"], "ok": True, "file": job["out"], "cached": True})
        elif wanted or not cached:
            todo.append((sc, job))
    if only:
        # scenes outside --only that are not cached still need rendering for a complete film; say so
        missing = [sc["id"] for sc, job in todo if sc["id"] not in only]
        if missing:
            log(f"note: {', '.join(missing)} not cached yet; rendering them too")
    workers = workers or max(1, min(len(todo), (os.cpu_count() or 2) - 1))
    log(f"render: {len(todo)} scene(s) to render, {len(results)} cached, {workers} worker(s)"
        + (" [preview 12fps half-res]" if preview else ""))
    if todo:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(render_scene, sc, job): sc["id"] for sc, job in todo}
            for f in as_completed(futs):
                r = f.result()
                results.append(r)
                log(f"  {r['id']}: " + (f"ok {r['frames']} frames in {r['seconds']}s" if r["ok"]
                                         else "FAILED - " + r["error"].splitlines()[0]))
    order = [sc["id"] for sc, _ in jobs]
    results.sort(key=lambda r: order.index(r["id"]))
    state = proj.build / ("render-state-preview.json" if preview else "render-state.json")
    state.write_text(json.dumps({"results": results, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}, indent=1))
    return results


def assemble(proj, timeline: dict, results: list[dict], mix: Path, out: Path, preview: bool = False) -> Path:
    failed = [r for r in results if not r["ok"]]
    if failed:
        details = "\n".join(f"  {r['id']}: {r['error'].strip().splitlines()[0]}" for r in failed)
        ids = ",".join(r["id"] for r in failed)
        raise OexError(f"{len(failed)} scene(s) failed; the film was not assembled:\n{details}",
                       f"fix the cause, then re-render only those: oex render --only {ids}")
    lst = proj.build / ("concat-preview.txt" if preview else "concat.txt")
    lst.write_text("".join(f"file '{Path(r['file']).resolve()}'\n" for r in results))
    video = proj.build / ("video-preview.mp4" if preview else "video.mp4")
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(video))
    out.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg("-i", str(video), "-i", str(mix), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
           "-b:a", "192k", "-t", f"{timeline['duration']:.4f}", "-movflags", "+faststart", str(out))
    return out
