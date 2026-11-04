#!/usr/bin/env python3
"""Render a store screenshot set from one JSON spec. Requires Pillow.

  python3 render_set.py set.json --out out/            # every preset listed in spec "sizes"
  python3 render_set.py set.json --out out/ --size ios # one preset
  python3 render_set.py --presets                      # list sizes

Writes out/<preset>/01.png … (RGB, no alpha, exact pixels) and out/<preset>/_render.json (headlines,
fonts, warnings) that check_set.py reads. See templates/set.example.json for every option.

Layouts per shot: "device" (default) · "zoom" (cropped card) · "full" (full-bleed screen + band/pill caption)
· "poster" (type only). Headline emphasis: wrap words in *asterisks*.
"""
import argparse
import json
import os
import re
import sys

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:  # pragma: no cover
    sys.exit("Pillow is required: pip install pillow")

PRESETS = {  # checked 2026-11-04, see references/store-specs.md
    "ios": (1206, 2622),
    "ios-1179": (1179, 2556),
    "ios-large": (1320, 2868),
    "ios-faceid": (1284, 2778),
    "ipad": (2064, 2752),
    "android": (1080, 1920),
    "android-tall": (1080, 2160),
}

FONT_CANDIDATES = {
    "bold": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/opentype/noto/NotoSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ],
    "regular": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSans-Regular.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ],
}

DEFAULT_STYLE = {
    "background": {"color": "#F4F1EA"},
    "text_color": "#111111",
    "sub_color": None,  # defaults to text_color at 75 % opacity look
    "font": None,
    "sub_font": None,
    "align": "center",
    "case": "none",
    "headline_size": 0.092,  # fraction of canvas width (upper bound; auto-fit shrinks)
    "min_headline_size": 0.055,
    "max_lines": 2,
    "line_height": 1.1,
    "text_width": 0.84,
    "caption_top": 0.085,  # fraction of width from the top edge
    "sub_scale": 0.5,
    "emphasis": {"style": "color", "color": "#E4572E"},
    "device": {"width": 0.80, "radius": 0.11, "border": 0.016, "border_color": "#111111", "shadow": True, "gap": 0.07, "bleed": True},
    "card": {"radius": 0.045, "shadow": True, "width": 0.86},
    "band_color": None,
}


def hexrgb(h, alpha=False):
    h = h.lstrip("#")
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h)
    vals = tuple(int(h[i:i + 2], 16) for i in range(0, len(h), 2))
    if alpha:
        return vals if len(vals) == 4 else vals + (255,)
    return vals[:3]


def luminance(rgb):
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(x) for x in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def tr_upper(s):
    return s.replace("i", "İ").replace("ı", "I").upper()


REPLACE_KEYS = {"background"}  # these dicts are replaced, not merged (a gradient must not inherit a colour)


def merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict) and k not in REPLACE_KEYS:
            out[k] = merge(out[k], v)
        else:
            out[k] = v
    return out


class Fonts:
    def __init__(self, spec_dir):
        self.spec_dir = spec_dir
        self.cache = {}
        self.used = set()

    def resolve(self, path, kind):
        if path:
            p = path if os.path.isabs(path) else os.path.join(self.spec_dir, path)
            if os.path.exists(p):
                return p
            print(f"! font not found: {path} - falling back", file=sys.stderr)
        for c in FONT_CANDIDATES[kind]:
            if os.path.exists(c):
                return c
        return None

    def get(self, path, kind, size):
        p = self.resolve(path, kind)
        key = (p, size)
        if key not in self.cache:
            self.cache[key] = ImageFont.truetype(p, size) if p else ImageFont.load_default()
            self.used.add(p or "PIL default")
        return self.cache[key]


# ------------------------------------------------------------------ text

def tokenize(text):
    """'Kaldığın bölüm *hep hazır*.' -> [(word, emphasised, glued)], '\n' = forced break.
    glued = no space before this token (punctuation right after an emphasis marker)."""
    out, emph, prev_text = [], False, " "
    for part in re.split(r"(\*|\n)", text):
        if part == "*":
            emph = not emph
            continue
        if part == "\n":
            out.append(("\n", False, False))
            prev_text = " "
            continue
        words = part.split(" ")
        for i, w in enumerate(words):
            if w:
                glued = i == 0 and bool(out) and out[-1][0] != "\n" and not prev_text.endswith(" ")
                out.append((w, emph, glued))
        if part:
            prev_text = part
    return out


