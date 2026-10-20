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
VERSION = "0.100"
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
    return [[it.mirrored() if isinstance(it, ArcSeg) else (2 * M - it[0], it[1]) for it in s] for s in strokes]


def sample(stroke):
    """Stroke (points and ArcSegs) -> polyline, exactly as the prototype sampled it."""
    out = []
    for it in stroke:
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
    "F": P((R, T), (L, T), (L, B)) + P((L, MID), (R - 60, MID)),
    # H: standard crossbar, stems pulled in by 45 (measured: separates it from N; a low bar read like h)
    "H": P((L + 45, B), (L + 45, T)) + P((R - 45, B), (R - 45, T)) + P((L + 45, MID), (R - 45, MID)),
    "I": P((L + 40, T), (R - 40, T)) + P((M, T), (M, B)) + P((L + 40, B), (R - 40, B)),
    "J": chain([(L + 60, T), (R, T), (R, 220)], arc(M, 220, RX, 220 - B, 0, -180)),
    "K": P((L, B), (L, T)) + P((R, T), (L + 10, 300)) + P((250, 420), (R, B)),
    "L": P((L, T), (L, B), (R, B)),
    # M: shallow vertex (470); a deep vertex was measured to collide with W
    "M": P((L, B), (L, T), (M, 470), (R, T), (R, B)),
    "N": P((L, B), (L, T), (R, B), (R, T)),
    "O": [arc(M, MID, RX, RY, 0, 360)],
    "P": P((L, B), (L, T)) + chain([(L, T), (310, T)], arc(310, 500, 160, 158, 90, -90), [(310, 342), (L, 342)]),
    # Q: tail drops from the bottom centre and turns right (measured best against O, G and D)
    "Q": [arc(M, MID, RX, RY, 0, 360)] + P((M, 30), (M, -60), (500, -60)),
    "R": P((L, B), (L, T)) + chain([(L, T), (310, T)], arc(310, 500, 160, 158, 90, -90), [(310, 342), (L, 342)])
         + P((290, 342), (R, B)),
    # S: lower terminal kept short (-140) so the silhouette separates from G
    "S": [arc(M, 505, 165, 153, 20, 270) + arc(M, 197, 170, 155, 90, -140)[1:]],
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
    """i/j dot: about 120 x 114 units, larger than the stroke, so i and dotless i stay apart."""
    return P((x - 18, DOT[0]), (x + 18, DOT[0])) + P((x - 18, DOT[1]), (x + 18, DOT[1]))


