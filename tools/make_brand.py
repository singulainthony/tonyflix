#!/usr/bin/env python3
"""Generate placeholder TonyFlix icon.png (512x512) and fanart.jpg (1280x720)
for every TonyFlix add-on. Replace with real artwork whenever you like; just
keep the same file names and sizes.

Usage: python3 tools/make_brand.py
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / "addons" / "skin.tonyflix" / "fonts" / "RobotoCondensed-Black.ttf"
BG = (14, 14, 16)
ACCENT = (245, 165, 36)  # amber, deliberately not any streaming service's brand colour
SUBTITLES = {
    "skin.tonyflix": "SKIN",
    "repository.tonyflix": "REPOSITORY",
    "plugin.program.tonyflix.wizard": "WIZARD",
    "service.tonyflix.maintenance": "MAINTENANCE",
}


def font(size):
    return ImageFont.truetype(str(FONT), size)


def centered(draw, box_w, y, text, fnt, fill):
    w = draw.textlength(text, font=fnt)
    draw.text(((box_w - w) / 2, y), text, font=fnt, fill=fill)


def icon(sub):
    im = Image.new("RGB", (512, 512), BG)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((36, 36, 476, 476), radius=72, outline=ACCENT, width=10)
    centered(d, 512, 70, "T", font(300), ACCENT)
    centered(d, 512, 372, "TONYFLIX", font(64), (235, 235, 235))
    if sub:
        centered(d, 512, 438, sub, font(26), ACCENT)
    return im


def fanart():
    im = Image.new("RGB", (1280, 720), BG)
    d = ImageDraw.Draw(im)
    for i in range(720):  # subtle vertical vignette
        shade = int(10 + 18 * (1 - abs(i - 360) / 360))
        d.line([(0, i), (1280, i)], fill=(shade, shade, shade + 2))
    centered(d, 1280, 250, "TONYFLIX", font(180), ACCENT)
    centered(d, 1280, 470, "MOVIES  ·  TV SHOWS", font(40), (200, 200, 200))
    return im


def main():
    name = json.loads((ROOT / "tools" / "config.json").read_text())["build_name"]
    assert name == "TonyFlix", "update make_brand.py text if you rename the build"
    for folder in sorted((ROOT / "addons").iterdir()):
        if not (folder / "addon.xml").is_file():
            continue
        icon(SUBTITLES.get(folder.name, "")).save(folder / "icon.png", optimize=True)
        fanart().save(folder / "fanart.jpg", quality=85, optimize=True)
        print(f"  {folder.name}: icon.png, fanart.jpg")


if __name__ == "__main__":
    main()