def wrap(tokens, measure, max_w):
    lines, cur = [], []
    for tok in tokens:
        if tok[0] == "\n":
            lines.append(cur)
            cur = []
            continue
        trial = cur + [tok]
        if cur and measure(trial) > max_w and not tok[2]:
            lines.append(cur)
            cur = [tok]
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


class Caption:
    def __init__(self, fonts, style, W, lang):
        self.fonts, self.s, self.W, self.lang = fonts, style, W, lang

    def prep(self, text):
        if self.s["case"] == "upper":
            text = tr_upper(text) if self.lang == "tr" else text.upper()
        return text

    def font_for(self, size, emph):
        e = self.s["emphasis"]
        if emph and e.get("style") == "font" and e.get("font"):
            return self.fonts.get(e["font"], "bold", size)
        return self.fonts.get(self.s["font"], "bold", size)

    def measure_line(self, line, size):
        space = self.font_for(size, False).getlength(" ")
        gaps = sum(1 for i, t in enumerate(line) if i > 0 and not t[2])
        return sum(self.font_for(size, t[1]).getlength(t[0]) for t in line) + space * gaps

    def layout(self, text, max_lines, max_size, min_size):
        tokens = tokenize(self.prep(text))
        max_w = self.W * self.s["text_width"]
        size = int(max_size)
        while True:
            lines = wrap(tokens, lambda l: self.measure_line(l, size), max_w)
            fits = len(lines) <= max_lines and all(self.measure_line(l, size) <= max_w for l in lines)
            if fits or size <= min_size:
                return lines, size, fits
            size = int(size * 0.95)

    def draw(self, img, text, top, max_lines=None, max_size=None, center_v=None, color=None):
        """Draw the headline; returns (bottom_y, size, warnings)."""
        s = self.s
        warnings = []
        max_lines = max_lines or s["max_lines"]
        max_size = max_size or s["headline_size"] * self.W
        lines, size, fits = self.layout(text, max_lines, max_size, s["min_headline_size"] * self.W)
        if not fits:
            warnings.append(f"headline doesn't fit {max_lines} lines even at minimum size: {text!r}")
        lh = int(size * s["line_height"])
        total_h = lh * len(lines)
        if center_v is not None:
            top = int(center_v - total_h / 2)
        d = ImageDraw.Draw(img)
        color = hexrgb(color or s["text_color"])
        e = s["emphasis"]
        space = self.font_for(size, False).getlength(" ")
        y = top
        for line in lines:
            lw = self.measure_line(line, size)
            x = (self.W - lw) / 2 if s["align"] == "center" else self.W * (1 - s["text_width"]) / 2
            # emphasis backgrounds first (contiguous runs)
            if e.get("style") in ("box", "marker"):
                cx, run = x, None
                for i, (w, em, g) in enumerate(line):
                    if i > 0 and not g:
                        cx += space
                    ww = self.font_for(size, em).getlength(w)
                    if em:
                        run = [cx, cx + ww] if run is None else [run[0], cx + ww]
                    if (not em or i == len(line) - 1) and run:
                        pad = size * 0.18
                        if e["style"] == "box":
                            d.rounded_rectangle([run[0] - pad, y - size * 0.02, run[1] + pad, y + size * 1.12],
                                                radius=int(size * 0.14), fill=hexrgb(e.get("color", "#FFFFFF")))
                        else:
                            d.rectangle([run[0] - pad * 0.5, y + size * 0.45, run[1] + pad * 0.5, y + size * 1.08],
                                        fill=hexrgb(e.get("color", "#FFE600")))
                        run = None
                    cx += ww
            cx = x
            for i, (w, em, g) in enumerate(line):
                if i > 0 and not g:
                    cx += space
                f = self.font_for(size, em)
                c = color
                if em and e.get("style") == "color":
                    c = hexrgb(e.get("color", "#E4572E"))
                if em and e.get("style") == "box" and e.get("text_color"):
                    c = hexrgb(e["text_color"])
                d.text((cx, y), w, font=f, fill=c)
                cx += f.getlength(w)
            y += lh
        return top + total_h, size, warnings

    def draw_sub(self, img, text, top, head_size, color=None):
        s = self.s
        size = int(head_size * s["sub_scale"])
        f = self.fonts.get(s["sub_font"], "regular", size)
        max_w = self.W * s["text_width"]
        tokens = [(w, False, False) for w in self.prep(text).split()]
        lines = wrap(tokens, lambda l: f.getlength(" ".join(t[0] for t in l)), max_w)[:3]
        d = ImageDraw.Draw(img)
        col = hexrgb(color or s["sub_color"] or s["text_color"])
        y = top
        for line in lines:
            t = " ".join(tok[0] for tok in line)
            lw = f.getlength(t)
            x = (self.W - lw) / 2 if s["align"] == "center" else self.W * (1 - s["text_width"]) / 2
            d.text((x, y), t, font=f, fill=col)
            y += int(size * 1.3)
        return y