_n_arch = chain([(L, 300)], arc(M, 300, RX, XT - 300, 180, 0), [(R, 300), (R, B)])
DOT = (620, 650)             # skeleton y-range of the i/j dot
LC = {
    # a: smaller bowl (top at 240) and a hook starting at 140 deg (search: separates a from o and e)
    "a": chain(arc(M, 360, RX, XT - 360, 140, 0), [(R, 360), (R, B)])
         + [arc(285, 141, 145, 141 - B, 0, 360)] + P((285, 240), (R, 240)),
    "b": P((L, AT), (L, B)) + [arc(320, XM, 150, XRY, 0, 360)],
    "c": [arc(M, XM, RX, XRY, 45, 315)],
    "d": P((R, AT), (R, B)) + [arc(280, XM, 150, XRY, 0, 360)],
    # e: bar raised to 290 and a wider aperture (ends at 300 deg): separates e from o and a
    "e": P((L, 290), (R, 290)) + [arc(M, XM, RX, XRY, 3, 300)],
    "f": chain([(260, B), (260, 560)], arc(370, 560, 110, AT - 560, 180, 40)) + P((L + 20, XT), (R - 30, XT)),
    "g": [arc(285, XM, 145, XRY, 0, 360)] + chain([(R, XT), (R, -60)], arc(M, -60, RX, -60 - DT, 0, -160)),
    "h": P((L, AT), (L, B)) + _n_arch,
    # i: serif left at the top, full base bar: keeps i, l, 1, I apart
    "i": P((L + 40, XT), (M, XT), (M, B)) + P((L + 20, B), (R - 20, B)) + _bigdot(M),
    "dotlessi": P((L + 40, XT), (M, XT), (M, B)) + P((L + 20, B), (R - 20, B)),
    "j": chain([(L + 40, XT), (360, XT), (360, -60)], arc(230, -60, 130, -60 - DT, 0, -150))
         + _bigdot(360),
    "k": P((L, AT), (L, B)) + P((R - 10, XT), (L + 10, 200)) + P((244, 290), (R, B)),
    # l: tail to the right, unlike 1 (flag + base bar) and I (two bars)
    "l": chain([(L + 40, AT), (M, AT), (M, 150)], arc(390, 150, 90, 150 - B, 180, 270), [(390, B), (R + 10, B)]),
    "m": P((L, B), (L, XT)) + chain([(L, 380)], arc(215, 380, 85, XT - 380, 180, 0), [(M, 380), (M, B)])
         + chain([(M, 380)], arc(385, 380, 85, XT - 380, 180, 0), [(R, 380), (R, B)]),
    "n": P((L, XT), (L, B)) + _n_arch,
    "o": [arc(M, XM, RX, XRY, 0, 360)],
    # p, q: descender serifs set them apart from b and d. q's serif points right only:
    # a left foot measured closer to g's leftward hook.
    "p": P((L, XT), (L, DT)) + [arc(320, XM, 150, XRY, 0, 360)] + P((L - 50, DT), (L + 110, DT)),
    "q": P((R, XT), (R, DT)) + [arc(280, XM, 150, XRY, 0, 360)] + P((R, DT), (R + 70, DT)),
    # r: top-left serif only; a base bar made it read like a broken c (seen by eye at 12 px)
    "r": P((170, XT), (170, B)) + chain([(170, 300)], arc(320, 300, 150, XT - 300, 180, 35)) + P((L - 10, XT), (170, XT)),
    "s": [arc(M, XM + XRY / 2, 160, XRY / 2, 20, 270) + arc(M, XM - XRY / 2, 165, XRY / 2, 90, -140)[1:]],
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
    "one": P((M, T), (M, B)) + P((M, T), (L + 20, 560)),
    "two": chain(arc(M, 495, 165, T - 495, 160, -20), [(L, B), (R, B)]),
    "three": [arc(M, 505, 160, 153, 160, -90) + arc(M, 197, 170, 155, 90, -160)[1:]] + P((230, 352), (M, 352)),
    "four": P((390, B), (390, T), (L, 220), (R + 10, 220)),
    "five": chain([(R - 20, T), (L + 10, T), (L + 10, 390)], arc(M, 225, RX, 225 - B, 145, -150)),
    # six and nine: straight diagonal stems (measured: separates 6 from G and b, 9 from q and g)
    "six": [arc(M, 230, RX, 230 - B, 0, 360)] + P((160, 330), (400, T)),
    "seven": P((L, T), (R, T), (220, B)),
    "eight": [arc(M, 520, 150, T - 520, 0, 360)] + [arc(M, 205, RX, 205 - B, 0, 360)],
    "nine": [arc(M, 470, RX, T - 470, 0, 360)] + P((440, 370), (200, B)),
}

