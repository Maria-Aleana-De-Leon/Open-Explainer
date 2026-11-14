"""The production pipeline: words -> timeline -> (mascot track, sfx cues) -> audio mix -> scenes -> film -> QA."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from . import captions as C
from . import qa as QA
from . import timeline as TL
from . import words as WD
from .audio import build_mix
from .config import Project
from .errors import OexError
from .media import duration


class Log:
    """Prints and appends to build/logs/<run>.log so every run is inspectable later."""

    def __init__(self, proj: Project, name: str):
        d = proj.build / "logs"
        d.mkdir(parents=True, exist_ok=True)
        self.path = d / f"{time.strftime('%Y%m%d-%H%M%S')}-{name}.log"
        self.f = open(self.path, "a", encoding="utf-8")

    def __call__(self, msg: str) -> None:
        print(msg, flush=True)
        self.f.write(msg + "\n")
        self.f.flush()


def words_path(proj: Project) -> Path:
    return proj.path(proj.cfg["narration"]["words"])


def transcribe(proj: Project, language: str | None = None, model: str | None = None, log=print) -> Path:
    n = proj.cfg["narration"]
    audio = proj.path(n["audio"])
    lang = language or n["language"]
    t0 = time.time()
    log(f"transcribing {audio.name} (model {model or n['model']}, language {lang or 'auto'})...")
    words, detected = WD.transcribe(audio, lang, model or n["model"], n["prompt"])
    out = words_path(proj)
    WD.save(out, words, detected, f"faster-whisper {model or n['model']}", duration(audio))
    log(f"{len(words)} words, language {detected}, {time.time() - t0:.0f}s -> {out}")
    return out


def import_words(proj: Project, src: Path, log=print) -> Path:
    if not src.exists():
        raise OexError(f"timings file not found: {src}", "give the path of the JSON your TTS or transcription tool saved")
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise OexError(f"{src} is not valid JSON ({e.msg}, line {e.lineno})") from None
    words, lang = WD.parse(data)
    words = WD.merge_fragments(words)
    audio = proj.path(proj.cfg["narration"]["audio"])
    problems = WD.validate(words, duration(audio))
    if problems:
        from .errors import ValidationError
        raise ValidationError(str(src), problems)
    out = words_path(proj)
    WD.save(out, words, lang or proj.cfg["narration"]["language"], f"import:{src.name}", duration(audio))
    log(f"imported {len(words)} words -> {out}")
    return out


def plan(proj: Project, log=print) -> dict:
    audio = proj.path(proj.cfg["narration"]["audio"])
    wp = words_path(proj)
    words = WD.load(wp)
    if wp.stat().st_mtime < audio.stat().st_mtime:
        log(f"warning: {wp.name} is older than {audio.name}; if you replaced the take, re-run `oex transcribe`")
    adur = duration(audio)
    problems = WD.validate(words, adur)
    if problems:
        from .errors import ValidationError
        raise ValidationError(str(wp), problems)
    tl = TL.build(proj, words, adur)
    if proj.cfg["sfx"]:
        from .sfx import plan_cues
        tl["sfx_events"] = plan_cues(proj, tl, log)
    else:
        tl["sfx_events"] = []
    proj.build.mkdir(parents=True, exist_ok=True)
    (proj.build / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"timeline: {len(tl['scenes'])} scenes, {tl['duration']:.2f}s, {tl['frames']} frames at {tl['fps']} fps")
    for sc in tl["scenes"]:
        log(f"  {sc['id']:<10} {sc['type']:<10} {sc['start']:7.2f} -> {sc['end']:7.2f}  ({sc['end'] - sc['start']:.2f}s)")
    for w in tl["warnings"]:
        log(f"  warning: {w}")
    return tl


def _mix_key(proj: Project, tl: dict) -> str:
    h = hashlib.sha256()
    h.update(proj.path(proj.cfg["narration"]["audio"]).read_bytes())
    if proj.cfg["music"]:
        h.update(proj.path(proj.cfg["music"]["file"]).read_bytes())
    h.update(json.dumps([tl["duration"], tl["sfx_events"], proj.cfg["music"], proj.cfg["audio"], "mix-r1"],
                        sort_keys=True).encode())
    return h.hexdigest()[:16]


def mix(proj: Project, tl: dict, log=print) -> Path:
    key = _mix_key(proj, tl)
    d = proj.build / "audio"
    stamp = d / "mix.key"
    if (d / "mix.wav").exists() and stamp.exists() and stamp.read_text() == key:
        log("audio: cached mix")
        return d / "mix.wav"
    rep = build_mix(proj, tl, tl["sfx_events"], log)
    (d / "report.json").write_text(json.dumps(rep, indent=1))
    stamp.write_text(key)
    return d / "mix.wav"


def mascot_provider(proj: Project, tl: dict, log=print):
    m = proj.cfg["mascot"]
    if not m or not m["enabled"]:
        return None
    from .presenter import plan
    return plan(proj, tl, log)


def render(proj: Project, *, preview: bool = False, only: list[str] | None = None, force: bool = False,
           workers: int | None = None, skip_qa: bool = False) -> dict:
    if only:   # fail fast on a typo, before any planning or mixing
        known = {s["id"] for s in proj.storyboard["scenes"]}
        bad = [o for o in only if o not in known]
        if bad:
            raise OexError(f"unknown scene id(s): {', '.join(bad)}", f"scene ids are: {', '.join(sorted(known))}")
    log = Log(proj, "preview" if preview else "render")
    t0 = time.time()
    tl = plan(proj, log)
    mascot_for = mascot_provider(proj, tl, log)
    mixf = mix(proj, tl, log)
    from .render import assemble, render_all
    results = render_all(proj, tl, preview=preview, only=only, force=force, workers=workers,
                         mascot_for=mascot_for, log=log)
    out_dir = proj.root / "renders"
    slug = "".join(ch if ch.isalnum() else "-" for ch in proj.cfg["title"].lower()).strip("-")[:48] or "film"
    name = f"{slug}-{proj.cfg['format'].replace(':', 'x')}" + ("-preview" if preview else "")
    film = assemble(proj, tl, results, mixf, out_dir / f"{name}.mp4", preview)
    cs = C.chunks([tuple(w) for sc in tl["scenes"] for w in sc["caption_words"]], proj.cfg["captions"]["max_words"])
    C.write_srt(out_dir / f"{name}.srt", cs)
    C.write_vtt(out_dir / f"{name}.vtt", cs)
    stems = out_dir / f"{name}-stems"
    stems.mkdir(exist_ok=True)
    for s in ("voice", "music", "sfx", "mix"):
        src = proj.build / "audio" / f"{s}.wav"
        if src.exists():
            (stems / f"{s}.wav").write_bytes(src.read_bytes())
    log(f"film: {film}  ({time.time() - t0:.0f}s)")
    rep = {"film": str(film), "ok": True}
    if not skip_qa and not preview:
        log("QA:")
        rep = QA.run(proj, tl, film, out_dir)
        QA.save(rep, proj.build / "qa.json")
        QA.print_report(rep, log)
        from . import review as RV
        notes = RV.run(proj, tl)
        RV.save(notes, proj.build / "review.json")
        log("quality review:")
        RV.print_report(notes, log)
        rep["review"] = notes
    credits = _provenance(proj, tl, out_dir / f"{name}.credits.json")
    if not preview:
        from .qa import contact_sheet
        times, labels = [], []
        for sc in tl["scenes"]:
            times.append(round(sc["start"] + (sc["end"] - sc["start"]) * 0.6, 2))
            labels.append(sc["id"])
        sheet = contact_sheet(film, times, out_dir / f"{name}-sheet.png", labels, cols=4, width=400)
        verify_md(proj, tl, film, rep, credits, sheet, out_dir / f"{name}.VERIFY.md", time.time() - t0)
        log(f"evidence: {out_dir / (name + '.VERIFY.md')}")
    log(f"log: {log.path}")
    return rep


def verify_md(proj: Project, tl: dict, film: Path, rep: dict, credits: dict, sheet: Path, out: Path,
              seconds: float) -> None:
    """Human-readable evidence for one render: inputs, what was checked on the file, and what to look at."""
    from . import __version__

    def digest(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest()[:12] if p.exists() else "-"

    rows = "\n".join(f"| {c['check']} | {'PASS' if c['ok'] else ('WARN' if c['level'] == 'warning' else 'FAIL')} "
                     f"| {c['detail']} |" for c in rep.get("checks", []))
    notes = rep.get("review", [])
    review_rows = "\n".join(f"- {n['level']}: {n['area']} at {n['where']}: {n['msg']}" for n in notes) or "- no findings"
    mc = proj.build / "mascot-check.json"
    mascot = json.loads(mc.read_text()) if (mc.exists() and proj.cfg["mascot"]) else None
    out.write_text(f"""# Verification: {film.name}

