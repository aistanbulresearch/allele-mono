"""Allele Mono (draft): monospace prototype tuned for nucleotide and amino-acid letters.

Glyphs are defined as centre-line skeletons, expanded to outlines with shapely
(square caps, then clipped to the glyph's vertical zone so stems sit exactly on
the baseline and cap/x-height), and written as a TrueType font with fontTools.
Accented letters are TrueType composites (base + accent components).

Prototype only: outlines are polygonal (no curves) and unhinted, so this is for
testing shapes, not for release.
"""
import math
import sys

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from shapely.geometry import LineString, MultiPolygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

FAMILY = "Allele Mono"
DESIGNER = "Ozge A. Cavus - AIstanbul Research Group"
REPO_URL = "https://github.com/aistanbulresearch/allele-mono"
PSNAME = "AlleleMono-Regular"
VERSION = "1.002"
COPYRIGHT = f"Copyright 2026 The Allele Mono Project Authors ({REPO_URL})"

UPM = 1000
ADV = 600
STROKE = 84
HS = STROKE / 2
CAP = 700
XH = 520
ASC = 740
DESC = -220
L, R, M = 130, 470, 300
B, T, MID = HS, CAP - HS, CAP / 2
XT = XH - HS                 # lowercase x-height skeleton line
AT = ASC - HS                # ascender skeleton line
DT = DESC + HS               # descender skeleton line
XM = (B + XT) / 2            # lowercase vertical centre
XRY = (XT - B) / 2           # lowercase round half-height

# ---------------------------------------------------------------- optical corrections (applied by ufo_build.py)
# The skeletons are drawn for one constant pen; these make the expanded strokes look even.
# The polygon prototype (build() below) ignores them, so the search scripts still see a monoline.
H_RATIO = 0.88               # horizontal strokes / vertical stems (JetBrains 0.91, Plex 0.87, Fira 0.82)
DIAG_THIN = 0.05             # 45-degree strokes lose this much more weight
OVERSHOOT = 11               # round strokes pass the guide lines by this much (references 8 to 12)
GUIDES = (0, XH, CAP, ASC, DESC)
TENSION_OUT = 0.58           # Bezier handle / radius of outer curves (a true ellipse is 0.552)
TENSION_IN = 0.62            # counters squarer still, so they do not look pinched
JOIN_THIN = 0.38             # a curve leaving a stem drops to 62% weight at the join (n, b, d, a, r)
JOIN_REACH = 110             # ... fading out over this distance from the stem's centre line
TAPER = 0.30                 # diagonals taper to lose this share of their inner half-width at a sharp vertex
TAPER_ANGLE = 80             # vertices sharper than this (degrees) taper: v w A V W M N Z 4 7
TAPER_BUTT = 0.16            # diagonals ending on another stroke (k K R y) thin on both sides
SQUARE_TERMINALS = {"at"}    # curve ends cut square to the stroke, not across: the tail of @ runs into its hook
WEIGHT = {"m": 0.90, "M": 0.94, "W": 0.93, "w": 0.93, "AE": 0.94, "OE": 0.94, "at": 0.94, "numbersign": 0.94}    # crowded glyphs are lightened to keep an even colour


class ArcSeg:
    """An elliptical arc kept as geometry, so it can become a true Bezier curve.

    Angles in degrees, counter-clockwise from +x (y up). sample() reproduces the
    polyline the prototype used, so the shapely path stays bit-for-bit the same.
    """
    __slots__ = ("cx", "cy", "rx", "ry", "a0", "a1", "skip_first")

    def __init__(self, cx, cy, rx, ry, a0, a1, skip_first=False):
        self.cx, self.cy, self.rx, self.ry, self.a0, self.a1 = cx, cy, rx, ry, a0, a1
        self.skip_first = skip_first

    def point(self, a):
        return (self.cx + self.rx * math.cos(math.radians(a)), self.cy + self.ry * math.sin(math.radians(a)))

    def sample(self, step=4):
        n = max(8, int(abs(self.a1 - self.a0) / step))
        return [self.point(self.a0 + (self.a1 - self.a0) * i / n) for i in range(n + 1)]

    def rotated(self, cy0):
        return ArcSeg(2 * M - self.cx, 2 * cy0 - self.cy, self.rx, self.ry, self.a0 + 180, self.a1 + 180,
                      self.skip_first)

    def mirrored(self):
        return ArcSeg(2 * M - self.cx, self.cy, self.rx, self.ry, 180 - self.a0, 180 - self.a1, self.skip_first)

    def beziers(self):
        """Cubic Bezier approximation, split into pieces of at most 90 degrees."""
        total = self.a1 - self.a0
        n = max(1, math.ceil(abs(total) / 90 - 1e-9))
        out = []
        for i in range(n):
            t0 = math.radians(self.a0 + total * i / n)
            t1 = math.radians(self.a0 + total * (i + 1) / n)
            k = 4 / 3 * math.tan((t1 - t0) / 4)
            p0 = (self.cx + self.rx * math.cos(t0), self.cy + self.ry * math.sin(t0))
            p3 = (self.cx + self.rx * math.cos(t1), self.cy + self.ry * math.sin(t1))
            c1 = (p0[0] - k * self.rx * math.sin(t0), p0[1] + k * self.ry * math.cos(t0))
            c2 = (p3[0] + k * self.rx * math.sin(t1), p3[1] - k * self.ry * math.cos(t1))
            out.append((c1, c2, p3))
        return out


class ArcList(list):
    """arc(...)[1:] meant 'drop the duplicated first point'; keep the arc, flag it."""

    def __getitem__(self, i):
        if isinstance(i, slice) and i == slice(1, None, None):
            return ArcList([ArcSeg(s.cx, s.cy, s.rx, s.ry, s.a0, s.a1, True) for s in self])
        return list.__getitem__(self, i)


def arc(cx, cy, rx, ry, a0, a1):
    return ArcList([ArcSeg(cx, cy, rx, ry, a0, a1)])


class DotSeg:
    """A square dot of side `size` centred on (x, y): tittles, periods, the dots of accents."""
    __slots__ = ("x", "y", "size")

    def __init__(self, x, y, size):
        self.x, self.y, self.size = x, y, size


