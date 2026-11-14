"""Draw the demo mascot "Pip" procedurally, as the same set of PNGs a creator would make with an image generator.

Pip is original artwork created by this script for this project (MIT, like the code), so it can be redistributed.
The variants are deliberately imperfect, like generated images: each is re-drawn with a small random scale/offset/
colour drift, one is exported on a white background, one on a fake transparency checkerboard. That exercises the
real preparation pipeline (alignment, background removal, drift rejection).

usage: python tools/make_demo_mascot.py <out_dir> [--clean]   (deterministic: fixed random seed)
"""
import argparse
import random
from pathlib import Path

from PIL import Image, ImageDraw

W, H = 900, 1300
SKIN, HAIR, SHIRT, INK, CHEEK = (246, 201, 160), (58, 42, 38), (46, 134, 171), (35, 28, 26), (240, 150, 140)


def draw(mouth="smile", eyes="open", arm=None, brows="flat", drift=(1.0, 0, 0, 0), bg=None):
    s, dx, dy, dc = drift
    im = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    def P(x, y):
        return ((W / 2 + (x - W / 2) * s + dx) * 2, (H / 2 + (y - H / 2) * s + dy) * 2)

    def box(x0, y0, x1, y1):
        a, b = P(x0, y0), P(x1, y1)
        return [a[0], a[1], b[0], b[1]]

    def col(c):
        return tuple(max(0, min(255, v + dc)) for v in c)

    lw = int(10 * s)
    # body
    d.rounded_rectangle(box(250, 700, 650, 1260), 120 * s, fill=col(SHIRT), outline=INK, width=lw)
    # arms
    if arm == "point":
        d.line([P(600, 800), P(760, 640), P(860, 520)], fill=col(SHIRT), width=int(80 * s), joint="curve")
        d.ellipse(box(820, 470, 900, 550), fill=col(SKIN), outline=INK, width=lw)
        d.line([P(860, 500), P(895, 455)], fill=INK, width=lw * 2)
    elif arm == "present":
        d.line([P(610, 850), P(780, 900)], fill=col(SHIRT), width=int(80 * s))
        d.ellipse(box(760, 860, 860, 930), fill=col(SKIN), outline=INK, width=lw)
    elif arm == "wave":
        d.line([P(610, 820), P(740, 640), P(760, 470)], fill=col(SHIRT), width=int(80 * s), joint="curve")
        d.ellipse(box(705, 380, 820, 490), fill=col(SKIN), outline=INK, width=lw)
    elif arm == "chin":
        d.line([P(560, 900), P(520, 700)], fill=col(SHIRT), width=int(80 * s))
    if arm != "point" and arm != "wave":
        d.line([P(600, 820), P(640, 1080)], fill=col(SHIRT), width=int(70 * s))
    d.line([P(300, 820), P(260, 1080)], fill=col(SHIRT), width=int(70 * s))
    # head
    d.ellipse(box(170, 60, 730, 690), fill=col(SKIN), outline=INK, width=lw)
    d.chord(box(165, 40, 735, 470), 180, 360, fill=col(HAIR), outline=INK, width=lw)
    d.polygon([P(200, 260), P(300, 180), P(330, 300)], fill=col(HAIR))
    if arm == "chin":
        d.ellipse(box(470, 640, 570, 720), fill=col(SKIN), outline=INK, width=lw)
    # cheeks
    d.ellipse(box(225, 455, 305, 505), fill=col(CHEEK))
    d.ellipse(box(595, 455, 675, 505), fill=col(CHEEK))
    # eyes
    for cx in (330, 570):
        if eyes == "open":
            d.ellipse(box(cx - 48, 330, cx + 48, 440), fill=(255, 255, 255), outline=INK, width=lw)
            d.ellipse(box(cx - 22, 360, cx + 22, 420), fill=INK)
            d.ellipse(box(cx - 8, 368, cx + 6, 382), fill=(255, 255, 255))
        elif eyes == "wide":
            d.ellipse(box(cx - 58, 315, cx + 58, 455), fill=(255, 255, 255), outline=INK, width=lw)
            d.ellipse(box(cx - 16, 368, cx + 16, 410), fill=INK)
        elif eyes == "up":
            d.ellipse(box(cx - 48, 330, cx + 48, 440), fill=(255, 255, 255), outline=INK, width=lw)
            d.ellipse(box(cx - 6, 338, cx + 34, 388), fill=INK)
        elif eyes == "happy":
            d.arc(box(cx - 46, 360, cx + 46, 430), 200, 340, fill=INK, width=lw * 2)
        else:  # closed
            d.arc(box(cx - 46, 340, cx + 46, 420), 20, 160, fill=INK, width=lw * 2)
    # brows
    for cx, side in ((330, -1), (570, 1)):
        if brows == "raised" and side == 1:
            d.line([P(cx - 50, 280), P(cx + 50, 255)], fill=INK, width=lw * 2)
        elif brows == "up":
            d.line([P(cx - 50, 270), P(cx + 50, 270)], fill=INK, width=lw * 2)
        else:
            d.line([P(cx - 50, 300), P(cx + 50, 300)], fill=INK, width=lw * 2)
    # mouth (centre 450, 560)
    if mouth == "smile":
        d.arc(box(385, 500, 515, 590), 20, 160, fill=INK, width=lw)
    elif mouth in ("closed", "mbp"):
        d.line([P(395, 560), P(505, 560)], fill=INK, width=lw)
    elif mouth in ("small", "half"):
        d.ellipse(box(420, 540, 480, 585), fill=(110, 30, 40), outline=INK, width=lw)
    elif mouth in ("open", "ah"):
        d.ellipse(box(395, 525, 505, 625), fill=(110, 30, 40), outline=INK, width=lw)
        d.chord(box(415, 585, 485, 630), 180, 360, fill=(230, 110, 120))
    elif mouth in ("wide", "ee"):
        d.rounded_rectangle(box(375, 535, 525, 595), 28 * s, fill=(110, 30, 40), outline=INK, width=lw)
        d.rectangle(box(390, 540, 510, 558), fill=(255, 255, 255))
    elif mouth in ("round", "oh"):
        d.ellipse(box(420, 525, 480, 610), fill=(110, 30, 40), outline=INK, width=lw)
    elif mouth == "oo":
        d.ellipse(box(432, 545, 468, 590), fill=(110, 30, 40), outline=INK, width=lw)
        d.arc(box(424, 538, 476, 598), 0, 360, fill=INK, width=max(2, lw // 2))
    elif mouth == "fv":
        d.rounded_rectangle(box(395, 540, 505, 585), 18 * s, fill=(110, 30, 40), outline=INK, width=lw)
        d.rectangle(box(405, 545, 495, 562), fill=(255, 255, 255))
    elif mouth == "grin":
        d.chord(box(375, 500, 525, 620), 0, 180, fill=(110, 30, 40), outline=INK, width=lw)
    elif mouth == "squiggle":
        d.line([P(395, 565), P(430, 550), P(470, 575), P(505, 555)], fill=INK, width=lw, joint="curve")
    out = im.resize((W, H), Image.LANCZOS)
    if bg == "white":
        flat = Image.new("RGB", out.size, (255, 255, 255))
        flat.paste(out, mask=out.getchannel("A"))
        return flat
    if bg == "checker":
        flat = Image.new("RGB", out.size, (255, 255, 255))
        dd = ImageDraw.Draw(flat)
        for y in range(0, H, 32):
            for x in range(0, W, 32):
                if (x // 32 + y // 32) % 2:
                    dd.rectangle([x, y, x + 31, y + 31], fill=(204, 204, 204))
        flat.paste(out, mask=out.getchannel("A"))
        return flat
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--clean", action="store_true", help="no drift / backgrounds (ideal assets)")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(7)

    def drift():
        if a.clean:
            return (1.0, 0, 0, 0)
        return (rnd.uniform(0.98, 1.02), rnd.uniform(-6, 6), rnd.uniform(-6, 6), rnd.randint(-4, 4))

    draw().save(out / "neutral.png")
    for shape in ("mbp", "half", "ah", "ee", "oh", "oo", "fv"):
        draw(mouth=shape, drift=drift()).save(out / f"mouth-{shape}.png")
    draw(eyes="closed", drift=drift()).save(out / "blink.png")
    draw(arm="point", drift=drift()).save(out / "pose-point.png")
    draw(arm="present", drift=drift()).save(out / "pose-present.png")
    draw(arm="wave", drift=drift(), bg=None if a.clean else "checker").save(out / "pose-wave.png")
    draw(eyes="happy", mouth="grin", drift=drift(), bg=None if a.clean else "white").save(out / "expr-happy.png")
    draw(eyes="wide", mouth="round", brows="up", drift=drift()).save(out / "expr-surprised.png")
    draw(brows="raised", mouth="squiggle", drift=drift()).save(out / "expr-confused.png")
    draw(eyes="up", arm="chin", mouth="closed", drift=drift()).save(out / "expr-thinking.png")
    (out / "LICENSE.txt").write_text("Pip, the open-explainer demo mascot, was drawn by tools/make_demo_mascot.py.\n"
                                     "It is part of open-explainer and is released under the MIT License.\n")
    print(f"wrote demo mascot images to {out}")


if __name__ == "__main__":
    main()