# ------------------------------------------------------------------ images

def background(W, H, bg, spec_dir):
    if "image" in bg:
        src = Image.open(os.path.join(spec_dir, bg["image"])).convert("RGB")
        scale = max(W / src.width, H / src.height)
        src = src.resize((int(src.width * scale + 1), int(src.height * scale + 1)), Image.LANCZOS)
        x, y = (src.width - W) // 2, (src.height - H) // 2
        img = src.crop((x, y, x + W, y + H))
        if bg.get("overlay"):
            ov = Image.new("RGBA", (W, H), hexrgb(bg["overlay"], alpha=True))
            img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
        return img
    if "gradient" in bg:
        a, b = hexrgb(bg["gradient"][0]), hexrgb(bg["gradient"][1])
        grad = Image.new("RGB", (1, 256))
        for i in range(256):
            t = i / 255
            grad.putpixel((0, i), tuple(int(a[k] + (b[k] - a[k]) * t) for k in range(3)))
        return grad.resize((W, H), Image.BICUBIC)
    return Image.new("RGB", (W, H), hexrgb(bg.get("color", "#FFFFFF")))


def bg_reference_color(bg, caption_bottom=False):
    """The colour behind the caption, mirroring background(): image > gradient > colour."""
    if "image" in bg:
        return None
    if "gradient" in bg:
        return hexrgb(bg["gradient"][1 if caption_bottom else 0])
    if "color" in bg:
        return hexrgb(bg["color"])
    return None


def rounded_mask(size, radius):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255)
    return m


def shadow(canvas, box, radius, strength=0.28):
    x0, y0, x1, y1 = [int(v) for v in box]
    w, h = x1 - x0, y1 - y0
    blur = max(8, int(w * 0.035))
    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([x0, y0 + blur * 0.6, x1, y1 + blur * 0.6], radius=radius,
                                         fill=(0, 0, 0, int(255 * strength)))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    return Image.alpha_composite(canvas.convert("RGBA"), sh).convert("RGB")


def paste_rounded(canvas, img, xy, radius):
    canvas.paste(img, (int(xy[0]), int(xy[1])), rounded_mask(img.size, radius))


def load_screen(spec_dir, path):
    p = os.path.join(spec_dir, path)
    if not os.path.exists(p):
        raise FileNotFoundError(f"screen not found: {path}")
    return Image.open(p).convert("RGB")


def crop_frac(img, box):
    x0, y0, x1, y1 = box
    return img.crop((int(x0 * img.width), int(y0 * img.height), int(x1 * img.width), int(y1 * img.height)))


def draw_device(canvas, screen, s, W, H, top, bottom_limit=None):
    dv = s["device"]
    dw = int(W * dv["width"])
    border = int(dw * dv["border"])
    sw = dw - 2 * border
    scr = screen.resize((sw, int(screen.height * sw / screen.width)), Image.LANCZOS)
    dh = scr.height + 2 * border
    limit = bottom_limit if bottom_limit is not None else H - W * 0.06
    if not dv.get("bleed", True) and top + dh > limit:
        avail = limit - top
        k = avail / dh
        dw, border = int(dw * k), int(border * k)
        sw = dw - 2 * border
        scr = screen.resize((sw, int(screen.height * sw / screen.width)), Image.LANCZOS)
        dh = scr.height + 2 * border
    x = (W - dw) // 2
    r_out = int(dw * dv["radius"])
    if dv.get("shadow", True):
        canvas = shadow(canvas, (x, top, x + dw, top + dh), r_out)
    d = ImageDraw.Draw(canvas)
    if border > 0:
        d.rounded_rectangle([x, top, x + dw, top + dh], radius=r_out, fill=hexrgb(dv["border_color"]))
    paste_rounded(canvas, scr, (x + border, top + border), max(r_out - border, 0))
    return canvas, (x + border, top + border, sw / screen.width)