def dot(x, y, size):
    return [[DotSeg(x, y, size)]]


DOT_I = 124                  # tittle of i and j: large, so i and dotless i stay apart at small sizes
DOT_ACCENT = 112             # dot accent
DOT_DIERESIS = 104
DOT_PUNCT = 104              # period, colon: a little over the stem weight, so they look as heavy


def P(*pts):
    return [list(pts)]


def chain(*parts):
    out = []
    for p in parts:
        if out and out[-1] == p[0]:
            out.extend(p[1:])
        else:
            out.extend(p)
    return [out]


def mirror(strokes):
    return [[it.mirrored() if isinstance(it, ArcSeg) else DotSeg(2 * M - it.x, it.y, it.size)
             if isinstance(it, DotSeg) else (2 * M - it[0], it[1]) for it in s] for s in strokes]


def sample(stroke):
    """Stroke (points and ArcSegs) -> polyline, exactly as the prototype sampled it."""
    out = []
    for it in stroke:
        if isinstance(it, DotSeg):
            return [(it.x, it.y)]
        if isinstance(it, ArcSeg):
            pts = it.sample()
            if it.skip_first or (out and out[-1] == pts[0]):
                pts = pts[1:]
            out.extend(pts)
        else:
            out.append(it)
    return out


RX, RY = R - M, (T - B) / 2

# ---------------------------------------------------------------- uppercase
H_IN, N_OUT = 20, 28         # H stems pulled in, N pushed out: N-H stays apart (blurred-pair search), widths near O
G = {
    "A": P((L, B), (M, T), (R, B)) + P((L + 58, 230), (R - 58, 230)),
    "B": P((L, B), (L, T)) + chain([(L, T), (320, T)], arc(320, 518, 140, 140, 90, -90), [(320, 378), (L, 378)])
         + chain([(L, 378), (330, 378)], arc(330, 210, 140, 168, 90, -90), [(330, B), (L, B)]),
    # C: wide open aperture
    "C": [arc(M, MID, RX, RY, 48, 312)],
    # G: short bar (to x=330) and a straight spur down the right side to the baseline.
    # A longer bar closed the lower bowl and read as 6 at 12 px (seen by eye; the metric missed it).
    "G": chain(arc(M, MID, RX, RY, 55, 345), [(R, 270), (R, 340), (330, 340)]) + P((R, 340), (R, B)),
    # D: short shoulders and a wide bowl (search result, separates it from G)
    "D": P((L, B), (L, T)) + chain([(L, T), (200, T)], arc(200, MID, 270, RY, 90, -90), [(200, B), (L, B)]),
    "E": P((R, T), (L, T), (L, B), (R, B)) + P((L, MID), (R - 40, MID)),
    # F: short arms and a lower middle arm (measured: separates it from P, E and T)
    "F": P((420, T), (L, T), (L, B)) + P((L, 300), (340, 300)),
    # H: standard crossbar, stems pulled in by H_IN (pulled in by 45 it separated best from N, but it was
    # 90 units narrower than O and broke the rhythm of capital sequences; a low bar read like h)
    "H": P((L + H_IN, B), (L + H_IN, T)) + P((R - H_IN, B), (R - H_IN, T)) + P((L + H_IN, MID), (R - H_IN, MID)),
    "I": P((L + 40, T), (R - 40, T)) + P((M, T), (M, B)) + P((L + 40, B), (R - 40, B)),
    "J": chain([(L + 60, T), (R, T), (R, 220)], arc(M, 220, RX, 220 - B, 0, -180)),
    "K": P((L, B), (L, T)) + P((R, T), (L + 10, 300)) + P((250, 420), (R, B)),
    "L": P((L, T), (L, B), (R, B)),
    # M: shallow vertex (470); a deep vertex was measured to collide with W
    "M": P((L, B), (L, T), (M, 470), (R, T), (R, B)),
    "N": P((L - N_OUT, B), (L - N_OUT, T), (R + N_OUT, B), (R + N_OUT, T)),  # wider than H: larger open triangles
    "O": [arc(M, MID, RX, RY, 0, 360)],
    "P": P((L, B), (L, T)) + chain([(L, T), (310, T)], arc(310, 500, 160, 158, 90, -90), [(310, 342), (L, 342)]),
    # Q: tail drops from the bottom centre and turns right (measured best against O, G and D)
    "Q": [arc(M, MID, RX, RY, 0, 360)] + P((M, 30), (M, -60), (500, -60)),
    "R": P((L, B), (L, T)) + chain([(L, T), (310, T)], arc(310, 500, 160, 158, 90, -90), [(310, 342), (L, 342)])
         + P((290, 342), (R, B)),
    # S: lower terminal kept short (-140) so the silhouette separates from G
    "S": [arc(M, 512, 157, 146, 20, 270) + arc(M, 204, 172, 162, 90, -140)[1:]],   # top bowl smaller
    "T": P((L, T), (R, T)) + P((M, T), (M, B)),
    "U": chain([(L, T), (L, 230)], arc(M, 230, RX, 230 - B, 180, 360), [(R, 230), (R, T)]),
    "V": P((L, T), (M, B), (R, T)),
    # W: low middle vertex (300) to separate it from V, M and N
    "W": P((L - 15, T), (205, B), (M, 300), (395, B), (R + 15, T)),
    "X": P((L, T), (R, B)) + P((R, T), (L, B)),
    "Y": P((L, T), (M, MID), (R, T)) + P((M, MID), (M, B)),
    "Z": P((L, T), (R, T), (L, B), (R, B)),
}

# ---------------------------------------------------------------- lowercase
def _bigdot(x):
    """i/j dot: a large square, set high, so i and dotless i stay apart at small sizes."""
    return dot(x, DOT_Y, DOT_I)


