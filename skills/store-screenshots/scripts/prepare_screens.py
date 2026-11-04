#!/usr/bin/env python3
"""Prepare raw app screens before rendering: check them, clean the status bar, cover debug UI. Requires Pillow.

  python3 prepare_screens.py screens/ --out prepared/                      # check + copy as PNG
  python3 prepare_screens.py screens/ --out prepared/ --status-bar 9:41    # same status bar on every screen
  python3 prepare_screens.py screens/ --out prepared/ --cover 05-home.jpg:0.62,0.085,0.88,0.13

Checks every screen and prints a report:
  - resolution (warns below 1080 px wide: soft when scaled into a 1206 px canvas)
  - aspect ratio vs. iPhone (2.17) and common Android ratios; mixed ratios in one set
  - JPEG source (prefer the original PNG)
  - status-bar consistency (time/battery differ between screens - detected roughly by comparing the bars)
  - thin demo data: the same figure ("48,2 B", "27,5%") three or more times on one screen - read with
    tesseract if it is installed (skipped otherwise; --no-ocr to skip)

--status-bar TIME   repaints the status bar band (top 6.2 % of the height) with the colour sampled under it
                    and draws TIME, signal, Wi-Fi and a full battery in a matching light/dark colour. Screens
                    whose bar sits on a photo or gradient are skipped (repainting would show) - capture those
                    with a clean bar instead (simulator: xcrun simctl status_bar booted override --time 9:41).
--cover FILE:x0,y0,x1,y1   fills a box (fractions of the screen) with the colour around it - for debug
                    buttons, test banners or personal data. Repeatable. Covering is simplifying, not inventing:
                    never use it to remove something the app really shows to users.

Writes PNGs to --out (same names, .png) and prepared/report.json. Point the spec's "screen" paths there.
"""
import argparse
import collections
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.normpath(os.path.join(HERE, "..", "assets", "fonts", "InterDisplay-SemiBold.otf"))
def pixels(im):
    return list(im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata())


EXT = re.compile(r"\.(png|jpe?g|webp)$", re.I)
IPHONE = 2556 / 1179
ANDROID = [16 / 9, 2.0, 20 / 9, 2.1]


def band_box(im):
    return (0, 0, im.width, int(im.height * 0.062))


def band_uniformity(im):
    """Std-dev of the status bar band with the text masked out roughly (bright/dark outliers ignored)."""
    band = im.crop(band_box(im)).convert("RGB").resize((60, 8))
    px = pixels(band)
    lum = sorted(0.3 * r + 0.59 * g + 0.11 * b for r, g, b in px)
    core = lum[int(len(lum) * 0.15): int(len(lum) * 0.75)]  # drop glyph pixels at both ends
    mean = sum(core) / len(core)
    return (sum((v - mean) ** 2 for v in core) / len(core)) ** 0.5, mean


