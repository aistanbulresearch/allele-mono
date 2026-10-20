"""Search G, 6 and 9 shapes against all uppercase-sequence letters and digits together."""
import itertools, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build as b
from test_pairs import load, vec

SET = list("ARNDCQEGHILKMFPSTWYVUO") + list("0123456789")


def all_pairs(path):
    f = load(path); v = {c: vec(f, c) for c in SET}
    return {x + y: float(v[x] @ v[y]) for x, y in itertools.combinations(SET, 2)}


def g_shape(a0, bar_x, spur_low):
    s = b.chain(b.arc(b.M, b.MID, b.RX, b.RY, a0, 345), [(b.R, 270), (b.R, 340), (bar_x, 340)])
    if spur_low:   # spur continues below the curve: a straight right edge 6 does not have
        s += b.P((b.R, 340), (b.R, b.B))
    return s


SIX = {"curved": [b.arc(b.M, 230, b.RX, 230 - b.B, 0, 360)] + [b.arc(330, b.MID, 200, b.RY, 180, 60)],
       "straight": [b.arc(b.M, 230, b.RX, 230 - b.B, 0, 360)] + b.P((160, 330), (400, b.T))}
NINE = {"curved": [b.arc(b.M, 470, b.RX, b.T - 470, 0, 360)] + [b.arc(270, b.MID, 200, b.RY, 0, -120)],
        "straight": [b.arc(b.M, 470, b.RX, b.T - 470, 0, 360)] + b.P((440, 370), (200, b.B))}


def main(tmp):
    rows = []
    for a0, bx, spur, six in itertools.product([30, 42, 55], [230, 285, 330], [0, 1], ["curved", "straight"]):
        g = dict(b.G); g["G"] = g_shape(a0, bx, spur)
        b.DIG["six"], b.DIG["nine"] = SIX[six], NINE[six]
        p = os.path.join(tmp, "v.ttf"); b.build(p, g); s = all_pairs(p)
        top = sorted(s.items(), key=lambda kv: -kv[1])[:4]
        rows.append((top[0][1], a0, bx, spur, six, s["G6"], s["CG"], s["GS"], s["DG"],
                     " ".join(f"{k}{v:.3f}" for k, v in top)))
    rows.sort()
    for r in rows[:8]:
        print(f"max {r[0]:.3f} a0={r[1]} bar={r[2]} spur={r[3]} six={r[4]:8} | G6 {r[5]:.3f} CG {r[6]:.3f} GS {r[7]:.3f} DG {r[8]:.3f} | {r[9]}")


if __name__ == "__main__":
    main(sys.argv[1])
