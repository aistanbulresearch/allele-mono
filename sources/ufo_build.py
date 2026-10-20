"""Generate the Allele Mono UFO source from the glyph skeletons in build.py.

Each skeleton stroke (straight segments and elliptical arcs) is expanded
geometrically: a straight segment becomes a rectangle, an arc becomes annular
sectors between the concentric ellipses rx +/- HS and ry +/- HS (true cubic
curves, split at the axis angles so points sit on extrema), corners get mitre
wedges and open ends square caps, the same parameters as the prototype. All
pieces are merged with Skia's boolean union and clipped to the glyph's zone.
Accented letters are UFO components. The result is an ordinary UFO that font
editors (Fontra, FontForge, Glyphs) can open, and that fontmake compiles.

Usage: python3 sources/ufo_build.py sources/AlleleMono-Regular.ufo
"""
import math
import os
import sys

import pathops
import ufoLib2
from fontTools.pens.basePen import decomposeQuadraticSegment
from fontTools.pens.filterPen import FilterPen
from fontTools.pens.roundingPen import RoundingPen
from fontTools.pens.transformPen import TransformPen
from ufoLib2.objects import Component

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build as b  # noqa: E402

MITRE = 2.2


class QuadToCubicPen(FilterPen):
    """Skia's stroker emits quadratic curves; UFO sources here are cubic, so elevate them exactly."""

    def __init__(self, outPen):
        super().__init__(outPen)
        self._last = None

    def moveTo(self, pt):
        self._last = pt
        self._outPen.moveTo(pt)

    def lineTo(self, pt):
        self._last = pt
        self._outPen.lineTo(pt)

    def curveTo(self, *points):
        self._last = points[-1]
        self._outPen.curveTo(*points)

    def qCurveTo(self, *points):
        for c, p in decomposeQuadraticSegment(points):
            p0 = self._last
            c1 = (p0[0] + 2 / 3 * (c[0] - p0[0]), p0[1] + 2 / 3 * (c[1] - p0[1]))
            c2 = (p[0] + 2 / 3 * (c[0] - p[0]), p[1] + 2 / 3 * (c[1] - p[1]))
            self._outPen.curveTo(c1, c2, p)
            self._last = p


def _close(p, q, tol=0.5):
    return math.hypot(p[0] - q[0], p[1] - q[1]) <= tol


def segments(stroke):
    """Skeleton stroke -> list of ("line", p0, p1) and ("arc", ArcSeg) in drawing order."""
    segs, cur = [], None
    for it in stroke:
        if isinstance(it, b.ArcSeg):
            st = it.point(it.a0)
            if cur is not None and not _close(cur, st):
                segs.append(("line", cur, st))
            segs.append(("arc", it))
            cur = it.point(it.a1)
        else:
            pt = (float(it[0]), float(it[1]))
            if cur is not None and not _close(cur, pt, 0.01):
                segs.append(("line", cur, pt))
            cur = pt
    return segs


def _norm(v):
    d = math.hypot(*v)
    return (v[0] / d, v[1] / d)


def seg_start(s):
    return s[1] if s[0] == "line" else s[1].point(s[1].a0)


def seg_end(s):
    return s[2] if s[0] == "line" else s[1].point(s[1].a1)


def tangent(s, at_end):
    if s[0] == "line":
        return _norm((s[2][0] - s[1][0], s[2][1] - s[1][1]))
    a = s[1]
    t = math.radians(a.a1 if at_end else a.a0)
    sgn = 1 if a.a1 > a.a0 else -1
    return _norm((-a.rx * math.sin(t) * sgn, a.ry * math.cos(t) * sgn))


def side_points(s, at_end):
    """(left, right) outline points at a segment end, left = +90 degrees from the tangent."""
    if s[0] == "line":
        p = s[2] if at_end else s[1]
        d = tangent(s, at_end)
        n = (-d[1], d[0])
        return (p[0] + n[0] * b.HS, p[1] + n[1] * b.HS), (p[0] - n[0] * b.HS, p[1] - n[1] * b.HS)
    a = s[1]
    t = math.radians(a.a1 if at_end else a.a0)
    outer = (a.cx + (a.rx + b.HS) * math.cos(t), a.cy + (a.ry + b.HS) * math.sin(t))
    inner = (a.cx + (a.rx - b.HS) * math.cos(t), a.cy + (a.ry - b.HS) * math.sin(t))
    return (inner, outer) if a.a1 > a.a0 else (outer, inner)   # CCW: left side is inside


