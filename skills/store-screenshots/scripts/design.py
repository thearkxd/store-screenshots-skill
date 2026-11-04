"""Design layer for render_set.py: directions, brand tokens, backgrounds, motifs, stickers, annotations.

A *direction* (assets/directions/<name>.json) is a complete visual system - type pairing, background
treatment, layout grammar, emphasis device, device treatment, motif - written with brand tokens:

  $primary  $secondary  $accent  $ink  $paper  $dark
  $primary_tint  $primary_shade  $secondary_tint  $paper_shade  $ink_soft

A spec picks one with "direction": "cinematic" and supplies "brand": {"primary": "#5B5BF5", ...}. Anything in
the spec's "style" or a shot overrides the direction. Directions may define "rotation" (per-shot overrides
cycled across the set), "shot_defaults" and "poster_defaults".
"""
import json
import math
import os
import random
import zlib

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
DIR_DIR = os.path.normpath(os.path.join(HERE, "..", "assets", "directions"))


# ------------------------------------------------------------------ colour

def hexrgb(h):
    h = h.lstrip("#")
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in range(0, 6, 2))


def rgbhex(c):
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(v)))) for v in c[:3])


def mix(a, b, t):
    a, b = hexrgb(a), hexrgb(b)
    return rgbhex(tuple(a[k] + (b[k] - a[k]) * t for k in range(3)))


def lum(h):
    r, g, b = (v / 255 for v in hexrgb(h))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def tokens_from_brand(brand):
    b = dict(brand or {})
    primary = b.get("primary", "#4F46E5")
    ink = b.get("ink", "#121212")
    paper = b.get("paper", "#F3EFE8")
    t = {
        "primary": primary,
        "secondary": b.get("secondary", mix(primary, "#FFB020", 0.55)),
        "accent": b.get("accent", primary),
        "ink": ink,
        "paper": paper,
        "dark": b.get("dark", mix(ink, primary, 0.12)),
    }
    t["primary_tint"] = b.get("primary_tint", mix(primary, "#FFFFFF", 0.82))
    t["primary_shade"] = b.get("primary_shade", mix(primary, "#000000", 0.55))
    t["primary_light"] = b.get("primary_light", mix(primary, "#FFFFFF", 0.38))
    t["secondary_tint"] = b.get("secondary_tint", mix(t["secondary"], "#FFFFFF", 0.8))
    t["paper_shade"] = b.get("paper_shade", mix(paper, ink, 0.07))
    t["ink_soft"] = b.get("ink_soft", mix(ink, paper, 0.35))
    t["on_primary"] = b.get("on_primary", paper if lum(primary) < 0.4 else ink)
    return t


def resolve_tokens(obj, tok):
    if isinstance(obj, str) and obj.startswith("$"):
        return tok.get(obj[1:], obj)
    if isinstance(obj, dict):
        return {k: resolve_tokens(v, tok) for k, v in obj.items()}
    if isinstance(obj, list):
        return [resolve_tokens(v, tok) for v in obj]
    return obj


def deep_merge(base, over, replace=("background",)):
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict) and k not in replace:
            out[k] = deep_merge(out[k], v, replace)
        else:
            out[k] = v
    return out


# ------------------------------------------------------------------ directions

def list_directions():
    out = {}
    if os.path.isdir(DIR_DIR):
        for f in sorted(os.listdir(DIR_DIR)):
            if f.endswith(".json"):
                with open(os.path.join(DIR_DIR, f), encoding="utf-8") as fh:
                    d = json.load(fh)
                out[f[:-5]] = d
    return out


def load_direction(name):
    path = os.path.join(DIR_DIR, f"{name}.json")
    if not os.path.exists(path):
        raise SystemExit(f"unknown direction {name!r}; available: {', '.join(list_directions())}")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


SHOT_KEYS = ("background", "text_color", "sub_color", "emphasis", "device", "card", "font", "case", "align",
             "shapes", "overline_style", "tracking", "band_color", "stickers_style", "annotation_style")


