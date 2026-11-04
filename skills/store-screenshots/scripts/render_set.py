#!/usr/bin/env python3
"""Render a store screenshot set from one JSON spec. Requires Pillow.

  python3 render_set.py set.json --out out/            # every preset listed in spec "sizes"
  python3 render_set.py set.json --out out/ --size ios # one preset
  python3 render_set.py --presets                      # list sizes and font aliases

Writes out/<preset>/01.png … (RGB, no alpha, exact pixels) and out/<preset>/_render.json (headlines,
fonts, warnings) that check_set.py reads. See templates/set.example.json for every option.

Layouts per shot: "device" (default) · "zoom" (cropped card) · "full" (full-bleed screen + band/pill caption)
· "poster" (type only); "span": 2 puts one picture across two slots. Device styles: "phone" (thin bezel +
island) · "android" (punch-hole camera) · "flat" · "none" (rounded screen, shadow - used for Google Play,
iPad and iPhone Duo sets). Sizes (--presets): ios + ios-large by default; duo-outer, duo-inner, ipad, android.
Any value can be given per size: {"default": …, "duo-inner": …}; "stores": ["ios"] keeps a shot out of other
sets. "feature_graphic" renders Google Play's 1024x500 graphic. "locales": ["tr", "en"] + {"tr": …, "en": …}
values render every language from one spec into out/<locale>/<preset>/.
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
    "ios": (1206, 2622),          # iPhone, Dynamic Island medium - the required iPhone size
    "ios-1179": (1179, 2556),
    "ios-large": (1320, 2868),    # Dynamic Island large - render with "ios" (without a large set Apple wants Face ID large)
    "ios-faceid": (1284, 2778),   # Face ID large
    "duo-outer": (1398, 2034),    # iPhone Duo outer display (required from April 2027 for iOS 27.1 SDK apps)
    "duo-inner": (2007, 2853),    # iPhone Duo inner display
    "ipad": (2064, 2752),         # iPad 13"
    "android": (1080, 1920),      # Google Play phone, 9:16 (promotion-eligible)
    "android-tall": (1080, 2160),
}
DEFAULT_SIZES = ["ios", "ios-large"]
PHONE_RATIO = 2622 / 1206  # the canvas shape the styles and directions are tuned for

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
    # Google Play advises against device imagery, so Android sets show the bare rounded screen; iPad and
    # iPhone Duo screens aren't drawn in a phone bezel either. Set "android_style": "android" for a frame.
    "device": {"style": "phone", "android_style": "none", "duo_style": "none", "ipad_style": "none", "width": 0.82, "radius": 0.15, "border": 0.022, "border_color": "#0E0E10",
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
        return int(min(head_size, self.W * max(self.s["headline_size"], 0.13 * self.s.get("_k", 1.0))) * self.s["sub_scale"])

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

def background(W, H, bg, spec_dir, screen=None, unit=None):
    """unit = one slot's width when the canvas is a span (2 slots wide): light x/r are in slot units."""
    img = _background(W, H, bg, spec_dir, screen)
    for light in ([bg["light"]] if isinstance(bg.get("light"), dict) else bg.get("light") or []):
        img = design.add_light(img, light, unit or W, H)
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


def device_geometry(screen, dv, W, even=False):
    dw = int(W * dv["width"])
    if even and dw % 2:
        dw += 1  # a span's phone centred on the seam: equal halves to the pixel
    k = {"android": 0.8, "flat": dv.get("flat_border", 1.6)}.get(dv.get("style"), 1)
    border = int(dw * dv["border"] * k) if dv.get("style", "phone") in FRAMED else 0
    sw = dw - 2 * border
    sh = int(screen.height * sw / screen.width)
    return dw, border, sw, sh, sh + 2 * border


def draw_device(canvas, screen, s, W, H, top, bottom_limit=None, cx=None, even=False):
    dv = s["device"]
    style = dv.get("style", "phone")
    dw, border, sw, sh, dh = device_geometry(screen, dv, W, even)
    limit = bottom_limit if bottom_limit is not None else H - W * 0.06
    if not dv.get("bleed", True) and top + dh > limit:
        k = (limit - top) / dh
        dv = dict(dv, width=dv["width"] * k)
        dw, border, sw, sh, dh = device_geometry(screen, dv, W, even)
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


STYLE_SHOT_KEYS = design.SHOT_KEYS + ("sub_color", "weight", "text_x", "text_width", "headline_size", "line_height",
                                      "caption_top", "max_lines")
MERGEABLE = ("emphasis", "device", "card", "overline_style", "stickers_style", "annotation_style")


