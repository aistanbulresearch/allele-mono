"""Grid search over G, S and D shapes.

Objective: the worst (highest) blurred-cosine similarity over all pairs of the 20
amino-acid letters plus U, so nucleotide pairs (C/G, G/U) are protected too.
"""
import itertools
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build as b  # noqa: E402

LET = "ARNDCQEGHILKMFPSTWYVU"


def sims(path):
    f = ImageFont.truetype(path, 64)
    try:
        axes = f.get_variation_axes()
        f.set_variation_by_axes([400 if str(a.get("name", "")).lower().find("weight") >= 0 else a["default"]
                                 for a in axes])
    except Exception:
        pass
    v = {}
    for c in LET:
        im = Image.new("L", (90, 110), 0)
        ImageDraw.Draw(im).text((15, 10), c, font=f, fill=255)
        a = np.asarray(im.filter(ImageFilter.GaussianBlur(5)), float).ravel()
        v[c] = a / np.linalg.norm(a)
    return {x + y: float(v[x] @ v[y]) for x, y in itertools.combinations(LET, 2)}


def g_shape(a0, bar_x, stem):
    s = b.chain(b.arc(b.M, b.MID, b.RX, b.RY, a0, 345), [(b.R, 270), (b.R, 340), (bar_x, 340)])
    if stem:
        s += b.P((b.R, 340), (b.R, b.B))
    return s


def s_shape(t_up, t_low):
    return [b.arc(b.M, 505, 165, 153, t_up, 270) + b.arc(b.M, 197, 170, 155, 90, t_low)[1:]]


def d_shape(sh):
    rx = b.R - sh
    return b.P((b.L, b.B), (b.L, b.T)) + b.chain([(b.L, b.T), (sh, b.T)], b.arc(sh, b.MID, rx, b.RY, 90, -90),
                                               [(sh, b.B), (b.L, b.B)])


def main(tmp):
    path = os.path.join(tmp, "v.ttf")
    b.build(path)
    base = sims(path)
    top = sorted(base.items(), key=lambda kv: -kv[1])[:4]
    print("current:", " ".join(f"{k}{v:.3f}" for k, v in top))
    rows = []
    for a0, bx, stem, tu, tl, sh in itertools.product([30, 42, 55], [285, 230], [0, 1], [20, 40], [-160, -140],
                                                      [200, 250, 300]):
        g = dict(b.G)
        g["G"], g["S"], g["D"] = g_shape(a0, bx, stem), s_shape(tu, tl), d_shape(sh)
        b.build(path, g)
        s = sims(path)
        top = sorted(s.items(), key=lambda kv: -kv[1])[:4]
        rows.append((top[0][1], a0, bx, stem, tu, tl, sh, s["CG"], s["GS"], s["DG"],
                     " ".join(f"{k}{v:.3f}" for k, v in top)))
    rows.sort()
    print("worst  Ga0 Gbar stem Sup Slow Dsh    CG    GS    DG   top4")
    for r in rows[:8]:
        print(f"{r[0]:.3f}  {r[1]:3} {r[2]:4} {r[3]:4} {r[4]:3} {r[5]:4} {r[6]:3}  {r[7]:.3f} {r[8]:.3f} {r[9]:.3f}  {r[10]}")


if __name__ == "__main__":
    main(sys.argv[1])
