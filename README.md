# Allele Mono

An open monospace typeface for reading DNA, RNA and protein sequences, and code.

In biology, alleles are variant forms of a gene that look alike but must be told apart.
Allele Mono is built around the same problem: letters that look alike at small sizes
(C and G, H and M, b and d, i and dotless i) are drawn so they stay distinguishable in
dense sequence alignments, FASTA files and source code.

Designed by Ozge A. Cavus, AIstanbul Research Group.
Licensed under the [SIL Open Font License 1.1](OFL.txt).

## Status

**Draft, version 0.100. Not yet ready for Google Fonts submission.**

- Character set: 106 characters (A-Z, a-z, 0-9, Turkish letters, basic punctuation).
  The Google Fonts minimum (GF Latin Core) is 319.
- Outlines are true cubic curves with points on extrema, built from a UFO source with fontmake.
- Autohinted with ttfautohint.

## Design decisions

Every decision below was measured against eleven popular monospace fonts from Google Fonts
and checked by eye at 12 px (see [Measuring legibility](#measuring-legibility)).

| Letters | Decision |
|---|---|
| C / G | C has a wide aperture; G has a short bar and a straight spur down to the baseline |
| G / 6, 9 | 6 and 9 have straight diagonal stems |
| H / M / N / W | M has a shallow middle vertex, W a low one; H stems are slightly narrower |
| D / G / Q | D has short shoulders and a wide bowl; Q's tail drops from the bottom and turns right |
| i / dotless i / l / 1 / I | i has a large dot; l has a tail to the right; 1 has a flag and no base bar |
| b / d / p / q | p and q have descender serifs (q's points right only, away from g) |
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
segments and elliptical arcs, drawn with one constant stroke width.
`sources/ufo_build.py` turns the skeletons into outlines: straight segments become rectangles,
arcs become sectors between two concentric ellipses (true Bezier curves, split at the axis
angles so every curve ends on an extremum), corners get mitre joins and open ends square caps.
The pieces are merged with a boolean union and written to the UFO source
`sources/AlleleMono-Regular.ufo`, which any font editor can open.

The UFO is generated, so **edit `sources/build.py`, not the UFO**: rebuilding overwrites
manual changes to the UFO.

`sources/build.py` can also write a quick polygon-outline prototype on its own
(`python3 sources/build.py out.ttf`); the search scripts use it.

## Building

```sh
pip install -r requirements.txt
sh make.sh
```

This regenerates the UFO, compiles it with fontmake, autohints it, and writes
`fonts/ttf/AlleleMono-Regular.ttf`.

## License

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is available with a FAQ at https://openfontlicense.org