def shot_style(style, shot):
    """The set's style with this shot's own look keys applied."""
    s = merge(style, shot.get("style"))
    for k in STYLE_SHOT_KEYS:
        if k in shot and k != "shapes":
            mergeable = k in MERGEABLE and isinstance(shot[k], dict) and isinstance(s.get(k), dict)
            s[k] = merge(s[k], shot[k]) if mergeable else shot[k]
    return s


def overline_text(shot, s):
    overline = shot.get("overline") if s.get("show_overline", True) else None
    if s.get("overline_prefix") and layout_has_caption(shot):
        prefix = s["overline_prefix"].format(n=shot.get("_index", 0) + 1, total=shot.get("_count", 1))
        overline = prefix + overline if overline else prefix.rstrip(" —–-:·/")
    return overline


def caption_bottom(shot, s, W, fonts, lang):
    """Where a top caption ends (px), measured without drawing; None for posters and bottom captions."""
    if shot.get("layout", "device") == "poster" or shot.get("caption_position", "top") != "top":
        return None
    headline, sub, overline = shot.get("headline", ""), shot.get("sub"), overline_text(shot, s)
    if not (headline or sub or overline):
        return None
    cap = Caption(fonts, s, W, lang)
    block, _ = cap.block_height(headline, sub) if (headline or sub) else (0, 0)
    return W * s["caption_top"] + block + cap.overline_height(overline)


def caption_floor(shots, style, W, H, fonts, lang):
    """The lowest top-caption bottom in the whole set, as a fraction of H. Motifs marked "clear_caption" stay
    below it on every shot, so they never run into a tall caption and still line up from shot to shot."""
    lows = []
    for sh in shots:
        s = shot_style(style, sh)
        units = span_halves(sh) if sh.get("span") == 2 else [sh]
        for u in units:
            b = caption_bottom(u, shot_style(s, u) if u is not sh else s, W, fonts, lang)
            if b is not None:
                lows.append(b / H)
    return max(lows) if lows else None


def render_shot(shot, style, W, H, fonts, spec_dir, lang, base=None, info=None, caption_only=False):
    info = info if info is not None else {}
    img, warnings, size = _render_shot(shot, style, W, H, fonts, spec_dir, lang, base, info, caption_only)
    return img, warnings + play_warnings(shot_style(style, shot), info, shot), size


PLAY_TEXT_SHARE = 0.20  # Google Play: "Taglines should not take up more than 20% of the image"


def play_warnings(s, info, shot):
    """Google Play's screenshot guidance, for Android sets only."""
    if s.get("_class") != "android":
        return []
    out = []
    if info.get("poster"):
        out.append("type-only poster in a Google Play set: Play wants screenshots that show the in-app experience "
                   "and taglines under 20% of the image - add \"stores\": [\"ios\"] to keep it in the App Store set only")
    elif info.get("text_ratio", 0) > PLAY_TEXT_SHARE:
        out.append(f"caption covers {info['text_ratio']:.0%} of the height - Google Play recommends taglines take up "
                   f"no more than 20% (shorter headline, no sub-line, or a smaller headline_size)")
    if shot.get("screen") and s["device"].get("style") in ("phone", "android"):
        out.append("device frame in a Google Play set - Play advises against device imagery; leave \"android_style\" "
                   "at \"none\" (the bare rounded screen)")
    return out


