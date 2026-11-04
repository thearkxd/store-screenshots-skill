#!/usr/bin/env python3
"""Render a store screenshot set from one JSON spec. Requires Pillow.

  python3 render_set.py set.json --out out/            # every preset listed in spec "sizes"
  python3 render_set.py set.json --out out/ --size ios # one preset
  python3 render_set.py --presets                      # list sizes and font aliases

Writes out/<preset>/01.png … (RGB, no alpha, exact pixels) and out/<preset>/_render.json (headlines,
fonts, warnings) that check_set.py reads. See templates/set.example.json for every option.

Layouts per shot: "device" (default) · "zoom" (cropped card) · "full" (full-bleed screen + band/pill caption)
· "poster" (type only). Device styles: "phone" (thin bezel + island) · "none" (rounded screen, shadow).
Headline emphasis: wrap words in *asterisks*; "\\n" forces a line break.
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

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.normpath(os.path.join(HERE, "..", "assets", "fonts"))

PRESETS = {  # checked 2026-11-04, see references/store-specs.md
    "ios": (1206, 2622),
    "ios-1179": (1179, 2556),
    "ios-large": (1320, 2868),
    "ios-faceid": (1284, 2778),
    "ipad": (2064, 2752),
    "android": (1080, 1920),
    "android-tall": (1080, 2160),
}

FONT_ALIASES = {  # bundled, OFL - see assets/fonts/FONTS.md
    "sans": ("InterDisplay-SemiBold.otf", None),
    "sans-bold": ("InterDisplay-Bold.otf", None),
    "sans-medium": ("InterDisplay-Medium.otf", None),
    "sans-italic": ("InterDisplay-SemiBoldItalic.otf", None),
    "text": ("Inter-Regular.otf", None),
    "text-medium": ("Inter-Medium.otf", None),
    "serif": ("Lora-Variable.ttf", 600),
    "serif-bold": ("Lora-Variable.ttf", 700),
    "serif-italic": ("Lora-Italic-Variable.ttf", 500),
}
SYSTEM_FALLBACK = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]

DEFAULT_STYLE = {
    "background": {"color": "#F3EEE6"},
    "text_color": "#151515",
    "sub_color": None,
    "font": "sans",
    "sub_font": "text",
    "weight": None,            # for variable fonts, e.g. 650
    "tracking": -0.018,        # em; display type looks better slightly tight
    "sub_tracking": -0.005,
    "align": "center",
    "case": "none",
    "headline_size": 0.096,    # fraction of canvas width (upper bound; auto-fit shrinks)
    "min_headline_size": 0.06,
    "max_lines": 2,
    "line_height": 1.06,
    "text_width": 0.84,
    "caption_top": 0.10,       # fraction of width from the top (or bottom) edge
    "sub_scale": 0.42,
    "sub_gap": 0.32,           # gap between headline and sub-line, in headline sizes
    "emphasis": {"style": "color", "color": "#E5482D"},
    "device": {"style": "phone", "width": 0.82, "radius": 0.15, "border": 0.022, "border_color": "#0E0E10",
               "island": True, "shadow": True, "gap": 0.075, "bleed": True},
    "card": {"radius": 0.045, "shadow": True, "width": 0.86},
    "band_color": None,
}

REPLACE_KEYS = {"background"}  # replaced, not merged (a gradient must not inherit a colour)


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


def merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict) and k not in REPLACE_KEYS:
            out[k] = merge(out[k], v)
        else:
            out[k] = v
    return out


class Fonts:
    """Resolves aliases, paths and variable weights; caches FreeType objects."""

    def __init__(self, spec_dir):
        self.spec_dir = spec_dir
        self.cache = {}
        self.used = set()

    def resolve(self, name):
        weight = None
        if isinstance(name, dict):
            name, weight = name.get("path") or name.get("font"), name.get("weight")
        if name in FONT_ALIASES:
            f, w = FONT_ALIASES[name]
            return os.path.join(FONT_DIR, f), weight or w
        if name:
            p = name if os.path.isabs(name) else os.path.join(self.spec_dir, name)
            if os.path.exists(p):
                return p, weight
            print(f"! font not found: {name} - using the bundled sans", file=sys.stderr)
        p = os.path.join(FONT_DIR, FONT_ALIASES["sans"][0])
        if os.path.exists(p):
            return p, None
        for c in SYSTEM_FALLBACK:
            if os.path.exists(c):
                return c, None
        return None, None

    def get(self, name, size, weight=None):
        path, w = self.resolve(name)
        w = weight or w
        key = (path, size, w)
        if key not in self.cache:
            if path is None:
                f = ImageFont.load_default()
            else:
                f = ImageFont.truetype(path, size)
                if w:
                    try:
                        f.set_variation_by_axes([w])
                    except Exception:
                        pass
            self.cache[key] = f
            self.used.add(os.path.basename(path) if path else "PIL default")
        return self.cache[key]


# ------------------------------------------------------------------ text

def tokenize(text):
    """'Kaldığın bölüm *hep hazır*.' -> [(word, emphasised, glued)], '\\n' = forced break.
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
        for i, w in enumerate(part.split(" ")):
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


