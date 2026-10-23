"""Optical centring of glyphs in the monospace cell.

Every glyph of a monospace has the same advance, so spacing means placing each drawing in its
cell. Centring the bounding box is not enough: c, r, L and F have white space cut into one side
and look shifted away from it. Here the white space on each side is measured the way spacing
tools such as HT Letterspacer do: the area between the cell edge and the glyph's profile, row by
row across the x-height (capital height for capitals and figures), with each row's depth capped
so that a deep counter (the aperture of c) does not count in full. The glyph moves sideways until
both areas match, damped and limited, since the eye only partly follows the measurement.
"""
import numpy as np
from fontTools.pens.basePen import BasePen
from PIL import Image, ImageDraw

import build as b

DEPTH = 110          # deepest white a row contributes, in units
DAMPING = 0.6        # share of the measured imbalance that is corrected
LIMIT = 30           # largest shift, in units


class _Polys(BasePen):
    def __init__(self, glyphset):
        super().__init__(glyphset)
        self.polys = []

    def _moveTo(self, p):
        self.polys.append([p])

    def _lineTo(self, p):
        self.polys[-1].append(p)

    def _curveToOne(self, c1, c2, p):
        p0 = self.polys[-1][-1]
        for i in range(1, 13):
            t = i / 12
            u = 1 - t
            self.polys[-1].append((u ** 3 * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * p[0],
                                   u ** 3 * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * p[1]))


def _mask(glyph, font, top):
    """Ink mask of the glyph between the baseline and `top`, one pixel per 2 units."""
    pen = _Polys(font)
    glyph.draw(pen)
    w, h = b.ADV // 2 + 200, top // 2 + 1
    img = Image.new("1", (w, h), 0)
    for poly in pen.polys:
        layer = Image.new("1", (w, h), 0)
        ImageDraw.Draw(layer).polygon([(x / 2 + 100, (top - y) / 2) for x, y in poly], fill=1)
        img = Image.fromarray(np.logical_xor(np.array(img), np.array(layer)))
    return np.array(img)


def shift(glyph, font, top):
    """Sideways move (units) that balances the white on both sides of the glyph."""
    ink = _mask(glyph, font, top)
    rows = ink.any(axis=1)
    if rows.sum() < 4:
        return 0
    cols = np.where(ink.any(axis=0))[0]
    x0, x1 = cols[0], cols[-1]
    depth = DEPTH / 2
    left = right = 0.0
    for row in ink:
        xs = np.where(row)[0]
        if len(xs):
            left += min(xs[0] - x0, depth)
            right += min(x1 - xs[-1], depth)
        else:
            left += depth
            right += depth
    n = len(ink)
    sb_left, sb_right = (x0 - 100) * 2, (b.ADV // 2 + 100 - 1 - x1) * 2
    white_left, white_right = sb_left + 2 * left / n, sb_right + 2 * right / n
    move = DAMPING * (white_right - white_left) / 2
    move = round(max(-LIMIT, min(LIMIT, move)))
    return move if abs(move) > 2 else 0          # symmetric glyphs measure +-1 from rasterising


# narrow letters whose serifs, tails and dots were placed by hand (i, l and 1 kept apart, their
# stems in line with each other): they stay where they are drawn
FIXED = {"i", "dotlessi", "j", "uni0237", "l", "one", "ij", "IJ", "ldot", "lslash", "longs"}


def centring(font):
    """{glyph name: sideways move} for the letters and figures."""
    import unicodedata
    names = list(b.G) + list(b.LC) + list(b.DIG) + list(b.ALT)
    names += [n for n in b.NEW if unicodedata.category(chr(b.NAME_TO_CP[n]))[0] == "L"]
    out = {}
    for n in names:
        if n in FIXED or n in b.MARK_GLYPHS or n not in font:
            continue
        lower = n in b.LC or n in b.ALT or (n in b.NEW and chr(b.NAME_TO_CP[n]).islower())
        s = shift(font[n], font, b.XH if lower else b.CAP)
        if s:
            out[n] = s
    return out
