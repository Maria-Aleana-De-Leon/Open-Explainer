"""oex - the open-explainer command line. Every command works from a project folder (or -C <folder>)."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import __version__
from .errors import OexError

STORYBOARD_TEMPLATE = {
    "scenes": [
        {"id": "s01", "type": "title", "say": "Replace this with the first paragraph of your narration.",
         "title": "Your *topic* here", "subtitle": "One line that sets up the question"},
        {"id": "s02", "type": "bullets", "say": "Replace with the second paragraph. First idea. Second idea.",
         "heading": "Two ideas", "items": [{"text": "First idea", "at": "first idea"},
                                           {"text": "Second idea", "at": "second idea"}]},
        {"id": "s03", "type": "end", "say": "Replace with your closing line.", "title": "Thanks for watching",
         "cta": "Follow for more"},
    ]
}


def cmd_doctor(a) -> int:
    import importlib
    import platform
    rows, bad = [], 0

    def row(ok, what, fix=""):
        nonlocal bad
        rows.append(f"{'OK     ' if ok else 'MISSING'} {what}" + (f"\n          fix: {fix}" if fix and not ok else ""))
        bad += 0 if ok else 1

    row(sys.version_info >= (3, 10), f"python {platform.python_version()} (need 3.10+)", "uv python install 3.12")
    for mod, pkg in (("numpy", "numpy"), ("PIL", "Pillow")):
        try:
            m = importlib.import_module(mod)
            row(True, f"{pkg} {getattr(m, '__version__', '')}")
        except ImportError:
            row(False, pkg, "uv sync   (or pip install -e .)")
    for t in ("ffmpeg", "ffprobe"):
        row(bool(shutil.which(t)), t, "macOS: brew install ffmpeg | Windows: winget install Gyan.FFmpeg | "
                                      "Linux: apt install ffmpeg")
    if shutil.which("ffmpeg"):
        import subprocess
        enc = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
        row("libx264" in enc, "ffmpeg has libx264", "install a full FFmpeg build (the brew/winget ones have it)")
    try:
        import faster_whisper
        rows.append(f"OK      faster-whisper {faster_whisper.__version__} (optional: automatic word timings)")
    except ImportError:
        rows.append("OPTIONAL faster-whisper not installed: `uv sync --extra transcribe`, or import timings "
                    "with `oex words import`")
    print("\n".join(rows))
    print("\nAll required tools present." if not bad else f"\n{bad} required item(s) missing.")
    return 1 if bad else 0


def _is_temp(r: Path) -> bool:
    import tempfile
    temps = {Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve(), Path("/var/tmp").resolve()}
    return any(r == t or t in r.parents for t in temps) or "/var/folders/" in r.as_posix()


def location_warning(d: Path) -> str | None:
    """Why `d` is a poor home for a film project, or None. Projects hold the user's own recordings and renders."""
    r = d.resolve()
    if _is_temp(r):
        return (f"{d} is in a temporary folder that the system clears; keep real projects somewhere durable, "
                "for example ~/OpenExplainer/<project>")
    for parent in [r, *r.parents]:
        pp = parent / "pyproject.toml"
        if pp.is_file() and 'name = "openexplainer"' in pp.read_text(errors="ignore"):
            return (f"{d} is inside the Open Explainer source folder; keep projects outside it so your recordings "
                    "and renders are never committed, for example ~/OpenExplainer/<project>")
    return None


def cmd_new(a) -> int:
    d = Path(a.folder)
    if d.exists() and any(d.iterdir()):
        raise OexError(f"{d} exists and is not empty", "choose a new folder name")
    (d / "audio").mkdir(parents=True)
    cfg = {"title": a.title or d.name, "format": a.format, "fps": 30, "style": a.style, "camera": "still",
           "narration": {"audio": "audio/narration.wav", "language": a.language},
           "mascot": None, "music": None, "sfx": None, "captions": {"burn_in": True}}
    (d / "project.json").write_text(json.dumps(cfg, indent=2) + "\n")
    (d / "storyboard.json").write_text(json.dumps(STORYBOARD_TEMPLATE, indent=2, ensure_ascii=False) + "\n")
    (d / ".gitignore").write_text("build/\nrenders/\n")
    warning = location_warning(d)
    if warning:
        print(f"warning: {warning}", file=sys.stderr)
    if a.demo:
        from . import demo
        demo.write(d)
        print(f"created demo project {d}/ (synthetic narration + timings)\n  oex -C {d} render")
        return 0
    print(f"created {d}/\n  1. put your narration at {d}/audio/narration.wav (MP3 also fine: edit project.json)\n"
          f"  2. edit storyboard.json: one scene per paragraph, 'say' = that paragraph's exact words\n"
          f"  3. oex -C {d} transcribe && oex -C {d} plan && oex -C {d} render --preview")
    return 0


