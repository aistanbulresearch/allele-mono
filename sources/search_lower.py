"""Search a, e, p, q shapes against every lowercase pair (and digits).

Objective: the worst (highest) blurred-cosine similarity over all pairs of
a-z, dotless i and 0-9, so a fix for one pair cannot silently create another
(the G/6 lesson).
"""
import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build as b  # noqa: E402
from test_pairs import load, vec  # noqa: E402

SET = list("abcdefghijklmnopqrstuvwxyz") + ["ı"] + list("0123456789")
WATCH = ["eo", "ao", "ae", "ce", "bp", "dq", "bd", "pq", "gq", "qy"]  # keys in alphabetical order


def pairs(path):
    f = load(path)
    v = {c: vec(f, c) for c in SET}
    return {x + y: float(v[x] @ v[y]) for x, y in itertools.combinations(SET, 2)}


def a_shape(bowl_top, hook_start):
    cy = (bowl_top + b.B) / 2
    return (b.chain(b.arc(b.M, 360, b.RX, b.XT - 360, hook_start, 0), [(b.R, 360), (b.R, b.B)])
            + [b.arc(285, cy, 145, cy - b.B, 0, 360)] + b.P((285, bowl_top), (b.R, bowl_top)))


def e_shape(bar_y, end_angle):
    return b.P((b.L, bar_y), (b.R, bar_y)) + [b.arc(b.M, b.XM, b.RX, b.XRY, 3, end_angle)]


def pq_shapes(serif):
    p = b.P((b.L, b.XT), (b.L, b.DT)) + [b.arc(320, b.XM, 150, b.XRY, 0, 360)]
    q = b.P((b.R, b.XT), (b.R, b.DT)) + [b.arc(280, b.XM, 150, b.XRY, 0, 360)]
    if serif:
        p += b.P((b.L - 50, b.DT), (b.L + 110, b.DT))
        q += b.P((b.R - 110, b.DT), (b.R + 50, b.DT))
    return p, q


def main(tmp):
    path = os.path.join(tmp, "lo.ttf")
    b.build(path)
    base = pairs(path)
    top = sorted(base.items(), key=lambda kv: -kv[1])[:5]
    print("current  | worst5:", " ".join(f"{k}{v:.3f}" for k, v in top), "|", " ".join(f"{k}{base[k]:.3f}" for k in WATCH))
    rows = []
    orig = dict(b.LC)
    for bar, end, btop, hook, serif in itertools.product([250, 270, 290], [300, 320, 340], [240, 278],
                                                         [140, 160], [0, 1]):
        b.LC.update(orig)
        b.LC["e"] = e_shape(bar, end)
        b.LC["a"] = a_shape(btop, hook)
        b.LC["p"], b.LC["q"] = pq_shapes(serif)
        b.build(path)
        s = pairs(path)
        top = sorted(s.items(), key=lambda kv: -kv[1])[:5]
        rows.append((top[0][1], sum(s[k] for k in WATCH) / len(WATCH), bar, end, btop, hook, serif, top, s))
    b.LC.update(orig)
    rows.sort(key=lambda r: (round(r[0], 3), r[1]))
    for r in rows[:6]:
        print(f"max {r[0]:.3f} watch-mean {r[1]:.3f} | e bar={r[2]} end={r[3]} a top={r[4]} hook={r[5]} pq_serif={r[6]}"
              f" | worst5: " + " ".join(f"{k}{v:.3f}" for k, v in r[7]) + " | "
              + " ".join(f"{k}{r[8][k]:.3f}" for k in WATCH))


if __name__ == "__main__":
    main(sys.argv[1])