def sample_bg(im, box):
    """Median colour of a thin frame just outside the box."""
    x0, y0, x1, y1 = box
    pad = max(4, int(im.width * 0.01))
    pts = []
    for (a, b, c, d) in ((x0 - pad, y0 - pad, x1 + pad, y0), (x0 - pad, y1, x1 + pad, y1 + pad),
                         (x0 - pad, y0, x0, y1), (x1, y0, x1 + pad, y1)):
        a, b, c, d = max(0, a), max(0, b), min(im.width, c), min(im.height, d)
        if c > a and d > b:
            pts += pixels(im.crop((a, b, c, d)).convert("RGB"))
    if not pts:
        return (0, 0, 0)
    return tuple(sorted(p[k] for p in pts)[len(pts) // 2] for k in range(3))


def draw_status_bar(im, time_text):
    W, H = im.size
    x0, y0, x1, y1 = band_box(im)
    bg = sample_bg(im, (int(W * 0.35), int(y1 * 0.3), int(W * 0.65), int(y1 * 0.9)))
    d = ImageDraw.Draw(im)
    d.rectangle([x0, y0, x1, y1], fill=bg)
    lum = 0.3 * bg[0] + 0.59 * bg[1] + 0.11 * bg[2]
    ink = (250, 250, 250) if lum < 140 else (12, 12, 12)
    s = W / 402  # points -> pixels (iPhone logical width 402 pt)
    base = y1 * 0.72
    try:
        f = ImageFont.truetype(FONT, int(17 * s))
    except OSError:
        f = ImageFont.load_default()
    tw = f.getlength(time_text)
    d.text((W * 0.155 - tw / 2 + 14 * s, base), time_text, font=f, fill=ink, anchor="ls")
    # signal bars
    bx = W * 0.705
    for i, hgt in enumerate((4, 6, 8.5, 11)):
        d.rounded_rectangle([bx + i * 5 * s, base - hgt * s, bx + i * 5 * s + 3.2 * s, base], radius=s, fill=ink)
    # wifi: three arcs
    wx, wy = W * 0.79, base + 0.5 * s
    for r in (11.5, 7.5, 3.6):
        d.arc([wx - r * s, wy - r * s * 1.05, wx + r * s, wy + r * s * 0.95], 225, 315, fill=ink, width=max(2, int(2.1 * s)))
    d.ellipse([wx - 1.6 * s, wy - 3.2 * s, wx + 1.6 * s, wy], fill=ink)
    # battery, full
    bx0, by0 = W * 0.845, base - 11.5 * s
    d.rounded_rectangle([bx0, by0, bx0 + 25 * s, by0 + 12 * s], radius=int(3.5 * s), outline=ink, width=max(1, int(1.2 * s)))
    d.rounded_rectangle([bx0 + 2 * s, by0 + 2 * s, bx0 + 23 * s, by0 + 10 * s], radius=int(2 * s), fill=ink)
    d.rounded_rectangle([bx0 + 26 * s, by0 + 4 * s, bx0 + 27.6 * s, by0 + 8 * s], radius=int(s), fill=ink)
    return im


# a figure a screen would show: 48,2 B · 12.5K · 1,2 Mn · 87% · 3,4 bin · 4.8 - not clock times or dates
FIGURE = re.compile(r"(?<![\d:./,])(\d{1,3}(?:[.,]\d{1,2})?\s?(?:B|K|M|Mn|bin|milyon|%)(?![A-Za-zçğıöşüÇĞİÖŞÜ])|%\s?\d{1,3}(?:[.,]\d)?"
                    r"|\d{1,3}[.,]\d{1,2}(?![\d:./]))")


def ocr_langs():
    exe = shutil.which("tesseract")
    if not exe:
        return None, None
    try:
        out = subprocess.run([exe, "--list-langs"], capture_output=True, text=True, timeout=20).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return None, None
    langs = "+".join(l for l in ("eng", "tur") if l in out) or None
    return exe, langs


def repeated_figures(im, exe, langs, times=3):
    """Figures that appear `times`+ times on one screen - a sign the demo data was copy-pasted."""
    g = im.convert("L")
    if g.width < 1400:
        g = g.resize((g.width * 2, g.height * 2))
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "s.png")
        g.save(path)
        try:
            text = subprocess.run([exe, path, "-", "-l", langs, "--psm", "11"], capture_output=True, text=True,
                                  timeout=120).stdout
        except (OSError, subprocess.SubprocessError):
            return []
    norm = [re.sub(r"\s+", " ", m.group(0).strip()).replace(" %", "%") for m in FIGURE.finditer(text)]
    return [(f, n) for f, n in collections.Counter(norm).most_common() if n >= times]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("inputs", nargs="+", help="screen files or folders")
    p.add_argument("--out", default="prepared")
    p.add_argument("--status-bar", metavar="TIME", help="repaint a clean status bar with this time, e.g. 9:41")
    p.add_argument("--cover", action="append", default=[], metavar="FILE:x0,y0,x1,y1")
    p.add_argument("--no-ocr", action="store_true", help="skip the demo-data check (tesseract)")
    a = p.parse_args()
    exe, langs = (None, None) if a.no_ocr else ocr_langs()

    files = []
    for i in a.inputs:
        files += sorted(f for f in glob.glob(os.path.join(i, "*")) if EXT.search(f)) if os.path.isdir(i) else [i]
    if not files:
        sys.exit("no screens found")
    covers = {}
    for c in a.cover:
        name, _, box = c.rpartition(":")
        covers.setdefault(os.path.basename(name), []).append([float(v) for v in box.split(",")])
    os.makedirs(a.out, exist_ok=True)

    report, ratios, bars = [], [], []
    for f in files:
        im = Image.open(f).convert("RGB")
        W, H = im.size
        r = H / W
        ratios.append(round(r, 3))
        notes = []
        if W < 1080:
            notes.append(f"{W} px wide - will be upscaled ~{1206 * 0.78 / W:.2f}x; ask for the original full-resolution PNG")
        if f.lower().endswith((".jpg", ".jpeg")):
            notes.append("JPEG - fine, but the original PNG is sharper (shared screenshots are usually recompressed)")
        if abs(r - IPHONE) / IPHONE > 0.02 and not any(abs(r - x) / x < 0.02 for x in ANDROID):
            notes.append(f"unusual aspect ratio {r:.3f} (iPhone is {IPHONE:.3f}) - cropped or a screen recording?")
        if exe and langs:
            for fig, n in repeated_figures(im, exe, langs)[:3]:
                notes.append(f"demo data looks thin: \"{fig}\" appears {n} times on this screen - seed varied, plausible "
                             "numbers (and more than one sample behind any 'best' or 'winner')")
        sd, mean = band_uniformity(im)
        bars.append(im.crop(band_box(im)).resize((80, 6)).convert("L"))
        for box in covers.get(os.path.basename(f), []):
            px = (int(box[0] * W), int(box[1] * H), int(box[2] * W), int(box[3] * H))
            ImageDraw.Draw(im).rectangle(px, fill=sample_bg(im, px))
            notes.append(f"covered {box}")
        if a.status_bar:
            if sd < 7:
                draw_status_bar(im, a.status_bar)
                notes.append(f"status bar repainted ({a.status_bar}, full battery)")
            else:
                notes.append("status bar sits on an image/gradient - not repainted (capture with a clean bar)")
        dest = os.path.join(a.out, os.path.splitext(os.path.basename(f))[0] + ".png")
        im.save(dest, optimize=True)
        report.append({"file": os.path.basename(f), "out": dest, "size": [W, H], "ratio": round(r, 3), "notes": notes})

    # status bars that differ between screens (time / battery changes show up as differences)
    diffs = []
    for i in range(1, len(bars)):
        a_px, b_px = pixels(bars[0]), pixels(bars[i])
        diffs.append(sum(abs(x - y) for x, y in zip(a_px, b_px)) / len(a_px))
    print(f"{len(files)} screens → {a.out}" + ("" if exe and langs or a.no_ocr else
                                                 "   (no tesseract: demo-data check skipped)"))
    for r_ in report:
        print(f"- {r_['file']}: {r_['size'][0]}x{r_['size'][1]} (ratio {r_['ratio']})")
        for n in r_["notes"]:
            print(f"    · {n}")
    if len(set(round(x, 2) for x in ratios)) > 1:
        print(f"! mixed aspect ratios {sorted(set(ratios))} - screens from different devices look uneven side by side")
    if not a.status_bar and diffs and max(diffs) > 6:
        print("! status bars differ between screens (time/battery). Re-capture with a fixed bar, or run with --status-bar 9:41")
    with open(os.path.join(a.out, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