def text_width(font, text, track_px):
    return font.getlength(text) + track_px * max(len(text) - 1, 0)


def draw_tracked(d, xy, text, font, fill, track_px, anchor="ls"):
    """Draw on a baseline with letter-spacing, keeping the font's kerning (advance = prefix width delta)."""
    if abs(track_px) < 0.05:
        d.text(xy, text, font=font, fill=fill, anchor=anchor)
        return
    x, y = xy
    for i, ch in enumerate(text):
        d.text((x + font.getlength(text[:i]) + track_px * i, y), ch, font=font, fill=fill, anchor=anchor)


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
            # a second family often has a smaller x-height; "scale" evens it out (e.g. 1.08 for Lora next to Inter)
            return self.fonts.get(e["font"], int(size * e.get("scale", 1.0)), e.get("weight"))
        return self.fonts.get(self.s["font"], size, self.s.get("weight"))

    def track(self, size):
        return self.s["tracking"] * size

    def word_w(self, tok, size):
        return text_width(self.font_for(size, tok[1]), tok[0], self.track(size))

    def measure_line(self, line, size):
        space = self.font_for(size, False).getlength(" ")
        gaps = sum(1 for i, t in enumerate(line) if i > 0 and not t[2])
        return sum(self.word_w(t, size) for t in line) + space * gaps

    def layout(self, text, max_lines, max_size, min_size):
        tokens = tokenize(self.prep(text))
        max_w = self.W * self.s["text_width"]
        size = int(max_size)
        while True:
            lines = wrap(tokens, lambda l: self.measure_line(l, size), max_w)
            fits = len(lines) <= max_lines and all(self.measure_line(l, size) <= max_w for l in lines)
            if fits or size <= min_size:
                return lines, size, fits
            size = int(size * 0.96)

    def x_for(self, lw):
        if self.s["align"] == "center":
            return (self.W - lw) / 2
        return self.W * (1 - self.s["text_width"]) / 2

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
        tr = self.track(size)
        ascent = self.font_for(size, False).getmetrics()[0]
        y = top
        for line in lines:
            x = self.x_for(self.measure_line(line, size))
            if e.get("style") in ("box", "marker"):
                cx, run = x, None
                for i, tok in enumerate(line):
                    if i > 0 and not tok[2]:
                        cx += space
                    ww = self.word_w(tok, size)
                    if tok[1]:
                        run = [cx, cx + ww] if run is None else [run[0], cx + ww]
                    if (not tok[1] or i == len(line) - 1) and run:
                        pad = size * 0.16
                        if e["style"] == "box":
                            d.rounded_rectangle([run[0] - pad, y + size * 0.02, run[1] + pad, y + size * 1.1],
                                                radius=int(size * 0.12), fill=hexrgb(e.get("color", "#FFFFFF")))
                        else:
                            d.rectangle([run[0] - pad * 0.4, y + size * 0.5, run[1] + pad * 0.4, y + size * 1.05],
                                        fill=hexrgb(e.get("color", "#FFE600")))
                        run = None
                    cx += ww
            cx = x
            for i, (w, em, g) in enumerate(line):
                if i > 0 and not g:
                    cx += space
                f = self.font_for(size, em)
                c = color
                if em and e.get("color") and e.get("style") in ("color", "font"):
                    c = hexrgb(e["color"])
                if em and e.get("style") == "box" and e.get("text_color"):
                    c = hexrgb(e["text_color"])
                draw_tracked(d, (cx, y + ascent), w, f, c, tr)
                cx += text_width(f, w, tr)
            y += lh
        return top + total_h, size, warnings

    def sub_size(self, head_size):
        return int(head_size * self.s["sub_scale"])

    def draw_sub(self, img, text, top, head_size, color=None):
        s = self.s
        size = self.sub_size(head_size)
        f = self.fonts.get(s["sub_font"], size)
        tr = s["sub_tracking"] * size
        max_w = self.W * s["text_width"]
        tokens = [(w, False, False) for w in self.prep(text).split()]
        lines = wrap(tokens, lambda l: text_width(f, " ".join(t[0] for t in l), tr), max_w)[:3]
        d = ImageDraw.Draw(img)
        col = hexrgb(color or s["sub_color"] or s["text_color"])
        ascent = f.getmetrics()[0]
        y = top
        for line in lines:
            t = " ".join(tok[0] for tok in line)
            draw_tracked(d, (self.x_for(text_width(f, t, tr)), y + ascent), t, f, col, tr)
            y += int(size * 1.32)
        return y

    def block_height(self, text, sub, max_lines=None):
        tmp = Image.new("RGB", (self.W, 10))
        b, size, _ = self.draw(tmp, text, 0, max_lines=max_lines)
        if sub:
            n = len(wrap([(w, False, False) for w in sub.split()],
                         lambda l: self.fonts.get(self.s["sub_font"], self.sub_size(size)).getlength(" ".join(t[0] for t in l)),
                         self.W * self.s["text_width"])[:3])
            b += int(size * self.s["sub_gap"]) + int(self.sub_size(size) * 1.32) * n
        return b, size


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
    scale = 3  # supersampled for smooth corners
    m = Image.new("L", (size[0] * scale, size[1] * scale), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size[0] * scale - 1, size[1] * scale - 1], radius=radius * scale, fill=255)
    return m.resize(size, Image.LANCZOS)