_E_A0 = math.degrees(math.asin((290 - HS * H_RATIO - XM) / XRY))   # e bowl: starts at the bar's underside
_n_arch = chain([(L, 300)], arc(M, 300, RX, XT - 300, 180, 0), [(R, 300), (R, B)])
DOT_Y = 670                  # centre of the i/j dot (raised: search on i vs dotless i)
LC = {
    # a: smaller bowl (top at 240) and a hook starting at 140 deg (search: separates a from o and e)
    # The bowl is open: its top runs flat into the stem and its right side merges
    # tangentially into the stem (a closed bowl plus a bar left a heavy blob top right).
    "a": chain(arc(M, 360, RX, XT - 360, 140, 0), [(R, 360), (R, B)])
         + chain([(R, 240), (M + 10, 240)], arc(M + 10, 141, RX - 10, 141 - B, 90, 360)),
    "b": P((L, AT), (L, B)) + [arc(M, XM, RX, XRY, 0, 360)],
    "c": [arc(M, XM, RX, XRY, 45, 315)],
    "d": P((R, AT), (R, B)) + [arc(M, XM, RX, XRY, 0, 360)],
    # e: bar raised to 290 and a wider aperture (ends at 300 deg): separates e from o and a.
    # Bar and bowl are one stroke, so the bowl starts exactly where the bar meets it.
    # the bowl starts level with the underside of the bar and rises straight to it, so the
    # bar meets the bowl in a square corner instead of a notch in the outer curve
    "e": chain([(L + 20, 290), (M + RX * math.cos(math.radians(_E_A0)), 290)], arc(M, XM, RX, XRY, _E_A0, 300)),
    "f": chain([(260, B), (260, 560)], arc(370, 560, 110, AT - 560, 180, 40)) + P((L + 20, XT), (R - 30, XT)),
    "g": [arc(M, XM, RX, XRY, 0, 360)] + chain([(R, XT), (R, -60)], arc(M, -60, RX, -60 - DT, 0, -160)),
    "h": P((L, AT), (L, B)) + _n_arch,
    # i: serif left at the top, full base bar: keeps i, l, 1, I apart
    # dot moved 35 units left of the stem centre: the top-left serif pulls the eye left, so a centred dot looked shifted right
    "i": P((L + 40, XT), (M, XT), (M, B)) + P((L + 20, B), (R - 20, B)) + _bigdot(M - 35),
    "dotlessi": P((L + 40, XT), (M, XT), (M, B)) + P((L + 20, B), (R - 20, B)),
    "uni0237": chain([(L + 40, XT), (360, XT), (360, -60)], arc(230, -60, 130, -60 - DT, 0, -150)),
    "j": chain([(L + 40, XT), (360, XT), (360, -60)], arc(230, -60, 130, -60 - DT, 0, -150))
         + _bigdot(360 - 35),                      # same optical shift as i
    "k": P((L, AT), (L, B)) + P((R - 10, XT), (L + 10, 200)) + P((244, 290), (R, B)),
    # l: tail to the right, unlike 1 (flag + base bar) and I (two bars)
    "l": chain([(L + 40, AT), (M, AT), (M, 150)], arc(390, 150, 90, 150 - B, 180, 270), [(390, B), (R + 10, B)]),
    "m": P((L, B), (L, XT)) + chain([(L, 380)], arc(215, 380, 85, XT - 380, 180, 0), [(M, 380), (M, B)])
         + chain([(M, 380)], arc(385, 380, 85, XT - 380, 180, 0), [(R, 380), (R, B)]),
    "n": P((L, XT), (L, B)) + _n_arch,
    "o": [arc(M, XM, RX, XRY, 0, 360)],
    # p, q: descender serifs set them apart from b and d. q's serif runs both ways from the stem
    # (a right-only stub looked clipped; centred it measured best against d, a and y, and no worse against g).
    "p": P((L, XT), (L, DT)) + [arc(M, XM, RX, XRY, 0, 360)] + P((L - 50, DT), (L + 110, DT)),
    "q": P((R, XT), (R, DT)) + [arc(M, XM, RX, XRY, 0, 360)] + P((R - 80, DT), (R + 70, DT)),
    # r: top-left serif only; a base bar made it read like a broken c (seen by eye at 12 px)
    # long curved arm (radius 150, ends at 40 deg): chosen by Ozge; long enough that r never reads as
    # dotless i at small sizes. Costs a little on n vs r (0.847 -> 0.870) compared with a flat arm.
    "r": P((170, XT), (170, B)) + chain([(170, 300)], arc(320, 300, 150, XT - 300, 180, 40))
         + P((L - 10, XT), (170, XT)),
    "s": [arc(M, XT - 103, 155, 103, 20, 270) + arc(M, B + 115, 167, 115, 90, -140)[1:]],   # top bowl smaller
    "t": chain([(260, 640), (260, 150)], arc(370, 150, 110, 150 - B, 180, 270), [(370, B), (450, B)])
         + P((L, XT), (R - 20, XT)),
    "u": chain([(L, XT), (L, 220)], arc(M, 220, RX, 220 - B, 180, 360), [(R, 220)]) + P((R, XT), (R, B)),
    "v": P((L, XT), (M, B), (R, XT)),
    "w": P((L - 15, XT), (205, B), (M, 240), (395, B), (R + 15, XT)),
    "x": P((L, XT), (R, B)) + P((R, XT), (L, B)),
    "y": P((L, XT), (M, B + 20)) + P((R, XT), (190, DT)),
    "z": P((L, XT), (R, XT), (L, B), (R, B)),
}

# ---------------------------------------------------------------- digits
DIG = {
    # zero: dotted, so it never reads as O (and avoids the slashed-zero / Ø clash)
    "zero": [arc(M, MID, 140, RY, 0, 360)] + P((M, 290), (M, 410)),    # narrower than O, dotted
    # one: flag, no base bar (measured: a base bar made it collide with i and I)
    "one": P((L + 20, 560), (M, T), (M, B)),        # flag and stem as one stroke: a clean mitred top
    "two": chain(arc(M, 495, 165, T - 495, 160, -20), [(L, B), (R, B)]),
    "three": [arc(M, 512, 152, 146, 160, -90) + arc(M, 204, 172, 162, 90, -160)[1:]] + P((230, 366), (M, 366)),
    "four": P((390, B), (390, T), (L, 220), (R + 10, 220)),
    "five": chain([(R - 20, T), (L + 10, T), (L + 10, 390)], arc(M, 225, RX, 225 - B, 145, -150)),
    # six and nine: straight diagonal stems (measured: separates 6 from G and b, 9 from q and g)
    "six": [arc(M, 230, RX, 230 - B, 0, 360)] + P((160, 330), (400, T)),
    "seven": P((L, T), (R, T), (220, B)),
    "eight": [arc(M, 520, 150, T - 520, 0, 360)] + [arc(M, 205, RX, 205 - B, 0, 360)],
    "nine": [arc(M, 470, RX, T - 470, 0, 360)] + P((440, 370), (200, B)),
}