def _proj(a, require_audio: bool = True):
    from .config import load_project
    return load_project(Path(a.C), require_audio)


def cmd_validate(a) -> int:
    from .config import load_project
    p = load_project(Path(a.C), require_audio=False)
    print(f"project.json + {p.cfg['storyboard']}: OK ({len(p.storyboard['scenes'])} scenes)")
    audio = p.path(p.cfg["narration"]["audio"])
    if not audio.exists():
        print(f"note: no narration yet at {audio} - record it, then `oex transcribe`")
    return 0


def cmd_transcribe(a) -> int:
    from .pipeline import transcribe
    transcribe(_proj(a), a.language, a.model)
    return 0


def cmd_words(a) -> int:
    from .pipeline import import_words
    import_words(_proj(a), Path(a.file))
    return 0


def cmd_tts(a) -> int:
    from . import tts
    from .pipeline import import_words
    p = _proj(a, require_audio=False)
    out = p.path(p.cfg["narration"]["audio"])
    if out.exists() and not a.overwrite:
        raise OexError(f"{out} already exists", "pass --overwrite to replace the narration with synthetic speech")
    alignment = p.build / "elevenlabs-alignment.json" if a.provider == "elevenlabs" else None
    d = tts.synthesize(p, out, a.provider, voice=a.voice, rate=a.rate, template=a.command, words_out=alignment)
    if alignment is not None:
        import_words(_proj(a), alignment)
    print(f"narration -> {out} ({d:.1f}s, checked: real audio)"
          + ("" if a.provider == "elevenlabs" else "\nnext: oex transcribe"))
    return 0


def cmd_estimate(a) -> int:
    """Length of a script before recording (a text file with blank-line paragraphs, or the storyboard's 'say')."""
    from . import durations as D
    if a.script:
        paras = [p.strip() for p in Path(a.script).read_text(encoding="utf-8").split("\n\n") if p.strip()]
        proj = None
    else:
        from .config import load_project
        proj = load_project(Path(a.C), require_audio=False)
        paras = [s["say"] for s in proj.storyboard["scenes"]]
    wpm, source = (a.wpm, "given") if a.wpm else (D.DEFAULT_WPM, "typical narration pace")
    if proj and not a.wpm:
        m = D.measured_wpm(proj.path(proj.cfg["narration"]["words"]), sum(D.count_words(p) for p in paras))
        if m:
            wpm, source = m, "measured from your take"
    target = D.parse_target(a.target) if a.target else None
    for line in D.report(paras, target, wpm, source):
        print(line)
    return 0


def cmd_use_narration(a) -> int:
    """Swap in a new recording: copy it into the project, re-time everything, report fit and length."""
    import shutil
    from . import durations as D
    from .pipeline import plan, transcribe
    src = Path(a.file).expanduser()
    if not src.is_file():
        raise OexError(f"{src} not found", "give the path of your MP3, WAV or M4A recording")
    p = _proj(a, require_audio=False)
    dest = p.root / "audio" / ("narration" + src.suffix.lower())
    dest.parent.mkdir(exist_ok=True)
    old = p.path(p.cfg["narration"]["audio"])
    if old.exists() and old.resolve() != dest.resolve():
        old.rename(old.with_name(old.stem + ".previous" + old.suffix))
    shutil.copy(src, dest)
    cfg_path = p.root / "project.json"
    cfg = json.loads(cfg_path.read_text())
    cfg["narration"]["audio"] = str(dest.relative_to(p.root))
    if a.language:
        cfg["narration"]["language"] = a.language
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")
    print(f"narration -> {dest}")
    p = _proj(a)
    transcribe(p)
    tl = plan(p, log=lambda *_: None)
    words = sum(D.count_words(s["say"]) for s in p.storyboard["scenes"])
    wpm = D.measured_wpm(p.path(p.cfg["narration"]["words"]), words)
    print(f"your pace: {wpm:.0f} words per minute; film length {D.fmt(tl['duration'])}")
    for w in tl["warnings"]:
        print(f"  note: {w}")
    print("next: oex render --preview   (check it), then oex render")
    return 0


