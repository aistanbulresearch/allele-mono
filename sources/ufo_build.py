"""Generate the Allele Mono UFO source from the glyph skeletons in build.py.

Each skeleton stroke (straight segments and elliptical arcs) is expanded
geometrically, with the optical corrections of optics.py: a straight segment
becomes a quadrilateral whose width depends on its direction (and tapers into
sharp vertices), an arc becomes pieces between an outer and an inner squared
ellipse (true cubic curves, split at the axis angles so points sit on extrema;
thinner where it leaves a stem, past the guide lines by the overshoot), corners
get mitre wedges, straight ends square caps and curve ends a horizontal or
vertical cut. All pieces are merged with Skia's boolean union and clipped to
the glyph's zone; spacing.py then centres each glyph optically in its cell.
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
import optics  # noqa: E402
import spacing  # noqa: E402

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
        if isinstance(it, b.DotSeg):
            return []
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


def side_points(s, at_end, pen):
    """(left, right) outline points at a segment end, left = +90 degrees from the tangent."""
    if s[0] == "line" and len(s) > 3:
        k = 1 if at_end else 0
        return s[3]["left"][k], s[3]["right"][k]
    if s[0] == "line":
        p = s[2] if at_end else s[1]
        d = tangent(s, at_end)
        n = (-d[1], d[0])
        lw, rw = optics.line_halfwidths(s[1], s[2], pen)
        return (p[0] + n[0] * lw, p[1] + n[1] * lw), (p[0] - n[0] * rw, p[1] - n[1] * rw)
    a, info = s[1], s[2]
    po, pi = optics.end_points(a, info.outer, info.inner, info.mult, a.a1 if at_end else a.a0)
    return (pi, po) if a.a1 > a.a0 else (po, pi)   # CCW: left side is inside


def _poly(pts):
    p = pathops.Path()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    p.close()
    return p


class ArcInfo:
    """Outline geometry of one arc: outer and inner contours, and the thinning towards stems."""

    def __init__(self, a, pen, flat_top, flat_bottom, stems):
        self.outer, self.inner = optics.arc_radii(a, pen, flat_top, flat_bottom)
        self.mult = None if pen.mark else optics.thinning(a, stems, pen)


def _intersect(p, d, q, e):
    den = d[0] * e[1] - d[1] * e[0]
    if abs(den) < 1e-9:
        return None
    t = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / den
    return (p[0] + d[0] * t, p[1] + d[1] * t)


def join_piece(s1, s2, pen, zone=None):
    """Mitre (or bevel past the mitre limit) wedge on the outer side of a corner.
    A mitre whose tip the zone clip will cut off (A apex, V point) is always kept."""
    d1, d2 = tangent(s1, True), tangent(s2, False)
    cross = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(cross) < 1e-6 and d1[0] * d2[0] + d1[1] * d2[1] > 0:
        return None                                   # smooth continuation
    v = seg_end(s1)
    l1, r1 = side_points(s1, True, pen)
    l2, r2 = side_points(s2, False, pen)
    a, c = (r1, r2) if cross > 0 else (l1, l2)        # left turn: outer side is the right
    side = "right" if cross > 0 else "left"
    m = _intersect(a, _edge_dir(s1, side, True), c, _edge_dir(s2, side, False))
    tip_clipped = m is not None and zone is not None and not (zone[0] <= m[1] <= zone[1])
    # a curve meeting a straight stroke at a corner (the bar of e) gets a bevel: a mitre tip
    # built from the curve's end tangent would stand outside the squared curve
    curved = s1[0] == "arc" or s2[0] == "arc"
    if m is None or curved or (math.hypot(m[0] - v[0], m[1] - v[1]) > MITRE * pen.V / 2 and not tip_clipped):
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


def cap_kind(s, at_end, zone, others, hs):
    """'long' where the zone clip will cut the end flat (stems and legs at the baseline,
    cap height, x-height); 'butt' where the end sits on another stroke (crossbars, arms),
    so no nub sticks out; otherwise a free end: 'square' cap, or a cut terminal on curves."""
    p = seg_end(s) if at_end else seg_start(s)
    d = tangent(s, at_end)
    for o in others:
        on_stroke = _dist_to_polyline(p, o) < 1.05 * hs
        at_its_end = min(math.hypot(p[0] - q[0], p[1] - q[1]) for q in (o[0], o[-1])) < hs
        if on_stroke and not at_its_end:
            return "butt"       # ends in the middle of another stroke: crossbars, arms, a leg
    # two strokes meeting at their ends form a corner (B, D, P, R): square caps fill it
    if abs(d[1]) > 0.2 and (p[1] - zone[0] < 1.5 * hs or zone[1] - p[1] < 1.5 * hs):
        return "long"
    return "square"


def cap_piece(s, at_end, pen, kind="square"):
    if kind == "butt":
        return None
    l, r = side_points(s, at_end, pen)
    d = tangent(s, at_end)
    ext = 4 * pen.hs0 if kind == "long" else pen.hs0
    k = ext if at_end else -ext
    return _poly([l, r, (r[0] + d[0] * k, r[1] + d[1] * k), (l[0] + d[0] * k, l[1] + d[1] * k)])


def _diagonal(s):
    d = tangent(s, False)
    return s[0] == "line" and abs(d[0]) > 0.15 and abs(d[1]) > 0.15


def _edge_dir(s, side, at_end):
    if s[0] == "line" and len(s) > 3:
        a, c = s[3][side]
        return _norm((c[0] - a[0], c[1] - a[1]))
    return tangent(s, at_end)


def line_edges(s, pen, tapers, exts):
    """Left and right edges (start, end) of a straight segment. A tapered end loses part of a
    half-width, the edge running straight from the other end (no kink points); a free end is
    extended along each edge by its cap length, so caps continue the edges exactly.
    tapers: {(end, side): fraction}; exts: {end: length}; end is 0 or 1."""
    p0, p1 = s[1], s[2]
    d = tangent(s, False)
    n = (-d[1], d[0])
    lw, rw = optics.line_halfwidths(p0, p1, pen)
    out = {}
    for side, w, sgn in (("left", lw, 1), ("right", rw, -1)):
        w0, w1 = sgn * w * (1 - tapers.get((0, side), 0)), sgn * w * (1 - tapers.get((1, side), 0))
        a = (p0[0] + n[0] * w0, p0[1] + n[1] * w0)
        c = (p1[0] + n[0] * w1, p1[1] + n[1] * w1)
        e = _norm((c[0] - a[0], c[1] - a[1]))
        e0, e1 = exts.get(0, 0), exts.get(1, 0)
        out[side] = ((a[0] - e[0] * e0, a[1] - e[1] * e0), (c[0] + e[0] * e1, c[1] + e[1] * e1))
    return out


def terminal(s, at_end, pen):
    """A free curve end, cut straight across horizontally or vertically (whichever is closer
    to square to the stroke) where the old square cap ended: one rule for every terminal.
    Returns (extension pieces trimmed to the body's side of the cut, cutter for the body)."""
    a, info = s[1], s[2]
    sgn = 1 if a.a1 > a.a0 else -1
    te = a.a1 if at_end else a.a0
    d = tangent(s, at_end)
    out = d if at_end else (-d[0], -d[1])
    p = a.point(te)
    p = (p[0] + out[0] * pen.hs0, p[1] + out[1] * pen.hs0)
    # far enough past the end to reach the cut line on both edges; never so far that a small
    # hook (the tail of @) curls back towards the body
    reach = min(60.0, math.degrees((pen.hs0 + 0.6 * pen.V + 8) / ((a.rx + a.ry) / 2)))
    lo, hi = (te, te + sgn * reach) if at_end else (te - sgn * reach, te)
    ext = optics.arc_paths(a, info.outer, info.inner, info.mult, min(lo, hi), max(lo, hi))
    # the body ends square to the stroke, at most half a stroke width short of or past the cut
    # line; the cutter trims what passes it, and the extension keeps only what falls short of it
    e, depth, back = 0.9 * pen.V + 10, 0.8 * pen.V, pen.hs0 + 1.5 * pen.V

    def box(lo_, hi_):                                 # band between two offsets along `out`
        if abs(out[1]) >= abs(out[0]):                 # stroke runs up or down here: cut horizontally
            s_ = 1 if out[1] > 0 else -1
            y0, y1 = p[1] + s_ * lo_, p[1] + s_ * hi_
            return _poly([(p[0] - e, y0), (p[0] + e, y0), (p[0] + e, y1), (p[0] - e, y1)])
        s_ = 1 if out[0] > 0 else -1
        x0, x1 = p[0] + s_ * lo_, p[0] + s_ * hi_
        return _poly([(x0, p[1] - e), (x0, p[1] + e), (x1, p[1] + e), (x1, p[1] - e)])
    kept = pathops.op(_union(ext), box(-back, 0), pathops.PathOp.INTERSECTION)
    return [kept], box(0, depth)


def _union(paths):
    builder = pathops.OpBuilder()
    for p in paths:
        builder.add(p, pathops.PathOp.UNION)
    return builder.resolve()


def _shape(segs, pen, closed):
    """Attach arc geometry to the segments; return them with the diagonal tapers at sharp vertices."""
    for i, s in enumerate(segs):
        if s[0] != "arc":
            continue
        a = s[1]
        prev = segs[i - 1] if (i > 0 or closed) else None
        nxt = segs[(i + 1) % len(segs)] if (i < len(segs) - 1 or closed) else None
        flats = [ang % 360 for ang, nb in ((a.a0, prev), (a.a1, nxt)) if nb is not None and nb[0] == "line"]
        segs[i] = ("arc", a, ArcInfo(a, pen, 90 in flats, 270 in flats, pen.stems))
    tapers = {i: {} for i in range(len(segs))}
    pairs = list(zip(range(len(segs)), range(1, len(segs))))
    if closed:
        pairs.append((len(segs) - 1, 0))
    for i, j in pairs:
        s1, s2 = segs[i], segs[j]
        if s1[0] != "line" or s2[0] != "line" or pen.mark:
            continue
        d1, d2 = tangent(s1, True), tangent(s2, False)
        interior = math.degrees(math.acos(max(-1.0, min(1.0, -(d1[0] * d2[0] + d1[1] * d2[1])))))
        if interior < b.TAPER_ANGLE:
            inner = "left" if d1[0] * d2[1] - d1[1] * d2[0] > 0 else "right"
            if _diagonal(s1):
                tapers[i][(1, inner)] = b.TAPER
            if _diagonal(s2):
                tapers[j][(0, inner)] = b.TAPER
    return segs, tapers, pairs


def stroke_pieces(stroke, pen, zone=(0, b.CAP), others=()):
    """(straight pieces, round pieces) of one stroke; round pieces may pass the zone by the overshoot."""
    if isinstance(stroke[0], b.DotSeg):
        t, h = stroke[0], stroke[0].size / 2
        return [_poly([(t.x - h, t.y - h), (t.x + h, t.y - h), (t.x + h, t.y + h), (t.x - h, t.y + h)])], []
    segs = segments(stroke)
    if not segs:
        return [], []
    closed = _close(seg_end(segs[-1]), seg_start(segs[0]))
    segs, tapers, pairs = _shape(segs, pen, closed)
    straight, round_, cutters = [], [], {}
    exts = {i: {} for i in range(len(segs))}
    if not closed:
        for k, at_end in ((0, False), (len(segs) - 1, True)):
            seg = segs[k]
            end = 1 if at_end else 0
            kind = cap_kind(seg, at_end, zone, others, pen.hs0)
            cut = not pen.mark and pen.name not in b.SQUARE_TERMINALS
            if seg[0] == "arc" and kind == "square" and cut and min(seg[1].rx, seg[1].ry) > 50:
                ext, cutter = terminal(seg, at_end, pen)
                round_ += ext
                cutters.setdefault(k, []).append(cutter)
            elif kind == "butt":
                if _diagonal(seg) and not pen.mark:
                    tapers[k][(end, "left")] = tapers[k][(end, "right")] = b.TAPER_BUTT
            elif seg[0] == "line":
                # a square cap reaches half the width of a stroke running across it, so where
                # strokes meet end to end (B, P, R) the corner is flush with the thinner one
                d = tangent(seg, at_end)
                exts[k][end] = 4 * pen.hs0 if kind == "long" else optics.line_width((-d[1], d[0]), pen) / 2
            else:
                straight.append(cap_piece(seg, at_end, pen, kind))
    for i, s in enumerate(segs):
        if s[0] == "line":
            segs[i] = s = ("line", s[1], s[2], line_edges(s, pen, tapers[i], exts[i]))
            straight.append(_poly([*s[3]["left"], *s[3]["right"][::-1]]))
        else:
            pieces = optics.arc_paths(s[1], s[2].outer, s[2].inner, s[2].mult,
                                      min(s[1].a0, s[1].a1), max(s[1].a0, s[1].a1))
            if i in cutters:            # a cut terminal trims only its own curve, never a stem nearby
                pieces = [pathops.op(_union(pieces), _union(cutters[i]), pathops.PathOp.DIFFERENCE)]
            round_ += pieces
    for i, j in pairs:
        w = join_piece(segs[i], segs[j], pen, zone)
        if w is not None:
            straight.append(w)
    return straight, round_


def glyph_outline(strokes, zone, pen):
    polylines = [b.sample(s) for s in strokes]

    def length(pts):
        return sum(math.hypot(x1 - x0, y1 - y0) for (x0, y0), (x1, y1) in zip(pts, pts[1:]))

    straight, round_ = [], []
    for i, s in enumerate(strokes):
        # only real strokes can hide a butt end; the short bars that build a dot cannot
        others = [o for j, o in enumerate(polylines) if j != i and length(o) >= 2 * b.STROKE]
        pen.stems = optics.stems_near(polylines, i)
        st, rd = stroke_pieces(s, pen, zone, others)
        straight += st
        round_ += rd

    def clipped(paths, pad):
        if not paths:
            return pathops.Path()
        box = _poly([(-200, zone[0] - pad), (b.ADV + 200, zone[0] - pad),
                     (b.ADV + 200, zone[1] + pad), (-200, zone[1] + pad)])
        return pathops.op(_union(paths), box, pathops.PathOp.INTERSECTION)
    return _union([clipped(straight, 0), clipped(round_, b.OVERSHOOT + 1)])


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
                limit = 0.1 if min(la, lb) < 25 else 0.05     # a short step: under ~6 degrees, else ~3
                straight = la and lb and cross / (la * lb) < limit and ax * bx + ay * by > 0
                span = math.hypot(nxt.x - prev.x, nxt.y - prev.y)
                nx, ny = abs(nxt.x - prev.x), abs(nxt.y - prev.y)
                makes_semi_axis = (0 < nx <= 3 and ny > 20) or (0 < ny <= 3 and nx > 20)
                sliver = (la and lb and span and min(la, lb) < 12 and cross / span < 4
                          and not makes_semi_axis)                    # tiny step where an
                if la == 0 or lb == 0 or straight or sliver:                 # oblique stroke meets an arc
                    del pts[i]
                    changed = True
                    break


def _true_up(glyph, guides):
    """Snap on-curve points lying within 2 units of a guide line onto it (where a curve
    crosses the flat top of a stem), and make nearly horizontal or vertical lines exact."""
    for contour in glyph.contours:
        pts = contour.points
        for p in pts:
            if p.type:
                for g in guides:
                    if 0 < abs(p.y - g) <= 2:
                        p.y = g
        n = len(pts)
        for i, p in enumerate(pts):
            q = pts[(i + 1) % n]
            if q.type != "line" or not p.type:
                continue
            dx, dy = abs(q.x - p.x), abs(q.y - p.y)
            if 0 < dy <= 2.5 and dx >= 40:
                on = [v.y for v in (p, q) if v.y in guides]
                p.y = q.y = on[0] if on else round((p.y + q.y) / 2)
            elif 0 < dx <= 2.5 and dy >= 40:
                p.x = q.x = round((p.x + q.x) / 2)


def _drop_slivers(glyph, min_area=40):
    """Remove stray contours of a few square units (boolean-operation dust), and say so:
    anything larger is a geometry error to fix, not to hide."""
    keep = []
    for contour in glyph.contours:
        pts = [(p.x, p.y) for p in contour.points]
        area = abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))) / 2
        if area >= min_area:
            keep.append(contour)
        else:
            print(f"  {glyph.name}: dropped a stray contour of {area:.0f} square units", file=sys.stderr)
    glyph.contours[:] = keep


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
        path = glyph_outline(strokes, zone, optics.Pen(name, name in b.MARK_GLYPHS))
        glyph = font[name]
        glyph.clearContours()
        path.draw(QuadToCubicPen(RoundingPen(TransformPen(glyph.getPen(), (1, 0, 0, 1, dx, 0)))))
        _drop_slivers(glyph)
        _drop_redundant_points(glyph)
        _merge_tiny_segments(glyph)
        _drop_redundant_points(glyph)
        _true_up(glyph, b.GUIDES)

    draw(".notdef", b.NOTDEF, (-300, 900))
    for name, strokes in simple.items():
        is_mark = name in b.MARK_GLYPHS
        with b.stroke_width(b.STROKE_FOR.get(name, b.STROKE)):
            draw(name, strokes, b.zone(name), -b.ADV if is_mark else 0)
        if is_mark:
            font[name].width = 0
        if name in b.NAME_TO_CP:
            font[name].unicodes = [b.NAME_TO_CP[name]]
    # optical centring in the cell; accents and anchors move with their letter
    shifts = spacing.centring(font)
    for name, dx in shifts.items():
        font[name].move((dx, 0))
    for name, cp, comps in [(n, cp, c) for n, (cp, c) in b.COMP.items()] + \
            [(n, None, c) for n, c in b.COMP_UNENCODED.items()]:
        g = font[name]
        if cp is not None:
            g.unicodes = [cp]
        base_dx = shifts.get(comps[0][0], 0)
        for k, (comp, dx, dy) in enumerate(comps):
            g.components.append(Component(comp, transformation=(1, 0, 0, 1, dx + (base_dx if k else 0), dy)))

    # anchors, so the mark feature can place any combining accent on any letter
    letters = [n for n in list(b.G) + list(b.LC) if n in font and n not in b.MARK_GLYPHS]
    for n in letters:
        g = font[n]
        top = b.CAP if n in b.G else (b.ASC if n in b._ASCENDERS else b.XH)
        dx = shifts.get(n, 0)
        g.appendAnchor({"name": "top", "x": b.TOP_X.get(n, b.M) + dx, "y": top})
        g.appendAnchor({"name": "bottom", "x": (b.M if n not in b._COMMA_X else b._COMMA_X[n]) + dx, "y": 0})
        if n in b._OGONEK_X:
            g.appendAnchor({"name": "ogonek", "x": b._OGONEK_X[n] + dx, "y": 0})
    font["uni25CC"].appendAnchor({"name": "top", "x": b.M, "y": b.XH})       # dotted circle carries marks
    font["uni25CC"].appendAnchor({"name": "bottom", "x": b.M, "y": 0})
    font["uni25CC"].appendAnchor({"name": "ogonek", "x": b.M + 100, "y": 0})
    letters.append("uni25CC")
    for n in b.MARK_GLYPHS:
        if n == "caroncomb.alt":
            continue
        kind = "ogonek" if n == "ogonekcomb" else ("bottom" if n in b._BELOW else "top")
        font[n].appendAnchor({"name": "_" + kind, "x": b.M - b.ADV, "y": 0 if kind != "top" else b.XH})
    # stacking: each top mark also gets a "top" anchor just above itself (mark-to-mark), so a second
    # accent clears the first; composites inherit anchors from their parts (propagateAnchors filter)
    tops = [n for n in b.MARK_GLYPHS if n != "caroncomb.alt" and n not in b._BELOW and n != "ogonekcomb"
            and font[n].contours]
    bounds = {n: font[n].getBounds(font) for n in tops}
    lift = sorted(bb.yMin - b.XH for bb in bounds.values())[len(tops) // 2]   # usual gap under a mark
    for n in tops:
        font[n].appendAnchor({"name": "top", "x": b.M - b.ADV, "y": round(bounds[n].yMax + 50 - lift)})
    font.lib["com.github.googlei18n.ufo2ft.filters"] = [{"name": "propagateAnchors", "pre": True}]
    composed = [n for n in list(b.COMP) + list(b.COMP_UNENCODED) if n not in b.MARK_GLYPHS]
    font.lib["public.openTypeCategories"] = {**{n: "base" for n in letters + composed},
                                             **{n: "mark" for n in b.MARK_GLYPHS}}

    font.features.text = b.FEATURES
    font.save(out_dir, overwrite=True)
    return font


if __name__ == "__main__":
    make_ufo(sys.argv[1])
    print("wrote", sys.argv[1])