# ---------------------------------------------------------------- punctuation and symbols
_dot0 = dot(M, DOT_PUNCT / 2, DOT_PUNCT)
_dot_x = dot(M, XH - DOT_PUNCT / 2, DOT_PUNCT)      # upper dot of colon and semicolon, on the x-height
PUN = {
    "period": _dot0,
    "comma": P((M + 10, B + 20), (M - 30, -100)),
    "colon": _dot0 + _dot_x,
    "semicolon": P((M + 10, B + 20), (M - 30, -100)) + _dot_x,
    "hyphen": P((L + 40, 300), (R - 40, 300)),
    "underscore": P((L - 40, -60), (R + 40, -60)),
    "parenleft": [arc(560, 330, 260, 450, 128, 232)],
    "parenright": mirror([arc(560, 330, 260, 450, 128, 232)]),
    "bracketleft": P((400, 760), (230, 760), (230, -100), (400, -100)),
    "bracketright": mirror(P((400, 760), (230, 760), (230, -100), (400, -100))),
    "braceleft": P((410, 760), (310, 760), (310, 400), (200, 330), (310, 260), (310, -100), (410, -100)),
    "braceright": mirror(P((410, 760), (310, 760), (310, 400), (200, 330), (310, 260), (310, -100), (410, -100))),
    "slash": P((170, -60), (430, 760)),
    "backslash": P((430, -60), (170, 760)),
    "bar": P((M, -120), (M, 780)),
    "less": P((450, 560), (150, 330), (450, 100)),
    "greater": mirror(P((450, 560), (150, 330), (450, 100))),
    "equal": P((L, 240), (R, 240)) + P((L, 420), (R, 420)),
    "plus": P((M, 150), (M, 510)) + P((L, 330), (R, 330)),
    "asterisk": P((M, 350), (M, 650)) + P((170, 425), (430, 575)) + P((170, 575), (430, 425)),
    "exclam": P((M, T), (M, 230)) + _dot0,
    "question": chain(arc(M, 520, 150, T - 520, 160, -60), [(M, 330), (M, 230)]) + _dot0,
    "quotesingle": P((M, T), (M, 500)),
    "quotedbl": P((210, T), (210, 500)) + P((390, T), (390, 500)),
    "numbersign": P((230, 80), (230, 620)) + P((370, 80), (370, 620)) + P((L, 250), (R, 250)) + P((L, 450), (R, 450)),
    "percent": [arc(190, 540, 70, 100, 0, 360)] + [arc(410, 160, 70, 100, 0, 360)] + P((L, B), (R, T)),
    "dollar": G["S"] + P((M, -60), (M, 760)),
}


def rot180(strokes, cy):
    """Rotate strokes half a turn about (M, cy): turns ? into an inverted question mark."""
    out = []
    for st in strokes:
        out.append([b_.rotated(cy) if isinstance(b_, ArcSeg) else
                    DotSeg(2 * M - b_.x, 2 * cy - b_.y, b_.size) if isinstance(b_, DotSeg) else
                    (2 * M - b_[0], 2 * cy - b_[1]) for b_ in st])
    return out


