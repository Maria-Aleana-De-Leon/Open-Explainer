"""oex mascot prepare|check - the mascot import and validation workflow."""
from __future__ import annotations

import json
from pathlib import Path

from .errors import OexError


def cmd_prepare(a) -> int:
    from .mascot import prepare
    meta = {k: v for k, v in (("name", a.name), ("author", a.author), ("license", a.license),
                              ("generated_with", a.generated_with)) if v}
    if not Path(a.dir).is_dir():
        raise OexError(f"{a.dir} is not a folder", "give the folder that holds neutral.png and the other images")
    print(f"preparing mascot from {a.dir}")
    info = prepare(Path(a.dir), meta=meta)
    errors = [c for c in info["checks"] if c["level"] == "error"]
    print("\nREADY - open review.png and approve it before rendering" if not errors else
          f"\nNOT READY - {len(errors)} error(s); fix the images and run again")
    return 0 if not errors else 2


def cmd_check(a) -> int:
    f = Path(a.dir) / "build" / "mascot.json"
    if not f.exists():
        raise OexError(f"{f} not found", f"run `oex mascot prepare {a.dir}` first")
    info = json.loads(f.read_text())
    for c in info["checks"]:
        print(f"  {c['level'].upper():<5} {c['msg']}")
    for n, st in info["states"].items():
        print(f"  state {n:<20} head {st['score']:.2f}  talk {st['talk']}  blink {st['blink']}")
    print("OK" if info["ok"] else "ERRORS")
    return 0 if info["ok"] else 2


def register(sub) -> None:
    p = sub.add_parser("mascot", help="prepare and validate a user-made mascot")
    s = p.add_subparsers(dest="mascot_cmd", required=True)
    q = s.add_parser("prepare", help="import PNGs, align, extract mouths/eyes, validate, write review.png")
    q.add_argument("dir")
    q.add_argument("--name")
    q.add_argument("--author")
    q.add_argument("--license", help="licence of the artwork, e.g. 'CC-BY-4.0' or 'all rights reserved (mine)'")
    q.add_argument("--generated-with", help="e.g. 'ChatGPT image generation'")
    q.set_defaults(fn=cmd_prepare)
    q = s.add_parser("check", help="print the validation results of a prepared mascot")
    q.add_argument("dir")
    q.set_defaults(fn=cmd_check)
