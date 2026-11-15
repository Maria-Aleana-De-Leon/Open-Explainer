"""Visual styles. A style is data: colours, fonts, shape radii and default motion. Add one by adding a dict."""
from __future__ import annotations

from pathlib import Path

FONT_DIR = Path(__file__).parent / "assets" / "fonts"
FONTS = {
    "regular": FONT_DIR / "Poppins-Regular.ttf",
    "medium": FONT_DIR / "Poppins-Medium.ttf",
    "bold": FONT_DIR / "Poppins-Bold.ttf",
}

STYLES: dict[str, dict] = {
    "paper": {  # warm light, editorial
        "bg": "#F6F1E7", "bg2": "#EFE7D8", "ink": "#1E1B16", "muted": "#6B6459", "accent": "#E4572E",
        "accent2": "#2E86AB", "card": "#FFFFFF", "card_ink": "#1E1B16", "line": "#D9CFBE", "marker": "#F2C14E", "good": "#2F8F5B", "bad": "#C8372D",
        "radius": 28, "decor": "dots", "transition": "slide", "camera": "push",
    },
    "midnight": {  # dark, technical
        "bg": "#0E1726", "bg2": "#14213A", "ink": "#F2F5FA", "muted": "#9AA8BF", "accent": "#3DDC97",
        "accent2": "#5AA9FF", "card": "#1B2A45", "card_ink": "#F2F5FA", "line": "#2A3B5C", "marker": "#2F6FD0", "good": "#4FD18B", "bad": "#FF6B6B",
        "radius": 24, "decor": "grid", "transition": "fade", "camera": "push",
    },
    "chalk": {  # classroom board
        "bg": "#1F3B2D", "bg2": "#24443A", "ink": "#F4F1E8", "muted": "#B9C4B5", "accent": "#FFD166",
        "accent2": "#F78C6B", "card": "#2A4D3F", "card_ink": "#F4F1E8", "line": "#3E6352", "marker": "#B5733F", "good": "#A6E08A", "bad": "#FF8A80",
        "radius": 16, "decor": "none", "transition": "wipe", "camera": "still",
    },
    "white": {  # pure white, nothing behind text: plain labels and captions, no pills or boxes
        "bg": "#FFFFFF", "bg2": "#F1F3F6", "ink": "#121826", "muted": "#5B6474", "accent": "#0E9F6E",
        "accent2": "#2563EB", "card": "#FFFFFF", "card_ink": "#121826", "line": "#D5DAE1", "marker": "#FDE68A",
        "good": "#16A34A", "bad": "#DC2626",
        "radius": 24, "decor": "none", "transition": "fade", "camera": "still", "boxes": False,
    },
    "pop": {  # bright, short-form
        "bg": "#FFE14D", "bg2": "#FFD60A", "ink": "#111111", "muted": "#3D3D3D", "accent": "#FF3D7F",
        "accent2": "#2B59FF", "card": "#FFFFFF", "card_ink": "#111111", "line": "#111111", "marker": "#FFFFFF", "good": "#11804A", "bad": "#D7261E",
        "radius": 36, "decor": "circles", "transition": "zoom", "camera": "push",
    },
}


COLOUR_KEYS = ("bg", "bg2", "ink", "muted", "accent", "accent2", "card", "card_ink", "line", "marker", "good", "bad")


def get(name: str, accent: str | None = None, colors: dict | None = None) -> dict:
    """A style, with the project's `accent` and any `colors` overrides (for example a brand palette, or the
    success colour `good`) applied on top."""
    s = dict(STYLES[name])
    if accent:
        s["accent"] = accent
    s.update(colors or {})
    return s


def rgb(hex_: str) -> tuple[int, int, int]:
    h = hex_.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
