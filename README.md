# Allele Mono

An open monospace typeface for reading DNA, RNA and protein sequences, and code.

In biology, alleles are variant forms of a gene that look alike but must be told apart.
Allele Mono is built around the same problem: letters that look alike at small sizes
(C and G, H and M, b and d, i and dotless i) are drawn so they stay distinguishable in
dense sequence alignments, FASTA files and source code.

Designed by Ozge A. Cavus, AIstanbul Research Group.

AI disclosure: an AI assistant wrote the build code that generates the outlines
and ran the legibility measurements. The designer set the goals and selected and approved every
design decision.

Licensed under the [SIL Open Font License 1.1](OFL.txt).

## Status

**Version 1.002.**

- Character set: the full Google Fonts minimum set, GF Latin Core (319 characters), plus the
  auxiliary letters of several European orthographies (for example Dutch IJ, Catalan L with
  middle dot, long s), a dotted circle and an R-form r alternate. Accented letters are
  components; combining accents are zero-width and placed with a mark feature (any accent on
  any letter), a second accent stacks above the first, and i and j lose their dot under an
  accent. See [documentation/specimen_all.png](documentation/specimen_all.png).
- Outlines are true cubic curves with points on extrema, built from a UFO source with fontmake.
- Autohinted with ttfautohint.

## Used in

- [ggmsa](https://github.com/YuLab-SMU/ggmsa) (R/Bioconductor, multiple sequence alignment plots):
  `ggmsa(..., font = "AlleleMono")`. Added in
  [YuLab-SMU/ggmsa#77](https://github.com/YuLab-SMU/ggmsa/pull/77); the glyph polygons are
  exported with `sources/export_ggmsa_glyphs.py`.
- [UGENE](https://github.com/ugeneunipro/ugene) Alignment Editor, as an installed system font:
  install `AlleleMono-Regular.ttf`, restart UGENE, open an alignment, then
  Actions > Appearance > Fonts > Allele Mono
  ([ugeneunipro/ugene#1968](https://github.com/ugeneunipro/ugene/issues/1968)).
  UGENE's Sequence View uses a fixed font.

## Design decisions

Every decision below was measured against eleven popular monospace fonts from Google Fonts
and checked by eye at 12 px (see [Measuring legibility](#measuring-legibility)).

| Letters | Decision |
|---|---|
| C / G | C has a wide aperture; G has a short bar and a straight spur down to the baseline |
| G / 6, 9 | 6 and 9 have straight diagonal stems |
| H / M / N / W | M has a shallow middle vertex, W a low one; H is a little narrower than O and N a little wider, so the open triangles of N stay visible without breaking the rhythm of capital sequences |
| F / P | F has short arms and a lower middle arm, so it stays open where P has its bowl |
| D / G / Q | D has short shoulders and a wide bowl; Q's tail drops from the bottom and turns right |
| i / dotless i / l / 1 / I | i has a large dot; l has a tail to the right; 1 has a flag and no base bar |
| b / d / p / q | p and q have descender serifs that cross the stem; the bowls share the stem's centre line, so the stem keeps its weight |
| a / e / o | a has a small, open bowl that runs flat into the stem; e has a raised bar and a wide aperture |
| O / 0 | zero is narrower than O and dotted (not slashed, to avoid confusion with Ø) |

### Stylistic set 1: R-form r

`ss01` replaces r with a small-capital R form. It is off by default because in code and
in soft-masked sequence files the case of a letter carries meaning, and the R form is
measurably closer to capital R.

Turn it on with `font-feature-settings: "ss01";` in CSS, or `"editor.fontLigatures": "'ss01'"`
in VS Code.

## Measuring legibility

`sources/test_pairs.py` renders each letter, blurs it to simulate small on-screen sizes, and
reports the cosine similarity between letter pairs (lower means easier to tell apart),
comparing against other fonts in a folder. Results for this version are in
[documentation/legibility_results.txt](documentation/legibility_results.txt).

This is a rough proxy, not a reading study. It missed at least one real problem
(an earlier G that read as 6 at 12 px), so every change was also checked by eye.
A claim that Allele Mono is easier to read needs a study with human readers.

The `sources/search_*.py` scripts are the parameter searches used to choose the shapes above.

## How the font is made

Each glyph is described in `sources/build.py` as a skeleton: centre lines made of straight
segments and elliptical arcs, drawn for one stem width.
`sources/ufo_build.py` turns the skeletons into outlines: straight segments become
quadrilaterals, arcs become pieces between an outer and an inner curve (true Bezier curves,
split at the axis angles so every curve ends on an extremum), corners get mitre joins,
straight ends square caps and curved ends a horizontal or vertical cut.
The pieces are merged with a boolean union and written to the UFO source
`sources/AlleleMono-Regular.ufo`, which any font editor can open.

Strokes of one constant width measure even but do not look even, so the expansion applies
the usual optical corrections (`sources/optics.py`, parameters in the "optical corrections"
block of `sources/build.py`):

- horizontal strokes are thinner than stems (0.88), diagonals a little thinner;
- round strokes pass the baseline and the x, cap, ascender and descender lines by 11 units;
- curves are squarer than a true ellipse, counters squarer than outer curves;
- a curve thins towards a stem it joins (n, m, h, u, a, b, d, p, q, g, r);
- diagonals taper on the inside into sharp vertices (v, w, A, V, W, M, N, Z, 4, 7);
- crowded glyphs (m, M, W, w) are lighter overall.

`sources/spacing.py` then centres each letter and figure optically in its cell: it compares
the white space on both sides, row by row with a depth limit, and moves the drawing
sideways (accents and anchors move with it). i, j, l and 1 keep their drawn positions.

The UFO is generated, so **edit `sources/build.py`, not the UFO**: rebuilding overwrites
manual changes to the UFO.

`sources/build.py` can also write a quick polygon-outline prototype on its own
(`python3 sources/build.py out.ttf`); the search scripts use it.

## Building

The repository follows the [Google Fonts project template](https://github.com/googlefonts/googlefonts-project-template).

```sh
make ufo     # regenerate sources/AlleleMono-Regular.ufo after editing sources/build.py
make build   # compile the UFO with gftools builder into fonts/ttf and fonts/webfonts
make test    # check the fonts with fontspector (needs: cargo binstall fontspector)
python3 sources/specimen.py   # redraw documentation/specimen_all.png
```

`make` creates a Python virtual environment from `requirements.txt` on first use.
GitHub Actions runs the same build and fontspector check on every push.

## License

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is available with a FAQ at https://openfontlicense.org
