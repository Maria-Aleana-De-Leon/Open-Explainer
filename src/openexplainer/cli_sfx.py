"""oex sfx add | map | find | label | check | cut - the sound-effect catalog (spec S5)."""
from __future__ import annotations

import json
from pathlib import Path

from . import sfx as X
from .errors import OexError


def _cat(a) -> Path:
    return Path(a.catalog).expanduser() if a.catalog else X.default_catalog()


def cmd_add(a) -> int:
    n = X.add_folder(_cat(a), Path(a.folder), a.rights, a.licence, a.holder, a.source, a.credit)
    print(f"{n} sound(s) added -> {_cat(a)}")
    return 0


def cmd_map(a) -> int:
    mp = Path(a.mapping)
    if not mp.exists():
        raise OexError(f"mapping file {mp} not found", "see docs/USER-GUIDE.md, 'Importing another catalog'")
    n = X.add_mapped(_cat(a), Path(a.source), json.loads(mp.read_text()))
    print(f"{n} sound(s) added -> {_cat(a)}")
    return 0


def cmd_find(a) -> int:
    if not _cat(a).exists():
        raise OexError(f"no sound catalog at {_cat(a)}", "add sounds first: oex sfx add <folder> --rights own "
                       "(or pass --catalog <file>)")
    hits = X.query(X.load(_cat(a)), " ".join(a.query))
    if a.json:
        print(json.dumps(hits, indent=1))
        return 0
    for s in hits:
        print(f"{s['id']:<34} {s['kind']:<10} {s['length_s']:5.2f}s  {s['rights']['status']:<8} {', '.join(s['labels'])}")
    print(f"{len(hits)} match(es)")
    return 0


def cmd_label(a) -> int:
    cp = _cat(a)
    cat = X.load(cp)
    s = next((x for x in cat["sounds"] if x["id"] == a.id), None)
    if not s:
        raise OexError(f"no sound '{a.id}'", "find ids with `oex sfx find <words>`")
    s["labels"] = sorted((set(s["labels"]) | set(a.add or [])) - set(a.drop or []))
    if a.kind:
        if a.kind not in X.KINDS:
            raise OexError(f"unknown kind '{a.kind}'", f"use one of {', '.join(X.KINDS)}")
        s["kind"] = a.kind
    if a.good_for:
        s["guidance"]["good_for"].append(a.good_for)
    if a.avoid:
        s["guidance"]["avoid"].append(a.avoid)
    X.save(cp, cat)
    print(json.dumps(s, indent=1))
    return 0


def cmd_check(a) -> int:
    probs = X.verify(_cat(a))
    for p in probs:
        print("  " + p)
    print("OK" if not probs else f"{len(probs)} problem(s)")
    return 0 if not probs else 2


def cmd_cut(a) -> int:
    print(X.cut(_cat(a), a.id, Path(a.out), a.offset, a.length, a.gain, a.ramp_ms))
    return 0


def register(sub) -> None:
    p = sub.add_parser("sfx", help="sound-effect catalog")
    p.add_argument("--catalog", help=f"catalog file (default {X.default_catalog()})")
    s = p.add_subparsers(dest="sfx_cmd", required=True)
    q = s.add_parser("add", help="add a folder of sounds you have rights to")
    q.add_argument("folder")
    q.add_argument("--rights", choices=X.STATUSES, required=True,
                   help="own = you made them; licensed = licence checked (give --licence); unknown = flagged")
    q.add_argument("--licence", help="e.g. CC0-1.0, CC-BY-4.0")
    q.add_argument("--holder", help="rights holder / author")
    q.add_argument("--source", help="where the sounds came from (URL)")
    q.add_argument("--credit", help="credit line the licence requires, if any")
    q.set_defaults(fn=cmd_add)
    q = s.add_parser("map", help="add sounds from another JSON catalog using a field mapping")
    q.add_argument("source")
    q.add_argument("--mapping", required=True, help="JSON file mapping our fields to the source's fields")
    q.set_defaults(fn=cmd_map)
    q = s.add_parser("find", help="query: words + kind:<k> rights:<own|licensed|unknown|safe> max:<seconds>")
    q.add_argument("query", nargs="*")
    q.add_argument("--json", action="store_true")
    q.set_defaults(fn=cmd_find)
    q = s.add_parser("label", help="edit a sound's labels, kind and guidance")
    q.add_argument("id")
    q.add_argument("--add", nargs="*")
    q.add_argument("--drop", nargs="*")
    q.add_argument("--kind")
    q.add_argument("--good-for")
    q.add_argument("--avoid")
    q.set_defaults(fn=cmd_label)
    q = s.add_parser("check", help="every catalogued file present and unchanged")
    q.set_defaults(fn=cmd_check)
    q = s.add_parser("cut", help="write a trimmed, faded 48 kHz WAV of a sound to a new file")
    q.add_argument("id")
    q.add_argument("out")
    q.add_argument("--offset", type=float, default=0.0)
    q.add_argument("--length", type=float)
    q.add_argument("--gain", type=float, default=0.0, help="dB")
    q.add_argument("--ramp-ms", type=int, default=8)
    q.set_defaults(fn=cmd_cut)
