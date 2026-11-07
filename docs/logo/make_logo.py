#!/usr/bin/env python3
"""Draws the GoldScout logo: a gold coin stamped with a G, under a magnifying
glass. Pure Pillow shapes (no fonts or outside art), drawn at 4x and scaled
down for smooth edges.

  python docs/logo/make_logo.py      writes goldscout-logo-1024.png and -400.png
"""
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
S = 4096  # working size; the final image is 1024


def radial(size, inner, outer, center=(0.5, 0.5), radius=0.75):
    """A radial gradient image from inner color (at center) to outer."""
    w, h = size
    small = Image.new("RGB", (256, 256))
    px = small.load()
    cx, cy = center[0] * 256, center[1] * 256
    for y in range(256):
        for x in range(256):
            t = min(1.0, math.hypot(x - cx, y - cy) / (radius * 256))
            px[x, y] = tuple(int(inner[i] + (outer[i] - inner[i]) * t) for i in range(3))
    return small.resize((w, h), Image.BICUBIC)


def linear(size, top, bottom, angle=0.0):
    """A linear gradient, rotated by angle degrees."""
    small = Image.new("RGB", (256, 256))
    px = small.load()
    ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    for y in range(256):
        for x in range(256):
            t = ((x - 128) * sa + (y - 128) * ca) / 256 + 0.5
            t = min(1.0, max(0.0, t))
            px[x, y] = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
    return small.resize(size, Image.BICUBIC)


def circle_mask(size, box, width=None):
    mask = Image.new("L", size, 0)
    d = ImageDraw.Draw(mask)
    if width:
        d.ellipse(box, outline=255, width=width)
    else:
        d.ellipse(box, fill=255)
    return mask


def paste(base, fill, mask):
    if isinstance(fill, tuple):
        fill = Image.new("RGBA", base.size, fill + (255,) if len(fill) == 3 else fill)
    elif fill.mode != "RGBA":
        fill = fill.convert("RGBA")
    base.paste(fill, (0, 0), mask)


