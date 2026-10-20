"""Grid search over H and M shape parameters to reduce amino-acid letter confusion.

Similarity proxy: cosine similarity of Gaussian-blurred glyph renders (blur simulates
small on-screen size). Lower = more distinguishable. Objective: the worst (highest)
pair among the 20 standard amino-acid letters.
"""
import itertools
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build as b  # noqa: E402

AA = "ARNDCQEGHILKMFPSTWYV"


def sims(path):
    f = ImageFont.truetype(path, 64)
    try:  # variable fonts: compare everyone at Regular (wght 400)
        axes = f.get_variation_axes()
        f.set_variation_by_axes([400 if str(a.get("name", "")).lower().find("weight") >= 0 else a["default"]
                                 for a in axes])
    except Exception:
        pass
    v = {}
    for c in AA:
        im = Image.new("L", (90, 110), 0)
        ImageDraw.Draw(im).text((15, 10), c, font=f, fill=255)
        a = np.asarray(im.filter(ImageFilter.GaussianBlur(5)), float).ravel()
        v[c] = a / np.linalg.norm(a)
    return {x + y: float(v[x] @ v[y]) for x, y in itertools.combinations(AA, 2)}


def variant(hbar, mdepth, splay):
    g = dict(b.G)
    g["H"] = b.P((b.L, b.B), (b.L, b.T)) + b.P((b.R, b.B), (b.R, b.T)) + b.P((b.L, hbar), (b.R, hbar))
    g["M"] = b.P((b.L - splay * 0.3, b.B), (b.L + splay, b.T), (b.M, mdepth), (b.R - splay, b.T),
                 (b.R + splay * 0.3, b.B))
    return g


def main(tmp):
    rows = []
    for hbar, md, sp in itertools.product([280, 350, 420, 480], [110, 230, 350, 470], [0, 35]):
        path = os.path.join(tmp, "v.ttf")
        b.build(path, variant(hbar, md, sp))
        s = sims(path)
        worst = max(s, key=s.get)
        rows.append((s[worst], worst, hbar, md, sp, s["HM"], s["NH"], s["NM"], s["MW"]))
    rows.sort()
    print("worst  pair  Hbar Mdep splay   HM    HN    MN    MW")
    for r in rows[:8] + rows[-3:]:
        print(f"{r[0]:.3f}  {r[1]}   {r[2]:4} {r[3]:4} {r[4]:4}   {r[5]:.3f} {r[6]:.3f} {r[7]:.3f} {r[8]:.3f}")


if __name__ == "__main__":
    main(sys.argv[1])