# ---------------------------------------------------------------- remaining GF Latin Core letters and symbols
_D = P((L, B), (L, T)) + chain([(L, T), (200, T)], arc(200, MID, 270, RY, 90, -90), [(200, B), (L, B)])
_E_RIGHT = chain([(M, 290), (385 + 85 * math.cos(math.radians(_E_A0)), 290)], arc(385, XM, 85, XRY, _E_A0, 300))
_QUOTE = lambda x, y: P((x + 15, y + 130), (x - 15, y))          # noqa: E731  a comma-like tick
_TURNED = lambda x, y: P((x - 15, y + 130), (x + 15, y))         # noqa: E731  the mirrored tick of opening quotes
_amp_bowl = arc(285, 215, 175, 173, 150, 360)
_S_UPPER = chain(arc(M, 520, 125, 95, 20, 270), arc(M, 330, 130, 95, 90, -90))
NEW = {
    # letters
    "AE": P((100, B), (330, T), (R, T)) + P((330, T), (330, B), (R, B)) + P((330, MID), (R - 30, MID))
          + P((175, 230), (330, 230)),
    "ae": chain(arc(215, 360, 85, XT - 360, 140, 0), [(M, 360), (M, B)])
          + chain([(M, 240), (215, 240)], arc(215, 141, 85, 99, 90, 360)) + _E_RIGHT,
    "OE": P((330, T), (330, B)) + chain([(R, T), (330, T)], arc(330, MID, 200, RY, 90, 270), [(330, B), (R, B)])
          + P((330, MID), (R - 30, MID)),
    "oe": [arc(215, XM, 85, XRY, 0, 360)] + _E_RIGHT,
    "Oslash": [arc(M, MID, RX, RY, 0, 360)] + P((140, -20), (460, 720)),
    "oslash": [arc(M, XM, RX, XRY, 0, 360)] + P((140, -20), (460, 540)),
    "Eth": _D + P((40, MID), (260, MID)),
    "dcroat": P((R, AT), (R, B)) + [arc(M, XM, RX, XRY, 0, 360)] + P((370, 610), (550, 610)),
    "eth": [arc(M, XM, RX, XRY, 0, 360)] + P((455, 330), (250, AT)) + P((230, 560), (430, 660)),
    "Thorn": P((L, B), (L, T)) + chain([(L, 540), (310, 540)], arc(310, 382, 160, 158, 90, -90), [(310, 224), (L, 224)]),
    "thorn": P((L, AT), (L, DT)) + [arc(M, XM, RX, XRY, 0, 360)],
    # one continuous stroke: stem, narrow upper bowl down to the waist, wider lower bowl back to the stem
    "germandbls": chain([(L, B), (L, 550)], arc(275, 550, 145, AT - 550, 180, -90), [(320, 402)],
                        arc(320, 222, 150, 180, 90, -90), [(320, B), (240, B)]),
    "uni1E9E": chain([(L, B), (L, T), (R, T), (300, 420), (330, 420)], arc(330, 231, 140, 189, 90, -90),
                     [(330, B), (250, B)]),
    "Hbar": G["H"] + P((L, 540), (R, 540)),
    "hbar": LC["h"] + P((60, 610), (260, 610)),
    "Lslash": G["L"] + P((50, 250), (260, 420)),
    "lslash": LC["l"] + P((200, 330), (400, 480)),
    # Indian rupee sign: two bars, a P-like bowl hanging from the top bar, and a diagonal leg
    # one stroke from the top bar round the bowl into the leg, so the leg has no cap sticking out
    "uni20B9": P((L, T), (R, T)) + chain([(L, T), (250, T)], arc(250, 509, 150, T - 509, 90, -90),
                                         [(250, 360), (L + 10, 360), (R, B)])
               + P((L, 530), (R, 530)),
    "longs": chain([(260, B), (260, 560)], arc(370, 560, 110, AT - 560, 180, 40)),      # f without its bar
    "Ldot": G["L"] + dot(340, 340, DOT_PUNCT),                                          # Catalan
    "ldot": LC["l"] + dot(450, 270, DOT_PUNCT),
    # Dutch IJ / ij: one cell, a plain I stem beside a J (j) with its hook turned left
    "IJ": P((150, T), (150, B)) + chain([(440, T), (440, 220)], arc(340, 220, 100, 220 - B, 0, -140)),
    "ij": P((170, XT), (170, B)) + _bigdot(170)
          + chain([(420, XT), (420, -60)], arc(300, -60, 120, -60 - DT, 0, -150)) + _bigdot(420),
    # symbols and punctuation
    # one continuous stroke: arm, lower bowl, up through the crossing, round the upper loop, leg
    "ampersand": chain([(490, 330)], arc(285, 215, 175, 173, 360, 150), [(280, 432)],
                       arc(280, 545, 110, 113, 270, 580), [(R + 10, B)]),
    "at": [arc(300, 330, 75, 110, 0, 360)] + chain([(375, 440), (375, 250)], arc(430, 250, 55, 60, 180, 360))
          + [arc(300, 340, 190, 298, 0, 300)],
    "asciicircum": P((170, 420), (M, T), (430, 420)),
    "grave": P((340, 560), (260, T)),
    "asciitilde": chain(arc(230, 330, 70, 50, 180, 0), arc(370, 330, 70, 50, 180, 360)),
    "exclamdown": _dot_x + P((M, 360), (M, -180)),
    "questiondown": rot180(PUN["question"], XM),
    "cent": [arc(M, XM, RX, XRY, 45, 315)] + P((M, -60), (M, 580)),
    "sterling": chain(arc(330, 520, 140, 138, 15, 180), [(190, 520), (190, 150), (L, B), (R, B)]) + P((L, 350), (380, 350)),
    "yen": P((L, T), (M, 380), (R, T)) + P((M, 380), (M, B)) + P((170, 330), (430, 330)) + P((170, 200), (430, 200)),
    # two S curves, the second a half-turn copy of the first; they share the middle loop exactly
    "section": _S_UPPER + rot180(_S_UPPER, 330),
    "copyright": [arc(M, MID, 210, RY, 0, 360)] + [arc(M, MID, 95, 130, 50, 310)],
    "registered": [arc(M, MID, 210, RY, 0, 360)] + P((240, 200), (240, 500))
                  + chain([(240, 500), (320, 500)], arc(320, 430, 60, 70, 90, -90), [(320, 360), (240, 360)])
                  + P((310, 360), (370, 200)),
    "trademark": P((50, T), (250, T)) + P((150, T), (150, 430)) + P((320, 430), (320, T), (420, 540), (520, T), (520, 430)),
    "ordfeminine": [arc(290, 500, 85, 65, 0, 360)] + chain(arc(290, 600, 85, 55, 150, 0), [(375, 600), (375, 440)])
                   + P((200, 330), (400, 330)),
    "ordmasculine": [arc(M, 540, 95, 110, 0, 360)] + P((200, 330), (400, 330)),
    "guillemotleft": P((290, 420), (160, 260), (290, 100)) + P((440, 420), (310, 260), (440, 100)),
    "guillemotright": mirror(P((290, 420), (160, 260), (290, 100)) + P((440, 420), (310, 260), (440, 100))),
    "guilsinglleft": P((370, 420), (230, 260), (370, 100)),
    "guilsinglright": mirror(P((370, 420), (230, 260), (370, 100))),
    "degree": [arc(M, 560, 90, 98, 0, 360)],
    "paragraph": P((310, T), (310, -120)) + P((450, T), (450, -120))      # stems far enough apart to read
                 + chain([(450, T), (268, T)], arc(268, 500, 110, 158, 90, 270), [(268, 342), (310, 342)]),
    "periodcentered": dot(M, 340, DOT_PUNCT),
    "multiply": P((180, 200), (420, 460)) + P((420, 200), (180, 460)),
    "divide": P((L, 330), (R, 330)) + dot(M, 490, DOT_PUNCT) + dot(M, 170, DOT_PUNCT),
    "minus": P((L, 330), (R, 330)),
    "endash": P((100, 300), (500, 300)),
    "emdash": P((42, 300), (558, 300)),
    "quoteleft": _TURNED(M, 570),
    "quoteright": _QUOTE(M, 570),
    "quotesinglbase": _QUOTE(M, -70),
    "quotedblleft": _TURNED(220, 570) + _TURNED(380, 570),
    "quotedblright": _QUOTE(220, 570) + _QUOTE(380, 570),
    "quotedblbase": _QUOTE(220, -70) + _QUOTE(380, -70),
    "bullet": dot(M, 330, 150),
    "ellipsis": dot(120, DOT_PUNCT / 2, DOT_PUNCT) + _dot0 + dot(480, DOT_PUNCT / 2, DOT_PUNCT),
    "Euro": [arc(330, MID, RX, RY, 48, 312)] + P((90, 410), (380, 410)) + P((90, 290), (350, 290)),
    "uni25CC": [P((M + 180 * math.cos(math.radians(a)) - 6, 330 + 220 * math.sin(math.radians(a))),
                  (M + 180 * math.cos(math.radians(a)) + 6, 330 + 220 * math.sin(math.radians(a))))[0]
                for a in range(0, 360, 30)],
}
NEW_ZONE = {"AE": (0, CAP), "OE": (0, CAP), "Oslash": (0, CAP), "Eth": (0, CAP), "Thorn": (0, CAP),
            "uni1E9E": (0, CAP), "Hbar": (0, CAP), "Lslash": (0, CAP),
            "ae": (0, XH), "oe": (0, XH), "oslash": (0, XH), "dcroat": (0, ASC), "eth": (0, ASC),
            "thorn": (DESC, ASC), "germandbls": (0, ASC), "hbar": (0, ASC), "lslash": (0, ASC),
            "uni20B9": (0, CAP), "longs": (0, ASC), "Ldot": (0, CAP), "ldot": (0, ASC), "IJ": (0, CAP), "ij": (DESC, ASC)}
