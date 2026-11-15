"""oex assets split|place-mouths - turn generated sprite sheets into individual, checked PNGs."""
from __future__ import annotations

from pathlib import Path

from .errors import OexError


def cmd_split(a) -> int:
    from .sheets import split
    sheet = Path(a.sheet)
    if not sheet.exists():
        raise OexError(f"{sheet} not found", "give the path of the sheet PNG")
    names = [n.strip() for n in a.names.split(",")] if a.names else None
    canvas = None
    if a.canvas:
        try:
            canvas = tuple(int(v) for v in a.canvas.lower().split("x"))
            assert len(canvas) == 2
        except (ValueError, AssertionError):
            raise OexError(f"--canvas {a.canvas!r} is not WxH", "e.g. --canvas 420x460") from None
    m = split(sheet, a.kind, Path(a.out), names, canvas=canvas)
    for it in m["items"]:
        mark = "WARN " if it.get("warnings") else "ok   "
        size = "x".join(map(str, it["size"])) if "size" in it else "-"
        print(f"  {mark}{it['name']:<20} {size:>10}  {'; '.join(it.get('warnings', []))}")
    for p in m["problems"]:
        print(f"  ERROR {p}")
    print(f"\n{len([i for i in m['items'] if 'file' in i])} file(s) in {a.out}; look at {Path(a.out) / 'split' / 'review.png'}")
    print("OK - check review.png by eye" if m["ok"] else "NOT OK - see the errors above")
    return 0 if m["ok"] else 2


def cmd_place_mouths(a) -> int:
    from .sheets import place_mouths
    try:
        cx, cy, w = (int(v) for v in a.box.split(","))
    except ValueError:
        raise OexError(f"--box {a.box!r} is not x,y,width", "e.g. --box 420,612,96 (pixels in the face image)") from None
    files = place_mouths(Path(a.mascot), Path(a.sprites), (cx, cy, w), Path(a.base) if a.base else None)
    print(f"wrote {', '.join(files)} in {a.mascot}")
    print(f"next: oex mascot prepare {a.mascot}, then check every mouth in build/review.png by eye")
    return 0


def register(sub) -> None:
    from .sheets import KINDS
    p = sub.add_parser("assets", help="split generated sprite sheets (poses, expressions, mouths, stickers)")
    s = p.add_subparsers(dest="assets_cmd", required=True)
    q = s.add_parser("split", help="split a sheet into named, checked transparent PNGs + manifest + review.png")
    q.add_argument("sheet")
    q.add_argument("--kind", required=True, choices=list(KINDS))
    q.add_argument("--out", required=True, help="output folder (for poses/expressions: a mascot folder)")
    q.add_argument("--names", help="comma-separated names in reading order, instead of the kind's defaults")
    q.add_argument("--canvas", help="WxH shared canvas for poses/expressions/mouthless (to line up two sheets)")
    q.set_defaults(fn=cmd_split)
    q = s.add_parser("place-mouths", help="paint split mouth sprites onto the mascot's face (mouth-*.png)")
    q.add_argument("mascot", help="mascot folder (holds neutral.png)")
    q.add_argument("sprites", help="folder with sprite-*.png from `oex assets split --kind mouths`")
    q.add_argument("--box", required=True, help="centre x, centre y and width of the mouth, in face pixels")
    q.add_argument("--base", help="a mouthless face on the same canvas (e.g. base-neutral.png); recommended")
    q.set_defaults(fn=cmd_place_mouths)