def ensure_brand(spec, spec_dir):
    """Fill missing brand tokens from "brand_from": [icon, screens...] (paths relative to the spec)."""
    src = spec.get("brand_from")
    if not src:
        return spec
    paths = [p if os.path.isabs(p) else os.path.join(spec_dir, p) for p in src]
    guess = brand_from_images([p for p in paths if os.path.exists(p)])
    return dict(spec, brand={**guess, **(spec.get("brand") or {})})


def apply_direction(spec):
    """Return (style, shots, tokens) with the direction and brand tokens applied. Spec values win."""
    name = spec.get("direction")
    tok = tokens_from_brand(spec.get("brand"))
    style = dict(spec.get("style") or {})
    shots = [dict(s) for s in spec.get("shots", [])]
    if name:
        d = load_direction(name)
        user_style = style
        style = deep_merge(d.get("style", {}), style)
        rot = (d.get("rotation") or []) if spec.get("rotation", True) is not False else []
        n = len(shots)
        for i, s in enumerate(shots):
            base = dict(d.get("shot_defaults", {}))
            if s.get("layout") == "poster":
                base = deep_merge(base, d.get("poster_defaults", {}))
            elif rot:
                base = deep_merge(base, rot[i % len(rot)])
            if i == n - 1 and d.get("last_defaults"):
                base = deep_merge(base, d["last_defaults"])
            if "text_color" in base and "sub_color" not in base:
                base["sub_color"] = base["text_color"]  # a new ground for the headline is a new ground for the sub
            # the spec's own "style" beats the direction's per-shot defaults for the keys it sets
            base = deep_merge(base, {k: user_style[k] for k in base if k in user_style})
            # shot keys win; a shot "style" dict also wins
            merged = deep_merge(base, {k: v for k, v in s.items()})
            shots[i] = merged
    style = resolve_tokens(style, tok)
    shots = [resolve_tokens(s, tok) for s in shots]
    for i, s in enumerate(shots):
        s["_index"] = i
        s["_count"] = len(shots)
    return style, shots, tok


# ------------------------------------------------------------------ backgrounds

def cover(img, W, H, box=None):
    if box:
        img = img.crop((int(box[0] * img.width), int(box[1] * img.height), int(box[2] * img.width), int(box[3] * img.height)))
    k = max(W / img.width, H / img.height)
    img = img.resize((max(1, int(img.width * k + 1)), max(1, int(img.height * k + 1))), Image.LANCZOS)
    x, y = (img.width - W) // 2, (img.height - H) // 2
    return img.crop((x, y, x + W, y + H))


