#!/usr/bin/env python3
"""Get crop boxes right: a labelled grid to read coordinates from, and a preview of every crop in a spec.
Requires Pillow.

  python3 crop_helper.py grid screens/02-home.png            # → 02-home.grid.png (5 % lines, labels every 10 %)
  python3 crop_helper.py grid screens/*.png --step 0.025      # finer grid
  python3 crop_helper.py check set.json -o crops.jpg          # draws every callout / zoom crop on its screen,
                                                              # plus the cropped pieces, one row per shot

Boxes are fractions of the screen image: [x0, y0, x1, y1]. Read them off the grid, then run `check` and look:
a crop should end between rows of UI, never through text, a card or a button.
"""
import argparse
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.normpath(os.path.join(HERE, "..", "assets", "fonts", "Inter-Medium.otf"))
COLORS = [(255, 59, 48), (0, 199, 190), (255, 204, 0), (88, 86, 214), (52, 199, 89), (255, 149, 0)]


def font(size):
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        return ImageFont.load_default()


def grid(path, step, out=None):
    im = Image.open(path).convert("RGB")
    W, H = im.size
    over = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    f = font(max(12, W // 45))
    n = int(round(1 / step))
    for i in range(1, n):
        v = i * step
        major = abs((v * 10) - round(v * 10)) < 1e-6
        col = (255, 40, 120, 200) if major else (255, 40, 120, 90)
        wdt = 2 if major else 1
        x, y = int(v * W), int(v * H)
        d.line([(x, 0), (x, H)], fill=col, width=wdt)
        d.line([(0, y), (W, y)], fill=col, width=wdt)
        if major:
            lab = f"{v:.1f}"
            d.rectangle([x + 2, 2, x + 2 + f.getlength(lab) + 6, 2 + f.size + 6], fill=(0, 0, 0, 170))
            d.text((x + 5, 4), lab, font=f, fill=(255, 255, 255, 255))
            d.rectangle([2, y + 2, 2 + f.getlength(lab) + 6, y + 2 + f.size + 6], fill=(0, 0, 0, 170))
            d.text((5, y + 4), lab, font=f, fill=(255, 255, 255, 255))
    res = Image.alpha_composite(im.convert("RGBA"), over).convert("RGB")
    out = out or os.path.splitext(path)[0] + ".grid.png"
    res.save(out)
    return out


def boxes_of(shot):
    out = []
    for c in shot.get("callouts", []):
        out.append(("callout", c["crop"]))
    if shot.get("layout") == "zoom":
        for b in shot.get("crops") or [shot.get("crop", [0, 0, 1, 0.5])]:
            out.append(("zoom", b))
    return out


def check(spec_path, out):
    spec_dir = os.path.dirname(os.path.abspath(spec_path))
    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)
    rows = []
    for i, shot in enumerate(spec["shots"], start=1):
        boxes = boxes_of(shot)
        screen = shot.get("screen")
        if isinstance(screen, dict):  # multi-locale: show the first locale's screen
            screen = next(iter(screen.values()))
        if not boxes or not screen:
            continue
        im = Image.open(os.path.join(spec_dir, screen)).convert("RGB")
        W, H = im.size
        marked = im.copy()
        d = ImageDraw.Draw(marked)
        pieces = []
        for k, (kind, b) in enumerate(boxes):
            col = COLORS[k % len(COLORS)]
            px = (int(b[0] * W), int(b[1] * H), int(b[2] * W), int(b[3] * H))
            d.rectangle(px, outline=col, width=max(3, W // 200))
            pieces.append((kind, b, col, im.crop(px)))
        rows.append((i, screen, marked, pieces))
    if not rows:
        sys.exit("no callouts or zoom crops in this spec")
    th = 520
    f = font(18)
    rendered = []
    for i, screen, marked, pieces in rows:
        m = marked.resize((int(marked.width * th / marked.height), th))
        parts = [m]
        for kind, b, col, pc in pieces:
            k = min(420 / pc.width, th / pc.height, 1.6)
            p_ = pc.resize((max(1, int(pc.width * k)), max(1, int(pc.height * k))))
            parts.append(p_)
        width = sum(p.width for p in parts) + 16 * (len(parts) + 1)
        row = Image.new("RGB", (max(width, 600), th + 70), (246, 246, 244))
        rd = ImageDraw.Draw(row)
        rd.text((16, 10), f"shot {i} · {os.path.basename(screen)}", font=f, fill=(30, 30, 30))
        x = 16
        for j, p_ in enumerate(parts):
            row.paste(p_, (x, 40))
            if j:
                kind, b, col, _ = pieces[j - 1]
                rd.rectangle([x - 3, 37, x + p_.width + 2, 42 + p_.height], outline=col, width=3)
                rd.text((x, 44 + p_.height + 2), f"{kind} {b}", font=font(14), fill=(80, 80, 80))
            x += p_.width + 16
        rendered.append(row)
    sheet = Image.new("RGB", (max(r.width for r in rendered), sum(r.height for r in rendered)), (246, 246, 244))
    y = 0
    for r in rendered:
        sheet.paste(r, (0, y))
        y += r.height
    sheet.save(out, quality=88)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("grid", help="draw a labelled coordinate grid on screens")
    g.add_argument("images", nargs="+")
    g.add_argument("--step", type=float, default=0.05)
    c = sub.add_parser("check", help="preview every crop box in a spec")
    c.add_argument("spec")
    c.add_argument("-o", "--output", default="crops.jpg")
    a = p.parse_args()
    if a.cmd == "grid":
        for img in a.images:
            print(grid(img, a.step))
    else:
        print(check(a.spec, a.output))


if __name__ == "__main__":
    main()