def _render_shot(shot, style, W, H, fonts, spec_dir, lang, base=None, info=None, caption_only=False):
    """One slot. base: a ready-made ground (a span half) - no background or shapes are drawn then.
    caption_only: a shot without a screen draws just its caption (span halves around a shared phone)."""
    s = shot_style(style, shot)
    layout = shot.get("layout", "device")
    if layout not in ("device", "zoom", "full", "poster"):
        raise ValueError(f"unknown layout {layout!r} (device, zoom, full, poster)")
    warnings = []
    screen = load_screen(spec_dir, shot["screen"]) if shot.get("screen") else None
    if screen is None and layout != "poster" and not caption_only:
        raise ValueError(f"layout {layout!r} needs a \"screen\" (or use \"layout\": \"poster\"; per-size screens "
                         f"need a \"default\" or a key for this size)")
    U = W * s.get("_k", 1.0)  # one slot's width on a phone-shaped canvas: spacing that should follow the height
    if screen is not None:
        warnings += screen_fit_warnings(screen, s, W, H)
    if base is not None:
        canvas = base.copy()
    else:
        canvas = background(W, H, s["background"], spec_dir, screen)
        canvas = design.draw_shapes(canvas, shot.get("shapes") or s.get("shapes"), shot.get("_index", 0), W, H,
                                    floor=s.get("_caption_floor"))
    cap = Caption(fonts, s, W, lang)
    headline = shot.get("headline", "")
    sub = shot.get("sub")
    overline = overline_text(shot, s)
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
            bottom = pcap.draw_sub(canvas, sub, bottom + U * 0.04, size)
        info.update(text_ratio=(bottom - (pcap.last_top - tmp_h)) / H, poster=True)
        ref = bg_reference_color(s["background"], False)
        if ref and contrast(hexrgb(s["text_color"]), ref) < 3.0:
            warnings.append(f"low poster headline contrast {contrast(hexrgb(s['text_color']), ref):.1f}:1 (aim ≥ 3)")
        if ref and sub and contrast(hexrgb(s.get("sub_color") or s["text_color"]), ref) < 4.5:
            warnings.append(f"low sub-line contrast {contrast(hexrgb(s.get('sub_color') or s['text_color']), ref):.1f}:1 (aim ≥ 4.5)")
        return finish(canvas), warnings + pcap.warnings, size

    if layout == "full" and screen is not None:
        k = max(W / screen.width, H / screen.height)
        scr = screen.resize((int(screen.width * k + 1), int(screen.height * k + 1)), Image.LANCZOS)
        canvas.paste(scr.crop(((scr.width - W) // 2, 0, (scr.width - W) // 2 + W, H)), (0, 0))
        mode = shot.get("caption_style", "band")
        block, size = cap.block_height(headline, sub)
        block += cap.overline_height(overline)
        pad = int(U * 0.055)
        y0 = int(W * s["caption_top"]) if pos == "top" else H - block - int(W * s["caption_top"])
        info.update(text_ratio=(block + 2 * pad) / H)
        d = ImageDraw.Draw(canvas)
        fill = hexrgb(s.get("band_color") or s["background"].get("color", "#111111"))
        if mode == "pill":
            d.rounded_rectangle([W * 0.05, y0 - pad, W * 0.95, y0 + block + pad], radius=int(U * 0.05), fill=fill)
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
    info.update(caption_top=top, caption_bottom=bottom if headline or sub or overline else None, caption_pos=pos,
                text_ratio=(bottom - top) / H if headline or sub or overline else 0.0)
    ref = bg_reference_color(s["background"], pos == "bottom")
    need = 3.0 if size >= 0.075 * U else 4.5  # WCAG: large display type needs 3:1
    if ref and contrast(hexrgb(s["text_color"]), ref) < need:
        warnings.append(f"low headline contrast {contrast(hexrgb(s['text_color']), ref):.1f}:1 (aim ≥ {need})")
    if ref and sub and contrast(hexrgb(s.get("sub_color") or s["text_color"]), ref) < 4.5:
        warnings.append(f"low sub-line contrast {contrast(hexrgb(s.get('sub_color') or s['text_color']), ref):.1f}:1 (aim ≥ 4.5)")
    if screen is None:  # caption only (a span half next to a shared phone)
        return finish(canvas), warnings, size

    if layout == "zoom":
        # one or more crops of the screen, stacked as cards ("crops": [[x0,y0,x1,y1], ...])
        boxes = shot.get("crops") or [shot.get("crop", [0, 0, 1, 0.5])]
        pieces = [crop_frac(screen, b) for b in boxes]
        area_top = bottom + U * 0.08 if pos == "top" else U * 0.07
        area_bot = H - U * 0.07 if pos == "top" else top - U * 0.08
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
            dev_top = max(dev_top, int(U * 0.06))
        limit = top - W * dv["gap"]
    s = fit_device(s, screen, W, H, dev_top, pos)
    canvas, xf = draw_device(canvas, screen, s, W, H, dev_top, limit)
    canvas, _ = draw_callouts(canvas, screen, shot, s, W, H, xf)
    return finish(canvas, xf), warnings, size


SCREEN_SHAPES = {"iphone": (1.9, 2.4), "android": (1.6, 2.4), "duo": (1.3, 1.6), "ipad": (1.25, 1.6)}
CLASS_NAMES = {"iphone": "an iPhone", "android": "an Android phone", "duo": "an iPhone Duo", "ipad": "an iPad"}


def screen_fit_warnings(screen, s, W, H):
    """A screen captured on another kind of device (a phone screenshot in an iPhone Duo or iPad set) looks
    wrong - and Apple shows a Duo set as "optimized for iPhone Duo"."""
    cls = s.get("_class")
    if cls not in SCREEN_SHAPES:
        return []
    r = screen.height / screen.width
    lo, hi = SCREEN_SHAPES[cls]
    if r < 1:
        return [f"screen is landscape ({screen.width}x{screen.height}) in a portrait set"]
    if not lo <= r <= hi:
        return [f"screen is {screen.width}x{screen.height} - that's not {CLASS_NAMES[cls]} screen; capture it on "
                f"{CLASS_NAMES[cls]} (per-size screens: \"screen\": {{\"default\": …, \"{s.get('_preset')}\": …}})"]
    return []


def fit_device(s, screen, W, H, dev_top, pos):
    """On a wider canvas a tall screen would run far off the bottom: shrink the device until at most a sliver
    bleeds (phone-shaped sets keep the normal bleed)."""
    if s.get("_k", 1.0) >= 0.999 or pos != "top":
        return s
    dv = s["device"]
    dh = device_geometry(screen, dv, W)[4]
    allowed = H + 0.06 * dh - dev_top
    if dh <= allowed:
        return s
    return dict(s, device=dict(dv, width=dv["width"] * allowed / dh))


def draw_callouts(canvas, screen, shot, s, W, H, xf):
    """UI pieces lifted out of the screen, larger. Returns the canvas and each callout's pixel box."""
    sx, sy, k = xf[0], xf[1], xf[2]
    boxes = []
    for co in shot.get("callouts", []):
        piece = crop_frac(screen, co["crop"])
        width_px = piece.width * k * co.get("scale", 1.12)
        # default: centred on the element's own position in the screen, so it covers the original
        cx = W * co["x"] if "x" in co else sx + (co["crop"][0] + co["crop"][2]) / 2 * screen.width * k
        cy = H * co["y"] if "y" in co else sy + (co["crop"][1] + co["crop"][3]) / 2 * screen.height * k
        cx += W * co.get("dx", 0)
        cy += H * co.get("dy", 0)
        canvas = draw_card(canvas, piece, s, W, cx, cy, width_px)
        h_px = piece.height * width_px / max(1, piece.width)
        boxes.append((cx - width_px / 2, cy - h_px / 2, cx + width_px / 2, cy + h_px / 2))
    return canvas, boxes


# ------------------------------------------------------------------ spans (one picture across two slots)

SPAN_CAPTION_KEYS = ("headline", "sub", "overline")
SPAN_HALF_KEYS = SPAN_CAPTION_KEYS + ("screen", "layout", "crop", "crops", "callouts", "caption_position", "caption_style",
                                      "card_gap", "card_align", "poster_size", "center", "max_lines", "stickers",
                                      "annotations", "style") + STYLE_SHOT_KEYS
SEAM_PAD = 0.012  # of a slot's width: how close to the seam something may come before it counts as crossing


def span_halves(shot):
    halves = shot.get("halves") or []
    if not isinstance(halves, list) or len(halves) > 2 or not all(isinstance(h, dict) for h in halves):
        raise ValueError('"halves" must be a list of at most two shot objects (left, right)')
    halves = [dict(h) for h in halves] + [{} for _ in range(2 - len(halves))]
    for k in SPAN_CAPTION_KEYS:  # top-level caption = the left half's
        if k in shot and k not in halves[0]:
            halves[0][k] = shot[k]
    for i, h in enumerate(halves, start=1):
        if h.get("span") or h.get("halves"):
            raise ValueError(f"half {i}: a half can't contain another span")
    return halves


def crosses(x0, x1, seam, pad):
    return x0 < seam - pad and x1 > seam + pad


def render_span(shot, style, W, H, fonts, spec_dir, lang, keep=None):
    """A picture two slots wide, drawn on ONE canvas and cut down the middle, so the halves always line up.
    Without a top-level "screen" each half is an ordinary shot on a shared ground ("pair"); with one, a single
    phone sits across the seam - by default exactly centred on it, half in each slot - and the halves carry
    only captions ("bridge"). Every x in a span runs 0..2
    (1 = the seam); y and sizes are as in a single shot. Returns ([left, right], warnings, headline_px)."""
    if shot.get("span") != 2:
        raise ValueError(f'"span" must be 2 (two slots); got {shot.get("span")!r}')
    s = shot_style(style, shot)
    # halves are single slots: the span's own device "x" (0..2) must not move their phones
    span_dv = shot.get("device") if isinstance(shot.get("device"), dict) else {}
    s_half = shot_style(style, dict({k: v for k, v in shot.items() if k != "device"},
                                    device={k: v for k, v in span_dv.items() if k != "x"}))
    warnings = []
    halves = span_halves(shot)
    screen = load_screen(spec_dir, shot["screen"]) if shot.get("screen") else None
    bridge = screen is not None
    if bridge:
        warnings += screen_fit_warnings(screen, s, W, H)
    if not bridge:
        for k in ("callouts", "crop", "crops"):
            if shot.get(k):
                raise ValueError(f'"{k}" on a span without a shared "screen" has nothing to crop - put it inside the half')
        if shot.get("layout", "device") != "device":
            raise ValueError('a span\'s halves choose their own layout - put "layout" inside the half')
    if bridge:
        if shot.get("layout", "device") != "device":
            raise ValueError('a span with a shared "screen" draws one phone across the seam: its layout must be "device"')
        for i, h in enumerate(halves, start=1):
            if h.get("screen"):
                raise ValueError(f'half {i} has its own "screen", but the span already has a shared one - use one or the other')
            if h.get("caption_position", "top") != "top" or h.get("layout", "device") != "device":
                raise ValueError(f"half {i}: next to a phone across the seam, captions go at the top (no bottom captions, posters or zooms)")
    sample = screen
    if sample is None:
        first = next((h["screen"] for h in halves if h.get("screen")), None)
        sample = load_screen(spec_dir, first) if first else None
    W2 = 2 * W
    canvas = background(W2, H, s["background"], spec_dir, sample, unit=W)
    canvas = design.draw_shapes(canvas, shot.get("shapes") or s.get("shapes"), shot.get("_index", 0), W, H,
                                floor=s.get("_caption_floor"))
    idx = shot.get("_index", 0)
    size = 0
    bottoms = []
    for h, half in enumerate(halves):
        hs = {k: v for k, v in half.items()}
        hs["_index"], hs["_count"] = idx + h, shot.get("_count", idx + 2)
        if not (hs.get("headline") or "").strip():
            warnings.append(f"half {h + 1} has no headline - each half is also seen on its own (while swiping, in Play's promo formats)")
        info = {}
        img, w, sz = render_shot(hs, s_half, W, H, fonts, spec_dir, lang, base=canvas.crop((h * W, 0, (h + 1) * W, H)),
                                 info=info, caption_only=bridge)
        canvas.paste(img, (h * W, 0))
        warnings += [f"half {h + 1}: {x}" for x in w]
        size = max(size, sz or 0)
        if info.get("caption_bottom") is not None:
            bottoms.append(info["caption_bottom"])
    xf = None
    pad = W * SEAM_PAD
    if bridge:
        dv = s["device"]
        dev_top = int((max(bottoms) if bottoms else W * s.get("_k", 1.0) * 0.12) + W * dv["gap"] + H * dv.get("dy", 0))
        if s.get("_class") == "android" and dv.get("style") in ("phone", "android"):
            warnings.append("device frame in a Google Play set - Play advises against device imagery")
        x = (shot.get("device") or {}).get("x", 1.0)  # default: centred on the seam, half the phone in each slot
        canvas, xf = draw_device(canvas, screen, s, W, H, dev_top, cx=W * x, even=(x == 1.0))
        if keep is not None:
            keep["device"] = xf
        canvas, boxes = draw_callouts(canvas, screen, shot, s, W, H, xf)
        sx, sw = xf[0], xf[3]
        if not crosses(sx, sx + sw, W, pad):
            warnings.append("the phone doesn't cross the seam - set device x to 1.0 (centred on the seam), "
                            "or make it two ordinary shots")
        for i, b in enumerate(boxes, start=1):
            if crosses(b[0], b[2], W, pad):
                warnings.append(f"callout {i} crosses the seam - the gap between screenshots will cut it")
    # span-level stickers and annotations are in span space (x 0..2)
    canvas = design.draw_stickers(canvas, shot.get("stickers"), fonts, W, H, s.get("stickers_style"))
    canvas = design.draw_annotations(canvas, shot.get("annotations"), fonts, W, H, xf, s.get("annotation_style"))
    for i, st in enumerate(shot.get("stickers") or [], start=1):
        o = design.deep_merge(s.get("stickers_style") or {}, st)
        f = fonts.get(o.get("font", "rounded"), int(W * o.get("size", 0.042)))
        half_w = f.getlength(o.get("text", "")) / 2 + f.size * 0.6
        if crosses(W * o["x"] - half_w, W * o["x"] + half_w, W, pad):
            warnings.append(f"sticker {i} ({o.get('text', '')!r}) crosses the seam - keep text on one side")
    for i, n in enumerate(shot.get("annotations") or [], start=1):
        xs = []
        if "screen_box" in n and xf:
            b = design.map_screen_box(n["screen_box"], xf)
            xs += [b[0], b[2]]
        elif "box" in n:
            xs += [n["box"][0] * W, n["box"][2] * W]
        for key in ("from", "to", "text_at"):
            if key in n:
                xs.append(n[key][0] * W)
        if xs and crosses(min(xs), max(xs), W, pad):
            warnings.append(f"annotation {i} crosses the seam - the gap between screenshots will break it")
    if keep is not None:
        keep["canvas"] = canvas  # tests: the halves must re-join to exactly this
    return [canvas.crop((0, 0, W, H)), canvas.crop((W, 0, W2, H))], warnings, size


def render_any(shot, style, W, H, fonts, spec_dir, lang):
    """Render one spec entry: ([image], ...) for a shot, ([left, right], ...) for a span."""
    span = shot.get("span", 1)
    if span == 1 and not shot.get("halves"):
        img, warnings, size = render_shot(shot, style, W, H, fonts, spec_dir, lang)
        return [img], warnings, size
    if shot.get("halves") and span != 2:
        raise ValueError('"halves" belongs to a span: add "span": 2')
    return render_span(shot, style, W, H, fonts, spec_dir, lang)


IPHONE_MEDIUM = {(1206, 2622), (1179, 2556)}
IPHONE_LARGE = {(1260, 2736), (1290, 2796), (1320, 2868), (1284, 2778), (1242, 2688)}


def iphone_size_warnings(sizes):
    """App Store Connect: at least one Dynamic Island medium screenshot; and a large set (Dynamic Island large,
    or else Face ID large is required). One spec renders both - list them in "sizes"."""
    got = set()
    for n in sizes:
        try:
            w, h = preset_size(n)
        except ValueError:
            continue
        got.add((min(w, h), max(w, h)))
    out = []
    if got and not got & IPHONE_MEDIUM:
        out.append("no iPhone Dynamic Island medium size (1206x2622 / 1179x2556) - App Store Connect requires it; add \"ios\" to \"sizes\"")
    if got & IPHONE_MEDIUM and not got & IPHONE_LARGE:
        out.append("no large iPhone size - without a Dynamic Island large set Apple requires Face ID large (1284x2778); "
                   "add \"ios-large\" to \"sizes\"")
    return out


def set_warnings(shots, store):
    """Rules for the whole set: how many spans, where they sit, how many slots."""
    out, slot, spans = [], 0, []
    for i, sh in enumerate(shots, start=1):
        n = sh.get("span", 1)
        if sh.get("halves") and n == 1:
            n = 2
        if n == 2:
            spans.append(slot + 1)
        slot += n if n in (1, 2) else 1
    limit = 8 if store == "android" else 10
    if slot > limit:
        out.append(f"{slot} screenshots ({len(spans)} span pair(s) count twice) - {store} allows at most {limit}")
    if len(spans) > 2:
        out.append(f"{len(spans)} span pairs - use one (two only in sets of 8+); they stop being special")
    elif len(spans) == 2 and slot < 8:
        out.append(f"2 span pairs in a set of {slot} - use one; two only in sets of 8 or more")
    for start in spans:
        if start == 3:
            out.append("a span on shots 3-4 is cut in half in search results (only shots 1-3 show) - "
                       "move it to 1-2 or 2-3, or after shot 4")
    return out


# ------------------------------------------------------------------ presets: stores, devices, canvas shape

def preset_size(name):
    if name in PRESETS:
        return PRESETS[name]
    if re.fullmatch(r"\d+x\d+", name or ""):
        return tuple(map(int, name.split("x")))
    raise ValueError(f"unknown size {name!r}; use --presets")


DUO_SIZES = {(1398, 2034), (2007, 2853)}
IPAD_SIZES = {(2064, 2752), (2048, 2732), (1488, 2266), (1668, 2420), (1668, 2388), (1640, 2360), (1668, 2224)}


def device_class(name, W, H):
    """iphone · duo · ipad · android - what kind of screens and frame a preset wants."""
    n = name or ""
    if n.startswith("android"):
        return "android"
    if n.startswith("duo") or (min(W, H), max(W, H)) in DUO_SIZES:
        return "duo"
    if n.startswith("ipad") or (min(W, H), max(W, H)) in IPAD_SIZES:
        return "ipad"
    if n.startswith("ios"):
        return "iphone"
    return "iphone" if max(W, H) / min(W, H) > 2.05 else "android"


def store_of(name, W, H):
    return "android" if device_class(name, W, H) == "android" else "ios"


VARIANT_KEYS = set(PRESETS) | {"iphone", "duo", "ipad", "android", "ios", "default"}


def resolve_variants(obj, name, W, H):
    """Per-preset values: {"default": "screens/01.png", "duo-inner": "screens/duo/01.png"} picks the exact preset,
    then its device class (iphone/duo/ipad/android), then its store (ios/android), then "default"."""
    if isinstance(obj, dict):
        keys = set(obj)
        if keys and keys <= VARIANT_KEYS:
            for k in (name, device_class(name, W, H), store_of(name, W, H), "default"):
                if k in obj:
                    return resolve_variants(obj[k], name, W, H)
            return None
        return {k: resolve_variants(v, name, W, H) for k, v in obj.items()}
    if isinstance(obj, list):
        return [resolve_variants(v, name, W, H) for v in obj]
    return obj


def keep_shot(shot, name, W, H):
    """"stores": ["ios"] (or "android", "iphone", "duo", "ipad") limits a shot to those sets."""
    st = shot.get("stores")
    if not st:
        return True
    st = [st] if isinstance(st, str) else st
    return store_of(name, W, H) in st or device_class(name, W, H) in st


def canvas_k(W, H):
    """1.0 for phone-shaped canvases; < 1 for wider ones (iPad, iPhone Duo), where every size that the styles
    give as a fraction of the width is scaled down so type and spacing keep their proportion to the height."""
    return min(1.0, (H / W) / PHONE_RATIO)


SCALED_KEYS = ("headline_size", "min_headline_size", "caption_top", "poster_size")


def scale_look(d, k):
    """Scale the width-relative sizes in a style or a shot by k (see canvas_k)."""
    if k >= 0.999 or not isinstance(d, dict):
        return d
    out = dict(d)
    for key in SCALED_KEYS:
        if isinstance(out.get(key), (int, float)):
            out[key] = out[key] * k
    for key, subkeys in (("overline_style", ("size", "gap")), ("stickers_style", ("size",)),
                         ("annotation_style", ("size", "width")), ("card", ("radius",)), ("device", ("gap",))):
        if isinstance(out.get(key), dict):
            out[key] = dict(out[key], **{sk: out[key][sk] * k for sk in subkeys if isinstance(out[key].get(sk), (int, float))})
    for key in ("stickers", "annotations"):
        if isinstance(out.get(key), list):
            out[key] = [dict(o, **{sk: o[sk] * k for sk in ("size", "width") if isinstance(o.get(sk), (int, float))}) for o in out[key]]
    if isinstance(out.get("shapes"), list):
        out["shapes"] = [dict(sh, **{sk: sh[sk] * k for sk in ("width", "r", "step", "stroke") if isinstance(sh.get(sk), (int, float))})
                         for sh in out["shapes"]]
    bg = out.get("background")
    if isinstance(bg, dict) and isinstance(bg.get("light"), dict) and isinstance(bg["light"].get("r"), (int, float)):
        out["background"] = dict(bg, light=dict(bg["light"], r=bg["light"]["r"] * k))
    if isinstance(out.get("halves"), list):
        out["halves"] = [scale_look(h, k) for h in out["halves"]]
    if isinstance(out.get("style"), dict):
        out["style"] = scale_look(out["style"], k)
    return out


def device_for(dv, cls, ref=None):
    """The frame a device class gets when the spec says "phone" (the iPhone-style bezel). ref: the set's
    device style, for its android_style / duo_style / ipad_style choices."""
    if not isinstance(dv, dict) or dv.get("style", "phone") != "phone":
        return dv
    ref = ref or dv
    alt = {"android": dv.get("android_style", ref.get("android_style", "none")),
           "duo": dv.get("duo_style", ref.get("duo_style", "none")),
           "ipad": dv.get("ipad_style", ref.get("ipad_style", "none"))}.get(cls)
    return dict(dv, style=alt) if alt else dv


def prepare(spec, name, spec_dir, fonts, lang):
    """Everything one preset needs: (W, H, style, shots, tokens) with variants, "stores", the direction, the
    device class's frame and the canvas-shape scaling applied."""
    W, H = preset_size(name)
    spec = resolve_variants(spec, name, W, H)
    spec = dict(spec, shots=[sh for sh in spec.get("shots", []) if keep_shot(sh, name, W, H)])
    spec = design.ensure_brand(spec, spec_dir)
    d_style, shots, tokens = design.apply_direction(spec)
    cls = device_class(name, W, H)
    k = canvas_k(W, H)
    style = scale_look(merge(DEFAULT_STYLE, d_style), k)
    ref = style["device"]
    style = merge(style, {"device": device_for(ref, cls), "_k": k, "_preset": name, "_class": cls})
    out = []
    for sh in shots:
        sh = scale_look(sh, k)
        if isinstance(sh.get("device"), dict) and sh["device"].get("style") == "phone":
            sh = dict(sh, device=device_for(sh["device"], cls, ref))  # only the style changes; a span keeps its own x
        if isinstance(sh.get("halves"), list):
            sh = dict(sh, halves=[dict(h, device=device_for(h["device"], cls, ref))
                                  if isinstance(h.get("device"), dict) and h["device"].get("style") == "phone" else h
                                  for h in sh["halves"]])
        out.append(sh)
    style = merge(style, {"_caption_floor": caption_floor(out, style, W, H, fonts, lang)})
    return W, H, style, out, tokens, spec


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
        if dv["style"] in ("phone", "android"):
            warnings.append("device frame in the feature graphic - Google Play advises against device imagery")
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
        spec_l = localize(raw_spec, loc, locales) if loc else raw_spec
        lang = (loc.split("-")[0] if loc else spec_l.get("lang", "en"))
        sizes = [a.size] if a.size else spec_l.get("sizes", DEFAULT_SIZES)
        for name in sizes:
            try:
                W, H, style, shots, tokens, spec = prepare(spec_l, name, spec_dir, fonts, lang)
            except ValueError as e:
                sys.exit(str(e))
            out_dir = os.path.join(out_root, name)
            os.makedirs(out_dir, exist_ok=True)
            cls = style["_class"]
            report = {"preset": name, "size": [W, H], "lang": lang, "locale": loc, "device": cls,
                      "store": store_of(name, W, H), "shots": [], "set_warnings": []}
            for w in set_warnings(shots, report["store"]):
                report["set_warnings"].append(w)
                print(f"! {loc or ''} {name} set: {w}")
            if cls == "iphone" and not a.size:
                for w in iphone_size_warnings(sizes):
                    report["set_warnings"].append(w)
                    print(f"! {loc or ''} {name} set: {w}")
            slot = 0
            for i, shot in enumerate(shots, start=1):
                n_slots = 2 if (shot.get("span", 1) == 2 or shot.get("halves")) else 1
                try:
                    imgs, warnings, size = render_any(shot, style, W, H, fonts, spec_dir, lang)
                except (FileNotFoundError, ValueError) as e:
                    print(f"x {name} shot {i}: {e}", file=sys.stderr)
                    exit_code = 1
                    slot += n_slots
                    continue
                heads = ([h.get("headline", "") for h in span_halves(shot)] if len(imgs) == 2 else [shot.get("headline", "")])
                subs = ([h.get("sub", "") for h in span_halves(shot)] if len(imgs) == 2 else [shot.get("sub", "")])
                label = f"{slot + 1:02d}" + (f"-{slot + len(imgs):02d}" if len(imgs) > 1 else "")
                for j, img in enumerate(imgs):
                    slot += 1
                    path = os.path.join(out_dir, f"{slot:02d}.png")
                    img.convert("RGB").save(path, optimize=True)
                    entry = {"file": os.path.basename(path), "shot": i,
                             "headline": (heads[j] or "").replace("*", "").replace("\n", " "),
                             "sub": subs[j] or "", "layout": shot.get("layout", "device"),
                             "headline_px": size, "warnings": warnings if j == 0 else []}
                    if len(imgs) > 1:
                        entry["span"] = label
                    report["shots"].append(entry)
                for w in warnings:
                    print(f"! {loc or ''} {name} {label}: {w}")
            report["fonts"] = sorted(fonts.used)
            with open(os.path.join(out_dir, "_render.json"), "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=1)
            print(f"{(loc + ' ') if loc else ''}{name}: {len(report['shots'])} shots → {out_dir}   fonts: {', '.join(report['fonts'])}")
        android_sizes = [n for n in sizes if store_of(n, *preset_size(n)) == "android"]
        if spec_l.get("feature_graphic") and (android_sizes or a.size is None):
            _, _, fg_style, _, tokens, fg_spec = prepare(spec_l, android_sizes[0] if android_sizes else "android",
                                                         spec_dir, fonts, lang)
            fg = design.resolve_tokens(fg_spec["feature_graphic"], tokens)
            fg_path = os.path.join(out_root, "feature-graphic.png")
            for w in render_feature_graphic(fg, fg_style, fonts, spec_dir, lang, fg_path):
                print(f"! {loc or ''} feature graphic: {w}")
            with open(os.path.join(out_root, "_feature-graphic.json"), "w", encoding="utf-8") as f:
                json.dump({"headline": (fg.get("headline") or "").replace("*", "").replace("\n", " "),
                           "sub": fg.get("sub") or "", "lang": lang}, f, ensure_ascii=False, indent=1)
            print(f"{(loc + ' ') if loc else ''}feature graphic → {fg_path}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
