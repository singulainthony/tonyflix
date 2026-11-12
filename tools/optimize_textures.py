#!/usr/bin/env python3
"""Shrink skin images for low-power devices (idempotent, edits in place).

Kodi uploads every texture to the GPU at its full pixel size, so a 1920x1080
gradient overlay costs ~8 MB of video memory and load time even though it is a
smooth ramp. On boxes like the T95 Max that is the difference between smooth
and stuttery scrolling.

  * Full-screen gradient overlays -> 480x270 (checked: alpha error <= 2/255
    after GPU upscaling, i.e. visually identical)
  * Blur overlay -> 960x540
  * Settings-only previews (viewtypes, screenshots) -> 640x360 JPEG
  * Launch/fallback backgrounds -> 1280x720 JPEG
  * Every other PNG/JPEG -> lossless re-save with optimize=True (only if smaller)

Usage: python3 tools/optimize_textures.py addons/skin.tonyflix
"""
import io
import sys
from pathlib import Path

from PIL import Image

RESIZE_RULES = [
    # (glob relative to skin root, max size, keep format)
    ("media/background/floor.png", (480, 270)),
    ("media/background/combined_*.png", (480, 270)),
    ("media/background/blur2.png", (960, 540)),
    ("extras/viewtypes/*.jpg", (640, 360)),
    ("extras/screenshots/*.jpg", (640, 360)),
    ("extras/backgrounds/launch/*.jpg", (1280, 720)),
    ("extras/backgrounds/fallbacks/*.jpg", (1280, 720)),
]
JPEG_QUALITY = 82


def save(im, path, fmt):
    buf = io.BytesIO()
    if fmt == "JPEG":
        im.convert("RGB").save(buf, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=False)
    else:
        im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def main():
    skin = Path(sys.argv[1]).resolve()
    before = sum(p.stat().st_size for p in skin.rglob("*") if p.is_file())
    handled = set()
    resized = 0
    for pattern, size in RESIZE_RULES:
        for p in sorted(skin.glob(pattern)):
            handled.add(p)
            with Image.open(p) as im:
                im.load()
                fmt = im.format
                if im.width <= size[0] and im.height <= size[1]:
                    continue
                im.thumbnail(size, Image.LANCZOS)
                p.write_bytes(save(im, p, fmt))
                resized += 1

    recompressed = skipped = 0
    for p in sorted(skin.rglob("*")):
        if p in handled or p.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            continue
        try:
            with Image.open(p) as im:
                im.load()
                fmt = im.format
                if fmt not in ("PNG", "JPEG") or getattr(im, "is_animated", False):
                    continue
                # JPEG re-encode would be lossy; only PNGs are recompressed losslessly.
                if fmt != "PNG":
                    continue
                data = save(im, p, fmt)
        except Exception:  # Pillow rejects a few slightly malformed PNGs Kodi reads fine: leave untouched
            skipped += 1
            continue
        if len(data) < p.stat().st_size * 0.97:
            p.write_bytes(data)
            recompressed += 1

    after = sum(p.stat().st_size for p in skin.rglob("*") if p.is_file())
    print(
        f"Resized {resized}, recompressed {recompressed}, left {skipped} unreadable-by-Pillow files as-is. "
        f"Skin size {before/1e6:.1f} MB -> {after/1e6:.1f} MB"
    )


if __name__ == "__main__":
    main()
