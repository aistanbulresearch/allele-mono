# Optical metrics, 1.002 and 1.100

Produced by `sources/measure_optics.py` on renders at 1000 px per em (1 px = 1 font unit),
Regular weight (wght 400 for variable fonts). The reference fonts are popular monospaces;
Consolas is not on Google Fonts and is included only as a familiar baseline.

- **O os, o os**: overshoot of O past the cap height and baseline, of o past the x-height and baseline.
- **H bar/stem, o top/side**: thickness of horizontal strokes relative to vertical ones.
- **m stem**: stem width of m (the n stem is 80 to 90 in every font).
- **n join/stem**: vertical thickness of the n shoulder just inside the stem, relative to the stem.
- **H w, o w**: ink widths.
- **lc evenness**: coefficient of variation of the ink of a to z (lower = more even colour).

| font | O os | o os | H bar/stem | o top/side | m stem | n join/stem | H w | o w | lc evenness (CV) |
|---|---|---|---|---|---|---|---|---|---|
| AlleleMono 1.002 | 0 | 0 | 1.00 | 1.00 | 84 | 1.62 | 334 | 424 | 0.226 |
| AlleleMono 1.100 | 11 | 11 | 0.88 | 0.88 | 76 | 1.01 | 384 | 424 | 0.205 |
| JetBrainsMono | 10 | 8 | 0.91 | 0.89 | 83 | 0.79 | 414 | 430 | 0.150 |
| IBMPlexMono | 12 | 12 | 0.87 | 0.81 | 74 | 0.56 | 440 | 468 | 0.174 |
| FiraMono | 11 | 11 | 0.82 | 0.76 | 77 | 0.89 | 434 | 454 | 0.194 |
| SourceCodePro | 12 | 12 | 0.86 | 0.80 | 82 | 0.82 | 442 | 480 | 0.213 |
| DMMono | 12 | 12 | 0.90 | 0.93 | 83 | 1.25 | 507 | 480 | 0.194 |
| Consolas | 9 | 9 | 0.86 | 0.83 | 78 | 1.08 | 442 | 460 | 0.186 |
