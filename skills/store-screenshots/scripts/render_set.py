#!/usr/bin/env python3
"""Render a store screenshot set from one JSON spec. Requires Pillow.

  python3 render_set.py set.json --out out/            # every preset listed in spec "sizes"
  python3 render_set.py set.json --out out/ --size ios # one preset
  python3 render_set.py --presets                      # list sizes and font aliases

Writes out/<preset>/01.png … (RGB, no alpha, exact pixels) and out/<preset>/_render.json (headlines,
fonts, warnings) that check_set.py reads. See templates/set.example.json for every option.

Layouts per shot: "device" (default) · "zoom" (cropped card) · "full" (full-bleed screen + band/pill caption)
· "poster" (type only). Device styles: "phone" (thin bezel + island) · "android" (punch-hole camera, used
automatically for android presets) · "none" (rounded screen, shadow). "feature_graphic" renders Google Play's
1024x500 graphic. "locales": ["tr", "en"] + {"tr": …, "en": …} values render every language from one spec
into out/<locale>/<preset>/.
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
sys.path.insert(0, HERE)
import design  # noqa: E402

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
    "serif": ("StoreSerif-Variable.ttf", 600),
    "serif-bold": ("StoreSerif-Variable.ttf", 700),
    "serif-italic": ("StoreSerif-Italic-Variable.ttf", 500),
    "condensed": ("Anton_400Regular.ttf", None),
    "display": ("Fraunces_600SemiBold.ttf", None),
    "display-black": ("Fraunces_900Black.ttf", None),
    "display-italic": ("Fraunces_400Regular_Italic.ttf", None),
    "elegant": ("InstrumentSerif_400Regular.ttf", None),
    "elegant-italic": ("InstrumentSerif_400Regular_Italic.ttf", None),
    "rounded": ("Baloo2_800ExtraBold.ttf", None),
    "rounded-medium": ("Baloo2_700Bold.ttf", None),
    "grotesk": ("SpaceGrotesk_700Bold.ttf", None),
    "grotesk-medium": ("SpaceGrotesk_500Medium.ttf", None),
    "bricolage": ("BricolageGrotesque_800ExtraBold.ttf", None),
    "bricolage-medium": ("BricolageGrotesque_500Medium.ttf", None),
    "hand": ("Caveat_700Bold.ttf", None),
    "mono": ("JetBrainsMono_700Bold.ttf", None),
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
    "device": {"style": "phone", "android_style": "android", "width": 0.82, "radius": 0.15, "border": 0.022, "border_color": "#0E0E10",
               "island": True, "shadow": True, "gap": 0.075, "bleed": True},
    "card": {"radius": 0.045, "shadow": True, "width": 0.86},
    "band_color": None,
    "overline_style": {"font": "sans-medium", "size": 0.034, "color": None, "tracking": 0.12, "case": "upper", "gap": 0.028},
    "stickers_style": {"font": "rounded", "size": 0.042, "bg": "#111111", "color": "#FFFFFF", "rotate": -5},
    "annotation_style": {"color": "#FF4D2E", "width": 0.009, "font": "hand", "size": 0.062},
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


_CMAPS = {}


def font_cmap(path):
    """Character map of a font (needs fontTools; returns None without it, so the check is skipped)."""
    if not path:
        return None
    if path not in _CMAPS:
        try:
            from fontTools.ttLib import TTFont
            _CMAPS[path] = TTFont(path, lazy=True).getBestCmap()
        except Exception:
            _CMAPS[path] = None
    return _CMAPS[path]


class Caption:
    def __init__(self, fonts, style, W, lang):
        self.fonts, self.s, self.W, self.lang = fonts, style, W, lang
        self.warnings = []
        self.last_top = 0

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

    def gap(self, line, i, size):
        """Advance before token i: a space (unless glued) plus room for a box/marker edge at an emphasis boundary."""
        if i == 0:
            return 0
        g = 0 if line[i][2] else self.font_for(size, False).getlength(" ")
        style = self.s["emphasis"].get("style")
        if style in ("box", "marker") and line[i][1] != line[i - 1][1]:
            g += size * (0.2 if style == "box" else 0.08)
        return g

    def measure_line(self, line, size):
        return sum(self.word_w(t, size) for t in line) + sum(self.gap(line, i, size) for i in range(1, len(line)))

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
        return self.W * self.s.get("text_x", (1 - self.s["text_width"]) / 2)

    def missing_glyphs(self, text):
        out = set()
        for emph in (False, True):
            path, _ = self.fonts.resolve(self.s["emphasis"]["font"] if emph and self.s["emphasis"].get("style") == "font"
                                         and self.s["emphasis"].get("font") else self.s["font"])
            cmap = font_cmap(path)
            if cmap:
                out |= {ch for ch in text if ch.strip() and ch not in "*" and ord(ch) not in cmap}
        return out

    def draw(self, img, text, top, max_lines=None, max_size=None, center_v=None, color=None):
        """Draw the headline; returns (bottom_y, size, warnings)."""
        s = self.s
        warnings = []
        miss = self.missing_glyphs(self.prep(text))
        if miss:
            warnings.append(f"font lacks glyphs {''.join(sorted(miss))} for {text!r} - pick a font that covers the language")
        max_lines = max_lines or s["max_lines"]
        max_size = max_size or s["headline_size"] * self.W
        lines, size, fits = self.layout(text, max_lines, max_size, s["min_headline_size"] * self.W)
        if not fits:
            warnings.append(f"headline doesn't fit {max_lines} lines even at minimum size: {text!r}")
        lh = int(size * s["line_height"])
        accented_lines = sum(1 for li, l in enumerate(lines) if li and s["line_height"] < 1.05
                             and any(ch in "ÇĞİÖŞÜÂÊÎÔÛÀÁÉÍÓÚÑÄËÏ" for t in l for ch in t[0]))
        # real ink extent: the last line's baseline plus the font's descender depth. Using lh * n instead
        # lets tall fonts (Anton, Baloo) at tight line heights run into whatever sits below the headline.
        f0 = self.font_for(size, False)
        ink_desc = f0.getbbox("gy", anchor="ls")[3]
        total_h = (lh * (len(lines) - 1) + f0.getmetrics()[0] + ink_desc
                   + accented_lines * int(size * (1.05 - s["line_height"]) + size * 0.06))
        if center_v is not None:
            top = int(center_v - total_h / 2)
        self.last_top = top
        d = ImageDraw.Draw(img)
        color = hexrgb(color or s["text_color"])
        e = s["emphasis"]
        tr = self.track(size)
        ascent = self.font_for(size, False).getmetrics()[0]
        y = top
        accented = set("ÇĞİÖŞÜÂÊÎÔÛÀÁÉÍÓÚÑÄËÏ")
        for li, line in enumerate(lines):
            if li and s["line_height"] < 1.05 and any(ch in accented for tok in line for ch in tok[0]):
                y += int(size * (1.05 - s["line_height"]) + size * 0.06)  # room for İ Ğ Ü marks in tight caps
            x = self.x_for(self.measure_line(line, size))
            if e.get("style") in ("box", "marker"):
                cx, run = x, None
                for i, tok in enumerate(line):
                    cx += self.gap(line, i, size)
                    ww = self.word_w(tok, size)
                    if tok[1]:
                        run = [cx, cx + ww] if run is None else [run[0], cx + ww]
                    if (not tok[1] or i == len(line) - 1) and run:
                        pad = size * 0.16
                        # box from the real glyph metrics, so tall fonts (Baloo, Anton) don't overflow the line
                        fe = self.font_for(size, True)
                        cap = -fe.getbbox("Hd", anchor="ls")[1]
                        desc = fe.getbbox("gy", anchor="ls")[3]
                        base = y + ascent
                        if e["style"] == "box":
                            d.rounded_rectangle([run[0] - pad, base - cap - size * 0.12, run[1] + pad, base + desc * 0.75],
                                                radius=int(size * 0.12), fill=hexrgb(e.get("color", "#FFFFFF")))
                        else:
                            d.rectangle([run[0] - pad * 0.4, base - cap * 0.42, run[1] + pad * 0.4, base + desc * 0.35],
                                        fill=hexrgb(e.get("color", "#FFE600")))
                        run = None
                    cx += ww
            cx = x
            for i, (w, em, g) in enumerate(line):
                cx += self.gap(line, i, size)
                f = self.font_for(size, em)
                c = color
                if em and e.get("color") and e.get("style") in ("color", "font", "underline", "scribble") and not e.get("keep_color"):
                    c = hexrgb(e["color"])
                if em and e.get("style") == "box" and e.get("text_color"):
                    c = hexrgb(e["text_color"])
                draw_tracked(d, (cx, y + ascent), w, f, c, tr)
                cx += text_width(f, w, tr)
            if e.get("style") in ("underline", "scribble"):
                cx2, run = x, None
                for i, tok in enumerate(line):
                    cx2 += self.gap(line, i, size)
                    ww = self.word_w(tok, size)
                    if tok[1]:
                        run = [cx2, cx2 + ww] if run is None else [run[0], cx2 + ww]
                    if (not tok[1] or i == len(line) - 1) and run:
                        col = hexrgb(e.get("mark_color", e.get("color", "#FF4D2E")))
                        wd = max(3, int(size * e.get("mark_width", 0.075)))
                        fe = self.font_for(size, True)
                        cap = -fe.getbbox("Hd", anchor="ls")[1]
                        base = y + ascent
                        if e["style"] == "underline":
                            design.hand_underline(d, run[0] - size * 0.05, run[1] + size * 0.05, base + size * 0.16, col, wd)
                        else:
                            design.hand_ellipse(d, [run[0] - size * 0.22, base - cap - size * 0.2, run[1] + size * 0.22, base + size * 0.24], col, wd)
                        run = None
                    cx2 += ww
            y += lh
        return top + total_h, size, warnings

    def sub_size(self, head_size):
        # follows the headline, but never larger than a readable sub-line (posters have huge headlines)
        return int(min(head_size, self.W * max(self.s["headline_size"], 0.13)) * self.s["sub_scale"])

    def draw_sub(self, img, text, top, head_size, color=None):
        s = self.s
        size = self.sub_size(head_size)
        f = self.fonts.get(s["sub_font"], size)
        tr = s["sub_tracking"] * size
        max_w = self.W * s["text_width"]
        sub_text = text
        if s.get("sub_case") == "upper":
            sub_text = tr_upper(text) if self.lang == "tr" else text.upper()
        tokens = [(w, False, False) for w in sub_text.split()]
        lines = wrap(tokens, lambda l: text_width(f, " ".join(t[0] for t in l), tr), max_w)
        if len(lines) > 3:
            self.warnings.append(f"sub-line needs {len(lines)} lines, only 3 are drawn - shorten it: {text!r}")
            lines = lines[:3]
        d = ImageDraw.Draw(img)
        col = hexrgb(color or s["sub_color"] or s["text_color"])
        ascent = f.getmetrics()[0]
        y = top
        for line in lines:
            t = " ".join(tok[0] for tok in line)
            draw_tracked(d, (self.x_for(text_width(f, t, tr)), y + ascent), t, f, col, tr)
            y += int(size * 1.32)
        return y

    def overline_height(self, text):
        if not text:
            return 0
        o = self.s["overline_style"]
        return int(self.W * o["size"] * 1.2 + self.W * o.get("gap", 0.028))

    def draw_overline(self, img, text, top):
        o = self.s["overline_style"]
        size = int(self.W * o["size"])
        f = self.fonts.get(o["font"], size)
        t = text
        if o.get("case") == "upper":
            t = tr_upper(t) if self.lang == "tr" else t.upper()
        tr = o.get("tracking", 0.12) * size
        d = ImageDraw.Draw(img)
        col = hexrgb(o.get("color") or self.s["text_color"])
        x = self.x_for(text_width(f, t, tr))
        if o.get("pill"):
            pw = text_width(f, t, tr)
            d.rounded_rectangle([x - size * 0.7, top - size * 0.35, x + pw + size * 0.7, top + size * 1.35],
                                radius=int(size), fill=hexrgb(o["pill"]))
        draw_tracked(d, (x, top + f.getmetrics()[0]), t, f, col, tr)
        return top + self.overline_height(text)

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

def background(W, H, bg, spec_dir, screen=None):
    img = _background(W, H, bg, spec_dir, screen)
    for light in ([bg["light"]] if isinstance(bg.get("light"), dict) else bg.get("light") or []):
        img = design.add_light(img, light, W, H)
    return design.add_grain(img, bg.get("grain", 0))


def _background(W, H, bg, spec_dir, screen=None):
    if bg.get("sample"):
        return design.sampled_background(W, H, bg, screen)
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
    if "image" in bg or bg.get("sample"):
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


FRAMED = ("phone", "android", "flat")


def device_geometry(screen, dv, W):
    dw = int(W * dv["width"])
    k = {"android": 0.8, "flat": dv.get("flat_border", 1.6)}.get(dv.get("style"), 1)
    border = int(dw * dv["border"] * k) if dv.get("style", "phone") in FRAMED else 0
    sw = dw - 2 * border
    sh = int(screen.height * sw / screen.width)
    return dw, border, sw, sh, sh + 2 * border


def draw_device(canvas, screen, s, W, H, top, bottom_limit=None, cx=None):
    dv = s["device"]
    style = dv.get("style", "phone")
    dw, border, sw, sh, dh = device_geometry(screen, dv, W)
    limit = bottom_limit if bottom_limit is not None else H - W * 0.06
    if not dv.get("bleed", True) and top + dh > limit:
        k = (limit - top) / dh
        dv = dict(dv, width=dv["width"] * k)
        dw, border, sw, sh, dh = device_geometry(screen, dv, W)
    scr = screen.resize((sw, sh), Image.LANCZOS)
    if cx is None:
        cx = W * dv.get("x", 0.5)
    x = int(cx - dw / 2)
    radius = {"phone": dv["radius"], "android": dv.get("android_radius", 0.085), "flat": dv.get("flat_radius", 0.13)}.get(
        style, dv.get("screen_radius", 0.07))
    r_out = int(dw * radius)
    angle = dv.get("rotate", 0) or 0
    target = canvas
    if angle:
        canvas = Image.new("RGBA", target.size, (0, 0, 0, 0))
    if dv.get("shadow", True) and style != "flat":
        canvas = shadow(canvas, (x, top, x + dw, top + dh), r_out)
    if style == "flat" and dv.get("offset_shadow"):
        off = int(dw * dv["offset_shadow"])
        sh_ = Image.new("RGB", (dw, dh), hexrgb(dv.get("offset_color", dv["border_color"])))
        paste_rounded(canvas, sh_, (x + off, top + off), r_out)
    if style in FRAMED and border > 0:
        frame = Image.new("RGB", (dw, dh), hexrgb(dv["border_color"]))
        paste_rounded(canvas, frame, (x, top), r_out)
    paste_rounded(canvas, scr, (x + border, top + border), max(r_out - border, 0))
    if style == "phone" and dv.get("island", True):
        d = ImageDraw.Draw(canvas)
        iw, ih = sw * 0.305, sw * 0.088
        cx, iy = x + dw / 2, top + border + sw * 0.028
        d.rounded_rectangle([cx - iw / 2, iy, cx + iw / 2, iy + ih], radius=int(ih / 2), fill=(0, 0, 0))
    if style == "android" and dv.get("island", True):
        # neutral punch-hole camera, not an iPhone island
        d = ImageDraw.Draw(canvas)
        r = sw * 0.017
        cx, cy = x + dw / 2, top + border + sw * 0.034
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 0, 0))
    centre = (x + dw / 2, top + dh / 2)
    if angle:
        layer = canvas.rotate(angle, resample=Image.BICUBIC, center=centre)
        base = target.convert("RGBA")
        base.alpha_composite(layer)
        canvas = base.convert("RGB")
    xf = (x + border, top + border, sw / screen.width, sw, sh, angle, centre)
    return canvas, xf


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

def layout_has_caption(shot):
    return shot.get("layout", "device") != "poster"


def render_shot(shot, style, W, H, fonts, spec_dir, lang):
    s = merge(style, shot.get("style"))
    for k in design.SHOT_KEYS + ("sub_color", "weight", "text_x", "text_width", "headline_size", "line_height",
                                 "caption_top", "max_lines"):
        if k in shot and k != "shapes":
            mergeable = k in ("emphasis", "device", "card", "overline_style", "stickers_style", "annotation_style") \
                and isinstance(shot[k], dict) and isinstance(s.get(k), dict)
            s[k] = merge(s[k], shot[k]) if mergeable else shot[k]
    layout = shot.get("layout", "device")
    warnings = []
    screen = load_screen(spec_dir, shot["screen"]) if shot.get("screen") else None
    canvas = background(W, H, s["background"], spec_dir, screen)
    canvas = design.draw_shapes(canvas, shot.get("shapes") or s.get("shapes"), shot.get("_index", 0), W, H)
    cap = Caption(fonts, s, W, lang)
    headline = shot.get("headline", "")
    sub = shot.get("sub")
    overline = shot.get("overline") if s.get("show_overline", True) else None
    if s.get("overline_prefix") and layout_has_caption(shot):
        prefix = s["overline_prefix"].format(n=shot.get("_index", 0) + 1, total=shot.get("_count", 1))
        overline = prefix + overline if overline else prefix.rstrip(" —–-:·/")
    pos = shot.get("caption_position", "top")

    def finish(img, xf=None):
        img = design.draw_stickers(img, shot.get("stickers"), fonts, W, H, s.get("stickers_style"))
        img = design.draw_annotations(img, shot.get("annotations"), fonts, W, H, xf, s.get("annotation_style"))
        return img

    if layout == "poster":
        ps = merge(s, {"text_width": shot.get("text_width", s.get("poster_text_width", 0.84)),
                       "line_height": shot.get("line_height", s.get("poster_line_height", 1.0))})
        pcap = Caption(fonts, ps, W, lang)
        tmp_h = pcap.overline_height(overline)
        bottom, size, w = pcap.draw(canvas, headline, 0, max_lines=shot.get("max_lines", 4),
                                    max_size=W * shot.get("poster_size", s.get("poster_size", 0.2)),
                                    center_v=H * shot.get("center", 0.46) + tmp_h / 2)
        if overline:
            pcap.draw_overline(canvas, overline, int(pcap.last_top - tmp_h))
        warnings += w
        if sub:
            pcap.draw_sub(canvas, sub, bottom + W * 0.04, size)
        ref = bg_reference_color(s["background"], False)
        if ref and contrast(hexrgb(s["text_color"]), ref) < 3.0:
            warnings.append(f"low poster headline contrast {contrast(hexrgb(s['text_color']), ref):.1f}:1 (aim ≥ 3)")
        if ref and sub and contrast(hexrgb(s.get("sub_color") or s["text_color"]), ref) < 4.5:
            warnings.append(f"low sub-line contrast {contrast(hexrgb(s.get('sub_color') or s['text_color']), ref):.1f}:1 (aim ≥ 4.5)")
        return finish(canvas), warnings + pcap.warnings, size

    if layout == "full":
        k = max(W / screen.width, H / screen.height)
        scr = screen.resize((int(screen.width * k + 1), int(screen.height * k + 1)), Image.LANCZOS)
        canvas.paste(scr.crop(((scr.width - W) // 2, 0, (scr.width - W) // 2 + W, H)), (0, 0))
        mode = shot.get("caption_style", "band")
        block, size = cap.block_height(headline, sub)
        block += cap.overline_height(overline)
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
        y = cap.draw_overline(canvas, overline, y0) if overline else y0
        bottom, size, _ = cap.draw(canvas, headline, y)
        if sub:
            cap.draw_sub(canvas, sub, bottom + size * s["sub_gap"], size)
        return finish(canvas), warnings, size

    # caption (device / zoom)
    block, size = cap.block_height(headline, sub)
    block += cap.overline_height(overline)
    top = int(W * s["caption_top"]) if pos == "top" else H - int(W * s["caption_top"]) - block
    y = cap.draw_overline(canvas, overline, top) if overline else top
    bottom, size, w = cap.draw(canvas, headline, y)
    warnings += w
    if sub:
        bottom = cap.draw_sub(canvas, sub, bottom + size * s["sub_gap"], size)
    warnings += cap.warnings
    ref = bg_reference_color(s["background"], pos == "bottom")
    need = 3.0 if size >= 0.075 * W else 4.5  # WCAG: large display type needs 3:1
    if ref and contrast(hexrgb(s["text_color"]), ref) < need:
        warnings.append(f"low headline contrast {contrast(hexrgb(s['text_color']), ref):.1f}:1 (aim ≥ {need})")
    if ref and sub and contrast(hexrgb(s.get("sub_color") or s["text_color"]), ref) < 4.5:
        warnings.append(f"low sub-line contrast {contrast(hexrgb(s.get('sub_color') or s['text_color']), ref):.1f}:1 (aim ≥ 4.5)")

    if layout == "zoom":
        # one or more crops of the screen, stacked as cards ("crops": [[x0,y0,x1,y1], ...])
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
        cx = W * s["card"].get("x", 0.5)
        for p_ in pieces:
            h = p_.height * k
            canvas = draw_card(canvas, p_, s, W, cx, y + h / 2, p_.width * k)
            y += h + gap
        return finish(canvas), warnings, size

    # device
    dv = s["device"]
    if pos == "top":
        dev_top = int(bottom + W * dv["gap"] + H * dv.get("dy", 0))
        limit = None
    else:
        dh = device_geometry(screen, dv, W)[4]
        dev_top = int(top - W * dv["gap"] - dh)
        if not dv.get("bleed", True):
            dev_top = max(dev_top, int(W * 0.06))
        limit = top - W * dv["gap"]
    canvas, xf = draw_device(canvas, screen, s, W, H, dev_top, limit)
    sx, sy, k = xf[0], xf[1], xf[2]
    for co in shot.get("callouts", []):
        piece = crop_frac(screen, co["crop"])
        width_px = piece.width * k * co.get("scale", 1.12)
        # default: centred on the element's own position in the screen, so it covers the original
        cx = W * co["x"] if "x" in co else sx + (co["crop"][0] + co["crop"][2]) / 2 * screen.width * k
        cy = H * co["y"] if "y" in co else sy + (co["crop"][1] + co["crop"][3]) / 2 * screen.height * k
        cx += W * co.get("dx", 0)
        cy += H * co.get("dy", 0)
        canvas = draw_card(canvas, piece, s, W, cx, cy, width_px)
    return finish(canvas, xf), warnings, size


LOCALE_KEY = re.compile(r"^[a-z]{2}(-[A-Za-z]{2,4})?$")


def localize(obj, loc, locales):
    """Pick the locale's value wherever a dict is keyed by locales: {"tr": "...", "en": "..."}."""
    if isinstance(obj, dict):
        keys = set(obj)
        if keys and keys <= set(locales) | {"default"}:
            return localize(obj.get(loc, obj.get("default", obj[next(iter(obj))])), loc, locales)
        return {k: localize(v, loc, locales) for k, v in obj.items()}
    if isinstance(obj, list):
        return [localize(v, loc, locales) for v in obj]
    return obj