# marks are drawn lighter than the 84-unit stems, as is usual; dots keep the full weight
_MARK_STROKE = {"gravecomb": 72, "acutecomb": 72, "circumflexcomb": 72, "caroncomb": 72, "macroncomb": 72,
                "brevecomb": 66, "hungarumlautcomb": 72, "commaaccentcomb": 72, "commaturnedabovecomb": 72,
                "caroncomb.alt": 72, "tildecomb": 66, "ringcomb": 60, "cedillacomb": 62, "ogonekcomb": 62}
STROKE_FOR = {**_MARK_STROKE, "copyright": 70, "registered": 60, "trademark": 60, "ordfeminine": 60, "ordmasculine": 60,
              "degree": 70, "uni25CC": 40, "section": 76}

# ---------------------------------------------------------------- accents (drawn at lowercase position)
ACC = {
    # Marks are drawn centred on x = 300 above the x-height (or below the baseline), then
    # stored shifted one advance to the left with zero width, so they combine onto the
    # preceding letter; composites place them back with dx = +ADV.
    "dotaccentcomb": dot(M, DOT_Y, DOT_ACCENT),
    "dieresiscomb": dot(200, DOT_Y, DOT_DIERESIS) + dot(400, DOT_Y, DOT_DIERESIS),
    # breve: wide and shallow, set high enough that a clear gap stays above the g's bowl at text sizes
    "brevecomb": [arc(M, 688, 120, 56, 180, 360)],
    "cedillacomb": chain([(M, 10), (M, -40)], arc(M, -102, 72, 62, 90, -150)),   # open hook, lighter stroke
    "gravecomb": P((345, 600), (255, 690)),
    "acutecomb": P((255, 600), (345, 690)),
    "circumflexcomb": P((195, 600), (M, 690), (405, 600)),
    "caroncomb": P((195, 690), (M, 600), (405, 690)),
    "tildecomb": chain(arc(250, 630, 55, 40, 180, 0), arc(350, 630, 55, 40, 180, 360)),
    "macroncomb": P((195, 640), (405, 640)),
    "ringcomb": [arc(M, 655, 78, 66, 0, 360)],                   # wide open ring, lighter stroke
    "hungarumlautcomb": P((175, 600), (245, 690)) + P((335, 600), (405, 690)),
    "commaaccentcomb": P((310, -70), (275, -180)),
    "commaturnedabovecomb": P((285, 700), (315, 590)),
    # ogonek: an open half circle, open on the right; the horizontal hook carries the weight,
    # and the tip stays within the letter's right edge (see _OGONEK_X)
    "ogonekcomb": chain([(M, 20)], arc(M + 45, -69, 70, 90, 130, 300)),
    "caroncomb.alt": P((315, 700), (290, 590)),     # the apostrophe-like caron of d l t L
}
MARK_GLYPHS = set(ACC)
UC_SHIFT = CAP - XH          # accents move up by this much over capitals

# alternates: small-capital R form of r (Ozge's handwriting), opt-in via ss01.
# Deliberately not mapped to U+0280: that character needs a case pair (U+01A6) the font lacks.
ALT = {
    "r.ss01": P((L, B), (L, XT)) + chain([(L, XT), (310, XT)], arc(310, XT - 110, 150, 110, 90, -90),
                                         [(310, XT - 220), (L, XT - 220)]) + P((290, XT - 220), (R, B)),
}
FEATURES = """
languagesystem DFLT dflt;
languagesystem latn dflt;
@TopMarks = [gravecomb acutecomb circumflexcomb tildecomb macroncomb brevecomb dotaccentcomb
             dieresiscomb ringcomb hungarumlautcomb caroncomb commaturnedabovecomb];
feature ccmp {
    # i and j lose their dot when an accent is typed on top of them
    sub [i j iogonek]' @TopMarks by [dotlessi uni0237 iogonek.dotless];
    sub [i j]' [cedillacomb commaaccentcomb ogonekcomb] @TopMarks by [dotlessi uni0237];
} ccmp;
feature ss01 {
    featureNames { name "R-form r"; };
    sub r by r.ss01;
} ss01;
"""

# composites: name -> (codepoint, [(component, dx, dy), ...]); built by _composites()
UC_SHIFT_FOR = {"brevecomb": 160}      # the high breve needs less lift over capitals to stay inside the ascent
ASC_SHIFT = ASC - XH - 30     # accents over ascenders (l acute) stay inside the 950 ascent
_MARK_FOR = {0x300: "gravecomb", 0x301: "acutecomb", 0x302: "circumflexcomb", 0x303: "tildecomb",
             0x304: "macroncomb", 0x306: "brevecomb", 0x307: "dotaccentcomb", 0x308: "dieresiscomb",
             0x30A: "ringcomb", 0x30B: "hungarumlautcomb", 0x30C: "caroncomb", 0x326: "commaaccentcomb",
             0x327: "cedillacomb", 0x328: "ogonekcomb"}
