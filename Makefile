# Build Allele Mono (adapted from the Google Fonts project template).
#   make ufo    regenerate sources/AlleleMono-Regular.ufo from the glyph skeletons in sources/build.py
#   make build  compile the UFO with gftools builder (fontmake, ttfautohint, gftools fix, woff2)
#   make test   check the fonts with fontspector (googlefonts profile)
#   make proof  create HTML proofs with diffenator3
SOURCES=$(shell python3 scripts/read-config.py --sources )
FAMILY=$(shell python3 scripts/read-config.py --family )

help:
	@echo "###"
	@echo "# Build targets for $(FAMILY)"
	@echo "###"
	@echo
	@echo "  make ufo:    Regenerates the UFO source from sources/build.py"
	@echo "  make build:  Builds the fonts and places them in the fonts/ directory"
	@echo "  make test:   Tests the fonts with fontspector"
	@echo "  make proof:  Creates HTML proof documents in the out/proof directory"
	@echo

build: build.stamp

venv: venv/touchfile

venv/touchfile: requirements.txt
	test -d venv || python3 -m venv venv
	. venv/bin/activate; pip install -Ur requirements.txt
	touch venv/touchfile

ufo: venv
	. venv/bin/activate; python3 sources/ufo_build.py sources/AlleleMono-Regular.ufo

build.stamp: venv sources/config.yaml $(SOURCES)
	rm -rf fonts
	(for config in sources/config*.yaml; do . venv/bin/activate; gftools builder $$config; done)  && touch build.stamp

test: build.stamp
	which fontspector || (echo "fontspector not found. Please install it with 'cargo binstall fontspector'." && exit 1)
	TOCHECK=$$(find fonts/ttf -type f 2>/dev/null); mkdir -p out/ out/fontspector; fontspector --profile googlefonts -l warn --full-lists --succinct --html out/fontspector/fontspector-report.html --ghmarkdown out/fontspector/fontspector-report.md --badges out/badges $$TOCHECK  || echo '::warning file=sources/config.yaml,title=fontspector failures::The fontspector QA check reported errors in your font. Please check the generated report.'

proof: venv build.stamp
	which diff3proof || (echo "diff3proof not found. Please install it with 'cargo binstall diffenator3'." && exit 1)
	TOCHECK=$$(find fonts/ttf -type f 2>/dev/null); . venv/bin/activate; mkdir -p out/ out/proof; diff3proof $$TOCHECK --output out/proof

clean:
	rm -rf venv build.stamp out
	find . -name "*.pyc" -delete

.PHONY: help build ufo test proof clean