def _poly(pts):
    p = pathops.Path()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    p.close()
    return p


def _arc_breaks(a0, a1):
    """Split an angle range at the axis angles, so every curve piece ends on an extremum."""
    lo, hi = min(a0, a1), max(a0, a1)
    cuts = [k * 90 for k in range(math.ceil(lo / 90 + 1e-9), math.floor(hi / 90 - 1e-9) + 1)]
    pts = [lo] + [c for c in cuts if lo < c < hi] + [hi]
    return list(zip(pts[:-1], pts[1:]))


def _ellipse_arc(path, cx, cy, rx, ry, t0, t1):
    seg = b.ArcSeg(cx, cy, rx, ry, t0, t1)
    for c1, c2, p3 in seg.beziers():
        path.cubicTo(*c1, *c2, *p3)


def arc_pieces(a):
    """Annular sectors between the concentric ellipses rx +/- HS, ry +/- HS."""
    out = []
    for t0, t1 in _arc_breaks(a.a0, a.a1):
        ro, ri = (a.rx + b.HS, a.ry + b.HS), (a.rx - b.HS, a.ry - b.HS)
        p = pathops.Path()
        p.moveTo(a.cx + ro[0] * math.cos(math.radians(t0)), a.cy + ro[1] * math.sin(math.radians(t0)))
        _ellipse_arc(p, a.cx, a.cy, ro[0], ro[1], t0, t1)
        p.lineTo(a.cx + ri[0] * math.cos(math.radians(t1)), a.cy + ri[1] * math.sin(math.radians(t1)))
        _ellipse_arc(p, a.cx, a.cy, ri[0], ri[1], t1, t0)
        p.close()
        out.append(p)
    return out


def _intersect(p, d, q, e):
    den = d[0] * e[1] - d[1] * e[0]
    if abs(den) < 1e-9:
        return None
    t = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / den
    return (p[0] + d[0] * t, p[1] + d[1] * t)


def join_piece(s1, s2, zone=None):
    """Mitre (or bevel past the mitre limit) wedge on the outer side of a corner.
    A mitre whose tip the zone clip will cut off (A apex, V point) is always kept."""
    d1, d2 = tangent(s1, True), tangent(s2, False)
    cross = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(cross) < 1e-6 and d1[0] * d2[0] + d1[1] * d2[1] > 0:
        return None                                   # smooth continuation
    v = seg_end(s1)
    l1, r1 = side_points(s1, True)
    l2, r2 = side_points(s2, False)
    a, c = (r1, r2) if cross > 0 else (l1, l2)        # left turn: outer side is the right
    m = _intersect(a, d1, c, d2)
    tip_clipped = m is not None and zone is not None and not (zone[0] <= m[1] <= zone[1])
    if m is None or (math.hypot(m[0] - v[0], m[1] - v[1]) > MITRE * b.HS and not tip_clipped):
        return _poly([v, a, c])
    return _poly([v, a, m, c])


def _dist_to_polyline(p, pts):
    best = float("inf")
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy
        t = 0 if L2 == 0 else max(0, min(1, ((p[0] - x0) * dx + (p[1] - y0) * dy) / L2))
        best = min(best, math.hypot(p[0] - (x0 + t * dx), p[1] - (y0 + t * dy)))
    return best


