"""Optical corrections used by ufo_build.py when it expands the skeletons of build.py.

A single constant pen makes strokes that measure equal but do not look equal. This module
holds the geometry that compensates (the parameters live in build.py, "optical corrections"):

- stroke weight depends on direction: horizontals are thinner than stems, diagonals a little;
- curves are squarer than a true ellipse, inner curves squarer than outer ones;
- round strokes pass the baseline and the x, cap, ascender and descender lines (overshoot);
- a curve that leaves a stem thins towards the join, so n, b, d, a do not darken there;
- diagonals taper on the inside into sharp vertices, so v, w, M, N do not fill in.
"""
import math

import pathops

import build as b


class Pen:
    """Stroke widths for one glyph: V for vertical stems, H for horizontals."""

    def __init__(self, name, is_mark):
        self.name = name
        self.mark = is_mark
        self.hs0 = b.HS                                # half-width the skeleton was drawn for
        self.V = b.STROKE * b.WEIGHT.get(name, 1.0)
        self.H = self.V * b.H_RATIO


# ---------------------------------------------------------------- straight strokes

def line_width(d, pen):
    """Stroke width perpendicular to a segment with unit direction d."""
    w = pen.H + (pen.V - pen.H) * d[1] ** 2
    return w * (1 - b.DIAG_THIN * (2 * d[0] * d[1]) ** 2)