_BELOW = {"cedillacomb", "commaaccentcomb", "ogonekcomb"}
_OGONEK_X = {"A": 445, "E": 430, "I": 300, "U": 330, "a": 430, "e": 360, "i": 380, "u": 430}
_COMMA_X = {"t": 260, "r": 190}
# Czech/Slovak d l t L take the apostrophe-like caron beside the stem: (dx, dy) of caroncomb.alt
_CARON_ALT = {"d": (255, 40), "l": (120, 40), "t": (80, 0), "L": (-40, 0)}
# Latvian: K L N R k l n r G take a comma below instead of the cedilla, g a turned comma above
_LATVIAN = set("GKLNRklnr")
_SPACING = {0xA8: "dieresiscomb", 0xAF: "macroncomb", 0xB4: "acutecomb", 0xB8: "cedillacomb",
            0x2DC: "tildecomb", 0x2DA: "ringcomb", 0x2D8: "brevecomb", 0x2DB: "ogonekcomb",
            0x2D9: "dotaccentcomb", 0x2DD: "hungarumlautcomb", 0x2C6: "circumflexcomb", 0x2C7: "caroncomb"}
_ASCENDERS = set("bdfhklt")
TOP_X = {"j": 360, "uni0237": 360}             # where accents sit when not centred on the cell


def _glyph_name(cp):
    from fontTools import agl
    return agl.UV2AGL.get(cp, f"uni{cp:04X}")


def _composites(codepoints):
    import unicodedata
    out = {}
    for cp in codepoints:
        ch = chr(cp)
        if cp in _SPACING:
            out[_glyph_name(cp)] = (cp, [(_SPACING[cp], ADV, 0)])
            continue
        parts = [int(x, 16) for x in unicodedata.decomposition(ch).split() if not x.startswith("<")]
        if len(parts) != 2 or parts[1] not in _MARK_FOR:
            continue
        base, mark = chr(parts[0]), _MARK_FOR[parts[1]]
        if not base.isascii():                    # e.g. O with stroke + acute: base is a drawn glyph
            out[_glyph_name(cp)] = (cp, [(_glyph_name(parts[0]), 0, 0),
                                         (mark, ADV, UC_SHIFT_FOR.get(mark, UC_SHIFT) if base.isupper() else 0)])
            continue
        upper = base.isupper()
        if mark == "cedillacomb" and base in _LATVIAN:
            mark = "commaaccentcomb"
        if mark == "cedillacomb" and base == "g":
            mark = "commaturnedabovecomb"
        if mark == "caroncomb" and base in _CARON_ALT:
            dx, dy = _CARON_ALT[base]
            out[_glyph_name(cp)] = (cp, [(base, 0, 0), ("caroncomb.alt", ADV + dx, dy)])
            continue
        if mark in _BELOW:
            dx = (_OGONEK_X.get(base, M) - M) if mark == "ogonekcomb" else (_COMMA_X.get(base, M) - M)
            dy = 0
        else:
            dx = 0
            dy = UC_SHIFT_FOR.get(mark, UC_SHIFT) if upper else (ASC_SHIFT if base in _ASCENDERS else 0)
        base_glyph = {"i": "dotlessi", "j": "uni0237"}.get(base, base) if mark not in _BELOW else base
        out[_glyph_name(cp)] = (cp, [(base_glyph, 0, 0), (mark, ADV + dx, dy)])
    return out


_TURKISH = [0x130, 0x11E, 0x11F, 0x15E, 0x15F, 0xC7, 0xE7, 0xD6, 0xF6, 0xDC, 0xFC]
_LATIN_CORE_ACCENTED = "".join(chr(c) for c in _SPACING) + (
    "ÀÁÂÃÄÅÈÉÊËÌÍÎÏÑÒÓÔÕÙÚÛÝàáâãäåèéêëìíîïñòóôõùúûýÿ"
    "ĀāĂăĄąĆćĊċČčĎďĒēĖėĘęĚěĠġĢģĪīĮįĶķĹĺĻļĽľŃńŅņŇňŌōŐőŔŕŘřŚśŠšŢţŤťŪūŮůŰűŲųŴŵŶŷŸŹźŻżŽž"
    "ȘșȚțẀẁẂẃẄẅỲỳ"
    # auxiliary letters of European orthographies (Fontspector shaping check)
    "ĔĕĬĭŎŏŬŭǓǔĨĩŨũẼẽŜŝǍǎǦǧǨǩǾǿȞȟŖŗ"
)
COMP = _composites(_TURKISH + [ord(c) for c in _LATIN_CORE_ACCENTED])
COMP[_glyph_name(0x110)] = (0x110, [("Eth", 0, 0)])       # D with stroke: same drawing as Eth
COMP_UNENCODED = {"iogonek.dotless": [("dotlessi", 0, 0), ("ogonekcomb", ADV + _OGONEK_X["i"] - M, 0)]}

NAME_TO_CP = {**{c: ord(c) for c in G}, **{c: ord(c) for c in LC if len(c) == 1}, "dotlessi": 0x131,
              "zero": 0x30, "one": 0x31, "two": 0x32, "three": 0x33, "four": 0x34, "five": 0x35, "six": 0x36,
              "seven": 0x37, "eight": 0x38, "nine": 0x39,
              "period": 0x2E, "comma": 0x2C, "colon": 0x3A, "semicolon": 0x3B, "hyphen": 0x2D, "underscore": 0x5F,
              "parenleft": 0x28, "parenright": 0x29, "bracketleft": 0x5B, "bracketright": 0x5D,
              "braceleft": 0x7B, "braceright": 0x7D, "slash": 0x2F, "backslash": 0x5C, "bar": 0x7C,
              "less": 0x3C, "greater": 0x3E, "equal": 0x3D, "plus": 0x2B, "asterisk": 0x2A, "exclam": 0x21,
              "question": 0x3F, "quotesingle": 0x27, "quotedbl": 0x22, "numbersign": 0x23, "percent": 0x25,
              "dollar": 0x24,
              "uni0237": 0x237, "commaturnedabovecomb": 0x312,
              **{v: k for k, v in _MARK_FOR.items()}}