def cap_kind(s, at_end, zone, others):
    """'long' where the zone clip will cut the end flat (stems and legs at the baseline,
    cap height, x-height); 'butt' where the end sits on another stroke (crossbars, arms),
    so no nub sticks out; otherwise the prototype's 'square' cap."""
    p = seg_end(s) if at_end else seg_start(s)
    d = tangent(s, at_end)
    for o in others:
        on_stroke = _dist_to_polyline(p, o) < 1.05 * b.HS
        at_its_end = min(math.hypot(p[0] - q[0], p[1] - q[1]) for q in (o[0], o[-1])) < b.HS
        if on_stroke and not at_its_end:
            return "butt"       # ends in the middle of another stroke: crossbars, arms, a leg
    # two strokes meeting at their ends form a corner (B, D, P, R): square caps fill it
    if abs(d[1]) > 0.2 and (p[1] - zone[0] < 1.5 * b.HS or zone[1] - p[1] < 1.5 * b.HS):
        return "long"
    return "square"


def cap_piece(s, at_end, kind="square"):
    if kind == "butt":
        return None
    l, r = side_points(s, at_end)
    d = tangent(s, at_end)
    ext = 4 * b.HS if kind == "long" else b.HS
    k = ext if at_end else -ext
    return _poly([l, r, (r[0] + d[0] * k, r[1] + d[1] * k), (l[0] + d[0] * k, l[1] + d[1] * k)])


def stroke_pieces(stroke, zone=(0, b.CAP), others=()):
    segs = segments(stroke)
    if not segs:
        return []
    pieces = []
    for s in segs:
        if s[0] == "line":
            l0, r0 = side_points(s, False)
            l1, r1 = side_points(s, True)
            pieces.append(_poly([l0, l1, r1, r0]))
        else:
            pieces.extend(arc_pieces(s[1]))
    for s1, s2 in zip(segs, segs[1:]):
        j = join_piece(s1, s2, zone)
        if j is not None:
            pieces.append(j)
    closed = _close(seg_end(segs[-1]), seg_start(segs[0]))
    if closed:
        j = join_piece(segs[-1], segs[0], zone)
        if j is not None:
            pieces.append(j)
    else:
        for seg, at_end in ((segs[0], False), (segs[-1], True)):
            c = cap_piece(seg, at_end, cap_kind(seg, at_end, zone, others))
            if c is not None:
                pieces.append(c)
    return pieces


def glyph_outline(strokes, zone):
    builder = pathops.OpBuilder()
    polylines = [b.sample(s) for s in strokes]

    def length(pts):
        return sum(math.hypot(x1 - x0, y1 - y0) for (x0, y0), (x1, y1) in zip(pts, pts[1:]))

    for i, s in enumerate(strokes):
        # only real strokes can hide a butt end; the short bars that build a dot cannot
        others = [o for j, o in enumerate(polylines) if j != i and length(o) >= 2 * b.STROKE]
        for piece in stroke_pieces(s, zone, others):
            builder.add(piece, pathops.PathOp.UNION)
    merged = builder.resolve()
    clip = _poly([(-200, zone[0]), (b.ADV + 200, zone[0]), (b.ADV + 200, zone[1]), (-200, zone[1])])
    return pathops.op(merged, clip, pathops.PathOp.INTERSECTION)


def _drop_redundant_points(glyph):
    """Remove on-curve points lying on a straight run between two line segments, and
    exact duplicates: leftovers where union pieces met edge to edge."""
    for contour in glyph.contours:
        changed = True
        while changed and len(contour.points) > 3:
            changed = False
            pts = contour.points
            n = len(pts)
            for i in range(n):
                p, prev, nxt = pts[i], pts[i - 1], pts[(i + 1) % n]
                if p.type != "line" or nxt.type != "line":
                    continue                      # only points joining two straight segments
                ax, ay, bx, by = p.x - prev.x, p.y - prev.y, nxt.x - p.x, nxt.y - p.y
                la, lb = math.hypot(ax, ay), math.hypot(bx, by)
                cross = abs(ax * by - ay * bx)
                straight = la and lb and cross / (la * lb) < 0.05 and ax * bx + ay * by > 0     # under ~3 degrees
                span = math.hypot(nxt.x - prev.x, nxt.y - prev.y)
                nx, ny = abs(nxt.x - prev.x), abs(nxt.y - prev.y)
                makes_semi_axis = (0 < nx <= 3 and ny > 20) or (0 < ny <= 3 and nx > 20)
                sliver = (la and lb and span and min(la, lb) < 12 and cross / span < 4
                          and not makes_semi_axis)                    # tiny step where an
                if la == 0 or lb == 0 or straight or sliver:                 # oblique stroke meets an arc
                    del pts[i]
                    changed = True
                    break


