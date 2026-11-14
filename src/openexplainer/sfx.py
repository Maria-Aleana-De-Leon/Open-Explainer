"""Sound-effect catalog (spec S5): import, label, query, verify, export, and cue planning for scene events.

Catalog file `oex-sfx-2` (JSON): {"schema": "oex-sfx-2", "sounds": [record, ...]}; a record:
    id, name, file (relative to the catalog when inside its folder), kind, labels[],
    length_s, loudest_at_s, peak_dbfs, rms_dbfs, brightness_hz, onset_s, sha256,
    guidance: {good_for[], avoid[]},
    rights:   {status: own | licensed | unknown, licence, holder, source, credit_line}

Sounds are referenced in place, never copied. Rights travel with every cue into the film's credits; anything not
`own` or `licensed` marks the film "needs review" before publishing.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

import numpy as np

from .errors import OexError
from .media import decode_mono, require_tool

SCHEMA = "oex-sfx-2"
AUDIO_EXT = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aif", ".aiff"}
KINDS = ["transition", "pop", "click", "impact", "chime", "riser", "ui", "ambience", "voice", "other"]
STATUSES = ["own", "licensed", "unknown"]
SAFE = {"own", "licensed"}
# words in a file name -> (kind, labels)
NAME_HINTS = {
    "whoosh": ("transition", ["whoosh"]), "swoosh": ("transition", ["whoosh"]), "swish": ("transition", ["whoosh"]),
    "sweep": ("transition", ["whoosh"]), "transition": ("transition", []), "pop": ("pop", ["pop"]),
    "bubble": ("pop", ["pop"]), "blip": ("pop", ["blip"]), "click": ("click", ["click"]), "tap": ("click", ["tap"]),
    "tick": ("click", ["tick"]), "type": ("click", ["typing"]), "impact": ("impact", ["hit"]),
    "hit": ("impact", ["hit"]), "thud": ("impact", ["thud"]), "boom": ("impact", ["boom"]),
    "punch": ("impact", ["hit"]), "ding": ("chime", ["ding", "success"]), "chime": ("chime", ["success"]),
    "bell": ("chime", ["bell"]), "success": ("chime", ["success"]), "notification": ("ui", ["notification"]),
    "riser": ("riser", ["build-up"]), "rise": ("riser", ["build-up"]), "drum": ("impact", ["drum"]),
    "laugh": ("voice", ["laugh"]), "wow": ("voice", ["exclamation"]), "buzz": ("ui", ["error"]),
    "error": ("ui", ["error"]),
}
NEVER_AUTO = {"voice", "ambience"}            # kinds never chosen automatically
NEVER_AUTO_LABELS = {"speech", "music", "explicit", "meme", "long"}


# ---------------- catalog io ----------------

def default_catalog() -> Path:
    return Path.home() / ".open-explainer" / "sfx" / "catalog.json"


def load(path: Path) -> dict:
    if not path.exists():
        return {"schema": SCHEMA, "sounds": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise OexError(f"{path} is not an {SCHEMA} catalog",
                       "re-import the sounds with `oex sfx add <folder>` or `oex sfx map <catalog.json> --mapping ...`")
    return data


def save(path: Path, cat: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cat["sounds"].sort(key=lambda s: s["id"])
    path.write_text(json.dumps(cat, indent=1, ensure_ascii=False), encoding="utf-8")


def file_of(cat_path: Path, rec: dict) -> Path:
    p = Path(rec["file"]).expanduser()
    return p if p.is_absolute() else (cat_path.parent / p)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def slug(s: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")[:64] or "sound"


def _portable(p: Path, cat_path: Path) -> str:
    rp, base = p.resolve(), cat_path.parent.resolve()
    return str(rp.relative_to(base)) if rp.is_relative_to(base) else str(rp)


# ---------------- analysis ----------------

def measure(p: Path) -> dict:
    """Technical description of a sound: length, loudest moment, levels, brightness, onset."""
    x = decode_mono(p, 16000)
    if len(x) < 160:
        raise OexError(f"{p.name}: audio too short or unreadable")
    hop = 160
    n = len(x) // hop
    env = np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(1) + 1e-12)
    m = min(len(x), 16000 * 4)
    spec = np.abs(np.fft.rfft(x[:m] * np.hanning(m)))
    freqs = np.fft.rfftfreq(m, 1 / 16000)
    return {"length_s": round(len(x) / 16000, 3), "loudest_at_s": round(int(np.argmax(env)) * hop / 16000, 3),
            "peak_dbfs": round(float(20 * np.log10(np.abs(x).max() + 1e-12)), 1),
            "rms_dbfs": round(float(20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-12)), 1),
            "brightness_hz": round(float((spec * freqs).sum() / (spec.sum() + 1e-12))),
            "onset_s": round(float(np.argmax(env > env.max() * 0.5) * hop / 16000), 3)}


def label(name: str, m: dict) -> tuple[str, list[str]]:
    kind, labels = None, set()
    for w in re.findall(r"[a-z]+", name.lower()):
        for k, (kd, ls) in NAME_HINTS.items():
            if w.startswith(k):
                kind = kind or kd
                labels.update(ls)
    L = m["length_s"]
    labels.add("short" if L < 0.6 else "medium" if L < 2.5 else "long")
    labels.add("bright" if m["brightness_hz"] > 2500 else "dark" if m["brightness_hz"] < 700 else "mid")
    if m["onset_s"] < 0.03:
        labels.add("sharp")
    if not kind:   # no name hint: guess from the sound's shape and say so
        kind = ("click" if L < 0.25 else "pop" if L < 0.6 and m["onset_s"] < 0.05 else
                "transition" if m["onset_s"] > 0.15 and L < 3 else "other")
        labels.add("kind-guessed")
    return kind, sorted(labels)


def _record(cat_path: Path, p: Path, sid: str, name: str, rights: dict, kind=None, labels=(), guidance=None) -> dict:
    m = measure(p)
    k, ls = label(name, m)
    return {"id": sid, "name": name, "file": _portable(p, cat_path), "kind": kind if kind in KINDS else k,
            "labels": sorted(set(ls) | set(labels)), **m, "sha256": sha256(p),
            "guidance": guidance or {"good_for": [], "avoid": []}, "rights": rights}


def _rights(status: str, licence=None, holder=None, source=None, credit=None) -> dict:
    if status not in STATUSES:
        raise OexError(f"unknown rights status '{status}'", f"use one of: {', '.join(STATUSES)}")
    if status == "licensed" and not licence:
        raise OexError("rights status 'licensed' needs --licence", "name the licence, e.g. CC0-1.0 or CC-BY-4.0")
    return {"status": status, "licence": licence, "holder": holder, "source": source, "credit_line": credit}


# ---------------- import ----------------

def add_folder(cat_path: Path, folder: Path, status: str, licence=None, holder=None, source=None, credit=None,
               log=print) -> int:
    rights = _rights(status, licence, holder, source, credit)
    cat = load(cat_path)
    by_hash = {s["sha256"]: s for s in cat["sounds"]}
    ids = {s["id"] for s in cat["sounds"]}
    files = sorted(p for p in Path(folder).rglob("*") if p.suffix.lower() in AUDIO_EXT)
    if not files:
        raise OexError(f"no audio files ({', '.join(sorted(AUDIO_EXT))}) in {folder}")
    added = 0
    for p in files:
        h = sha256(p)
        if h in by_hash:
            log(f"  = {p.name}: same audio as '{by_hash[h]['id']}', skipped")
            continue
        sid = slug(p.stem)
        while sid in ids:
            sid += "-2"
        try:
            rec = _record(cat_path, p, sid, p.stem, rights)
        except OexError as e:
            log(f"  skip {p.name}: {e.message}")
            continue
        ids.add(sid)
        by_hash[h] = rec
        cat["sounds"].append(rec)
        added += 1
        log(f"  + {sid:<34} {rec['kind']:<10} {rec['length_s']:5.2f}s  {', '.join(rec['labels'])}")
    save(cat_path, cat)
    return added


def _get(obj, path: str):
    for part in path.split("."):
        if obj is None:
            return None
        obj = obj.get(part) if isinstance(obj, dict) else None
    return obj


def add_mapped(cat_path: Path, src: Path, mapping: dict, log=print) -> int:
    """Import any JSON catalog: `mapping` says where each of our fields lives in the source records.
    Required keys: "records" (path to the list, "" = top level), "file", "name". Optional: "id", "kind",
    "labels", "good_for", "avoid", "status", "licence", "holder", "source", "credit_line", "status_values"
    (source value -> own|licensed|unknown). Files are referenced relative to the source catalog."""
    data = json.loads(src.read_text(encoding="utf-8"))
    recs = data if mapping.get("records", "") == "" else _get(data, mapping["records"])
    if not isinstance(recs, list):
        raise OexError(f"mapping 'records' does not point to a list in {src}")
    for k in ("file", "name"):
        if k not in mapping:
            raise OexError(f"mapping needs '{k}'", "see docs/USER-GUIDE.md (sound catalog)")
    sv = mapping.get("status_values", {})
    cat = load(cat_path)
    have = {s["sha256"] for s in cat["sounds"]}
    ids = {s["id"] for s in cat["sounds"]}
    added = 0
    for r in recs:
        f = _get(r, mapping["file"])
        if not f:
            continue
        p = (src.parent / f).resolve()
        if not p.exists():
            log(f"  skip {f}: file not found")
            continue
        if sha256(p) in have:
            continue
        name = str(_get(r, mapping["name"]) or p.stem)
        sid = slug(str(_get(r, mapping["id"]) if "id" in mapping else name))
        while sid in ids:
            sid += "-2"
        raw_status = _get(r, mapping["status"]) if "status" in mapping else None
        status = sv.get(str(raw_status), raw_status if raw_status in STATUSES else "unknown")
        rights = {"status": status, "licence": _get(r, mapping["licence"]) if "licence" in mapping else None,
                  "holder": _get(r, mapping["holder"]) if "holder" in mapping else None,
                  "source": _get(r, mapping["source"]) if "source" in mapping else None,
                  "credit_line": _get(r, mapping["credit_line"]) if "credit_line" in mapping else None}
        guid = {"good_for": list(_get(r, mapping["good_for"]) or []) if "good_for" in mapping else [],
                "avoid": list(_get(r, mapping["avoid"]) or []) if "avoid" in mapping else []}
        rec = _record(cat_path, p, sid, name, rights, _get(r, mapping["kind"]) if "kind" in mapping else None,
                      list(_get(r, mapping["labels"]) or []) if "labels" in mapping else [], guid)
        ids.add(sid)
        have.add(rec["sha256"])
        cat["sounds"].append(rec)
        added += 1
    save(cat_path, cat)
    unknown = sum(1 for s in cat["sounds"] if s["rights"]["status"] == "unknown")
    log(f"mapped {added} record(s) from {src.name}; {unknown} sound(s) in the catalog have unknown rights "
        "(films using them are marked 'needs review')")
    return added


# ---------------- query ----------------

def query(cat: dict, q: str = "") -> list[dict]:
    """Words must all appear in name/labels/kind/guidance. Filters: kind:<k>  rights:<status|safe>  max:<seconds>.
    Ranked by number of word hits (more first), then shorter sounds first."""
    words, kind, rights, maxlen = [], None, None, None
    for tok in q.lower().split():
        if tok.startswith("kind:"):
            kind = tok[5:]
        elif tok.startswith("rights:"):
            rights = tok[7:]
        elif tok.startswith("max:"):
            maxlen = float(tok[4:])
        else:
            words += re.findall(r"[a-z0-9]+", tok)
    hits = []
    for s in cat["sounds"]:
        if kind and s["kind"] != kind:
            continue
        st = s["rights"]["status"]
        if rights and not (st in SAFE if rights == "safe" else st == rights):
            continue
        if maxlen is not None and s["length_s"] > maxlen:
            continue
        hay = " ".join([s["id"], s["name"], s["kind"], *s["labels"], *s["guidance"]["good_for"]]).lower()
        score = sum(hay.count(w) for w in words)
        if all(w in hay for w in words):
            hits.append((-score, s["length_s"], s["id"], s))
    return [h[-1] for h in sorted(hits)]


def verify(cat_path: Path) -> list[str]:
    problems = []
    for s in load(cat_path)["sounds"]:
        p = file_of(cat_path, s)
        if not p.exists():
            problems.append(f"{s['id']}: file missing ({p})")
        elif sha256(p) != s["sha256"]:
            problems.append(f"{s['id']}: file changed since it was added (hash differs) - add it again")
    return problems


def cut(cat_path: Path, sid: str, out: Path, offset: float = 0.0, length: float | None = None, gain: float = 0.0,
        ramp_ms: int = 8) -> Path:
    """Write a trimmed, faded, gain-adjusted 48 kHz stereo WAV of a catalogued sound to a NEW file."""
    s = next((x for x in load(cat_path)["sounds"] if x["id"] == sid), None)
    if not s:
        raise OexError(f"no sound '{sid}' in {cat_path}", "find ids with `oex sfx find <words>`")
    if out.exists():
        raise OexError(f"{out} already exists", "choose a new output name; existing files are never replaced")
    L = length or max(0.01, s["length_s"] - offset)
    r = ramp_ms / 1000
    flt = (f"atrim=start={offset}:duration={L},asetpts=N/SR/TB,afade=t=in:d={r},"
           f"afade=t=out:st={max(0.0, L - r)}:d={r},volume={gain}dB")
    res = subprocess.run([require_tool("ffmpeg"), "-v", "error", "-nostdin", "-i", str(file_of(cat_path, s)), "-af",
                          flt, "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(out)], capture_output=True, text=True)
    if res.returncode:
        raise OexError(f"cut failed: {res.stderr[-300:]}")
    return out


# ---------------- cue planning ----------------

ROLE_KINDS = {"transition": ["transition"], "reveal": ["pop", "click", "ui"], "emphasis": ["impact", "chime"],
              "number": ["chime", "impact", "pop"], "finale": ["chime", "pop"]}
ROLE_PRIORITY = {"transition": 3, "finale": 3, "number": 2, "emphasis": 2, "reveal": 1}
TRANSITION_GAP = 8.0   # seconds between automatic transition whooshes
ROLE_PEAK = {"transition": -22.0, "reveal": -24.0, "emphasis": -21.0, "number": -20.0, "finale": -19.0}   # dBFS


def _events(tl: dict) -> list[dict]:
    ev = []
    for i, sc in enumerate(tl["scenes"]):
        if i > 0:
            ev.append({"t": sc["start"], "role": "transition", "scene": sc["id"], "why": "scene change"})
        if sc["type"] in ("bullets", "flow"):
            for k, it in enumerate(sc.get("items", [])):
                ev.append({"t": it["t"], "role": "reveal", "scene": sc["id"], "why": f"item {k + 1} appears"})
        elif sc["type"] == "diagram":
            for k, step in enumerate(sc.get("steps", [])):
                if step.get("show"):
                    ev.append({"t": step["t"], "role": "reveal", "scene": sc["id"], "why": f"diagram step {k + 1}"})
        elif sc["type"] == "number":
            ev.append({"t": sc["t"] + 0.9, "role": "number", "scene": sc["id"], "why": "count-up lands"})
        elif sc["type"] == "statement" and sc.get("emphasis_t"):
            ev.append({"t": sc["emphasis_t"], "role": "emphasis", "scene": sc["id"], "why": "emphasis word"})
        elif sc["type"] == "end":
            ev.append({"t": sc["t"] + 0.5, "role": "finale", "scene": sc["id"], "why": "call to action"})
    return ev


def choose(cat: dict, role: str, k: int) -> dict | None:
    """Every suitable sound for the role, in kind order, rotated: consecutive cues of a role never repeat a sound
    while there is more than one candidate."""
    cands = []
    for kind in ROLE_KINDS[role]:
        cands += sorted((s for s in cat["sounds"] if s["kind"] == kind and s["kind"] not in NEVER_AUTO
                         and not (set(s["labels"]) & NEVER_AUTO_LABELS)
                         and s["length_s"] <= (3.0 if role == "transition" else 1.5)), key=lambda s: s["id"])
    return cands[k % len(cands)] if cands else None


def level_gain(sound: dict, role: str, offset_db: float = 0.0) -> float:
    """Gain that puts the sound's peak at the role's target level, whatever its own loudness: a heavy impact and a
    faint click end up equally present. Targets sit well under narration peaks (about -6 dBFS after mastering)."""
    return round(ROLE_PEAK[role] + offset_db - sound.get("peak_dbfs", -6.0), 1)


def plan_cues(proj, tl: dict, log=print) -> list[dict]:
    cfg = proj.cfg["sfx"]
    cat_path = proj.path(cfg["catalog"]) if cfg["catalog"] else default_catalog()
    cat = load(cat_path)
    by_id = {s["id"]: s for s in cat["sounds"]}
    picked, problems = [], []
    for sc in tl["scenes"]:
        for c in sc.get("sfx", []):
            if c.get("t") is None:
                continue
            if c.get("sound"):
                s = by_id.get(c["sound"])
                if not s:
                    problems.append(f"scene {sc['id']}: sound '{c['sound']}' is not in {cat_path}")
                    continue
            else:
                hits = query(cat, c.get("tag", ""))
                if not hits:
                    problems.append(f"scene {sc['id']}: no sound matches '{c.get('tag')}'")
                    continue
                s = hits[0]
            picked.append({"t": c["t"], "sound": s, "gain_db": c.get("gain_db", cfg["gain_db"]), "role": "explicit",
                           "why": f"storyboard cue in {sc['id']}"})
    if problems:
        from .errors import ValidationError
        raise ValidationError("sfx cues", problems)
    auto_n = 0
    if cfg["auto"]:
        budget = int(cfg["max_per_minute"] * tl["duration"] / 60 + 0.5)
        # a whoosh on every cut is the most common way to overdo sound: transitions get at most half the budget
        # and are spaced at least TRANSITION_GAP apart, leaving cues for the moments that matter
        cap = {"transition": max(1, budget // 2)}
        used: dict = {}
        taken, rot = [p["t"] for p in picked], {}
        for e in sorted(_events(tl), key=lambda e: (-ROLE_PRIORITY[e["role"]], e["t"])):
            if auto_n >= budget:
                break
            if any(abs(e["t"] - t) < cfg["min_gap"] for t in taken):
                continue
            if used.get(e["role"], 0) >= cap.get(e["role"], budget):
                continue
            if e["role"] == "transition":
                if any(abs(e["t"] - t) < TRANSITION_GAP for t, r in ((p["t"], p["role"]) for p in picked)
                       if r == "transition"):
                    continue
            s = choose(cat, e["role"], rot.get(e["role"], 0))
            if not s:
                continue
            near = [p["sound"]["id"] for p in picked if abs(p["t"] - e["t"]) < 10]
            for extra in range(1, 6):            # never the same sound as a neighbouring cue, whatever its role
                if s["id"] not in near:
                    break
                alt = choose(cat, e["role"], rot.get(e["role"], 0) + extra)
                if alt and alt["id"] not in near:
                    s = alt
                    break
            if s["id"] in near:
                continue                         # no fresh sound for this moment: silence beats a repeat
            rot[e["role"]] = rot.get(e["role"], 0) + 1
            used[e["role"]] = used.get(e["role"], 0) + 1
            picked.append({"t": e["t"], "sound": s, "gain_db": level_gain(s, e["role"], cfg["gain_db"] + 12),
                           "role": e["role"], "why": f"{e['why']} ({e['scene']})"})
            taken.append(e["t"])
            auto_n += 1
    events = []
    for p in sorted(picked, key=lambda p: p["t"]):
        s = p["sound"]
        start = max(0.0, p["t"] - min(s["loudest_at_s"], 0.6))     # loudest moment lands on the event
        r = s["rights"]
        events.append({"t": round(start, 3), "event_t": round(p["t"], 3), "id": s["id"],
                       "file": str(file_of(cat_path, s)), "gain_db": round(p["gain_db"], 1),
                       "duration": min(s["length_s"], 3.0), "role": p["role"], "why": p["why"],
                       "license": r.get("licence"), "license_status": {"own": "verified", "licensed": "verified"}
                       .get(r["status"], "unverified"), "author": r.get("holder"), "source_url": r.get("source"),
                       "attribution": r.get("credit_line")})
    log(f"sfx: {len(events)} cue(s) ({auto_n} automatic, {len(events) - auto_n} from the storyboard) from "
        f"{len(cat['sounds'])} catalogued sounds")
    for e in events:
        log(f"  {e['event_t']:7.2f}s  {e['id']:<30} {e['gain_db']:+.0f} dB  {e['why']}")
    return events