def shadow(canvas, box, radius, strength=0.22, spread=0.06):
    x0, y0, x1, y1 = [int(v) for v in box]
    w = x1 - x0
    blur = max(10, int(w * spread))
    pad = blur * 3
    layer = Image.new("L", (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), 0)
    ImageDraw.Draw(layer).rounded_rectangle([pad, pad + blur * 0.5, pad + x1 - x0, pad + y1 - y0 + blur * 0.5],
                                            radius=radius, fill=int(255 * strength))
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    black = Image.new("RGB", layer.size, (0, 0, 0))
    canvas.paste(black, (x0 - pad, y0 - pad), layer)
    return canvas


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


def device_geometry(screen, dv, W):
    dw = int(W * dv["width"])
    border = int(dw * dv["border"]) if dv.get("style", "phone") == "phone" else 0
    sw = dw - 2 * border
    sh = int(screen.height * sw / screen.width)
    return dw, border, sw, sh, sh + 2 * border


def draw_device(canvas, screen, s, W, H, top, bottom_limit=None):
    dv = s["device"]
    style = dv.get("style", "phone")
    dw, border, sw, sh, dh = device_geometry(screen, dv, W)
    limit = bottom_limit if bottom_limit is not None else H - W * 0.06
    if not dv.get("bleed", True) and top + dh > limit:
        k = (limit - top) / dh
        dv = dict(dv, width=dv["width"] * k)
        dw, border, sw, sh, dh = device_geometry(screen, dv, W)
    scr = screen.resize((sw, sh), Image.LANCZOS)
    x = (W - dw) // 2
    r_out = int(dw * (dv["radius"] if style == "phone" else dv.get("screen_radius", 0.07)))
    if dv.get("shadow", True):
        canvas = shadow(canvas, (x, top, x + dw, top + dh), r_out)
    if style == "phone" and border > 0:
        frame = Image.new("RGB", (dw, dh), hexrgb(dv["border_color"]))
        paste_rounded(canvas, frame, (x, top), r_out)
    paste_rounded(canvas, scr, (x + border, top + border), max(r_out - border, 0))
    if style == "phone" and dv.get("island", True):
        d = ImageDraw.Draw(canvas)
        iw, ih = sw * 0.305, sw * 0.088
        cx, iy = x + dw / 2, top + border + sw * 0.028
        d.rounded_rectangle([cx - iw / 2, iy, cx + iw / 2, iy + ih], radius=int(ih / 2), fill=(0, 0, 0))
    return canvas, (x + border, top + border, sw / screen.width)


