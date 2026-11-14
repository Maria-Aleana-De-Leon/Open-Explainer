"""project.json + storyboard.json: schemas, defaults, loading.

A project folder:
    project.json        settings (format, style, narration, mascot, music, sfx, captions)
    storyboard.json     scenes: narration text ("say") + what appears, with cue phrases ("at")
    audio/              narration and music
    build/              everything generated (safe to delete)
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path

from .errors import OexError, ValidationError
from .schema import B, CUE, HEX, N, S, check

FORMATS = {"16:9": (1920, 1080), "9:16": (1080, 1920)}
SCENE_TYPES = ["title", "bullets", "statement", "flow", "number", "compare", "image", "diagram", "end"]
TRANSITIONS = ["fade", "slide", "wipe", "zoom", "none"]
POSITIONS = ["left", "right", "bottom-left", "bottom-right"]

MASCOT_ACTION = {"type": "object", "required": ["at"], "fields": {
    "at": CUE, "pose": S, "expression": S, "for": {"type": "number", "min": 0.2}}}
SFX_CUE = {"type": "object", "required": ["at"], "fields": {
    "at": CUE, "sound": S, "tag": S, "gain_db": N}}
ITEM = {"type": ["object", "string"], "required": ["text"], "fields": {"text": S, "at": CUE}}
IDS = {"type": "array", "items": S}
UNIT = {"type": "number", "min": 0, "max": 1}
EASES = ["linear", "in_out_sine", "out_sine", "out_cubic", "in_out_cubic", "out_quint", "in_out_quint", "out_expo",
         "out_back", "spring"]
NODE = {"type": "object", "required": ["id", "label"], "fields": {
    "id": S, "label": S, "x": UNIT, "y": UNIT, "sub": S,
    "shape": {"type": "string", "enum": ["box", "pill", "circle", "diamond"]}}}
EDGE = {"type": "object", "required": ["from", "to"], "fields": {
    "id": S, "from": S, "to": S, "label": S, "route": {"type": "string", "enum": ["straight", "curve", "elbow"]}}}
GROUP = {"type": "object", "required": ["id", "nodes"], "fields": {"id": S, "label": S, "nodes": IDS}}
FLOW = {"type": "object", "fields": {"edge": S, "path": IDS, "label": S, "back": S, "reverse": {"type": "boolean"},
                                     "dur": {"type": "number", "min": 0.3, "max": 6}}}
MOVE = {"type": "object", "required": ["x", "y"], "fields": {"x": UNIT, "y": UNIT,
                                                            "ease": {"type": "string", "enum": EASES}}}
STEP = {"type": "object", "required": ["at"], "fields": {
    "at": CUE, "show": IDS, "hide": IDS, "draw": IDS, "activate": IDS, "deactivate": IDS, "done": IDS, "error": IDS,
    "dim": IDS, "undim": IDS, "focus": IDS, "unfocus": {"type": "boolean"},
    "label": {"type": "object", "values": S}, "move": {"type": "object", "values": MOVE},
    "flow": {"type": ["object", "array"], "fields": FLOW["fields"], "items": FLOW},
    "ease": {"type": "string", "enum": EASES}, "stagger": {"type": "number", "min": 0, "max": 2}}}

SCENE = {"type": "object", "required": ["id", "type", "say"], "fields": {
    "id": {"type": "string", "pattern": r"[a-z][a-z0-9_-]{0,31}"},
    "type": {"type": "string", "enum": SCENE_TYPES},
    "say": {"type": "string"},
    "title": S, "subtitle": S, "heading": S, "text": S, "label": S, "value": S, "cta": S,
    "emphasis": S, "image": S,
    "items": {"type": "array", "items": ITEM},
    "nodes": {"type": "array", "items": NODE}, "edges": {"type": "array", "items": EDGE},
    "steps": {"type": "array", "items": STEP}, "groups": {"type": "array", "items": GROUP},
    "center": S, "continue": {"type": "boolean"},
    "left": {"type": "object", "fields": {"title": S, "items": {"type": "array", "items": ITEM}, "at": CUE}},
    "right": {"type": "object", "fields": {"title": S, "items": {"type": "array", "items": ITEM}, "at": CUE}},
    "at": CUE,
    "transition": {"type": "string", "enum": TRANSITIONS},
    "camera": {"type": "string", "enum": ["push", "still"]},
    "layout": {"type": "string", "enum": ["row", "cycle", "column", "hub", "manual"]},
    "mascot": {"type": ["array", "boolean"], "items": MASCOT_ACTION},
    "sfx": {"type": "array", "items": SFX_CUE},
    "notes": S,
}}
STORYBOARD = {"type": "object", "required": ["scenes"], "fields": {
    "scenes": {"type": "array", "items": SCENE, "min": 1},
    "notes": S,
}}

PROJECT = {"type": "object", "required": ["title", "narration"], "fields": {
    "title": S,
    "format": {"type": "string", "enum": list(FORMATS)},
    "fps": {"type": "integer", "min": 12, "max": 60},
    "style": S,
    "accent": HEX,
    "camera": {"type": "string", "enum": ["push", "still"]},
    "narration": {"type": "object", "required": ["audio"], "fields": {
        "audio": S, "language": {"type": ["string", "null"]}, "words": S, "prompt": S, "model": S}},
    "storyboard": S,
    "tail": {"type": "number", "min": 0, "max": 10},
    "mascot": {"type": ["object", "null"], "fields": {
        "dir": S, "position": {"type": "string", "enum": POSITIONS}, "scale": {"type": "number", "min": 0.2, "max": 3},
        "enabled": B}},
    "music": {"type": ["object", "null"], "required": ["file"], "fields": {
        "file": S, "gain_db": N, "duck_db": N, "license": S, "fade_out": N}},
    "sfx": {"type": ["object", "null"], "fields": {
        "catalog": S, "auto": B, "gain_db": N, "max_per_minute": {"type": "number", "min": 0},
        "min_gap": {"type": "number", "min": 0}}},
    "captions": {"type": "object", "fields": {"burn_in": B, "max_words": {"type": "integer", "min": 1},
                                              "source": {"type": "string", "enum": ["script", "transcript"]}}},
    "audio": {"type": "object", "fields": {"target_lufs": N, "true_peak": N}},
}}

DEFAULTS = {
    "format": "16:9", "fps": 30, "style": "paper", "storyboard": "storyboard.json", "tail": 1.2,
    "narration": {"language": None, "words": "build/words.json", "prompt": "", "model": "small"},
    "mascot": None, "music": None, "sfx": None,
    "captions": {"burn_in": True, "max_words": 6, "source": "script"},
    "audio": {"target_lufs": -16.0, "true_peak": -1.5},
}
MASCOT_DEFAULTS = {"position": "left", "scale": 1.0, "enabled": True}
MUSIC_DEFAULTS = {"gain_db": -14.0, "duck_db": 8.0, "license": "", "fade_out": 2.0}   # ~20 dB under speech, ~12 dB in pauses
SFX_DEFAULTS = {"catalog": "", "auto": False, "gain_db": -12.0, "max_per_minute": 6.0, "min_gap": 3.0}


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def read_json(path: Path) -> dict:
    if not path.exists():
        raise OexError(f"{path} not found", "run `oex new <folder>` to create a project, or check the path")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise OexError(f"{path} is not valid JSON: line {e.lineno} col {e.colno}: {e.msg}",
                       "fix the syntax (trailing commas and comments are not allowed in JSON)") from e


@dataclass
class Project:
    root: Path
    cfg: dict
    storyboard: dict

    @property
    def size(self) -> tuple[int, int]:
        return FORMATS[self.cfg["format"]]

    @property
    def fps(self) -> int:
        return self.cfg["fps"]

    @property
    def build(self) -> Path:
        return self.root / "build"

    def path(self, rel: str) -> Path:
        p = Path(rel).expanduser()
        return p if p.is_absolute() else self.root / p


def load_project(root: Path, require_audio: bool = True) -> Project:
    root = root.resolve()
    raw = read_json(root / "project.json")
    problems = check(raw, PROJECT, "project.json")
    if problems:
        raise ValidationError("project.json", problems)
    cfg = _merge(DEFAULTS, raw)
    if cfg["mascot"] is not None:
        cfg["mascot"] = _merge(MASCOT_DEFAULTS, cfg["mascot"])
    if cfg["music"] is not None:
        cfg["music"] = _merge(MUSIC_DEFAULTS, cfg["music"])
    if cfg["sfx"] is not None:
        cfg["sfx"] = _merge(SFX_DEFAULTS, cfg["sfx"])
    from .styles import STYLES
    if cfg["style"] not in STYLES:
        raise ValidationError("project.json", [f"$.style: unknown style '{cfg['style']}'; available: {', '.join(STYLES)}"])
    sb_path = root / cfg["storyboard"]
    sb = read_json(sb_path)
    problems = check(sb, STORYBOARD, sb_path.name)
    ids = [s.get("id") for s in sb.get("scenes", []) if isinstance(s, dict)]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        problems.append(f"{sb_path.name}: duplicate scene id(s): {', '.join(dup)}")
    problems += _scene_content_problems(sb)
    if problems:
        raise ValidationError(sb_path.name, problems)
    proj = Project(root, cfg, sb)
    audio = proj.path(cfg["narration"]["audio"])
    if require_audio and not audio.exists():
        raise OexError(f"narration audio not found: {audio}",
                       "put your MP3/WAV take there, or change narration.audio in project.json")
    return proj


REQUIRED_CONTENT = {
    "title": ["title"], "bullets": ["items"], "statement": ["text"], "flow": ["items"],
    "number": ["value"], "compare": ["left", "right"], "image": ["image"], "diagram": ["nodes"], "end": ["title"],
}


def _scene_content_problems(sb: dict) -> list[str]:
    out = []
    for i, s in enumerate(sb.get("scenes", [])):
        if not isinstance(s, dict) or s.get("type") not in REQUIRED_CONTENT:
            continue
        for f in REQUIRED_CONTENT[s["type"]]:
            if not s.get(f):
                out.append(f"scenes[{i}] ({s.get('id')}): a '{s['type']}' scene needs '{f}'")
        if not str(s.get("say", "")).strip():
            out.append(f"scenes[{i}] ({s.get('id')}): 'say' is empty; every scene needs the narration it covers")
        if s["type"] == "diagram" and s.get("nodes"):
            from .errors import OexError
            from .scenes import check_diagram
            try:
                check_diagram(s)
            except OexError as e:
                out.append(f"{e.message}; {e.fix}")
            except (KeyError, TypeError, AttributeError):
                pass                                    # malformed fields: the schema check reports those
    return out
