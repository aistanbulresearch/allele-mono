#!/bin/sh
# Build Allele Mono from the glyph skeletons in sources/build.py and autohint it.
# Usage: sh make.sh        (needs: pip install -r requirements.txt)
set -e
cd "$(dirname "$0")"
mkdir -p build fonts/ttf
python3 sources/build.py build/AlleleMono-Regular.unhinted.ttf
python3 -c "from ttfautohint import ttfautohint; ttfautohint(in_file='build/AlleleMono-Regular.unhinted.ttf', out_file='fonts/ttf/AlleleMono-Regular.ttf')"
echo "built fonts/ttf/AlleleMono-Regular.ttf"
