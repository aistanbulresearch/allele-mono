"""Draw the images of documentation/article/ from the built font.

Usage: python3 sources/article_images.py [fonts/ttf/AlleleMono-Regular.ttf] [documentation/article]
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = sys.argv[1] if len(sys.argv) > 1 else "fonts/ttf/AlleleMono-Regular.ttf"
OUT = sys.argv[2] if len(sys.argv) > 2 else "documentation/article"
INK, GREY, RULE, MARK = (24, 35, 42), (107, 118, 124), (213, 217, 219), (223, 240, 239)

ALIGNMENT = [
    ("seq_01", "GCTAAAGACGATTACATAACATAGGCGTCAGCACGAAATTTGTTGGCTCAGTGTGA"),
    ("seq_02", "GCTAAAGACAATTACATAACATACTCGTCAGCACGAAAGTTGTTGGCCCAGTGTGA"),
    ("seq_03", "GCTAAAGACAATTACATA---TACACGTCAGCACGAAACTTGTTGGCCCAGTGTGA"),
    ("seq_04", "GCTAAAGACTATTACATAACATATACGTCANNNNNNAACTTGTTGGCGCAGTGTGA"),
    ("seq_05", "GCTAAAGACAATTACATAACATAGTCGTCAGCACGAAAATTGTTGGCGCAGTGTGA"),
    ("seq_06", "GCTAAAGACCATTARATAACATAGGCGTCAGCACGAAAGTTYTTGGCCCAGTGTGA"),
    ("seq_07", "GCTAAAGACAATTACATAACATACGCGTCAGCACGAAACTTGTTggcccagtgtga"),
]
GROUPS = ["C G", "D G Q", "H M N W", "F P", "O 0", "b d p q", "i ı l 1 I", "a e o", "rn m"]
SMALL = ["ACGTNNRYKMSWHBDV  CCGGCGGCCG", "MKHRLFPEDNQGSTYVWCAI", "il1I| O0 bdpq rn m ğışİ"]


def font(size):
    return ImageFont.truetype(FONT, size)


def alignment():
    big, small = font(44), font(28)
    cell = 44 * 0.6
    x0, y0, row = 310, 95, 69
    img = Image.new("RGB", (1913, 772), "white")
    d = ImageDraw.Draw(img)
    d.text((60, 30), "Multiple sequence alignment (illustrative)", font=small, fill=GREY)
    seqs = [s for _, s in ALIGNMENT]
    for c in range(len(seqs[0])):
        letters = {s[c].upper() for s in seqs} - {"-", "N"}
        if len(letters) > 1:                       # a variant column
            d.rectangle([x0 + c * cell - 2, y0 - 12, x0 + (c + 1) * cell + 2, y0 + row * len(seqs) - 12], fill=MARK)
    for i, (name, seq) in enumerate(ALIGNMENT):
        d.text((60, y0 + i * row), name, font=big, fill=GREY)
        d.text((x0, y0 + i * row), seq, font=big, fill=INK)
    d.text((60, 615), "IUPAC codes  R Y K M S W B D H V N", font=small, fill=INK)
    d.text((780, 615), "protein  MKHRLFPEDNQGSTYVWCAI", font=small, fill=INK)
    d.text((60, 675), "variant columns highlighted; NNNNNN = unknown bases; lowercase = soft-masked repeat",
           font=font(24), fill=GREY)
    return img


def pairs():
    img = Image.new("RGB", (2000, 900), "white")
    d = ImageDraw.Draw(img)
    d.text((60, 30), "Letters that are easy to confuse, drawn apart", font=font(30), fill=GREY)
    for k, group in enumerate(GROUPS):
        x, y = 60 + (k % 3) * 627, 120 + (k // 3) * 250
        d.rounded_rectangle([x, y, x + 597, y + 220], radius=16, outline=RULE, width=2)
        big = font(min(120, int(540 / (0.6 * len(group)))))      # long groups set smaller to fit
        w = d.textlength(group, font=big)
        d.text((x + (597 - w) / 2, y + 110), group, font=big, fill=INK, anchor="lm")
    return img


def small_sizes():
    img = Image.new("RGB", (2000, 755), "white")
    d = ImageDraw.Draw(img)
    d.text((60, 30), "Checked at 11 to 14 px, and blurred to simulate a low-resolution screen",
           font=font(30), fill=GREY)
    d.text((190, 100), "sharp", font=font(24), fill=GREY)
    d.text((1120, 100), "blurred", font=font(24), fill=GREY)
    y = 155
    for px in (11, 12, 14):
        step = round(px * 1.55)
        lines = Image.new("RGB", (300, step * 3), "white")
        ld = ImageDraw.Draw(lines)
        for i, line in enumerate(SMALL):
            ld.text((0, i * step), line, font=font(px), fill=INK)
        sharp = lines.resize((lines.width * 3, lines.height * 3), Image.NEAREST)   # shown at 3x
        blurred = lines.filter(ImageFilter.GaussianBlur(0.8)).resize(sharp.size, Image.BILINEAR)
        d.text((60, y), f"{px} px", font=font(24), fill=GREY)
        img.paste(sharp, (190, y))
        img.paste(blurred, (1120, y))
        y += sharp.height + 24
    return img


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, make in (("alignment", alignment), ("pairs", pairs), ("small-sizes", small_sizes)):
        make().save(os.path.join(OUT, name + ".png"), optimize=True)
        print("wrote", os.path.join(OUT, name + ".png"))