def render_feature_graphic(fg, style, fonts, spec_dir, lang, out_path):
    """Google Play feature graphic, 1024x500: headline left, the app's screen on a phone at the right."""
    W, H = 1024, 500
    s = merge(style, {"align": "left", "text_x": 0.065, "text_width": 0.53, "headline_size": 0.068,
                      "min_headline_size": 0.042, "max_lines": 2, "line_height": 1.06})
    for k in ("background", "text_color", "sub_color", "emphasis", "font", "device"):
        if k in fg:
            s[k] = merge(s[k], fg[k]) if k in ("emphasis", "device") else fg[k]
    screen = load_screen(spec_dir, fg["screen"]) if fg.get("screen") else None
    canvas = background(W, H, s["background"], spec_dir, screen)
    warnings = []
    if screen is not None:
        if fg.get("crop"):
            screen = crop_frac(screen, fg["crop"])
        dv = merge(s["device"], {"width": fg.get("device_width", 0.3), "style": s["device"].get("android_style") or s["device"]["style"]})
        canvas, _ = draw_device(canvas, screen, dict(s, device=dv), W, H, int(H * fg.get("device_top", 0.12)),
                                cx=W * fg.get("device_x", 0.76))
    cap = Caption(fonts, s, W, lang)
    lines = fg.get("max_lines", 2)
    block, size = cap.block_height(fg.get("headline", ""), fg.get("sub"), max_lines=lines)
    top = int((H - block) / 2)
    bottom, size, w = cap.draw(canvas, fg.get("headline", ""), top, max_lines=lines)
    warnings += w
    if fg.get("sub"):
        cap.draw_sub(canvas, fg["sub"], bottom + size * s["sub_gap"], size)
    warnings += cap.warnings
    canvas.convert("RGB").save(out_path, optimize=True)
    return warnings


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("spec", nargs="?")
    p.add_argument("--out", default="out")
    p.add_argument("--size", help="render only this preset (or WxH)")
    p.add_argument("--locale", help="render only this locale (specs with \"locales\")")
    p.add_argument("--presets", action="store_true")
    a = p.parse_args()
    if a.presets:
        for k, (w, h) in PRESETS.items():
            print(f"{k:13} {w} x {h}")
        print("feature graphic: 1024 x 500 (spec \"feature_graphic\", rendered with Android sizes)")
        print("directions: " + ", ".join(f"{k} ({v.get('label', '')})" for k, v in design.list_directions().items()))
        print("\nfont aliases: " + ", ".join(FONT_ALIASES))
        return
    if not a.spec:
        p.error("spec is required")
    spec_dir = os.path.dirname(os.path.abspath(a.spec))
    with open(a.spec, encoding="utf-8") as f:
        raw_spec = json.load(f)
    locales = raw_spec.get("locales")
    runs = [(loc, os.path.join(a.out, loc)) for loc in locales] if locales else [(None, a.out)]
    if a.locale:
        runs = [r for r in runs if r[0] == a.locale] or sys.exit(f"locale {a.locale!r} not in spec locales {locales}")
    fonts = Fonts(spec_dir)
    exit_code = 0
    for loc, out_root in runs:
        spec = localize(raw_spec, loc, locales) if loc else raw_spec
        lang = (loc.split("-")[0] if loc else spec.get("lang", "en"))
        spec = design.ensure_brand(spec, spec_dir)
        d_style, d_shots, tokens = design.apply_direction(spec)
        spec = dict(spec, shots=d_shots)
        if spec.get("feature_graphic"):
            spec["feature_graphic"] = design.resolve_tokens(spec["feature_graphic"], tokens)
        base_style = merge(DEFAULT_STYLE, d_style)
        sizes = [a.size] if a.size else spec.get("sizes", ["ios"])
        for name in sizes:
            if name in PRESETS:
                W, H = PRESETS[name]
            elif re.fullmatch(r"\d+x\d+", name):
                W, H = map(int, name.split("x"))
            else:
                sys.exit(f"unknown size {name!r}; use --presets")
            style = base_style
            if name.startswith("android") and base_style["device"].get("style") == "phone" and base_style["device"].get("android_style"):
                style = merge(base_style, {"device": {"style": base_style["device"]["android_style"]}})
            out_dir = os.path.join(out_root, name)
            os.makedirs(out_dir, exist_ok=True)
            report = {"preset": name, "size": [W, H], "lang": lang, "locale": loc, "shots": []}
            for i, shot in enumerate(spec["shots"], start=1):
                if name.startswith("android") and isinstance(shot.get("device"), dict) and shot["device"].get("style") == "phone":
                    shot = merge(shot, {"device": {"style": style["device"]["style"]}})
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
                    print(f"! {loc or ''} {name} {i:02d}: {w}")
            report["fonts"] = sorted(fonts.used)
            with open(os.path.join(out_dir, "_render.json"), "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=1)
            print(f"{(loc + ' ') if loc else ''}{name}: {len(report['shots'])} shots → {out_dir}   fonts: {', '.join(report['fonts'])}")
        if spec.get("feature_graphic") and (any(n.startswith("android") for n in sizes) or a.size is None):
            fg_path = os.path.join(out_root, "feature-graphic.png")
            for w in render_feature_graphic(spec["feature_graphic"], base_style, fonts, spec_dir, lang, fg_path):
                print(f"! {loc or ''} feature graphic: {w}")
            print(f"{(loc + ' ') if loc else ''}feature graphic → {fg_path}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
