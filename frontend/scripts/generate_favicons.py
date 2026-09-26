"""Generate CAOS Care favicons from one geometry (source of truth: public/favicon.svg).

Mark: the "C" of the CAOS wordmark (Outfit is geometric, its C is a near-circle)
in bone #F7F6F2 on a forest #153428 rounded square - the wordmark's own colours.
Drawn geometrically (no font dependency) and supersampled so 16x16 stays crisp.

Run from frontend/:  python3 scripts/generate_favicons.py
Writes: public/favicon.ico (16, 32, 48), public/apple-touch-icon.png (180).
"""
import math
import os

from PIL import Image, ImageDraw

FOREST, BONE = (0x15, 0x34, 0x28, 255), (0xF7, 0xF6, 0xF2, 255)
# Geometry on a 100-unit canvas - keep in sync with public/favicon.svg
CORNER, CX, CY, R, STROKE, GAP_DEG = 22, 50, 50, 26, 14, 42
SS = 8  # supersampling factor
PUBLIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public")


def render(size, corner=True):
    n = size * SS
    u = n / 100.0
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if corner:
        d.rounded_rectangle([0, 0, n - 1, n - 1], radius=CORNER * u, fill=FOREST)
    else:
        d.rectangle([0, 0, n - 1, n - 1], fill=FOREST)   # iOS masks its own corners
    outer = (R + STROKE / 2) * u
    box = [CX * u - outer, CY * u - outer, CX * u + outer, CY * u + outer]
    # PIL arcs run clockwise from 3 o'clock: GAP..360-GAP leaves the C open on the right
    d.arc(box, GAP_DEG, 360 - GAP_DEG, fill=BONE, width=round(STROKE * u))
    return img.resize((size, size), Image.LANCZOS)


def main():
    icons = [render(s) for s in (16, 32, 48)]
    icons[-1].save(os.path.join(PUBLIC, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)],
                   append_images=icons[:-1])
    render(180, corner=False).convert("RGB").save(os.path.join(PUBLIC, "apple-touch-icon.png"))


if __name__ == "__main__":
    main()
