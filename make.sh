#!/bin/sh
# Build Allele Mono.
#   1. sources/ufo_build.py turns the glyph skeletons (sources/build.py) into the UFO source
#   2. fontmake compiles the UFO to TrueType
#   3. ttfautohint adds hinting
# Usage: sh make.sh        (needs: pip install -r requirements.txt)
set -e
cd "$(dirname "$0")"
mkdir -p build fonts/ttf
python3 sources/ufo_build.py sources/AlleleMono-Regular.ufo
fontmake -u sources/AlleleMono-Regular.ufo -o ttf --output-path build/AlleleMono-Regular.unhinted.ttf
python3 -c "from ttfautohint import ttfautohint; ttfautohint(in_file='build/AlleleMono-Regular.unhinted.ttf', out_file='fonts/ttf/AlleleMono-Regular.ttf')"
echo "built fonts/ttf/AlleleMono-Regular.ttf"