Rendered {time.strftime('%Y-%m-%d %H:%M')} by oex {__version__} in {seconds:.0f} s.

## Inputs
| | |
|---|---|
| narration | `{proj.cfg['narration']['audio']}` sha256 {digest(proj.path(proj.cfg['narration']['audio']))} |
| storyboard | `{proj.cfg['storyboard']}` sha256 {digest(proj.root / proj.cfg['storyboard'])} |
| scenes / duration | {len(tl['scenes'])} / {tl['duration']:.2f} s, {tl['frames']} frames at {tl['fps']} fps, {tl['width']}x{tl['height']} |
| timing warnings | {len(tl['warnings'])} |
| mascot | {f"{mascot['talk_share']:.0%} of words with an open mouth, {mascot['rest_share']:.0%} of long pauses at rest" if mascot else "none"} |
| publish-safe assets | {"yes" if credits['publish_safe'] else "NO - see " + film.stem + ".credits.json"} |

## Checks on the rendered file ({'PASS' if rep.get('ok') else 'FAIL'})
| check | result | detail |
|---|---|---|
{rows}

## Quality review (heuristics - prompts to look, not verdicts)
{review_rows}

## Look and listen
Checks do not prove visual or audio quality. Frames from every scene: `{sheet.name}`. Not checkable automatically:
whether motion feels natural, whether the visuals explain the idea, tone of music and effects, mascot personality.
""", encoding="utf-8")


def _provenance(proj: Project, tl: dict, path: Path) -> None:
    """Every third-party asset used in the film, with its licence status, so credits/publishing are checkable."""
    assets = []
    if proj.cfg["music"]:
        assets.append({"kind": "music", "file": proj.cfg["music"]["file"],
                       "license": proj.cfg["music"]["license"] or "UNSPECIFIED"})
    seen = set()
    for e in tl.get("sfx_events", []):
        if e["id"] in seen:
            continue
        seen.add(e["id"])
        assets.append({"kind": "sfx", "id": e["id"], "license": e.get("license") or "UNSPECIFIED",
                       "license_status": e.get("license_status", "unknown"), "author": e.get("author"),
                       "source_url": e.get("source_url"), "attribution": e.get("attribution")})
    blocked = [a for a in assets if a.get("license_status") in ("unverified", "unknown")
               or a["license"] == "UNSPECIFIED"]
    credits = {"fonts": "Poppins (SIL OFL 1.1)", "assets": assets, "publish_safe": not blocked,
               "needs_review": blocked}
    path.write_text(json.dumps(credits, indent=1), encoding="utf-8")
    if blocked:
        print(f"note: {len(blocked)} asset(s) have no verified licence; see {path.name} before publishing")
    return credits


def preflight(proj: Project, log=print) -> bool:
    """Everything that can be checked before rendering. Returns True when there are no errors."""
    rows: list[tuple[str, str]] = []

    def row(level, msg):
        rows.append((level, msg))
        log(f"  {level:<5} {msg}")

    from .media import require_tool
    for t in ("ffmpeg", "ffprobe"):
        try:
            require_tool(t)
            row("OK", f"{t} found")
        except OexError as e:
            row("FAIL", e.message)
    audio = proj.path(proj.cfg["narration"]["audio"])
    row("OK", f"narration {audio.name}: {duration(audio):.2f}s")
    wp = words_path(proj)
    if not wp.exists():
        row("FAIL", "no word timings - run `oex transcribe` or `oex words import`")
    else:
        if wp.stat().st_mtime < audio.stat().st_mtime:
            row("WARN", "word timings are older than the narration; re-run `oex transcribe` if the take changed")
        try:
            tl = plan(proj, log=lambda *_: None)
            row("OK", f"storyboard aligned: {len(tl['scenes'])} scenes, {tl['duration']:.2f}s")
            for w in tl["warnings"]:
                row("WARN", w)
            if proj.cfg["mascot"] and proj.cfg["mascot"]["enabled"]:
                from .presenter import plan as mascot_plan
                mascot_plan(proj, tl, log=lambda *_: None)
                row("OK", "mascot prepared and every pose/expression in the storyboard exists")
            unknown = {e["id"] for e in tl.get("sfx_events", []) if e["license_status"] != "verified"}
            if unknown:
                row("WARN", f"sound effects without confirmed rights: {', '.join(sorted(unknown))}")
        except OexError as e:
            row("FAIL", str(e).splitlines()[0] if "\n" not in str(e) else str(e))
    if proj.cfg["sfx"] and proj.cfg["sfx"]["catalog"]:
        from .sfx import verify
        probs = verify(proj.path(proj.cfg["sfx"]["catalog"]))
        row("FAIL" if probs else "OK", f"sound catalog: {len(probs)} missing/changed file(s)" + (
            f" ({probs[0]})" if probs else ""))
    m = proj.cfg["music"]
    if m:
        if not proj.path(m["file"]).exists():
            row("FAIL", f"music file not found: {m['file']}")
        elif not m.get("license"):
            row("WARN", "music has no licence recorded (music.license); the film will be marked needs review")
        else:
            row("OK", f"music: {m['file']} ({m['license']})")
    ok = not any(lv == "FAIL" for lv, _ in rows)
    log("preflight: " + ("PASS" if ok else "FAIL"))
    return ok


def require_words(proj: Project) -> None:
    if not words_path(proj).exists():
        raise OexError("no word timings yet", "run `oex transcribe` or `oex words import <file.json>` first")