def line_halfwidths(p0, p1, pen):
    """(left, right) half-widths of a straight segment, left = +90 degrees from its direction.

    A horizontal stroke drawn against a guide line keeps its outer edge on the line
    and loses its weight on the inside, so E, T, z stay exactly cap or x-height tall."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    n = math.hypot(dx, dy)
    d = (dx / n, dy / n)
    w = line_width(d, pen)
    left = right = w / 2
    if abs(d[1]) < 0.05 and not pen.mark:
        y = (p0[1] + p1[1]) / 2
        for g in b.GUIDES:
            if abs(y - (g - pen.hs0)) < 1:             # stroke hangs from the line: upper edge on it
                up, down = pen.hs0, w - pen.hs0
                break
            if abs(y - (g + pen.hs0)) < 1:             # stroke stands on the line: lower edge on it
                up, down = w - pen.hs0, pen.hs0
                break
        else:
            return left, right
        left, right = (up, down) if d[0] > 0 else (down, up)
    return left, right


# ---------------------------------------------------------------- curves

def _quadrant(q, ax, by, k):
    """Cubic for quadrant q (0: 0-90 degrees, counter-clockwise) of a squared ellipse."""
    pts = {0: [(ax, 0), (ax, k * by), (k * ax, by), (0, by)],
           1: [(0, by), (-k * ax, by), (-ax, k * by), (-ax, 0)],
           2: [(-ax, 0), (-ax, -k * by), (-k * ax, -by), (0, -by)],
           3: [(0, -by), (k * ax, -by), (ax, -k * by), (ax, 0)]}
    return pts[q]


def _bez(c, t):
    u = 1 - t
    return (u ** 3 * c[0][0] + 3 * u * u * t * c[1][0] + 3 * u * t * t * c[2][0] + t ** 3 * c[3][0],
            u ** 3 * c[0][1] + 3 * u * u * t * c[1][1] + 3 * u * t * t * c[2][1] + t ** 3 * c[3][1])


def _split(c, t0, t1):
    """Sub-curve of cubic c between parameters t0 < t1 (de Casteljau, twice)."""
    def left(c, t):
        p01, p12, p23 = _lerp(c[0], c[1], t), _lerp(c[1], c[2], t), _lerp(c[2], c[3], t)
        p012, p123 = _lerp(p01, p12, t), _lerp(p12, p23, t)
        mid = _lerp(p012, p123, t)
        return [c[0], p01, p012, mid], [mid, p123, p23, c[3]]
    _, right = left(c, t0)
    if t1 >= 1:
        return right
    seg, _ = left(right, (t1 - t0) / (1 - t0))
    return seg


def _lerp(p, q, t):
    return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)


def _param(c, ax, by, q, phi):
    """Parameter on quadrant cubic c whose normalised polar angle is phi (0..90 within q)."""
    if phi <= 0:
        return 0.0
    if phi >= 90:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        x, y = _bez(c, mid)
        a = (math.degrees(math.atan2(y / by, x / ax)) - 90 * q) % 360
        if a > 300:
            a -= 360
        lo, hi = (mid, hi) if a < phi else (lo, mid)
    return (lo + hi) / 2


class Radii:
    """Radii of one contour of an arc, per side: right, top, left, bottom."""

    def __init__(self, right, top, left, bottom, k):
        self.r = (right, top, left, bottom)
        self.k = k

    def quad(self, q):
        ax = self.r[0] if q in (0, 3) else self.r[2]
        by = self.r[1] if q in (0, 1) else self.r[3]
        return ax, by

    def piece(self, t0, t1):
        """Cubic of this contour between angles t0 < t1 lying in one quadrant (relative to centre)."""
        q = math.floor(t0 / 90 + 1e-9) % 4
        base = math.floor(t0 / 90 + 1e-9) * 90
        ax, by = self.quad(q)
        c = _quadrant(q, ax, by, self.k)
        u0, u1 = _param(c, ax, by, q, t0 - base), _param(c, ax, by, q, t1 - base)
        return _split(c, u0, u1)

    def point(self, t):
        q = math.floor(t / 90) % 4
        ax, by = self.quad(q)
        c = _quadrant(q, ax, by, self.k)
        return _bez(c, _param(c, ax, by, q, t - math.floor(t / 90) * 90))


def _covers(a, ang):
    lo, hi = min(a.a0, a.a1), max(a.a0, a.a1)
    return any(lo <= ang + 360 * k <= hi for k in (-2, -1, 0, 1, 2))


def arc_radii(a, pen, flat_top=False, flat_bottom=False):
    """Outer and inner Radii of an arc. Sides carry the stem weight V, top and bottom the
    horizontal weight H; a stroke that touches a guide line keeps its outer edge there
    and, unless a straight stroke continues from it, passes the line by the overshoot."""
    V, H = pen.V, pen.H
    out = [a.rx + V / 2, a.ry + H / 2, a.rx + V / 2, a.ry + H / 2]
    if not pen.mark:
        top, bottom = a.cy + a.ry + pen.hs0, a.cy - a.ry - pen.hs0
        if _covers(a, 90) and any(abs(top - g) < 1 for g in b.GUIDES):
            out[1] = a.ry + pen.hs0 + (0 if flat_top else b.OVERSHOOT)
        if _covers(a, 270) and any(abs(bottom - g) < 1 for g in b.GUIDES):
            out[3] = a.ry + pen.hs0 + (0 if flat_bottom else b.OVERSHOOT)
    inn = [out[0] - V, out[1] - H, out[2] - V, out[3] - H]
    return Radii(*out, b.TENSION_OUT), Radii(*inn, b.TENSION_IN)


# ---------------------------------------------------------------- joins of curves and stems

def stems_near(polylines, own):
    """Vertical straight segments of the other strokes: the stems a curve can join."""
    out = []
    for j, pts in enumerate(polylines):
        if j == own:
            continue
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if abs(x1 - x0) < 1 and abs(y1 - y0) > b.STROKE:
                out.append((x0, min(y0, y1), max(y0, y1)))
    return out


def thinning(a, stems, pen):
    """Weight multiplier along arc a (function of the angle), 1 away from any stem.

    Only stems the arc stays on one side of count: a stroke crossing a curve (the bar of
    $ or the cent sign) is not a join."""
    reach = b.JOIN_REACH * pen.V / b.STROKE
    lo, hi = min(a.a0, a.a1), max(a.a0, a.a1)
    angles = [lo + (hi - lo) * i / 72 for i in range(73)]
    use = []
    for x, y0, y1 in stems:
        near = []
        for t in angles:
            px, py = a.point(t)
            dy = max(y0 - py, 0, py - y1)
            if math.hypot(px - x, dy) < reach:
                near.append(px - x)
        if near and (min(near) > -3 or max(near) < 3):
            use.append((x, y0, y1))
    if not use:
        return None

    def mult(t):
        px, py = a.point(t)
        d = min(math.hypot(px - x, max(y0 - py, 0, py - y1)) for x, y0, y1 in use)
        s = max(0.0, 1 - d / reach)
        return 1 - b.JOIN_THIN * s * s * (3 - 2 * s)    # smoothstep
    return mult


def fit_cubic(pts, t0, t3):
    """Least-squares cubic through angle-uniform sample points: ends fixed, handle directions
    t0 (out of the start) and t3 (out of the end, backwards) fixed, handle lengths fitted."""
    p0, p3 = pts[0], pts[-1]
    us = [i / (len(pts) - 1) for i in range(len(pts))]
    a11 = a12 = a22 = r1 = r2 = 0.0
    for u, p in zip(us, pts):
        b1, b2 = 3 * (1 - u) ** 2 * u, 3 * (1 - u) * u * u
        base = ((1 - u) ** 3 + b1, b2 + u ** 3)
        rx = p[0] - (base[0] * p0[0] + base[1] * p3[0])
        ry = p[1] - (base[0] * p0[1] + base[1] * p3[1])
        v1, v2 = (b1 * t0[0], b1 * t0[1]), (b2 * t3[0], b2 * t3[1])
        a11 += v1[0] ** 2 + v1[1] ** 2
        a12 += v1[0] * v2[0] + v1[1] * v2[1]
        a22 += v2[0] ** 2 + v2[1] ** 2
        r1 += v1[0] * rx + v1[1] * ry
        r2 += v2[0] * rx + v2[1] * ry
    det = a11 * a22 - a12 * a12
    chord = math.hypot(p3[0] - p0[0], p3[1] - p0[1])
    if abs(det) < 1e-9:
        l1 = l2 = chord / 3
    else:
        l1, l2 = (r1 * a22 - r2 * a12) / det, (a11 * r2 - a12 * r1) / det
        if l1 <= 0 or l2 <= 0:
            l1 = l2 = chord / 3
    return [p0, (p0[0] + t0[0] * l1, p0[1] + t0[1] * l1), (p3[0] + t3[0] * l2, p3[1] + t3[1] * l2), p3]


def _axis_dir(p, q, t):
    """Direction from p towards q, made exactly horizontal or vertical when p sits on an axis angle."""
    d = _unit((q[0] - p[0], q[1] - p[1]))
    if abs(t / 90 - round(t / 90)) > 1e-6:
        return d
    if round(t / 90) % 2 == 0:                       # 0 or 180 degrees: the curve runs vertically here
        return (0.0, 1.0 if d[1] > 0 else -1.0)
    return (1.0 if d[0] > 0 else -1.0, 0.0)


def _unit(v):
    n = math.hypot(*v)
    return (v[0] / n, v[1] / n)


# ---------------------------------------------------------------- arc outlines

def breaks(a0, a1):
    """Split an angle range at the axis angles, so every curve piece ends on an extremum."""
    lo, hi = min(a0, a1), max(a0, a1)
    cuts = [k * 90 for k in range(math.ceil(lo / 90 + 1e-9), math.floor(hi / 90 - 1e-9) + 1)]
    pts = [lo] + [c for c in cuts if lo < c < hi] + [hi]
    return list(zip(pts[:-1], pts[1:]))


def _offset(cx, cy, p):
    return (cx + p[0], cy + p[1])


def end_points(a, outer, inner, mult, t):
    """Outer and inner outline points of arc a at angle t."""
    po, pi = _offset(a.cx, a.cy, outer.point(t)), _offset(a.cx, a.cy, inner.point(t))
    if mult is not None:
        pi = _lerp(po, pi, mult(t))
    return po, pi


def arc_paths(a, outer, inner, mult, lo, hi):
    """Annular pieces of arc a between angles lo < hi (pathops paths)."""
    out = []
    for t0, t1 in breaks(lo, hi):
        p = pathops.Path()
        oc = [_offset(a.cx, a.cy, q) for q in outer.piece(t0, t1)]
        p.moveTo(*oc[0])
        p.cubicTo(*oc[1], *oc[2], *oc[3])
        if mult is None or min(mult(t0 + (t1 - t0) * i / 8) for i in range(9)) > 0.999:
            ic = [_offset(a.cx, a.cy, q) for q in inner.piece(t0, t1)]
            p.lineTo(*ic[3])
            p.cubicTo(*ic[2], *ic[1], *ic[0])
        else:
            n = max(6, int((t1 - t0) / 3))
            pts = [end_points(a, outer, inner, mult, t0 + (t1 - t0) * i / n)[1] for i in range(n + 1)]
            # piece ends lie on axis angles (extrema): their handles stay horizontal or vertical
            c = fit_cubic(pts, _axis_dir(pts[0], pts[1], t0), _axis_dir(pts[-1], pts[-2], t1))
            p.lineTo(*c[3])
            p.cubicTo(*c[2], *c[1], *c[0])
        p.close()
        out.append(p)
    return out