def _merge_tiny_segments(glyph, tol=10):
    """Fold segments shorter than `tol` units into a neighbour. They appear where the boolean
    union cuts a curve a hair away from another stroke's edge (the hooks of the section sign)."""
    from ufoLib2.objects import Point
    for contour in glyph.contours:
        pts = contour.points
        on = [i for i, p in enumerate(pts) if p.type]
        if len(on) < 3:
            continue
        segs = []                                   # [type, [offcurves], (x, y)]
        for k, i in enumerate(on):
            j = on[k - 1]
            offs = [(pts[m].x, pts[m].y) for m in range((j + 1) % len(pts), i) if pts[m].type is None] \
                if j < i else [(pts[m].x, pts[m].y) for m in list(range(j + 1, len(pts))) + list(range(0, i))
                               if pts[m].type is None]
            segs.append([pts[i].type, offs, (pts[i].x, pts[i].y)])
        changed = True
        while changed and len(segs) > 3:
            changed = False
            for k in range(len(segs)):
                start = segs[k - 1][2]
                typ, offs, end = segs[k]
                if math.hypot(end[0] - start[0], end[1] - start[1]) >= tol:
                    continue
                prev, nxt = segs[k - 1], segs[(k + 1) % len(segs)]
                d = (end[0] - start[0], end[1] - start[1])
                if prev[0] == "curve" and prev[1]:
                    a1, a2 = prev[1]
                    prev[1] = [a1, (a2[0] + d[0], a2[1] + d[1])]
                    prev[2] = end
                elif nxt[0] == "curve" and nxt[1]:
                    c1, c2 = nxt[1]
                    nxt[1] = [(c1[0] - d[0], c1[1] - d[1]), c2]
                    prev[2] = start
                else:
                    mid = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
                    prev[2] = mid
                del segs[k]
                changed = True
                break
        new = []
        for typ, offs, end in segs:
            new += [Point(round(x), round(y)) for x, y in offs]
            new.append(Point(round(end[0]), round(end[1]), type=typ))
        contour.points[:] = new