def sampled_background(W, H, bg, screen):
    """Cinematic ground: the screen's hero area, blurred and darkened, so the set takes the app's own colour."""
    src = screen if screen is not None else Image.new("RGB", (10, 10), hexrgb(bg.get("color", "#111111")))
    small = cover(src, max(8, W // 8), max(8, H // 8), bg.get("box", [0, 0.1, 1, 0.5]))
    small = small.filter(ImageFilter.GaussianBlur(max(2, W // 8 * bg.get("blur", 0.08))))
    img = small.resize((W, H), Image.BICUBIC)
    dark = hexrgb(bg.get("tint", "#0A0A0E"))
    top_a, bot_a = bg.get("darken", [0.62, 0.78])
    grad = Image.linear_gradient("L").resize((W, H))
    alpha = grad.point(lambda v: int(255 * (top_a + (bot_a - top_a) * v / 255)))
    img.paste(Image.new("RGB", (W, H), dark), (0, 0), alpha)
    return img


def add_light(img, light, W, H):
    """A soft radial light (not neon glow): {"color", "x", "y", "r", "opacity"}."""
    r = int(W * light.get("r", 0.7))
    size = max(4, r * 2)
    g = Image.radial_gradient("L").resize((size, size))
    mask = g.point(lambda v: int(255 * light.get("opacity", 0.3) * max(0.0, 1 - v / 255) ** 1.6))
    col = Image.new("RGB", (size, size), hexrgb(light.get("color", "#FFFFFF")))
    img.paste(col, (int(W * light.get("x", 0.5)) - r, int(H * light.get("y", 0.2)) - r), mask)
    return img


def add_grain(img, amount, seed=7):
    if not amount:
        return img
    W, H = img.size
    noise = Image.effect_noise((W // 2, H // 2), 64).resize((W, H), Image.NEAREST)
    noise = noise.point(lambda v: 128 + (v - 128))
    grey = Image.merge("RGB", (noise, noise, noise))
    return Image.blend(img, Image.composite(grey, img, Image.new("L", (W, H), 255)), amount)


# ------------------------------------------------------------------ shapes & motifs

def _rgba(c, a=1.0):
    r, g, b = hexrgb(c)
    return (r, g, b, int(255 * a))


def draw_shapes(img, shapes, index, W, H):
    """Shapes behind the device. Coordinates are fractions of the canvas; "line" points use set space
    (x = shot index + fraction), so a motif can run continuously across the whole set."""
    if not shapes:
        return img
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for sh in shapes:
        t = sh.get("type")
        col = _rgba(sh.get("color", "#FFFFFF"), sh.get("opacity", 1.0))
        if t == "circle":
            cx, cy, r = sh["x"] * W, sh["y"] * H, sh["r"] * W
            if sh.get("stroke"):
                d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=max(1, int(sh["stroke"] * W)))
            else:
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
        elif t == "arch":
            x0, y0, w, h = sh["x"] * W, sh["y"] * H, sh["w"] * W, sh["h"] * H
            d.rounded_rectangle([x0, y0, x0 + w, y0 + h + w], radius=int(w / 2), fill=col)
        elif t == "rect":
            d.rounded_rectangle([sh["x"] * W, sh["y"] * H, (sh["x"] + sh["w"]) * W, (sh["y"] + sh["h"]) * H],
                                radius=int(sh.get("radius", 0) * W), fill=col)
        elif t == "band":
            band = Image.new("RGBA", (W * 3, int(sh.get("h", 0.08) * H)), col)
            band = band.rotate(sh.get("angle", -12), expand=True, resample=Image.BICUBIC)
            layer.alpha_composite(band, (int(W / 2 - band.width / 2), int(sh.get("y", 0.5) * H - band.height / 2)))
        elif t == "grid":
            step = int(sh.get("step", 0.08) * W)
            wdt = max(1, int(sh.get("width", 0.0015) * W))
            for x in range(step // 2, W, step):
                d.line([(x, 0), (x, H)], fill=col, width=wdt)
            for y in range(step // 2, H, step):
                d.line([(0, y), (W, y)], fill=col, width=wdt)
        elif t == "dots":
            step = int(sh.get("step", 0.05) * W)
            r = max(1, int(sh.get("r", 0.004) * W))
            for y in range(step // 2, H, step):
                for x in range(step // 2, W, step):
                    d.ellipse([x - r, y - r, x + r, y + r], fill=col)
        elif t == "wave":
            # continuous across the set: y(x) = y + amp * sin(2pi * (index + x) / period + phase)
            pts = []
            for i in range(0, 61):
                xs = i / 60
                xg = index + xs
                yy = sh.get("y", 0.5) + sh.get("amp", 0.04) * math.sin(2 * math.pi * xg / sh.get("period", 1.4) + sh.get("phase", 0))
                pts.append((xs * W, yy * H))
            d.line(pts, fill=col, width=max(2, int(sh.get("width", 0.03) * W)), joint="curve")
            if sh.get("double"):
                off = sh["double"] * H
                d.line([(x, y + off) for x, y in pts], fill=col, width=max(2, int(sh.get("width", 0.03) * W)), joint="curve")
        elif t == "line":
            pts = smooth([((p[0] - index) * W, p[1] * H) for p in sh["points"]])
            if pts:
                d.line(pts, fill=col, width=max(2, int(sh.get("width", 0.02) * W)), joint="curve")
                if sh.get("caps", True):
                    rr = max(1, int(sh.get("width", 0.02) * W / 2))
                    for p in (pts[0], pts[-1]):
                        d.ellipse([p[0] - rr, p[1] - rr, p[0] + rr, p[1] + rr], fill=col)
    img = img.convert("RGBA")
    img.alpha_composite(layer)
    return img.convert("RGB")


def smooth(points, steps=24):
    """Catmull-Rom through the points, so motifs look drawn, not plotted."""
    if len(points) < 3:
        return points
    out = []
    p = [points[0]] + points + [points[-1]]
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for s in range(steps):
            t = s / steps
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2
                                    + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3) for k in range(2)))
    out.append(points[-1])
    return out


# ------------------------------------------------------------------ hand-drawn marks

def _rng(*seed):
    # zlib.crc32, not hash(): str hashes change per process, marks must be the same on every render
    return random.Random(zlib.crc32(repr(seed).encode()))


def hand_ellipse(d, box, color, width, seed=1):
    x0, y0, x1, y1 = box
    cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
    r = _rng("e", seed, int(cx), int(cy))
    start = r.uniform(-2.4, -1.8)
    pts = []
    n = 90
    for i in range(n + 12):  # overlap the start, like a pen stroke
        a = start + 2 * math.pi * i / n
        k = 1 + 0.035 * math.sin(3 * a + seed) + r.uniform(-0.008, 0.008)
        grow = 1 + 0.06 * i / n
        pts.append((cx + rx * k * grow * math.cos(a), cy + ry * k * math.sin(a)))
    d.line(pts, fill=color, width=width, joint="curve")


def hand_underline(d, x0, x1, y, color, width, seed=1):
    r = _rng("u", seed, int(x0))
    pts = []
    n = 30
    for i in range(n + 1):
        t = i / n
        pts.append((x0 + (x1 - x0) * t, y + math.sin(t * math.pi) * width * 0.6 + r.uniform(-0.12, 0.12) * width))
    d.line(pts, fill=color, width=width, joint="curve")


def hand_arrow(d, a, b, color, width, curve=0.25, seed=1):
    (x0, y0), (x1, y1) = a, b
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    nx, ny = -(y1 - y0), (x1 - x0)
    cx, cy = mx + nx * curve, my + ny * curve
    pts = [((1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x1, (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y1)
           for t in (i / 40 for i in range(41))]
    d.line(pts, fill=color, width=width, joint="curve")
    ang = math.atan2(y1 - pts[-4][1], x1 - pts[-4][0])
    L = width * 4.2
    for s in (-0.5, 0.5):
        d.line([(x1, y1), (x1 - L * math.cos(ang + s), y1 - L * math.sin(ang + s))], fill=color, width=width)


# ------------------------------------------------------------------ stickers & annotations

def draw_text_rotated(img, xy, text, font, fill, angle=0, bg=None, pad=(0.5, 0.28), radius=1.0, shadow=False, anchor="mm"):
    """Text (optionally on a pill) rotated around its centre at xy."""
    l, t, r, b = font.getbbox(text)
    tw, th = r - l, b - t
    px, py = int(font.size * pad[0]), int(font.size * pad[1])
    w, h = tw + 2 * px, th + 2 * py
    tile = Image.new("RGBA", (w + 8, h + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    if bg:
        d.rounded_rectangle([4, 4, 4 + w, 4 + h], radius=int(h / 2 * radius), fill=_rgba(bg))
    d.text((4 + px - l, 4 + py - t), text, font=font, fill=_rgba(fill))
    tile = tile.rotate(angle, expand=True, resample=Image.BICUBIC)
    base = img.convert("RGBA")
    x, y = int(xy[0] - tile.width / 2), int(xy[1] - tile.height / 2)
    if shadow:
        sh = Image.new("RGBA", tile.size, (0, 0, 0, 0))
        sh.paste((0, 0, 0, 70), (0, 0), tile.split()[3])
        sh = sh.filter(ImageFilter.GaussianBlur(max(2, font.size // 6)))
        base.alpha_composite(sh, (x, y + max(2, font.size // 8)))
    base.alpha_composite(tile, (x, y))
    return base.convert("RGB")


def draw_stickers(img, stickers, fonts, W, H, defaults=None):
    for st in stickers or []:
        o = deep_merge(defaults or {}, st)
        f = fonts.get(o.get("font", "rounded"), int(W * o.get("size", 0.042)))
        img = draw_text_rotated(img, (W * o["x"], H * o["y"]), o["text"], f, o.get("color", "#FFFFFF"),
                                o.get("rotate", -5), bg=o.get("bg", "#111111"), shadow=o.get("shadow", True))
    return img


def map_screen_box(box, xf):
    """screen-fraction box -> canvas pixels, through the device transform (x, y, scale, w, h, angle, centre)."""
    sx, sy, k, sw, sh, ang, (cx, cy) = xf
    pts = [(sx + box[0] * sw, sy + box[1] * sh), (sx + box[2] * sw, sy + box[3] * sh)]
    if ang:
        a = math.radians(-ang)
        pts = [(cx + (x - cx) * math.cos(a) - (y - cy) * math.sin(a), cy + (x - cx) * math.sin(a) + (y - cy) * math.cos(a)) for x, y in pts]
    (x0, y0), (x1, y1) = pts
    return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]


def draw_annotations(img, notes, fonts, W, H, xf=None, defaults=None):
    """Hand-drawn marks on top: circle / underline / arrow / note. Boxes: "box" (canvas fractions) or
    "screen_box" (fractions of the screen image, mapped through the device)."""
    if not notes:
        return img
    o0 = defaults or {}
    img = img.convert("RGBA")
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    texts = []
    for i, n in enumerate(notes):
        o = deep_merge(o0, n)
        col = _rgba(o.get("color", "#FF4D2E"))
        wdt = max(3, int(W * o.get("width", 0.009)))
        if "screen_box" in o and xf:
            bx = map_screen_box(o["screen_box"], xf)
        elif "box" in o:
            b = o["box"]
            bx = [b[0] * W, b[1] * H, b[2] * W, b[3] * H]
        else:
            bx = None
        pad = W * o.get("pad", 0.02)
        t = o.get("type")
        if t == "circle" and bx:
            hand_ellipse(d, [bx[0] - pad, bx[1] - pad, bx[2] + pad, bx[3] + pad], col, wdt, seed=i + 1)
        elif t == "underline" and bx:
            hand_underline(d, bx[0], bx[2], bx[3] + pad * 0.6, col, wdt, seed=i + 1)
        elif t == "arrow":
            a = (o["from"][0] * W, o["from"][1] * H)
            if "to" in o:
                b = (o["to"][0] * W, o["to"][1] * H)
            elif bx:
                b = ((bx[0] + bx[2]) / 2, bx[1] - pad)
            else:
                continue
            hand_arrow(d, a, b, col, wdt, o.get("curve", 0.25), seed=i + 1)
        if o.get("text"):
            texts.append(o)
    img.alpha_composite(layer)
    img = img.convert("RGB")
    for o in texts:
        f = fonts.get(o.get("font", "hand"), int(W * o.get("size", 0.06)))
        x, y = (o["text_at"] if "text_at" in o else o.get("from", [0.5, 0.5]))
        img = draw_text_rotated(img, (W * x, H * y), o["text"], f, o.get("text_color", o.get("color", "#FF4D2E")),
                                o.get("rotate", -4), bg=None)
    return img


# ------------------------------------------------------------------ brand from images

def palette(img, n=5):
    small = img.convert("RGB").resize((64, 64))
    q = small.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[: n * 3]
    cols = sorted(q.getcolors(), reverse=True)
    return [rgbhex(pal[i * 3:i * 3 + 3]) for _, i in cols]


def saturation(h):
    r, g, b = (v / 255 for v in hexrgb(h))
    mx, mn = max(r, g, b), min(r, g, b)
    return 0 if mx == 0 else (mx - mn) / mx


def brand_from_images(paths):
    """Guess brand tokens from the icon and screens: the most saturated frequent colour is the primary."""
    cols = []
    for p in paths:
        try:
            cols += palette(Image.open(p), 6)
        except Exception:
            pass
    vivid = [c for c in cols if saturation(c) > 0.35 and 0.05 < lum(c) < 0.75]
    primary = vivid[0] if vivid else "#4F46E5"
    darkish = [c for c in cols if lum(c) < 0.03]
    out = {"primary": primary}
    if darkish:
        out["dark"] = darkish[0]
    return out