def draw_card(canvas, img, s, W, cx, cy, width_px):
    c = s["card"]
    k = width_px / img.width
    card = img.resize((max(1, int(img.width * k)), max(1, int(img.height * k))), Image.LANCZOS)
    r = int(W * c["radius"])
    x, y = int(cx - card.width / 2), int(cy - card.height / 2)
    if c.get("shadow", True):
        canvas = shadow(canvas, (x, y, x + card.width, y + card.height), r, 0.28, 0.05)
    paste_rounded(canvas, card, (x, y), r)
    return canvas


# ------------------------------------------------------------------ shots

def render_shot(shot, style, W, H, fonts, spec_dir, lang):
    s = merge(style, shot.get("style"))
    for k in ("background", "text_color", "sub_color", "align", "emphasis", "band_color", "device", "card", "case",
              "font", "weight", "tracking"):
        if k in shot:
            mergeable = k in ("emphasis", "device", "card") and isinstance(shot[k], dict) and isinstance(s.get(k), dict)
            s[k] = merge(s[k], shot[k]) if mergeable else shot[k]
    layout = shot.get("layout", "device")
    warnings = []
    canvas = background(W, H, s["background"], spec_dir)
    cap = Caption(fonts, s, W, lang)
    headline = shot.get("headline", "")
    sub = shot.get("sub")
    pos = shot.get("caption_position", "top")

    if layout == "poster":
        ps = merge(s, {"text_width": shot.get("text_width", 0.84), "line_height": shot.get("line_height", 1.0)})
        pcap = Caption(fonts, ps, W, lang)
        bottom, size, w = pcap.draw(canvas, headline, 0, max_lines=shot.get("max_lines", 4),
                                    max_size=W * shot.get("poster_size", 0.2), center_v=H * shot.get("center", 0.46))
        warnings += w
        if sub:
            pcap.draw_sub(canvas, sub, bottom + size * s["sub_gap"], size)
        return canvas, warnings, size

    if layout == "full":
        screen = load_screen(spec_dir, shot["screen"])
        k = max(W / screen.width, H / screen.height)
        scr = screen.resize((int(screen.width * k + 1), int(screen.height * k + 1)), Image.LANCZOS)
        canvas.paste(scr.crop(((scr.width - W) // 2, 0, (scr.width - W) // 2 + W, H)), (0, 0))
        mode = shot.get("caption_style", "band")
        block, size = cap.block_height(headline, sub)
        pad = int(W * 0.055)
        y0 = int(W * s["caption_top"]) if pos == "top" else H - block - int(W * s["caption_top"])
        d = ImageDraw.Draw(canvas)
        fill = hexrgb(s.get("band_color") or s["background"].get("color", "#111111"))
        if mode == "pill":
            d.rounded_rectangle([W * 0.05, y0 - pad, W * 0.95, y0 + block + pad], radius=int(W * 0.05), fill=fill)
        elif pos == "top":
            d.rectangle([0, 0, W, y0 + block + pad], fill=fill)
        else:
            d.rectangle([0, y0 - pad, W, H], fill=fill)
        bottom, size, _ = cap.draw(canvas, headline, y0)
        if sub:
            cap.draw_sub(canvas, sub, bottom + size * s["sub_gap"], size)
        return canvas, warnings, size

    # caption (device / zoom)
    block, size = cap.block_height(headline, sub)
    top = int(W * s["caption_top"]) if pos == "top" else H - int(W * s["caption_top"]) - block
    bottom, size, w = cap.draw(canvas, headline, top)
    warnings += w
    if sub:
        bottom = cap.draw_sub(canvas, sub, bottom + size * s["sub_gap"], size)
    ref = bg_reference_color(s["background"], pos == "bottom")
    if ref and contrast(hexrgb(s["text_color"]), ref) < 4.5:
        warnings.append(f"low headline contrast {contrast(hexrgb(s['text_color']), ref):.1f}:1 (aim ≥ 4.5)")

    if layout == "zoom":
        # one or more crops of the screen, stacked as cards ("crops": [[x0,y0,x1,y1], ...])
        screen = load_screen(spec_dir, shot["screen"])
        boxes = shot.get("crops") or [shot.get("crop", [0, 0, 1, 0.5])]
        pieces = [crop_frac(screen, b) for b in boxes]
        area_top = bottom + W * 0.08 if pos == "top" else W * 0.07
        area_bot = H - W * 0.07 if pos == "top" else top - W * 0.08
        gap = W * shot.get("card_gap", 0.04)
        width_px = W * s["card"]["width"]
        # same scale for every card so the UI stays consistent; shrink to fit the free area
        k = width_px / max(p.width for p in pieces)
        total = sum(p.height for p in pieces) * k + gap * (len(pieces) - 1)
        if total > area_bot - area_top:
            k *= (area_bot - area_top - gap * (len(pieces) - 1)) / (sum(p.height for p in pieces) * k)
            total = area_bot - area_top
        y = (area_top + area_bot - total) / 2 if shot.get("card_align", "center") == "center" else area_top
        for p_ in pieces:
            h = p_.height * k
            canvas = draw_card(canvas, p_, s, W, W / 2, y + h / 2, p_.width * k)
            y += h + gap
        return canvas, warnings, size

    # device
    screen = load_screen(spec_dir, shot["screen"])
    dv = s["device"]
    if pos == "top":
        dev_top = int(bottom + W * dv["gap"])
        limit = None
    else:
        dh = device_geometry(screen, dv, W)[4]
        dev_top = int(top - W * dv["gap"] - dh)
        if not dv.get("bleed", True):
            dev_top = max(dev_top, int(W * 0.06))
        limit = top - W * dv["gap"]
    canvas, (sx, sy, k) = draw_device(canvas, screen, s, W, H, dev_top, limit)
    for co in shot.get("callouts", []):
        piece = crop_frac(screen, co["crop"])
        width_px = piece.width * k * co.get("scale", 1.12)
        cx = W * co.get("x", 0.5)
        cy = H * co["y"] if "y" in co else sy + (co["crop"][1] + co["crop"][3]) / 2 * screen.height * k
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
        print("\nfont aliases: " + ", ".join(FONT_ALIASES))
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
            report["shots"].append({"file": os.path.basename(path), "headline": shot.get("headline", "").replace("*", "").replace("\n", " "),
                                    "sub": shot.get("sub", ""), "layout": shot.get("layout", "device"),
                                    "headline_px": size, "warnings": warnings})
            for w in warnings:
                print(f"! {name} {i:02d}: {w}")
        report["fonts"] = sorted(fonts.used)
        with open(os.path.join(out_dir, "_render.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        print(f"{name}: {len(report['shots'])} shots → {out_dir}   fonts: {', '.join(report['fonts'])}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