def cmd_use_mascot(a) -> int:
    """Swap in a mascot: copy its PNGs into the project's mascot/ folder, prepare and validate them."""
    import shutil
    from .mascot import SHAPES, prepare
    src = Path(a.folder).expanduser()
    if not src.is_dir() or not (src / "neutral.png").exists():
        raise OexError(f"no neutral.png in {src}", "give the folder with your mascot PNGs (see `oex prompts`)")
    p = _proj(a, require_audio=False)
    dest = p.root / "mascot"
    if dest.exists() and dest.resolve() != src.resolve():
        backup = p.root / "mascot-previous"
        if backup.exists():
            shutil.rmtree(backup)
        dest.rename(backup)
        print(f"previous mascot kept in {backup}")
    if dest.resolve() != src.resolve():
        dest.mkdir()
        for f in src.glob("*.png"):
            shutil.copy(f, dest / f.name.lower())
    cfg_path = p.root / "project.json"
    cfg = json.loads(cfg_path.read_text())
    cfg["mascot"] = {**(cfg.get("mascot") or {}), "dir": "mascot"}
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")
    found = sorted(f.stem for f in dest.glob("*.png"))
    print("found: " + ", ".join(found))
    missing = [f"mouth-{s}" for s in SHAPES if f"mouth-{s}" not in found] + \
              [n for n in ("blink",) if n not in found]
    if missing:
        print("optional images not provided (fallbacks are used): " + ", ".join(missing))
    info = prepare(dest)
    used = {(m.get("pose"), m.get("expression")) for sc in p.storyboard["scenes"]
            for m in (sc.get("mascot") or []) if isinstance(sc.get("mascot"), list)}
    lacking = sorted({f"pose-{po}.png" if po and po != "neutral" else f"expr-{ex}.png" for po, ex in used
                      if not any(n in info["states"] for n in
                                 ([f"pose-{po}"] if po and po != "neutral" else []) + ([f"expr-{ex}"] if ex else []))
                      and not (po == "neutral" and not ex)})
    if lacking:
        print("the storyboard uses gestures this mascot does not have (it keeps its pose there): " + ", ".join(lacking))
    errors = [c["msg"] for c in info["checks"] if c["level"] == "error"]
    if errors:
        print("NOT READY: fix these images and run again:\n  " + "\n  ".join(errors))
        return 2
    print(f"READY: look at {dest / 'build' / 'review.png'}, then: oex render --preview")
    return 0


def _prompts_dir() -> Path:
    here = Path(__file__).parent / "prompts"                 # installed package
    return here if here.exists() else Path(__file__).resolve().parents[2] / "prompts"   # source checkout


def cmd_prompts(a) -> int:
    """The ChatGPT mascot prompts, ready to copy."""
    files = sorted(_prompts_dir().glob("0*.md"))
    if not files:
        raise OexError("prompt files not found", "reinstall open-explainer")
    if a.number is None:
        print("Mascot prompts - copy them into ChatGPT in this order (show one with: oex prompts <number>):\n")
        for f in files:
            title = f.read_text(encoding="utf-8").splitlines()[0].lstrip("# ")
            print(f"  {title}")
        print("\nThen: oex use-mascot <your folder>")
        return 0
    f = next((f for f in files if f.name.startswith(f"{a.number:02d}")), None)
    if not f:
        raise OexError(f"no prompt {a.number}", f"choose 1-{len(files)}")
    print(f.read_text(encoding="utf-8"))
    return 0


