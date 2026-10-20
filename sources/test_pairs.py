"""Compare confusable character pairs across all fonts in a folder.

Same proxy as before: cosine similarity of Gaussian-blurred renders (lower = more
distinguishable). Variable fonts are measured at Regular (wght 400).
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

GROUPS = {
    "upper (seq)": ["CG", "GU", "GS", "DG", "QG", "NH", "HM", "NM"],
    "lower": ["il", "l1", "i1", "ıl", "ıi", "Il", "I1", "l|", "bd", "pq", "bp", "dq",
              "ao", "oe", "ce", "ae", "un", "hn", "hb", "gq", "qy", "nr"],
    "digits": ["G6", "O0", "o0", "1l", "5S", "8B", "2Z", "6b", "9q", "9g"],
}


def load(path):
    f = ImageFont.truetype(path, 64)
    try:
        axes = f.get_variation_axes()
        f.set_variation_by_axes([400 if str(a.get("name", "")).lower().find("weight") >= 0 else a["default"]
                                 for a in axes])
    except Exception:
        pass
    return f


def vec(f, ch):
    im = Image.new("L", (90, 130), 0)
    ImageDraw.Draw(im).text((15, 15), ch, font=f, fill=255)
    a = np.asarray(im.filter(ImageFilter.GaussianBlur(5)), float).ravel()
    return a / np.linalg.norm(a)


def main(folder, mine):
    fonts = sorted(x for x in os.listdir(folder) if x.endswith(".ttf"))
    data = {}
    for fn in fonts:
        f = load(os.path.join(folder, fn))
        cache = {}
        get = lambda c: cache.setdefault(c, vec(f, c))  # noqa: E731
        data[fn] = {p: float(get(p[0]) @ get(p[1])) for g in GROUPS.values() for p in g}
    others = [fn for fn in fonts if fn != mine]
    for gname, pairs in GROUPS.items():
        print(f"\n== {gname}")
        print("pair   mine   others(min..max)  rank")
        for p in pairs:
            m = data[mine][p]
            o = [data[fn][p] for fn in others]
            rank = 1 + sum(v < m for v in o)
            print(f"{p:5}  {m:.3f}  {min(o):.3f}..{max(o):.3f}     {rank}/{len(fonts)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
