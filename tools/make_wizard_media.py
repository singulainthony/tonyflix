#!/usr/bin/env python3
"""Draw the TonyFlix Wizard's screen artwork (resources/skins/Default/media).

The wizard's own screens must work under any skin (Estuary during first setup, TonyFlix later), and the only
font every skin has is `font13`. So headings and the wordmark are pre-rendered images; body text uses font13.

Usage: python3 tools/make_wizard_media.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "addons" / "skin.tonyflix" / "fonts"
OUT = ROOT / "addons" / "plugin.program.tonyflix.wizard" / "resources" / "skins" / "Default" / "media"
ACCENT = (245, 165, 36, 255)
WHITE = (255, 255, 255, 255)
SCALE = 4  # draw big, then downsample = smooth edges


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def text_image(text, fnt, fill, tracking=0, pad=8):
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    widths = [probe.textlength(ch, font=fnt) for ch in text]
    w = int(sum(widths) + tracking * (len(text) - 1)) + pad * 2
    asc, desc = fnt.getmetrics()
    im = Image.new("RGBA", (w, asc + desc + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = pad
    for ch, cw in zip(text, widths):
        d.text((x, pad), ch, font=fnt, fill=fill)
        x += cw + tracking
    l, _, r, _ = im.getbbox()
    return im.crop((l, 0, r, im.height))   # trim sides only: every heading keeps the same baseline


def rounded(size, radius, outline=0):
    big = Image.new("RGBA", (size * SCALE, size * SCALE), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    box = (0, 0, size * SCALE - 1, size * SCALE - 1)
    if outline:
        d.rounded_rectangle(box, radius * SCALE, outline=WHITE, width=outline * SCALE)
    else:
        d.rounded_rectangle(box, radius * SCALE, fill=WHITE)
    return big.resize((size, size), Image.LANCZOS)


def circle(size, check=False):
    big = Image.new("RGBA", (size * SCALE, size * SCALE), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    d.ellipse((0, 0, size * SCALE - 1, size * SCALE - 1), fill=WHITE)
    if check:
        s = size * SCALE
        d.line([(s * .28, s * .52), (s * .44, s * .68), (s * .74, s * .36)], fill=(0, 0, 0, 0), width=int(s * .1),
               joint="curve")
    return big.resize((size, size), Image.LANCZOS)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (8, 8), WHITE).save(OUT / "white.png")
    rounded(96, 22).save(OUT / "rounded.png")              # buttons, cards (9-slice border 28)
    rounded(96, 22, outline=4).save(OUT / "rounded_ring.png")  # focus ring
    circle(48, check=True).save(OUT / "check.png")
    circle(48).save(OUT / "dot.png")
    text_image("TONYFLIX", font("RobotoCondensed-Black.ttf", 84), ACCENT, tracking=12).save(OUT / "wordmark.png")
    heads = {
        "h_setup.png": "Set up TonyFlix",
        "h_progress.png": "Setting up TonyFlix",
        "h_accounts.png": "Accounts",
        "h_done.png": "You're all set",
    }
    for name, text in heads.items():
        text_image(text, font("RobotoCondensed-Bold.ttf", 96), WHITE).save(OUT / name)
    for p in sorted(OUT.iterdir()):
        with Image.open(p) as im:
            print(f"  {p.name:18s} {im.size[0]}x{im.size[1]}")


if __name__ == "__main__":
    main()