def cmd_transcript(a) -> int:
    """The recording as text, split into paragraphs at its natural pauses: the starting point for a storyboard when
    someone brings a voiceover but no written script."""
    from .words import load
    p = _proj(a)
    words = load(p.path(p.cfg["narration"]["words"]))
    paras, cur = [], []
    for w, nxt in zip(words, words[1:] + [None]):
        cur.append(w.w)
        gap = (nxt.s - w.e) if nxt else 99
        if gap >= a.pause or (gap >= a.pause * 0.6 and w.w.rstrip()[-1:] in ".?!"):
            paras.append(" ".join(cur))
            cur = []
    for i, t in enumerate(paras, 1):
        print(f"[{i}] {t}\n")
    print(f"{len(paras)} paragraphs - one scene each; copy each paragraph as that scene's \"say\" exactly")
    return 0


def cmd_plan(a) -> int:
    from .pipeline import plan
    plan(_proj(a))
    return 0


def cmd_render(a) -> int:
    from .pipeline import render
    only = [s.strip() for s in a.only.split(",")] if a.only else None
    rep = render(_proj(a), preview=a.preview, only=only, force=a.force, workers=a.workers, skip_qa=a.no_qa)
    return 0 if rep.get("ok", True) else 2


def _latest_film(p, film: str | None) -> Path:
    if film:
        return Path(film)
    films = [f for f in (p.root / "renders").glob("*.mp4") if not f.stem.endswith("-preview")]
    if not films:
        raise OexError("no rendered film in renders/", "run `oex render` first")
    return max(films, key=lambda f: f.stat().st_mtime)


def _timeline(p) -> dict:
    f = p.build / "timeline.json"
    if not f.exists():
        raise OexError("no build/timeline.json", "run `oex plan` or `oex render` first")
    return json.loads(f.read_text())


def cmd_preflight(a) -> int:
    from .pipeline import preflight
    return 0 if preflight(_proj(a)) else 2


def cmd_review(a) -> int:
    from . import review
    p = _proj(a)
    notes = review.run(p, _timeline(p))
    review.print_report(notes)
    review.save(notes, p.build / "review.json")
    return 0


def cmd_qa(a) -> int:
    from . import qa
    p = _proj(a)
    film = _latest_film(p, a.film)
    if film.stat().st_mtime < (p.build / "timeline.json").stat().st_mtime:
        print(f"warning: {film.name} is older than the current plan (build/timeline.json); results compare an old "
              "film with new timings - run `oex render` first")
    rep = qa.run(p, _timeline(p), film, film.parent)
    qa.print_report(rep)
    qa.save(rep, p.build / "qa.json")
    return 0 if rep["ok"] else 2


