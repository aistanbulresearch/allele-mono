"""Write documentation/specimen_all.png: every encoded character of the font, in code point order."""
import os
import sys
import unicodedata

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

FONT = sys.argv[1] if len(sys.argv) > 1 else "fonts/ttf/AlleleMono-Regular.ttf"
OUT = sys.argv[2] if len(sys.argv) > 2 else "documentation/specimen_all.png"
PER_ROW, PX = 26, 48

cps = [cp for cp in sorted(TTFont(FONT).getBestCmap())
       if unicodedata.category(chr(cp))[0] not in "CZ" and unicodedata.category(chr(cp)) != "Mn"]
rows = [cps[i:i + PER_ROW] for i in range(0, len(cps), PER_ROW)]
font = ImageFont.truetype(FONT, PX)
cell, line = PX * 0.6 + 12, int(PX * 1.75)
im = Image.new("L", (int(40 + cell * PER_ROW), 40 + line * len(rows)), 255)
draw = ImageDraw.Draw(im)
for r, row in enumerate(rows):
    for c, cp in enumerate(row):
        draw.text((20 + c * cell, 20 + r * line), chr(cp), font=font, fill=0)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
im.save(OUT, optimize=True)
print(f"{len(cps)} characters -> {OUT}")
