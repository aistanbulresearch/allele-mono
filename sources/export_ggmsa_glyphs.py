"""Export Allele Mono outlines as ggmsa glyph polygons (x, y in em units, one ring per glyph).

Usage: python3 sources/export_ggmsa_glyphs.py fonts/ttf/AlleleMono-Regular.ttf allele_mono_glyphs.csv

Holes and separate pieces are joined to the first contour by a zero-width slit
(out to the nearest point and back the same way), so a single polygon draws
correctly with either fill rule.
"""
import csv, math, sys
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.basePen import decomposeQuadraticSegment

FONT, OUT = sys.argv[1], sys.argv[2]
CHARS = list("ARNDCEQGHILKMFPSTWYVUBJOXZ") + ["-", "."]
STEPS = 16

f = TTFont(FONT)
upm = f["head"].unitsPerEm
gs = f.getGlyphSet()
cmap = f.getBestCmap()

def contours(name):
    pen = DecomposingRecordingPen(gs)
    gs[name].draw(pen)
    out, cur, last = [], [], None
    for op, args in pen.value:
        if op == "moveTo":
            cur = [args[0]]; last = args[0]
        elif op == "lineTo":
            cur.append(args[0]); last = args[0]
        elif op == "curveTo":
            p0, (p1, p2, p3) = last, args
            for i in range(1, STEPS + 1):
                t = i / STEPS; u = 1 - t
                cur.append((u**3*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t**3*p3[0],
                            u**3*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t**3*p3[1]))
            last = p3
        elif op == "qCurveTo":
            for p1, p2 in decomposeQuadraticSegment(args):
                p0 = last
                for i in range(1, STEPS + 1):
                    t = i / STEPS; u = 1 - t
                    cur.append((u*u*p0[0] + 2*u*t*p1[0] + t*t*p2[0], u*u*p0[1] + 2*u*t*p1[1] + t*t*p2[1]))
                last = p2
        elif op in ("closePath", "endPath"):
            if cur and cur[0] != cur[-1]:
                cur.append(cur[0])
            out.append(cur); cur = []
    return out

def ring(cs):
    base = cs[0]
    pts = list(base)
    anchor = base[0]
    for c in cs[1:]:
        body = c[:-1]                      # closed contour without the repeated end point
        k = min(range(len(body)), key=lambda i: math.dist(body[i], anchor))
        loop = body[k:] + body[:k] + [body[k]]
        pts += loop + [anchor]             # slit out and back along the same line
    return pts

with open(OUT, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["char", "x", "y", "order"])
    for ch in CHARS:
        cs = contours(cmap[ord(ch)])
        # largest contour first, so the slits start from the outer shape
        cs.sort(key=lambda c: -abs(sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(c, c[1:]))))
        for i, (x, y) in enumerate(ring(cs), 1):
            w.writerow([ch, round(x / upm, 6), round(y / upm, 6), i])
print("ok", upm)