def cmd_sheet(a) -> int:
    """Frames per scene: entrance, middle, just before the end (or every N seconds with --every)."""
    from . import qa
    p = _proj(a)
    film = _latest_film(p, a.film)
    tl = _timeline(p)
    times, labels = [], []
    if a.every:
        t = 0.0
        while t < tl["duration"]:
            times.append(t)
            labels.append("")
            t += a.every
    else:
        for sc in tl["scenes"]:
            if a.scene and sc["id"] not in a.scene.split(","):
                continue
            d = sc["end"] - sc["start"]
            for frac in (0.15, 0.55, 0.92):
                times.append(round(sc["start"] + d * frac, 2))
                labels.append(sc["id"])
    out = qa.contact_sheet(film, times, Path(a.out) if a.out else p.build / "sheet.png", labels, cols=a.cols)
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="oex", description="open-explainer: narrated explainer videos")
    ap.add_argument("-C", default=".", metavar="DIR", help="project folder (default: current folder)")
    ap.add_argument("--version", action="version", version=f"oex {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor", help="check this machine").set_defaults(fn=cmd_doctor)
    p = sub.add_parser("new", help="create a project folder")
    p.add_argument("folder")
    p.add_argument("--title")
    p.add_argument("--format", choices=["16:9", "9:16"], default="16:9")
    p.add_argument("--style", default="paper")
    p.add_argument("--language", default=None, help="narration language code, e.g. en, tl (Tagalog/Taglish)")
    p.add_argument("--demo", action="store_true", help="a ready-to-render starter (no microphone or model needed)")
    p.set_defaults(fn=cmd_new)
    sub.add_parser("validate", help="check project.json and storyboard.json").set_defaults(fn=cmd_validate)
    p = sub.add_parser("transcribe", help="word timings from the narration (faster-whisper)")
    p.add_argument("--language")
    p.add_argument("--model", help="tiny|base|small|medium|large-v3 (default from project, small)")
    p.set_defaults(fn=cmd_transcribe)
    p = sub.add_parser("words", help="import word timings (ElevenLabs alignment/Scribe, whisper JSON)")
    p.add_argument("action", choices=["import"])
    p.add_argument("file")
    p.set_defaults(fn=cmd_words)
    p = sub.add_parser("tts", help="optional: synthesise the narration from the storyboard text")
    p.add_argument("--provider", choices=["say", "elevenlabs", "command"], required=True)
    p.add_argument("--voice", help="say: voice name; elevenlabs: voice id")
    p.add_argument("--rate", type=int, help="say: words per minute")
    p.add_argument("--command", help="command provider: template with {text_file} and {out}")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(fn=cmd_tts)
    p = sub.add_parser("transcript", help="your recording as paragraphs (to build scenes from a voiceover)")
    p.add_argument("--pause", type=float, default=0.7, help="pause (s) that starts a new paragraph")
    p.set_defaults(fn=cmd_transcript)
    p = sub.add_parser("prompts", help="show the ChatGPT prompts for making your mascot")
    p.add_argument("number", nargs="?", type=int)
    p.set_defaults(fn=cmd_prompts)
    p = sub.add_parser("use-narration", help="replace the narration with your recording (copies, re-times, reports)")
    p.add_argument("file")
    p.add_argument("--language", help="e.g. en, tl (Tagalog/Taglish)")
    p.set_defaults(fn=cmd_use_narration)
    p = sub.add_parser("use-mascot", help="replace the mascot with your images (copies, prepares, validates)")
    p.add_argument("folder")
    p.set_defaults(fn=cmd_use_mascot)
    p = sub.add_parser("estimate", help="predict the film length from the script (before recording)")
    p.add_argument("script", nargs="?", help="script text file (paragraphs separated by blank lines); default: "
                                              "the project's storyboard")
    p.add_argument("--target", help="intended length, e.g. 3:00, 90s, 5m")
    p.add_argument("--wpm", type=float, help="speaking pace in words per minute (default: measured or 150)")
    p.set_defaults(fn=cmd_estimate)
    sub.add_parser("plan", help="align storyboard to narration; print scene times").set_defaults(fn=cmd_plan)
    p = sub.add_parser("render", help="render the film (cached per scene)")
    p.add_argument("--preview", action="store_true", help="fast 12 fps half-resolution preview")
    p.add_argument("--only", help="comma-separated scene ids to (re)render")
    p.add_argument("--force", action="store_true", help="ignore the cache for the selected scenes")
    p.add_argument("--workers", type=int)
    p.add_argument("--no-qa", action="store_true")
    p.set_defaults(fn=cmd_render)
    sub.add_parser("preflight", help="check everything before rendering").set_defaults(fn=cmd_preflight)
    sub.add_parser("review", help="quality heuristics: layout, text, pacing, sound (prompts to look, not a "
                                  "verdict)").set_defaults(fn=cmd_review)
    p = sub.add_parser("qa", help="quality checks on a rendered film")
    p.add_argument("--film")
    p.set_defaults(fn=cmd_qa)
    p = sub.add_parser("sheet", help="contact sheet of the rendered film (3 frames per scene)")
    p.add_argument("--film")
    p.add_argument("--scene", help="comma-separated scene ids")
    p.add_argument("--every", type=float, help="one frame every N seconds instead")
    p.add_argument("--cols", type=int, default=3)
    p.add_argument("--out")
    p.set_defaults(fn=cmd_sheet)
    try:
        from .cli_mascot import register as reg_m
        reg_m(sub)
    except ImportError:
        pass
    try:
        from .cli_sfx import register as reg_s
        reg_s(sub)
    except ImportError:
        pass
    return ap


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    try:
        return a.fn(a) or 0
    except OexError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    except Exception as e:  # noqa: BLE001 - never show a raw traceback to a user by default
        import os
        if os.environ.get("OEX_DEBUG"):
            raise
        print(f"error: unexpected {type(e).__name__}: {e}\n  fix: this is a bug in oex - run again with OEX_DEBUG=1 "
              "for the details and report it with build/logs/", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