# ---------------------------------------------------------------- punctuation and symbols
_dot0 = P((M, B), (M, B + 20))
PUN = {
    "period": _dot0,
    "comma": P((M + 10, B + 20), (M - 30, -100)),
    "colon": _dot0 + P((M, 400), (M, 420)),
    "semicolon": P((M + 10, B + 20), (M - 30, -100)) + P((M, 400), (M, 420)),
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

# ---------------------------------------------------------------- accents (drawn at lowercase position)
ACC = {
    "dotaccentcomb": _bigdot(M),
    "dieresiscomb": P((200, DOT[0]), (200, DOT[1])) + P((400, DOT[0]), (400, DOT[1])),
    "brevecomb": [arc(M, 640, 110, 70, 180, 360)],   # tips kept clear of cap height
    "cedillacomb": chain([(M, 10), (M, -60)], arc(M, -110, 60, 50, 90, -160)),
}
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
feature ss01 {
    featureNames { name "R-form r"; };
    sub r by r.ss01;
} ss01;
"""

# composites: name -> (codepoint, base, accent, dy)
COMP = {
    "Idotaccent": (0x130, "I", "dotaccentcomb", UC_SHIFT),
    "Gbreve": (0x11E, "G", "brevecomb", UC_SHIFT),
    "gbreve": (0x11F, "g", "brevecomb", 0),
    "Scedilla": (0x15E, "S", "cedillacomb", 0),
    "scedilla": (0x15F, "s", "cedillacomb", 0),
    "Ccedilla": (0xC7, "C", "cedillacomb", 0),
    "ccedilla": (0xE7, "c", "cedillacomb", 0),
    "Odieresis": (0xD6, "O", "dieresiscomb", UC_SHIFT),
    "odieresis": (0xF6, "o", "dieresiscomb", 0),
    "Udieresis": (0xDC, "U", "dieresiscomb", UC_SHIFT),
    "udieresis": (0xFC, "u", "dieresiscomb", 0),
}

NAME_TO_CP = {**{c: ord(c) for c in G}, **{c: ord(c) for c in LC if len(c) == 1}, "dotlessi": 0x131,
              "zero": 0x30, "one": 0x31, "two": 0x32, "three": 0x33, "four": 0x34, "five": 0x35, "six": 0x36,
              "seven": 0x37, "eight": 0x38, "nine": 0x39,
              "period": 0x2E, "comma": 0x2C, "colon": 0x3A, "semicolon": 0x3B, "hyphen": 0x2D, "underscore": 0x5F,
              "parenleft": 0x28, "parenright": 0x29, "bracketleft": 0x5B, "bracketright": 0x5D,
              "braceleft": 0x7B, "braceright": 0x7D, "slash": 0x2F, "backslash": 0x5C, "bar": 0x7C,
              "less": 0x3C, "greater": 0x3E, "equal": 0x3D, "plus": 0x2B, "asterisk": 0x2A, "exclam": 0x21,
              "question": 0x3F, "quotesingle": 0x27, "quotedbl": 0x22, "numbersign": 0x23, "percent": 0x25,
              "dollar": 0x24,
              "dotaccentcomb": 0x307, "dieresiscomb": 0x308, "brevecomb": 0x306, "cedillacomb": 0x327}


NOTDEF = P((90, 0), (90, 700), (510, 700), (510, 0), (90, 0))   # hollow box, the conventional .notdef


def zone(name):
    """Vertical clip zone (ymin, ymax) for a glyph's outline."""
    if name in G:
        return (-120, CAP) if name == "Q" else (0, CAP)
    if name in DIG:
        return (0, CAP)
    if name in ALT:
        return (0, XH)
    if name in LC:
        top = ASC if name in ("b", "d", "f", "h", "k", "l", "t", "i", "j") else XH
        bottom = DESC if name in ("g", "j", "p", "q", "y") else 0
        return (bottom, top)
    return (-300, 900)         # punctuation and accents: no clipping in practice


def outline(strokes, clip=(0, CAP)):
    geom = unary_union([LineString(sample(s)).buffer(HS, cap_style="square", join_style="mitre", mitre_limit=2.2)
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
    simple = {**upper, **LC, **DIG, **PUN, **ACC, **ALT}
    encoded = {n: s for n, s in simple.items() if n not in ALT}
    order = [".notdef", "space", "uni00A0"] + sorted(simple) + sorted(COMP)
    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(order)
    cmap = {32: "space", 0xA0: "uni00A0", **{NAME_TO_CP[n]: n for n in encoded}, **{v[0]: k for k, v in COMP.items()}}
    fb.setupCharacterMap(cmap)
    glyphs = {".notdef": outline(NOTDEF, (-300, 900)), "space": TTGlyphPen(None).glyph(),
              "uni00A0": TTGlyphPen(None).glyph()}
    glyphs.update({n: outline(s, zone(n)) for n, s in simple.items()})
    for name, (_, base, acc, dy) in COMP.items():
        pen = TTGlyphPen(glyphs)
        pen.addComponent(base, (1, 0, 0, 1, 0, 0))
        pen.addComponent(acc, (1, 0, 0, 1, 0, dy))
        glyphs[name] = pen.glyph()
    fb.setupGlyf(glyphs)
    glyf = fb.font["glyf"]
    lsb = {}
    for g in order:
        glyf[g].recalcBounds(glyf)
        lsb[g] = getattr(glyf[g], "xMin", 0) if glyf[g].numberOfContours else 0
    fb.setupHorizontalMetrics({g: (ADV, lsb[g]) for g in order})
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
