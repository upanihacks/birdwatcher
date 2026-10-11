#!/usr/bin/env python3
"""Rebuild the BMP font atlases in fonts/ (needs Pillow).

  python3 tools/build_fonts.py ShareTechMono-Regular.ttf VT323-Regular.ttf

Both fonts are on Google Fonts (SIL OFL). Each atlas is white-on-black, 16 glyphs per row,
plus a JSON file with the advance, cell height and ascent.
"""
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(__file__), '..', 'APPS', 'Birdwatcher', 'fonts')
CHARS = ''.join(chr(c) for c in range(32, 127)) + ''.join(chr(c) for c in range(160, 256)) + '…'
SIZES = {'M': [10, 11, 12, 13, 15, 16, 18, 20, 24, 32], 'V': [18, 20, 22, 26, 38, 48, 64]}


def make(ttf, size, out):
    f = ImageFont.truetype(ttf, size)
    asc, desc = f.getmetrics()
    adv = int(round(f.getlength('M')))
    h = asc + desc
    cols = 16
    rows = math.ceil(len(CHARS) / cols)
    im = Image.new('L', (cols * adv, rows * h), 0)
    d = ImageDraw.Draw(im)
    for i, c in enumerate(CHARS):
        d.text(((i % cols) * adv, (i // cols) * h), c, font=f, fill=255)
    im.convert('RGB').save(out + '.bmp')
    with open(out + '.json', 'w') as fh:
        json.dump({'adv': adv, 'h': h, 'ascent': asc, 'cols': cols, 'chars': CHARS}, fh, ensure_ascii=False)


mono, vt = sys.argv[1], sys.argv[2]
for kind, ttf in (('M', mono), ('V', vt)):
    for s in SIZES[kind]:
        make(ttf, s, os.path.join(OUT, '%s%d' % (kind, s)))
        print(kind, s)
