# Changelog

## 1.100

Optical corrections. Until 1.002 every stroke was expanded with one constant width, which
measures even but does not look even. The outline generator now applies the corrections
type designers make by hand (`sources/optics.py`, parameters in `sources/build.py`):

- Horizontal strokes are thinner than stems (0.88 of the stem); diagonals are a little thinner.
- Round strokes overshoot the baseline and the x, cap, ascender and descender lines by 11 units.
- Curves are squarer than a true ellipse, and counters squarer than outer curves.
- A curve thins where it leaves a stem (n m h u a b d p q g r), so the joins no longer darken.
- Diagonals taper on the inside into sharp vertices (v w A V W M N Z 4 7).
- m, M, W, w and other crowded glyphs are drawn lighter.
- Curve ends are cut horizontally or vertically, one rule for every terminal.
- Every glyph is centred optically in its cell (`sources/spacing.py`); accents and anchors follow.

Shapes:

- b, d, p, q, g and thorn: the bowl shares the stem's centre line, so the stem keeps its weight.
- S, s and 3: the top bowl is smaller than the bottom one.
- H and N widths are closer to O, with N still clearly wider than H (checked with the
  blurred-pair measurement).
- e: the bar meets the bowl in a square corner.
- Dots are squares of one family of sizes; the colon's dots sit on the x-height and the baseline.

Before/after measurements against six popular monospaces are in
`documentation/optics_metrics.md`; the legibility results for this version are in
`documentation/legibility_results.txt`.

## 1.002

- i, j: dot shifted left for optical balance.

## 1.001

- Indian rupee sign.

## 1.000

- First release: GF Latin Core plus auxiliary European letters, mark positioning, R-form r (ss01).