def draw_card(canvas, img, s, W, cx, cy, width_px):
    c = s["card"]
    k = width_px / img.width
    card = img.resize((int(img.width * k), int(img.height * k)), Image.LANCZOS)
    r = int(W * c["radius"])
    x, y = int(cx - card.width / 2), int(cy - card.height / 2)
    if c.get("shadow", True):
        canvas = shadow(canvas, (x, y, x + card.width, y + card.height), r, 0.32)
    paste_rounded(canvas, card, (x, y), r)
    return canvas


# ------------------------------------------------------------------ shots

def render_shot(shot, style, W, H, fonts, spec_dir, lang):
    s = merge(style, shot.get("style"))
    for k in ("background", "text_color", "sub_color", "align", "emphasis", "band_color", "device", "card", "case"):
        if k in shot:
            mergeable = k in ("emphasis", "device", "card") and isinstance(shot[k], dict) and isinstance(s.get(k), dict)
            s[k] = merge(s[k], shot[k]) if mergeable else shot[k]
    layout = shot.get("layout", "device")
    warnings = []
    canvas = background(W, H, s["background"], spec_dir)
    cap = Caption(fonts, s, W, lang)
    headline = shot.get("headline", "")
    pos = shot.get("caption_position", "top")

    if layout == "poster":
        bottom, size, w = cap.draw(canvas, headline, 0, max_lines=shot.get("max_lines", 4),
                                   max_size=W * shot.get("poster_size", 0.2), center_v=H * 0.45)
        warnings += w
        if shot.get("sub"):
            cap.draw_sub(canvas, shot["sub"], bottom + size * 0.4, size)
        return canvas, warnings, size

    if layout == "full":
        screen = load_screen(spec_dir, shot["screen"])
        k = max(W / screen.width, H / screen.height)
        scr = screen.resize((int(screen.width * k + 1), int(screen.height * k + 1)), Image.LANCZOS)
        canvas.paste(scr.crop(((scr.width - W) // 2, 0, (scr.width - W) // 2 + W, H)), (0, 0))
        mode = shot.get("caption_style", "band")
        tmp = Image.new("RGB", (W, H))
        b, size, w = cap.draw(tmp, headline, 0)
        warnings += w
        sub_h = int(size * s["sub_scale"] * 1.3 * 2) if shot.get("sub") else 0
        block = b + sub_h
        pad = int(W * 0.055)
        y0 = int(W * s["caption_top"]) if pos == "top" else H - block - int(W * s["caption_top"])
        d = ImageDraw.Draw(canvas)
        fill = hexrgb(s.get("band_color") or s["background"].get("color", "#111111"))
        if mode == "pill":
            d.rounded_rectangle([W * 0.05, y0 - pad, W * 0.95, y0 + block + pad], radius=int(W * 0.05), fill=fill)
        else:
            if pos == "top":
                d.rectangle([0, 0, W, y0 + block + pad], fill=fill)
            else:
                d.rectangle([0, y0 - pad, W, H], fill=fill)
        bottom, size, _ = cap.draw(canvas, headline, y0)
        if shot.get("sub"):
            cap.draw_sub(canvas, shot["sub"], bottom + size * 0.25, size)
        return canvas, warnings, size

    # caption first (device / zoom)
    top = int(W * s["caption_top"])
    if pos == "bottom":
        tmp = Image.new("RGB", (W, H))
        b, size, w = cap.draw(tmp, headline, 0)
        sub_h = int(size * s["sub_scale"] * 1.3 * 2 + size * 0.3) if shot.get("sub") else 0
        top = H - int(W * s["caption_top"]) - b - sub_h
    bottom, size, w = cap.draw(canvas, headline, top)
    warnings += w
    if shot.get("sub"):
        bottom = cap.draw_sub(canvas, shot["sub"], bottom + size * 0.3, size)
    ref = bg_reference_color(s["background"], pos == "bottom")
    if ref and contrast(hexrgb(s["text_color"]), ref) < 4.5:
        warnings.append(f"low headline contrast {contrast(hexrgb(s['text_color']), ref):.1f}:1 (aim ≥ 4.5)")

    if layout == "zoom":
        screen = load_screen(spec_dir, shot["screen"])
        piece = crop_frac(screen, shot.get("crop", [0, 0, 1, 0.5]))
        area_top = bottom + W * 0.05 if pos == "top" else W * 0.06
        area_bot = H - W * 0.06 if pos == "top" else top - W * 0.05
        width_px = W * s["card"]["width"]
        max_h = area_bot - area_top
        if piece.height * width_px / piece.width > max_h:
            width_px = max_h * piece.width / piece.height
        canvas = draw_card(canvas, piece, s, W, W / 2, (area_top + area_bot) / 2, width_px)
        return canvas, warnings, size

    # device
    screen = load_screen(spec_dir, shot["screen"])
    if pos == "top":
        dev_top = int(bottom + W * s["device"]["gap"])
    else:
        # caption at the bottom: the device ends above it and bleeds off the top edge if it's tall
        dv = s["device"]
        dw = int(W * dv["width"])
        bw = int(dw * dv["border"])
        dh = int(screen.height * (dw - 2 * bw) / screen.width) + 2 * bw
        dev_top = int(top - W * dv["gap"] - dh)
        if not dv.get("bleed", True):
            dev_top = max(dev_top, int(W * 0.06))
    limit = None if pos == "top" else top - W * s["device"]["gap"]
    canvas, (sx, sy, k) = draw_device(canvas, screen, s, W, H, dev_top, limit)
    for co in shot.get("callouts", []):
        piece = crop_frac(screen, co["crop"])
        scale = co.get("scale", 1.2)
        width_px = piece.width * k * scale
        cx = W * co.get("x", 0.5)
        if "y" in co:
            cy = H * co["y"]
        else:
            cy = sy + (co["crop"][1] + co["crop"][3]) / 2 * screen.height * k
        canvas = draw_card(canvas, piece, s, W, cx, cy, width_px)
    return canvas, warnings, size


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("spec", nargs="?")
    p.add_argument("--out", default="out")
    p.add_argument("--size", help="render only this preset (or WxH)")
    p.add_argument("--presets", action="store_true")
    a = p.parse_args()
    if a.presets:
        for k, (w, h) in PRESETS.items():
            print(f"{k:13} {w} x {h}")
        return
    if not a.spec:
        p.error("spec is required")
    spec_dir = os.path.dirname(os.path.abspath(a.spec))
    with open(a.spec, encoding="utf-8") as f:
        spec = json.load(f)
    style = merge(DEFAULT_STYLE, spec.get("style"))
    lang = spec.get("lang", "en")
    sizes = [a.size] if a.size else spec.get("sizes", ["ios"])
    fonts = Fonts(spec_dir)
    exit_code = 0
    for name in sizes:
        if name in PRESETS:
            W, H = PRESETS[name]
        elif re.fullmatch(r"\d+x\d+", name):
            W, H = map(int, name.split("x"))
        else:
            sys.exit(f"unknown size {name!r}; use --presets")
        out_dir = os.path.join(a.out, name)
        os.makedirs(out_dir, exist_ok=True)
        report = {"preset": name, "size": [W, H], "lang": lang, "shots": []}
        for i, shot in enumerate(spec["shots"], start=1):
            try:
                img, warnings, size = render_shot(shot, style, W, H, fonts, spec_dir, lang)
            except FileNotFoundError as e:
                print(f"x shot {i}: {e}", file=sys.stderr)
                exit_code = 1
                continue
            path = os.path.join(out_dir, f"{i:02d}.png")
            img.convert("RGB").save(path, optimize=True)
            report["shots"].append({"file": os.path.basename(path), "headline": shot.get("headline", "").replace("*", ""),
                                    "sub": shot.get("sub", ""), "layout": shot.get("layout", "device"),
                                    "headline_px": size, "warnings": warnings})
            for w in warnings:
                print(f"! {name} {i:02d}: {w}")
        report["fonts"] = sorted(fonts.used)
        with open(os.path.join(out_dir, "_render.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        print(f"{name}: {len(report['shots'])} shots → {out_dir}   fonts: {', '.join(os.path.basename(x) for x in report['fonts'])}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