def main():
    size = (S, S)
    img = Image.new("RGBA", size, (0, 0, 0, 0))

    # Background: rounded square, deep teal night.
    bg_mask = Image.new("L", size, 0)
    ImageDraw.Draw(bg_mask).rounded_rectangle((0, 0, S - 1, S - 1), radius=int(S * 0.2), fill=255)
    paste(img, radial(size, (26, 72, 88), (6, 20, 30), center=(0.42, 0.38), radius=0.8), bg_mask)

    # Coin geometry.
    cx, cy, r = int(S * 0.43), int(S * 0.43), int(S * 0.30)
    coin_box = (cx - r, cy - r, cx + r, cy + r)

    # Soft shadow under the coin.
    shadow = circle_mask(size, (cx - r + 60, cy - r + 140, cx + r + 60, cy + r + 140))
    shadow = shadow.filter(ImageFilter.GaussianBlur(90))
    paste(img, (0, 0, 0, 150), ImageChops.multiply(shadow, bg_mask))

    # Coin body, rim and face.
    paste(img, linear(size, (255, 222, 120), (176, 116, 28), angle=-25), circle_mask(size, coin_box))
    rim = int(r * 0.13)
    face = (cx - r + rim, cy - r + rim, cx + r - rim, cy + r - rim)
    paste(img, linear(size, (196, 132, 34), (255, 214, 110), angle=-25), circle_mask(size, face))
    inner = int(r * 0.05)
    face2 = (face[0] + inner, face[1] + inner, face[2] - inner, face[3] - inner)
    paste(img, linear(size, (250, 208, 100), (205, 140, 40), angle=-25), circle_mask(size, face2))

    # Stamped G: a thick arc open to the right, with a crossbar.
    g_r = int(r * 0.52)
    g_w = int(r * 0.17)
    g_box = (cx - g_r, cy - g_r, cx + g_r, cy + g_r)
    g_mask = Image.new("L", size, 0)
    gd = ImageDraw.Draw(g_mask)
    gd.arc(g_box, start=40, end=330, fill=255, width=g_w)
    bar_y0, bar_y1 = cy - int(g_w * 0.12), cy + int(g_w * 0.88)
    gd.rectangle((cx + int(g_r * 0.02), bar_y0, cx + g_r, bar_y1), fill=255)
    gd.rectangle((cx + g_r - g_w, bar_y0, cx + g_r, cy + int(g_r * 0.62)), fill=255)
    # Engraved look: dark offset below-right, light face on top.
    paste(img, (120, 70, 10, 255), ImageChops.offset(g_mask, int(S * 0.006), int(S * 0.008)))
    paste(img, linear(size, (255, 236, 160), (226, 166, 56), angle=-25), g_mask)

    # Magnifying glass over the lower right of the coin.
    lx, ly, lr = int(S * 0.64), int(S * 0.62), int(S * 0.18)
    ring_w = int(lr * 0.24)
    lens_box = (lx - lr, ly - lr, lx + lr, ly + lr)

    # Handle: from the lens toward the bottom-right corner.
    ang = math.radians(45)
    hx0, hy0 = lx + math.cos(ang) * (lr + ring_w * 0.2), ly + math.sin(ang) * (lr + ring_w * 0.2)
    hx1, hy1 = lx + math.cos(ang) * (lr * 1.98), ly + math.sin(ang) * (lr * 1.98)
    handle = Image.new("L", size, 0)
    ImageDraw.Draw(handle).line((hx0, hy0, hx1, hy1), fill=255, width=int(lr * 0.42))
    ImageDraw.Draw(handle).ellipse((hx1 - lr * 0.21, hy1 - lr * 0.21, hx1 + lr * 0.21, hy1 + lr * 0.21), fill=255)
    hshadow = ImageChops.offset(handle, 40, 70).filter(ImageFilter.GaussianBlur(40))
    paste(img, (0, 0, 0, 140), ImageChops.multiply(hshadow, bg_mask))
    paste(img, linear(size, (110, 66, 34), (58, 32, 14), angle=45), handle)
    collar = Image.new("L", size, 0)
    cx0, cy0 = lx + math.cos(ang) * (lr * 1.18), ly + math.sin(ang) * (lr * 1.18)
    cx1, cy1 = lx + math.cos(ang) * (lr * 1.42), ly + math.sin(ang) * (lr * 1.42)
    ImageDraw.Draw(collar).line((cx0, cy0, cx1, cy1), fill=255, width=int(lr * 0.5))
    paste(img, linear(size, (236, 242, 246), (140, 156, 168), angle=45), collar)

    # Glass: a cool tint over whatever is beneath, plus a highlight.
    glass = circle_mask(size, lens_box)
    tint = Image.new("RGBA", size, (150, 220, 255, 70))
    img.alpha_composite(Image.composite(tint, Image.new("RGBA", size, (0, 0, 0, 0)), glass))
    shine = Image.new("L", size, 0)
    ImageDraw.Draw(shine).arc((lx - lr * 0.72, ly - lr * 0.72, lx + lr * 0.72, ly + lr * 0.72),
                              start=200, end=262, fill=255, width=int(lr * 0.13))
    paste(img, (255, 255, 255, 255), shine.filter(ImageFilter.GaussianBlur(6)))

    # Lens ring: shadow, then steel.
    ring = circle_mask(size, lens_box, width=ring_w)
    rshadow = ImageChops.offset(ring, 30, 50).filter(ImageFilter.GaussianBlur(30))
    paste(img, (0, 0, 0, 120), rshadow)
    paste(img, linear(size, (248, 250, 252), (128, 146, 160), angle=-30), ring)
    inner_ring = circle_mask(size, (lx - lr + ring_w - 18, ly - lr + ring_w - 18,
                                    lx + lr - ring_w + 18, ly + lr - ring_w + 18), width=26)
    paste(img, (70, 86, 98, 255), inner_ring)

    # A sparkle on the coin's upper left.
    sx, sy, sr = int(cx - r * 0.55), int(cy - r * 0.62), int(r * 0.16)
    sparkle = Image.new("L", size, 0)
    sd = ImageDraw.Draw(sparkle)
    sd.polygon([(sx, sy - sr), (sx + sr * 0.18, sy - sr * 0.18), (sx + sr, sy), (sx + sr * 0.18, sy + sr * 0.18),
                (sx, sy + sr), (sx - sr * 0.18, sy + sr * 0.18), (sx - sr, sy), (sx - sr * 0.18, sy - sr * 0.18)],
               fill=255)
    paste(img, (255, 250, 225, 255), sparkle)

    # Clip everything to the rounded square and scale down.
    final = Image.new("RGBA", size, (0, 0, 0, 0))
    final.paste(img, (0, 0), bg_mask)
    for px in (1024, 400):
        final.resize((px, px), Image.LANCZOS).save(HERE / ("goldscout-logo-%d.png" % px))
    print("Wrote", HERE / "goldscout-logo-1024.png")


if __name__ == "__main__":
    main()