def _cp_for(name):
    from fontTools import agl
    return agl.AGL2UV.get(name) or int(name[3:], 16)


NAME_TO_CP.update({n: _cp_for(n) for n in NEW})


class stroke_width:
    """Temporarily draw with another stroke width (small symbols such as the registered sign)."""

    def __init__(self, width):
        self.width = width

    def __enter__(self):
        global STROKE, HS
        self.saved = (STROKE, HS)
        STROKE, HS = self.width, self.width / 2

    def __exit__(self, *exc):
        global STROKE, HS
        STROKE, HS = self.saved


NOTDEF = P((90, 0), (90, 700), (510, 700), (510, 0), (90, 0))   # hollow box, the conventional .notdef


def zone(name):
    """Vertical clip zone (ymin, ymax) for a glyph's outline."""
    if name in G:
        return (-120, CAP) if name == "Q" else (0, CAP)
    if name in DIG:
        return (0, CAP)
    if name in ALT:
        return (0, XH)
    if name in NEW_ZONE:
        return NEW_ZONE[name]
    if name in LC:
        top = ASC if name in ("b", "d", "f", "h", "k", "l", "t", "i", "j") else XH
        bottom = DESC if name in ("g", "j", "p", "q", "y", "uni0237") else 0
        return (bottom, top)
    return (-300, 900)         # punctuation and accents: no clipping in practice


def outline(strokes, clip=(0, CAP)):
    geom = unary_union([box(s[0].x - s[0].size / 2, s[0].y - s[0].size / 2, s[0].x + s[0].size / 2,
                            s[0].y + s[0].size / 2) if isinstance(s[0], DotSeg) else
                        LineString(sample(s)).buffer(HS, cap_style="square", join_style="mitre", mitre_limit=2.2)
                        for s in strokes])
    geom = geom.intersection(box(-200, clip[0], ADV + 200, clip[1])).simplify(1.5)
    polys = list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]
    pen = TTGlyphPen(None)
    for poly in polys:
        if poly.is_empty or poly.geom_type != "Polygon":
            continue
        poly = orient(poly, sign=-1.0)  # TrueType: outer contours clockwise
        for ring in [poly.exterior, *poly.interiors]:
            pts = [(round(x), round(y)) for x, y in ring.coords[:-1]]
            pen.moveTo(pts[0])
            for p in pts[1:]:
                pen.lineTo(p)
            pen.closePath()
    return pen.glyph()


def build(path, glyph_defs=None):
    upper = glyph_defs or G
    simple = {**upper, **LC, **DIG, **PUN, **NEW, **ACC, **ALT}
    encoded = {n: s for n, s in simple.items() if n in NAME_TO_CP}   # alternates stay unencoded
    order = [".notdef", "space", "uni00A0"] + sorted(simple) + sorted(COMP) + sorted(COMP_UNENCODED)
    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(order)
    cmap = {32: "space", 0xA0: "uni00A0", **{NAME_TO_CP[n]: n for n in encoded}, **{v[0]: k for k, v in COMP.items()}}
    fb.setupCharacterMap(cmap)
    glyphs = {".notdef": outline(NOTDEF, (-300, 900)), "space": TTGlyphPen(None).glyph(),
              "uni00A0": TTGlyphPen(None).glyph()}
    for n, st in simple.items():
        with stroke_width(STROKE_FOR.get(n, STROKE)):
            glyphs[n] = outline(st, zone(n))
    for n in MARK_GLYPHS:                         # zero-width marks sit one advance to the left
        if glyphs[n].numberOfContours:
            glyphs[n].coordinates.translate((-ADV, 0))
    for name, comps in [(n, c) for n, (_, c) in COMP.items()] + list(COMP_UNENCODED.items()):
        pen = TTGlyphPen(glyphs)
        for comp, dx, dy in comps:
            pen.addComponent(comp, (1, 0, 0, 1, dx, dy))
        glyphs[name] = pen.glyph()
    fb.setupGlyf(glyphs)
    glyf = fb.font["glyf"]
    lsb = {}
    for g in order:
        glyf[g].recalcBounds(glyf)
        lsb[g] = getattr(glyf[g], "xMin", 0) if glyf[g].numberOfContours else 0
    fb.setupHorizontalMetrics({g: (0 if g in MARK_GLYPHS else ADV, lsb[g]) for g in order})
    fb.setupHorizontalHeader(ascent=950, descent=-250)
    fb.setupNameTable({
        "familyName": FAMILY, "styleName": "Regular",
        "uniqueFontIdentifier": f"{VERSION};NONE;{PSNAME}",
        "fullName": f"{FAMILY} Regular", "psName": PSNAME,
        "version": f"Version {VERSION}",
        "copyright": COPYRIGHT,
        "licenseDescription": ("This Font Software is licensed under the SIL Open Font License, Version 1.1. "
                               "This license is available with a FAQ at: https://openfontlicense.org"),
        "licenseInfoURL": "https://openfontlicense.org",
        "designer": DESIGNER,
        "vendorURL": REPO_URL,
    })
    fb.setupOS2(version=4, fsType=0, usWeightClass=400, usWidthClass=5, fsSelection=0x40 | 0x80,sTypoAscender=950, sTypoDescender=-250, usWinAscent=950, usWinDescent=250, sCapHeight=CAP,
                sxHeight=XH,
                panose={"bFamilyType": 2, "bSerifStyle": 0, "bWeight": 5, "bProportion": 9, "bContrast": 0,
                        "bStrokeVariation": 0, "bArmStyle": 0, "bLetterForm": 0, "bMidline": 0, "bXHeight": 0})
    fb.setupPost(isFixedPitch=1)
    fb.font["head"].fontRevision = float(VERSION)
    fb.font["head"].flags |= 1 << 3        # integer PPEM rounding, required for hinted fonts
    fb.font["OS/2"].recalcCodePageRanges(fb.font)
    fb.font["OS/2"].recalcUnicodeRanges(fb.font)
    addOpenTypeFeaturesFromString(fb.font, FEATURES)
    fb.save(path)


if __name__ == "__main__":
    build(sys.argv[1])
    print("saved", sys.argv[1])
