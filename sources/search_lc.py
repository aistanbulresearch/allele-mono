import itertools, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build as b
from test_pairs import load, vec
PAIRS = ["ıi", "i1", "il", "l1", "I1", "Il", "O0", "o0", "NH", "HM", "NM"]
def score(path):
    f = load(path); c = {}
    g = lambda ch: c.setdefault(ch, vec(f, ch))
    return {p: float(g(p[0]) @ g(p[1])) for p in PAIRS}
def main(TMP):
    rows = []
    for dot, one_base, zero_rx, hbar in itertools.product(["sq", "tall", "wide"], [1, 0], [170, 140], [350, 300]):
        d = {"sq": [(b.M, 620), (b.M, 640)], "tall": [(b.M, 600), (b.M, 670)], "wide": [(b.M - 20, 630), (b.M + 20, 630)]}[dot]
        b.LC["i"] = b.P((b.L + 40, b.XT), (b.M, b.XT), (b.M, b.B)) + b.P((b.L + 20, b.B), (b.R - 20, b.B)) + [d]
        b.DIG["one"] = b.P((b.M, b.T), (b.M, b.B)) + b.P((b.M, b.T), (b.L + 20, 560)) + (b.P((b.L + 20, b.B), (b.R - 20, b.B)) if one_base else [])
        b.DIG["zero"] = [b.arc(b.M, b.MID, zero_rx, b.RY, 0, 360)] + b.P((b.M, 290), (b.M, 410))
        g = dict(b.G); g["H"] = b.P((b.L, b.B), (b.L, b.T)) + b.P((b.R, b.B), (b.R, b.T)) + b.P((b.L, hbar), (b.R, hbar))
        p = os.path.join(TMP, "v.ttf"); b.build(p, g); s = score(p)
        rows.append((max(s.values()), dot, one_base, zero_rx, hbar, s))
    rows.sort(key=lambda r: r[0])
    for r in rows[:6]:
        print(f"max {r[0]:.3f} dot={r[1]:4} 1base={r[2]} zero_rx={r[3]} Hbar={r[4]} | " + " ".join(f"{k}{v:.3f}" for k, v in r[5].items()))


if __name__ == "__main__":
    main(sys.argv[1])