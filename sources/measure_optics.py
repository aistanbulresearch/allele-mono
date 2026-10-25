"""Measure optical corrections of monospace fonts: overshoot, stroke contrast, joins, widths, colour.

Usage: python3 sources/measure_optics.py FONT.ttf [OTHER.ttf ...]   (prints a Markdown table)
Variable fonts are measured at wght 400. Values are font units at 1000 UPM (1 px = 1 unit).
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = 1300          # baseline row of the render canvas


def runs(line):
    """Lengths of the ink runs along a row or column."""
    out, n = [], 0
    for v in line:
        if v:
            n += 1
        elif n:
            out.append(n)
            n = 0
    if n:
        out.append(n)
    return out


def glyph(font, ch):
    """Ink mask of one character, and its ink bounds (x0, x1, y0, y1) on the canvas."""
    img = Image.new("L", (1600, 1800), 0)
    ImageDraw.Draw(img).text((300, BASE), ch, font=font, fill=255, anchor="ls")
    a = np.array(img) > 127
    ys, xs = np.nonzero(a)
    return a, xs.min(), xs.max(), ys.min(), ys.max()


def ink(font, ch):
    img = Image.new("L", (500, 700), 0)
    ImageDraw.Draw(img).text((50, 50), ch, font=font, fill=255)
    return np.asarray(img, float).sum() / 255


def load(path, size):
    f = ImageFont.truetype(path, size)
    try:
        f.set_variation_by_axes([400])
    except OSError:
        pass                                   # not a variable font
    return f


def measure(path):
    f, small = load(path, 1000), load(path, 400)
    a, x0, x1, y0, y1 = glyph(f, "H")
    cap = BASE - y0
    stem = runs(a[BASE - int(cap * 0.25), :])[0]
    bar = runs(a[:, (x0 + x1) // 2])[0]
    h_width, h_top, h_bottom = x1 - x0 + 1, y0, y1
    _, _, _, y0, y1 = glyph(f, "O")
    o_cap = ((h_top - y0) + (y1 - h_bottom)) / 2
    a, x0, x1, y0, y1 = glyph(f, "o")
    side = runs(a[(y0 + y1) // 2, :])[0]
    top = runs(a[:, (x0 + x1) // 2])[0]
    o_width, o_top, o_bottom = x1 - x0 + 1, y0, y1
    _, _, _, x_top, x_bottom = glyph(f, "x")
    o_lower = ((x_top - o_top) + (o_bottom - x_bottom)) / 2
    a, x0, x1, y0, y1 = glyph(f, "n")
    xh = BASE - y0
    row = a[BASE - int(xh * 0.25), :]
    n_stem = runs(row)[0]
    inside = np.nonzero(row)[0][0] + n_stem + 6           # just right of the left stem
    col = a[:, inside]
    join = runs(col[np.nonzero(col)[0][0]:])[0]          # shoulder thickness there
    a, *_ = glyph(f, "m")
    m_stem = runs(a[BASE - int(xh * 0.25), :])[0]
    colour = np.array([ink(small, c) for c in "abcdefghijklmnopqrstuvwxyz"])
    return [f"{o_cap:.0f}", f"{o_lower:.0f}", f"{bar / stem:.2f}", f"{top / side:.2f}", str(m_stem),
            f"{join / n_stem:.2f}", str(h_width), str(o_width), f"{colour.std() / colour.mean():.3f}"]


if __name__ == "__main__":
    print("| font | O os | o os | H bar/stem | o top/side | m stem | n join/stem | H w | o w | lc evenness (CV) |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for p in sys.argv[1:]:
        print("| " + " | ".join([os.path.splitext(os.path.basename(p))[0]] + measure(p)) + " |")