def make_ufo(out_dir):
    font = ufoLib2.Font()
    info = font.info
    info.familyName = b.FAMILY
    info.styleName = "Regular"
    info.styleMapFamilyName = b.FAMILY
    info.styleMapStyleName = "regular"
    info.versionMajor, info.versionMinor = (int(x) for x in b.VERSION.split("."))
    info.unitsPerEm = b.UPM
    info.ascender, info.descender = 950, -250
    info.capHeight, info.xHeight = b.CAP, b.XH
    info.copyright = b.COPYRIGHT
    info.openTypeNameDesigner = b.DESIGNER
    info.openTypeNameManufacturerURL = b.REPO_URL
    info.openTypeNameLicense = ("This Font Software is licensed under the SIL Open Font License, Version 1.1. "
                                "This license is available with a FAQ at: https://openfontlicense.org")
    info.openTypeNameLicenseURL = "https://openfontlicense.org"
    info.openTypeOS2Type = []                       # fsType 0: installable embedding
    info.openTypeOS2WeightClass, info.openTypeOS2WidthClass = 400, 5
    info.openTypeOS2Selection = [7, 8]              # USE_TYPO_METRICS, WWS (naming is WWS-conformant)
    info.openTypeOS2TypoAscender, info.openTypeOS2TypoDescender, info.openTypeOS2TypoLineGap = 950, -250, 0
    info.openTypeOS2WinAscent, info.openTypeOS2WinDescent = 950, 250
    info.openTypeHheaAscender, info.openTypeHheaDescender, info.openTypeHheaLineGap = 950, -250, 0
    info.openTypeHeadFlags = [0, 1, 3]              # bit 3: integer PPEM (hinted font)
    info.postscriptIsFixedPitch = True
    info.openTypeOS2Panose = [2, 0, 5, 9, 0, 0, 0, 0, 0, 0]   # bProportion 9 = monospaced
    info.postscriptUnderlinePosition, info.postscriptUnderlineThickness = -150, 60

    simple = {**b.G, **b.LC, **b.DIG, **b.PUN, **b.NEW, **b.ACC, **b.ALT}
    blanks = {"space": 0x20, "uni00A0": 0xA0, "uni2028": 0x2028, "uni2029": 0x2029}   # empty glyphs
    order = [".notdef", *blanks] + sorted(simple) + sorted(b.COMP) + sorted(b.COMP_UNENCODED)

    for name in order:
        g = font.newGlyph(name)
        g.width = b.ADV
    for name, cp in blanks.items():
        font[name].unicodes = [cp]
    # zero-width marks first, so every glyph after them shares one advance (short hmtx)
    marks = [n for n in order if n in b.MARK_GLYPHS]
    font.lib["public.glyphOrder"] = [".notdef"] + marks + [n for n in order[1:] if n not in b.MARK_GLYPHS]

    def draw(name, strokes, zone, dx=0):
        path = glyph_outline(strokes, zone)
        glyph = font[name]
        glyph.clearContours()
        path.draw(QuadToCubicPen(RoundingPen(TransformPen(glyph.getPen(), (1, 0, 0, 1, dx, 0)))))
        _drop_redundant_points(glyph)
        _merge_tiny_segments(glyph)
        _drop_redundant_points(glyph)

    draw(".notdef", b.NOTDEF, (-300, 900))
    for name, strokes in simple.items():
        is_mark = name in b.MARK_GLYPHS
        with b.stroke_width(b.STROKE_FOR.get(name, b.STROKE)):
            draw(name, strokes, b.zone(name), -b.ADV if is_mark else 0)
        if is_mark:
            font[name].width = 0
        if name in b.NAME_TO_CP:
            font[name].unicodes = [b.NAME_TO_CP[name]]
    for name, cp, comps in [(n, cp, c) for n, (cp, c) in b.COMP.items()] + \
            [(n, None, c) for n, c in b.COMP_UNENCODED.items()]:
        g = font[name]
        if cp is not None:
            g.unicodes = [cp]
        for comp, dx, dy in comps:
            g.components.append(Component(comp, transformation=(1, 0, 0, 1, dx, dy)))

    # anchors, so the mark feature can place any combining accent on any letter
    letters = [n for n in list(b.G) + list(b.LC) if n in font and n not in b.MARK_GLYPHS]
    for n in letters:
        g = font[n]
        top = b.CAP if n in b.G else (b.ASC if n in b._ASCENDERS else b.XH)
        g.appendAnchor({"name": "top", "x": b.TOP_X.get(n, b.M), "y": top})
        g.appendAnchor({"name": "bottom", "x": b.M if n not in b._COMMA_X else b._COMMA_X[n], "y": 0})
        if n in b._OGONEK_X:
            g.appendAnchor({"name": "ogonek", "x": b._OGONEK_X[n], "y": 0})
    font["uni25CC"].appendAnchor({"name": "top", "x": b.M, "y": b.XH})       # dotted circle carries marks
    font["uni25CC"].appendAnchor({"name": "bottom", "x": b.M, "y": 0})
    font["uni25CC"].appendAnchor({"name": "ogonek", "x": b.M + 100, "y": 0})
    letters.append("uni25CC")
    for n in b.MARK_GLYPHS:
        if n == "caroncomb.alt":
            continue
        kind = "ogonek" if n == "ogonekcomb" else ("bottom" if n in b._BELOW else "top")
        font[n].appendAnchor({"name": "_" + kind, "x": b.M - b.ADV, "y": 0 if kind != "top" else b.XH})
    font.lib["public.openTypeCategories"] = {**{n: "base" for n in letters},
                                             **{n: "mark" for n in b.MARK_GLYPHS}}

    font.features.text = b.FEATURES
    font.save(out_dir, overwrite=True)
    return font


if __name__ == "__main__":
    make_ufo(sys.argv[1])
    print("wrote", sys.argv[1])
