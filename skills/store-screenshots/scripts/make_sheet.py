#!/usr/bin/env python3
"""Contact sheets: one row per app/folder, screenshots side by side in order. Requires Pillow.

  python3 make_sheet.py --rows out/ios ../competitor-shots -o sheet.jpg
  python3 make_sheet.py --raw raw/ --out sheets/ --pdf all.pdf     # maintainers: one sheet per country/category
"""
import argparse
import glob
import json
import os
import sys
import re

from PIL import Image, ImageDraw, ImageFont

THUMB_W = 180
GAP = 10
LABEL_H = 34
BG = (246, 246, 244)
INK = (30, 30, 30)
MUTED = (120, 120, 120)
EXT = re.compile(r"\.(png|jpe?g|webp)$", re.I)


def font(size):
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "/usr/share/fonts/TTF/DejaVuSans.ttf",
                 "/System/Library/Fonts/Supplemental/Arial.ttf",
                 "C:/Windows/Fonts/arial.ttf"):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def files_in(folder):
    return sorted(f for f in glob.glob(os.path.join(folder, "*")) if EXT.search(f) and not os.path.basename(f).startswith("_"))


def load_row(src, width=THUMB_W):
    files = src if isinstance(src, (list, tuple)) else files_in(src)
    thumbs = []
    for f in files:
        im = Image.open(f).convert("RGB")
        thumbs.append(im.resize((width, round(im.height * width / im.width)), Image.LANCZOS))
    return thumbs


def build(rows, title, out, width=THUMB_W):
    """rows: list of (label, folder-or-list-of-files)."""
    loaded = [(label, load_row(src, width)) for label, src in rows]
    loaded = [(l, t) for l, t in loaded if t]
    if not loaded:
        return False
    max_cols = max(len(t) for _, t in loaded)
    sheet_w = GAP + max_cols * (width + GAP)
    heights = [LABEL_H + max(im.height for im in t) + GAP for _, t in loaded]
    sheet = Image.new("RGB", (sheet_w, 56 + sum(heights)), BG)
    d = ImageDraw.Draw(sheet)
    d.text((GAP, 14), title, fill=INK, font=font(22))
    y = 56
    for (label, thumbs), h in zip(loaded, heights):
        d.text((GAP, y + 8), label, fill=MUTED, font=font(15))
        x = GAP
        for im in thumbs:
            sheet.paste(im, (x, y + LABEL_H))
            x += width + GAP
        y += h
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    sheet.save(out, quality=82, optimize=True)
    return True


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--rows", nargs="+", help="folders, one row each")
    p.add_argument("-o", "--output", default="sheet.jpg")
    p.add_argument("--title", default="Contact sheet")
    p.add_argument("--width", type=int, default=THUMB_W)
    p.add_argument("--raw", help="maintainers: collected examples root (with manifest.json)")
    p.add_argument("--out", default="sheets", help="output folder for --raw mode")
    p.add_argument("--pdf", help="in --raw mode, also combine all sheets into this PDF")
    a = p.parse_args()

    if a.rows:
        build([(os.path.basename(os.path.normpath(r)), r) for r in a.rows], a.title, a.output, a.width)
        print(a.output)
        return
    if not a.raw:
        p.error("give --rows or --raw")
    with open(os.path.join(a.raw, "manifest.json"), encoding="utf-8") as f:
        records = json.load(f)
    groups = {}
    for r in records:
        folder = os.path.join(a.raw, os.path.dirname(r["file"]))
        groups.setdefault((r["country"], r["category"]), {})[folder] = f'{r["chart_rank"]}. {r["app"]}'
    built = []
    for (country, cat), folders in sorted(groups.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        rows = [(label, folder) for folder, label in sorted(folders.items())]
        out = os.path.join(a.out, f"{country}-{cat}.jpg")
        if build(rows, f"{country.upper()} · {cat}", out, a.width):
            built.append(out)
            print(out)
    if a.pdf and built:
        pages = [Image.open(f).convert("RGB") for f in built]
        pages[0].save(a.pdf, save_all=True, append_images=pages[1:], resolution=110, quality=80)
        print(f"{a.pdf} ({len(pages)} pages)")


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):  # Windows consoles and pipes default to a legacy code page
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    main()
