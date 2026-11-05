#!/usr/bin/env python3
"""Scenes: free compositions built from primitive layers, drawn to PNG (resvg, or Pillow) and to editable SVG.

A scene is not a template. It is a canvas plus an ordered list of layers - text boxes, real screens (or crops
of them), registered brand images, rectangles, ellipses, paths, groups and hand marks - each placed freely.
Nothing about "headline on top, phone in the middle" is built in. See references/scene-format.md.

Units: 1u = 1/2.174 of the canvas height (= the full width of an iPhone canvas). Every canvas is 2.174u tall;
width varies (iPhone 1u, Android 1.22u, iPhone Duo 1.49u, a span 2x). Any x/w can also be a percentage of
the canvas width ("50%"), any y/h a percentage of its height. Anchors: x / cx / right, y / cy / bottom.

Truth rules built into the format: a "screen" layer shows pixels of a registered evidence screen only;
it takes a width OR a height - the other follows the crop, so UI can't be stretched; no filters, no
recolouring, opacity is always 1.

This module is a library; compose.py is the command line.
"""
import base64
import io
import math
import os
import re
import sys
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design  # noqa: E402
import device3d as d3  # noqa: E402
import render_set as rs  # noqa: E402
from PIL import Image, ImageChops, ImageDraw, ImageFilter  # noqa: E402

PHONE_RATIO = rs.PHONE_RATIO

TEXT_DEFAULTS = {"size": 0.096, "min_size": None, "line_height": 1.06, "tracking": -0.018, "align": "left",
                 "case": "none", "max_lines": 3, "color": "#151515", "font": "sans", "weight": None,
                 "emphasis": {"style": "color", "color": "#E5482D"}}
SHADOW_PRESETS = {"soft": {"blur": 0.035, "dy": 0.02, "opacity": 0.28, "color": "#000000"},
                  "deep": {"blur": 0.06, "dy": 0.04, "opacity": 0.4, "color": "#000000"},
                  "tight": {"blur": 0.012, "dy": 0.008, "opacity": 0.3, "color": "#000000"}}


class SceneError(ValueError):
    pass


# ------------------------------------------------------------------ canvas & units

class Canvas:
    def __init__(self, W, H, span=1):
        self.slot_w, self.H, self.span = W, H, span
        self.W = W * span
        self.U = H / PHONE_RATIO

    def len_x(self, v, what="x"):
        if isinstance(v, str) and v.strip().endswith("%"):
            return float(v.strip()[:-1]) / 100 * self.W
        if isinstance(v, (int, float)):
            return v * self.U
        raise SceneError(f"{what}: expected a number (units) or 'N%', got {v!r}")

    def len_y(self, v, what="y"):
        if isinstance(v, str) and v.strip().endswith("%"):
            return float(v.strip()[:-1]) / 100 * self.H
        if isinstance(v, (int, float)):
            return v * self.U
        raise SceneError(f"{what}: expected a number (units) or 'N%', got {v!r}")

    def place_x(self, L, w):
        """Left edge in px from x / cx / right."""
        if "x" in L:
            return self.len_x(L["x"], "x")
        if "cx" in L:
            return self.len_x(L["cx"], "cx") - w / 2
        if "right" in L:
            return self.W - self.len_x(L["right"], "right") - w
        return (self.W - w) / 2

    def place_y(self, L, h):
        if "y" in L:
            return self.len_y(L["y"], "y")
        if "cy" in L:
            return self.len_y(L["cy"], "cy") - h / 2
        if "bottom" in L:
            return self.H - self.len_y(L["bottom"], "bottom") - h
        return (self.H - h) / 2


# ------------------------------------------------------------------ colours

def color(c, tokens, what="colour"):
    if c is None:
        return None
    if isinstance(c, dict):
        return c
    if isinstance(c, str) and c.startswith("$"):
        if c[1:] not in tokens:
            raise SceneError(f"unknown colour token {c} (tokens: {', '.join(sorted(tokens))})")
        c = tokens[c[1:]]
    if not (isinstance(c, str) and re.fullmatch(r"#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?", c)):
        raise SceneError(f"{what}: expected #RRGGBB, a $token or a gradient, got {c!r}")
    return c.upper()


def resolve_fill(f, tokens):
    """#hex · $token · {"linear": {"angle", "stops": [[0, c], [1, c]]}} · {"radial": {"cx", "cy", "r", "stops"}}"""
    if f is None or isinstance(f, str):
        return color(f, tokens)
    for kind in ("linear", "radial"):
        if kind in f:
            g = dict(f[kind])
            g["stops"] = [[float(o), color(c, tokens)] for o, c in g.get("stops", [])]
            if len(g["stops"]) < 2:
                raise SceneError(f"{kind} gradient needs at least two stops")
            return {kind: g}
    raise SceneError(f"fill: unknown {f!r}")


def rgba(c, opacity=1.0):
    h = c.lstrip("#")
    a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(255 * a * opacity))


def fill_colors(f):
    if f is None:
        return []
    if isinstance(f, str):
        return [f]
    g = f.get("linear") or f.get("radial")
    return [c for _, c in g["stops"]]


# ------------------------------------------------------------------ fonts

WEIGHT_WORDS = [("thin", 100), ("extralight", 200), ("ultralight", 200), ("light", 300), ("regular", 400),
                ("book", 400), ("medium", 500), ("semibold", 600), ("demibold", 600), ("extrabold", 800),
                ("ultrabold", 800), ("bold", 700), ("black", 900), ("heavy", 900)]


def face(path):
    """(family, weight, italic) as resvg/SVG should ask for this exact file."""
    from PIL import ImageFont
    f = ImageFont.truetype(path, 20)
    family, style = f.getname()
    words = (family + " " + style).lower().replace("-", "").replace(" ", "")
    weight = 400
    for w, n in WEIGHT_WORDS:
        if w in words:
            weight = n
            break
    try:
        from fontTools.ttLib import TTFont
        weight = TTFont(path, lazy=True)["OS/2"].usWeightClass or weight
    except Exception:
        pass
    italic = "italic" in style.lower() or "oblique" in style.lower()
    return family, weight, italic


def font_ref(fonts, name, campaign_fonts):
    """A font name in a scene: a campaign role ("display"), a bundled alias ("sans-bold") or a path."""
    if isinstance(name, str) and name in (campaign_fonts or {}):
        name = campaign_fonts[name]
    return fonts.resolve(name)


# ------------------------------------------------------------------ text layout

class TextLayout:
    """Lays out a text layer into positioned word runs (shared by both backends)."""

    def __init__(self, L, canvas, fonts, lang, tokens, campaign):
        self.c, self.fonts, self.lang, self.tokens = canvas, fonts, lang, tokens
        styles = (campaign or {}).get("type", {})
        base = dict(TEXT_DEFAULTS)
        if L.get("style"):
            if L["style"] not in styles:
                raise SceneError(f"text style {L['style']!r} isn't in the campaign's \"type\" ({', '.join(styles) or 'none'})")
            base = rs.merge(base, styles[L["style"]])
        self.s = rs.merge(base, {k: v for k, v in L.items() if k not in ("type",)})
        self.cfonts = (campaign or {}).get("fonts", {})

    def font(self, size, emph):
        e = self.s["emphasis"] or {}
        if emph and e.get("style") == "font" and e.get("font"):
            path, w = font_ref(self.fonts, e["font"], self.cfonts)
            return self.fonts.get({"path": path, "weight": e.get("weight") or w}, int(size * e.get("scale", 1.0))), path, e.get("weight") or w
        path, w = font_ref(self.fonts, self.s["font"], self.cfonts)
        return self.fonts.get({"path": path, "weight": self.s.get("weight") or w}, size), path, self.s.get("weight") or w

    def track(self, size):
        return self.s["tracking"] * size

    def word_w(self, tok, size):
        return rs.text_width(self.font(size, tok[1])[0], tok[0], self.track(size))

    def gap(self, line, i, size):
        if i == 0:
            return 0
        g = 0 if line[i][2] else self.font(size, False)[0].getlength(" ")
        style = (self.s["emphasis"] or {}).get("style")
        if style in ("box", "marker") and line[i][1] != line[i - 1][1]:
            g += size * ((self.s["emphasis"].get("pad", 0.16) + 0.04) if style == "box" else 0.08)
        return g

    def measure(self, line, size):
        return sum(self.word_w(t, size) for t in line) + sum(self.gap(line, i, size) for i in range(1, len(line)))

    def prep(self, text):
        case = self.s.get("case")
        if case == "upper":
            return rs.tr_upper(text) if self.lang == "tr" else text.upper()
        if case == "lower":
            return rs.tr_lower(text) if self.lang == "tr" else text.lower()
        return text

    def block_h(self, lines, size):
        lh = int(size * self.s["line_height"])
        f0 = self.font(size, False)[0]
        accented = sum(1 for li, l in enumerate(lines) if li and self.s["line_height"] < 1.05
                       and any(ch in "ÇĞİÖŞÜÂÊÎÔÛÀÁÉÍÓÚÑÄËÏ" for t in l for ch in t[0]))
        return (lh * (len(lines) - 1) + f0.getmetrics()[0] + f0.getbbox("gy", anchor="ls")[3]
                + accented * int(size * (1.05 - self.s["line_height"]) + size * 0.06)), lh

    def layout(self, L):
        c = self.c
        text = self.prep(str(L.get("text", "")))
        if not text.strip():
            raise SceneError("text layer without text")
        w_px = c.len_x(L["w"], "w") if "w" in L else c.W * 0.86
        max_h = c.len_y(L["h"], "h") if "h" in L else None
        size = int(c.U * self.s["size"])
        min_size = int(c.U * (self.s["min_size"] if self.s["min_size"] is not None else self.s["size"] * 0.6))
        toks = rs.tokenize(text)
        warnings = []
        # explicit line breaks are the designer's: shrink the type before breaking a line again ("wrap": true re-wraps)
        max_lines = self.s["max_lines"]
        if "\n" in text and self.s.get("wrap") is not True:
            max_lines = min(max_lines, text.count("\n") + 1)
        while True:
            lines = rs.wrap(toks, lambda l: self.measure(l, size), w_px)
            bh, lh = self.block_h(lines, size)
            fits = (len(lines) <= max_lines and all(self.measure(l, size) <= w_px + 0.5 for l in lines)
                    and (max_h is None or bh <= max_h))
            if fits or size <= min_size:
                break
            size = max(min_size, int(size * 0.96))
        if not fits:
            warnings.append(f"text doesn't fit its box even at the minimum size: {text[:40]!r}")
        bh, lh = self.block_h(lines, size)
        x0 = c.place_x(L, w_px)
        y0 = c.place_y(L, bh)
        runs, rects, marks = [], [], []
        f0 = self.font(size, False)[0]
        ascent = f0.getmetrics()[0]
        e = self.s["emphasis"] or {}
        base_col = color(self.s["color"], self.tokens, "text colour")
        y = y0
        accented_set = set("ÇĞİÖŞÜÂÊÎÔÛÀÁÉÍÓÚÑÄËÏ")
        line_boxes, inks = [], []
        for li, line in enumerate(lines):
            if li and self.s["line_height"] < 1.05 and any(ch in accented_set for t in line for ch in t[0]):
                y += int(size * (1.05 - self.s["line_height"]) + size * 0.06)
            lw = self.measure(line, size)
            align = self.s["align"]
            x = x0 if align == "left" else x0 + (w_px - lw) / 2 if align == "center" else x0 + w_px - lw
            base = y + ascent
            cx, run_emph = x, None
            for i, (word, em, glued) in enumerate(line):
                cx += self.gap(line, i, size)
                fnt, path, weight = self.font(size, em)
                ww = rs.text_width(fnt, word, self.track(size))
                col = base_col
                if em and e.get("color") and e.get("style") in ("color", "font", "underline", "scribble"):
                    col = color(e["color"], self.tokens, "emphasis colour")
                if em and e.get("style") == "box" and e.get("text_color"):
                    col = color(e["text_color"], self.tokens, "emphasis text colour")
                runs.append({"text": word, "x": cx, "y": base, "path": path, "weight": weight, "size": fnt.size,
                             "fill": col, "tracking": self.track(size) * fnt.size / max(size, 1)})
                ib = fnt.getbbox(word, anchor="ls")
                inks.append((cx + ib[0], base + ib[1], cx + ww, base + ib[3]))
                if em:
                    run_emph = [cx, cx + ww] if run_emph is None else [run_emph[0], cx + ww]
                cx += ww
                end_of_run = em and (i == len(line) - 1 or not line[i + 1][1])
                if end_of_run and run_emph:
                    self._emph_mark(run_emph, base, size, e, rects, marks)
                    run_emph = None
            line_boxes.append((x, y, x + lw, base + f0.getbbox("gy", anchor="ls")[3]))
            y += lh
        bbox = (min(b[0] for b in line_boxes), y0, max(b[2] for b in line_boxes), y0 + bh)
        ink = (min(b[0] for b in inks), min(b[1] for b in inks), max(b[2] for b in inks), max(b[3] for b in inks)) if inks else bbox
        return {"runs": runs, "rects": rects, "marks": marks, "bbox": bbox, "ink": ink, "size": size, "lines": len(lines),
                "warnings": warnings, "text": text}

    def _emph_mark(self, run, base, size, e, rects, marks):
        style = e.get("style")
        fe = self.font(size, True)[0]
        cap = -fe.getbbox("Hd", anchor="ls")[1]
        desc = fe.getbbox("gy", anchor="ls")[3]
        if style == "box":
            pad = size * e.get("pad", 0.16)
            rects.append({"box": (run[0] - pad, base - cap - size * 0.12, run[1] + pad, base + desc * 0.75),
                          "radius": size * e.get("radius", 0.12), "fill": color(e.get("color", "#FFFFFF"), self.tokens)})
        elif style == "marker":
            pad = size * 0.16
            rects.append({"box": (run[0] - pad * 0.4, base - cap * 0.42, run[1] + pad * 0.4, base + desc * 0.35),
                          "radius": 0, "fill": color(e.get("color", "#FFE600"), self.tokens)})
        elif style in ("underline", "scribble"):
            col = color(e.get("mark_color", e.get("color", "#FF4D2E")), self.tokens)
            wd = max(3, int(size * e.get("mark_width", 0.075)))
            rec = Recorder()
            if style == "underline":
                design.hand_underline(rec, run[0] - size * 0.05, run[1] + size * 0.05, base + size * 0.16, col, wd)
            else:
                design.hand_ellipse(rec, [run[0] - size * 0.22, base - cap - size * 0.2, run[1] + size * 0.22, base + size * 0.24], col, wd)
            marks += rec.lines


class Recorder:
    """Stands in for ImageDraw: records the hand-drawn lines design.py makes, for both backends."""

    def __init__(self):
        self.lines = []

    def line(self, pts, fill=None, width=1, joint=None):
        self.lines.append({"points": [(float(x), float(y)) for x, y in pts], "color": fill if isinstance(fill, str) else
                           "#%02X%02X%02X" % tuple(fill[:3]), "width": width})


# ------------------------------------------------------------------ paths

PATH_TOKEN = re.compile(r"[MmLlHhVvCcSsQqTtZzAa]|-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def parse_path(d):
    """SVG path data -> list of absolute commands [(cmd, [points...])] with M L C Q Z only."""
    toks = PATH_TOKEN.findall(d)
    out, i, cmd = [], 0, None
    cur, start, last_ctrl = (0.0, 0.0), (0.0, 0.0), None

    def num():
        nonlocal i
        v = float(toks[i])
        i += 1
        return v
    while i < len(toks):
        if re.fullmatch(r"[A-Za-z]", toks[i]):
            cmd = toks[i]
            i += 1
            if cmd in "Zz":
                out.append(("Z", []))
                cur = start
                continue
        if cmd is None:
            raise SceneError("path data must start with a command")
        rel = cmd.islower()
        c = cmd.upper()
        ox, oy = cur if rel else (0.0, 0.0)
        if c == "A":
            raise SceneError("path arcs (A) aren't supported - draw curves with C or Q")
        if c in "ML":
            p = (ox + num(), oy + num())
            out.append((c if not (c == "M" and out and out[-1][0] == "M" and False) else "L", [p]))
            if c == "M":
                start = p
                cmd = "l" if rel else "L"
            cur, last_ctrl = p, None
        elif c == "H":
            p = ((cur[0] if rel else 0) + num(), cur[1])
            out.append(("L", [p]))
            cur, last_ctrl = p, None
        elif c == "V":
            p = (cur[0], (cur[1] if rel else 0) + num())
            out.append(("L", [p]))
            cur, last_ctrl = p, None
        elif c == "C":
            p1 = (ox + num(), oy + num())
            p2 = (ox + num(), oy + num())
            p = (ox + num(), oy + num())
            out.append(("C", [p1, p2, p]))
            cur, last_ctrl = p, p2
        elif c == "S":
            p1 = (2 * cur[0] - last_ctrl[0], 2 * cur[1] - last_ctrl[1]) if last_ctrl else cur
            p2 = (ox + num(), oy + num())
            p = (ox + num(), oy + num())
            out.append(("C", [p1, p2, p]))
            cur, last_ctrl = p, p2
        elif c == "Q":
            p1 = (ox + num(), oy + num())
            p = (ox + num(), oy + num())
            out.append(("Q", [p1, p]))
            cur, last_ctrl = p, p1
        elif c == "T":
            p1 = (2 * cur[0] - last_ctrl[0], 2 * cur[1] - last_ctrl[1]) if last_ctrl else cur
            p = (ox + num(), oy + num())
            out.append(("Q", [p1, p]))
            cur, last_ctrl = p, p1
    return out


def path_to_px(cmds, k, ox=0.0, oy=0.0):
    return [(c, [(ox + x * k, oy + y * k) for x, y in pts]) for c, pts in cmds]


def path_d(cmds):
    parts = []
    for c, pts in cmds:
        parts.append(c + " ".join(f"{x:.1f} {y:.1f}" for x, y in pts))
    return " ".join(parts)


def flatten(cmds, steps=20):
    """-> list of (points, closed) polylines."""
    polys, cur = [], []
    pos = (0.0, 0.0)
    closed = False
    for c, pts in cmds:
        if c == "M":
            if len(cur) > 1:
                polys.append((cur, closed))
            cur, closed = [pts[0]], False
            pos = pts[0]
        elif c == "L":
            cur.append(pts[0])
            pos = pts[0]
        elif c == "C":
            p0, (p1, p2, p3) = pos, pts
            for s in range(1, steps + 1):
                t = s / steps
                mt = 1 - t
                cur.append((mt ** 3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t ** 3 * p3[0],
                            mt ** 3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t ** 3 * p3[1]))
            pos = p3
        elif c == "Q":
            p0, (p1, p2) = pos, pts
            for s in range(1, steps + 1):
                t = s / steps
                mt = 1 - t
                cur.append((mt * mt * p0[0] + 2 * mt * t * p1[0] + t * t * p2[0], mt * mt * p0[1] + 2 * mt * t * p1[1] + t * t * p2[1]))
            pos = p2
        elif c == "Z":
            closed = True
            if cur:
                pos = cur[0]
    if len(cur) > 1:
        polys.append((cur, closed))
    return polys


# ------------------------------------------------------------------ geometry helpers

def rot_bbox(box, angle, centre):
    if not angle:
        return box
    x0, y0, x1, y1 = box
    a = math.radians(angle)
    cx, cy = centre
    pts = [(cx + (x - cx) * math.cos(a) - (y - cy) * math.sin(a), cy + (x - cx) * math.sin(a) + (y - cy) * math.cos(a))
           for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    return (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))


def rot_point(p, angle, centre):
    if not angle:
        return p
    a = math.radians(angle)
    cx, cy = centre
    x, y = p
    return (cx + (x - cx) * math.cos(a) - (y - cy) * math.sin(a), cy + (x - cx) * math.sin(a) + (y - cy) * math.cos(a))


def glow_spec(g, U, tokens):
    """A coloured halo behind a layer (no offset): {"color": "$accent", "blur": 0.08, "opacity": 0.45, "spread": 0}."""
    if not g:
        return None
    if not isinstance(g, dict) or not g.get("color"):
        raise SceneError('glow: {"color": "$token", "blur": 0.08, "opacity": 0.45, "spread": 0.0} (u)')
    return {"blur": float(g.get("blur", 0.08)) * U, "dx": 0.0, "dy": 0.0, "opacity": float(g.get("opacity", 0.45)),
            "color": color(g["color"], tokens), "spread": float(g.get("spread", 0.0)) * U}


def glass_spec(g, U, tokens):
    """Frosted glass: what is behind the panel, blurred and tinted, with a hairline edge.
    {"blur": 0.03, "tint": "#FFFFFF", "opacity": 0.12, "edge": "#FFFFFF", "edge_opacity": 0.28}; {} or true = defaults"""
    if g is None or g is False:
        return None
    g = {} if g is True else dict(g)
    return {"blur": float(g.get("blur", 0.03)) * U, "tint": color(g.get("tint", "#FFFFFF"), tokens),
            "opacity": float(g.get("opacity", 0.12)), "edge": color(g.get("edge", "#FFFFFF"), tokens),
            "edge_opacity": float(g.get("edge_opacity", 0.28)), "edge_w": max(1.0, float(g.get("edge_width", 0.0025)) * U)}


def grown(box, d):
    return (box[0] - d, box[1] - d, box[2] + d, box[3] + d)


def shadow_spec(s, U):
    if not s:
        return None
    if isinstance(s, str):
        if s not in SHADOW_PRESETS:
            raise SceneError(f"shadow {s!r}: use {', '.join(SHADOW_PRESETS)} or {{blur, dy, opacity, color}}")
        s = SHADOW_PRESETS[s]
    return {"blur": s.get("blur", 0.035) * U, "dy": s.get("dy", 0.02) * U, "dx": s.get("dx", 0) * U,
            "opacity": s.get("opacity", 0.28), "color": s.get("color", "#000000")}


# ------------------------------------------------------------------ resolve a scene into draw ops

class Scene:
    """Resolve one shot (or a span) into backend-neutral draw ops plus metadata for the validators."""

    def __init__(self, shot, W, H, ctx):
        self.shot = shot
        self.span = shot.get("span", 1)
        if self.span not in (1, 2):
            raise SceneError(f'"span" must be 1 or 2, got {self.span!r}')
        self.c = Canvas(W, H, self.span)
        self.ctx = ctx  # fonts, lang, tokens, campaign, evidence, spec_dir
        self.ops, self.meta, self.warnings = [], [], []
        self.by_id = {}
        self._depth = 0

    # -- loading
    def evidence_image(self, eid, kind="screen"):
        ev = self.ctx["evidence"]
        pool = ev.get("screens" if kind == "screen" else "assets", {})
        if eid not in pool:
            avail = ", ".join(sorted(pool)) or "none"
            raise SceneError(f"{kind} {eid!r} isn't in the evidence manifest ({avail}) - run evidence.py, never draw UI by hand")
        item = pool[eid]
        path = item["path"] if os.path.isabs(item["path"]) else os.path.join(self.ctx["evidence_dir"], item["path"])
        if not os.path.exists(path):
            raise SceneError(f"{kind} {eid!r}: file not found: {item['path']}")
        cache = self.ctx.setdefault("_img", {})
        if path not in cache:
            img = Image.open(path)
            cache[path] = (img.convert("RGBA") if kind == "asset" else img.convert("RGB"), path)
        return cache[path][0], item, path

    def region(self, L, item):
        r = L.get("crop", [0, 0, 1, 1])
        if isinstance(r, str):
            named = item.get("regions", {})
            if r not in named:
                raise SceneError(f"region {r!r} isn't named in the evidence for this screen ({', '.join(named) or 'none'})")
            r = named[r]
        if len(r) != 4 or not (0 <= r[0] < r[2] <= 1.0001 and 0 <= r[1] < r[3] <= 1.0001):
            raise SceneError(f"crop {r!r}: fractions [x0, y0, x1, y1] of the screen, x0 < x1, y0 < y1, within 0..1")
        return [max(0.0, r[0]), max(0.0, r[1]), min(1.0, r[2]), min(1.0, r[3])]

    # -- background
    def background(self):
        bg = self.shot.get("background") or {"fill": "#FFFFFF"}
        tokens = self.ctx["tokens"]
        c = self.c
        if "fill" in bg:
            f = resolve_fill(bg["fill"], tokens)
            self.ops.append({"op": "rect", "box": (0, 0, c.W, c.H), "radius": 0, "fill": f,
                             "meta": {"role": "background", "colors": fill_colors(f)}})
        elif "sample" in bg:
            s = bg["sample"]
            img, item, path = self.evidence_image(s["evidence"])
            r = self.region(s, item)
            piece = rs.crop_frac(img, r)
            sb = design.sampled_background(int(c.W), int(c.H), {"box": [0, 0, 1, 1], "blur": s.get("blur", 0.08),
                                                                "darken": s.get("darken", [0.6, 0.8]),
                                                                "tint": color(s.get("tint", "#0A0A0E"), tokens)}, piece)
            self.ops.append({"op": "raster", "img": sb, "box": (0, 0, c.W, c.H), "meta": {"role": "background", "kind": "sample"}})
        elif "image" in bg:
            img, item, path = self.evidence_image(bg["image"]["asset"], "asset")
            cov = design.cover(img.convert("RGB"), int(c.W), int(c.H), bg["image"].get("crop"))
            self.ops.append({"op": "raster", "img": cov, "box": (0, 0, c.W, c.H), "meta": {"role": "background", "kind": "photo"}})
        else:
            raise SceneError('background: use {"fill": …}, {"sample": {…}} or {"image": {"asset": …}}')
        if bg.get("light"):
            for lt in ([bg["light"]] if isinstance(bg["light"], dict) else bg["light"]):
                layer = Image.new("RGB", (int(c.W), int(c.H)), (0, 0, 0))
                mask = Image.new("L", layer.size, 0)
                r = int(c.U * lt.get("r", 0.7))
                g = Image.radial_gradient("L").resize((max(4, 2 * r), max(4, 2 * r)))
                g = g.point(lambda v: int(255 * lt.get("opacity", 0.25) * max(0.0, 1 - v / 255) ** 1.6))
                mask.paste(g, (int(c.len_x(lt.get("x", "50%"))) - r, int(c.len_y(lt.get("y", "10%"))) - r))
                col = rgba(color(lt.get("color", "#FFFFFF"), tokens))
                layer.paste(Image.new("RGB", layer.size, col[:3]), (0, 0))
                self.ops.append({"op": "glow", "img": layer, "mask": mask, "meta": {"role": "background", "kind": "light"}})
        if bg.get("grain"):
            self.ops.append({"op": "grain", "amount": float(bg["grain"]), "meta": {"role": "background"}})

    # -- layers
    def build(self):
        self.background()
        for L in self.shot.get("layers") or []:
            if L is not None:  # a layer can be left out of one size: {"default": {...}, "android": null}
                self.layer(L, self.ops)
        return self

    def common(self, L, op, box):
        op["opacity"] = float(L.get("opacity", 1.0))
        op["rotate"] = float(L.get("rotate", 0) or 0)
        op["centre"] = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        m = {"role": L.get("role", "decor" if op["op"] in ("rect", "ellipse", "path") else op["op"]),
             "id": L.get("id"), "motive": L.get("motive"), "type": L.get("type"),
             "bbox": rot_bbox(box, op["rotate"], op["centre"])}
        op["meta"] = {**op.get("meta", {}), **m}
        if L.get("id"):
            if str(L["id"]).startswith("_ss-"):
                raise SceneError(f'layer id {L["id"]!r}: ids starting with "_ss-" are the renderer\'s own')
            self.by_id[L["id"]] = op
        return op

    def layer(self, L, ops):
        t = L.get("type")
        fn = {"text": self.text, "screen": self.screen, "image": self.image, "rect": self.shape, "ellipse": self.shape,
              "path": self.path, "group": self.group, "mark": self.mark, "svg": self.svg, "device3d": self.device3d}.get(t)
        if not fn:
            raise SceneError(f"unknown layer type {t!r} (text, screen, device3d, image, rect, ellipse, path, group, mark, svg)")
        try:
            fn(self.anchored(L), ops)
        except SceneError as e:
            raise SceneError(f"layer {L.get('id') or t}: {e}") from None

    def anchored(self, L):
        """Relative placement: "below" / "above" / "right_of" / "left_of" an earlier layer's id, with "gap" (units,
        default 0.03) - so a sub-line follows its headline however many lines the headline wraps to."""
        rel = [k for k in ("below", "above", "right_of", "left_of") if k in L]
        if not rel:
            return L
        L = dict(L)
        c = self.c
        gap = float(L.get("gap", 0.03))
        for k in rel:
            ref = self.by_id.get(L[k])
            if not ref:
                raise SceneError(f'"{k}": no earlier layer with "id": {L[k]!r}')
            b = ref["meta"]["bbox"]
            if k in ("below", "above"):
                for key in ("y", "cy", "bottom"):
                    L.pop(key, None)
                if k == "below":
                    L["y"] = b[3] / c.U + gap
                else:
                    L["bottom"] = (c.H - b[1]) / c.U + gap
            else:
                for key in ("x", "cx", "right"):
                    L.pop(key, None)
                if k == "right_of":
                    L["x"] = b[2] / c.U + gap
                else:
                    L["right"] = (c.W - b[0]) / c.U + gap
        return L

    def text(self, L, ops):
        tl = TextLayout(L, self.c, self.ctx["fonts"], self.ctx["lang"], self.ctx["tokens"], self.ctx["campaign"])
        res = tl.layout(L)
        self.warnings += res["warnings"]
        op = {"op": "text", "runs": res["runs"], "rects": res["rects"], "marks": res["marks"]}
        self.common(L, op, res["bbox"])
        op["meta"].update(role=L.get("role", "text"), text=res["text"], size=res["size"], lines=res["lines"], style=L.get("style"),
                          color=tl.s["color"], text_bbox=res["bbox"], ink=rot_bbox(res["ink"], op["rotate"], op["centre"]))
        ops.append(op)

    def geometry_from_crop(self, L, piece_w, piece_h):
        c = self.c
        if "w" in L and "h" in L:
            raise SceneError('give "w" or "h", not both - the other follows the crop, so the UI keeps its proportions')
        if "h" in L:
            h = c.len_y(L["h"], "h")
            w = h * piece_w / piece_h
        else:
            w = c.len_x(L.get("w", "80%"), "w")
            h = w * piece_h / piece_w
        return w, h

    def screen(self, L, ops, kind="screen"):
        for bad in ("filter", "blur", "tint", "recolor", "saturation", "brightness", "opacity"):
            if bad in L and not (bad == "opacity" and kind == "asset"):
                raise SceneError(f'"{bad}" isn\'t allowed on a {kind} - the app\'s pixels are shown as they are')
        eid = L.get("evidence") if kind == "screen" else L.get("asset")
        img, item, path = self.evidence_image(eid, kind)
        r = self.region(L, item)
        piece = img.crop((round(r[0] * img.width), round(r[1] * img.height), round(r[2] * img.width), round(r[3] * img.height)))
        c = self.c
        if L.get("lift"):
            src = self.by_id.get(L["lift"]["from"])
            if src and src["op"] == "device3d":
                raise SceneError("lift: a 3D device can't be lifted from (a flat piece over a turned phone looks pasted on) - "
                                 "lift from a flat screen layer, or show the crop as its own layer")
            if not src or src["op"] != "image" or src["meta"].get("evidence") != eid:
                raise SceneError(f'lift: "from" must name an earlier screen layer of the same evidence ({eid})')
            sb = src["src_box"]
            sr = src["crop"]
            # where the region sits inside the source layer
            fx0 = (r[0] - sr[0]) / (sr[2] - sr[0])
            fy0 = (r[1] - sr[1]) / (sr[3] - sr[1])
            fx1 = (r[2] - sr[0]) / (sr[2] - sr[0])
            fy1 = (r[3] - sr[1]) / (sr[3] - sr[1])
            x0 = sb[0] + fx0 * (sb[2] - sb[0])
            y0 = sb[1] + fy0 * (sb[3] - sb[1])
            x1 = sb[0] + fx1 * (sb[2] - sb[0])
            y1 = sb[1] + fy1 * (sb[3] - sb[1])
            k = L["lift"].get("scale", 1.12)
            w, h = (x1 - x0) * k, (y1 - y0) * k
            cx = (x0 + x1) / 2 + c.len_x(L["lift"].get("dx", 0))
            cy = (y0 + y1) / 2 + c.len_y(L["lift"].get("dy", 0))
            if not (cx - w / 2 <= x0 + 1 and cx + w / 2 >= x1 - 1 and cy - h / 2 <= y0 + 1 and cy + h / 2 >= y1 - 1):
                self.warnings.append(f"the lifted piece of {eid!r} doesn't cover its place in the screen, so the same UI shows "
                                     f"twice - lower dx/dy or raise the scale")
            cx, cy = rot_point((cx, cy), src["rotate"], src["centre"])
            x, y = cx - w / 2, cy - h / 2
        else:
            w, h = self.geometry_from_crop(L, piece.width, piece.height)
            x, y = c.place_x(L, w), c.place_y(L, h)
        radius = c.len_x(L.get("radius", 0)) if "radius" in L else 0
        rr = (item.get("region_radius") or {}).get(L.get("crop")) if isinstance(L.get("crop"), str) else None
        if "radius" not in L and rr:  # a snapped component keeps its own corner radius, at its new scale
            radius = rr * w / piece.width
        frame = L.get("frame")
        fr = None
        if frame:
            border = c.len_x(frame.get("border", 0.022))
            fr = {"style": frame.get("style", "phone"), "border": border, "color": color(frame.get("color", "#0E0E10"), self.ctx["tokens"]),
                  "island": frame.get("island", frame.get("style", "phone") == "phone"),
                  "punch": frame.get("style") == "android"}
        outer = (x - (fr["border"] if fr else 0), y - (fr["border"] if fr else 0),
                 x + w + (fr["border"] if fr else 0), y + h + (fr["border"] if fr else 0))
        op = {"op": "image", "img": piece, "box": (x, y, x + w, y + h), "src_box": (x, y, x + w, y + h), "crop": r,
              "radius": radius, "frame": fr, "shadow": shadow_spec(L.get("shadow"), c.U), "src_path": path,
              "glow": glow_spec(L.get("glow"), c.U, self.ctx["tokens"]),
              "lossless": path.lower().endswith(".png")}
        self.common(L, op, outer)
        op["meta"].update(role=L.get("role", "proof" if kind == "screen" else "brand"), kind=kind,
                          evidence=eid, sha256=item.get("sha256"), file=path, crop=r, lift=bool(L.get("lift")))
        ops.append(op)

    DEVICE3D_FORBIDDEN = {"filter": "the app's pixels are shown as they are", "blur": "the app's pixels are shown as they are",
                          "tint": "the app's pixels are shown as they are", "recolor": "the app's pixels are shown as they are",
                          "saturation": "the app's pixels are shown as they are", "brightness": "the app's pixels are shown as they are",
                          "opacity": "the app's pixels are shown as they are",
                          "crop": "a 3D device shows the whole screen - use a flat \"screen\" layer for a crop",
                          "rotate": "turn it with \"rotate3d\": {\"yaw\", \"pitch\", \"roll\"}",
                          "lift": "lift from a flat screen layer", "frame": "the 3D device is its own frame (\"model\", \"body\")",
                          "radius": "the corner radius comes from the \"model\" (or \"body\": {\"radius\"})"}

    def device3d(self, L, ops):
        """A real screen on a phone body turned in space (device3d.py): exact perspective, one light, a shadow."""
        for bad, why in self.DEVICE3D_FORBIDDEN.items():
            if bad in L:
                raise SceneError(f'"{bad}" isn\'t allowed on a device3d - {why}')
        if "w" in L and "h" in L:
            raise SceneError('give "w" or "h", not both - the other follows the screen, so the UI keeps its proportions')
        eid = L.get("evidence")
        img, item, path = self.evidence_image(eid)
        c = self.c
        tokens = self.ctx["tokens"]
        cam = dict((self.ctx.get("campaign") or {}).get("camera") or {})
        cam.update(L.get("camera") or {})
        if cam.get("rim"):
            cam["rim"] = dict(cam["rim"], color=color(cam["rim"].get("color"), tokens)) if cam["rim"].get("color") else cam["rim"]
        context = L.get("role") == "context"
        r3 = L.get("rotate3d") or {}
        body = dict(L.get("body") or {})
        if body.get("color") and body["color"] not in d3.FRAMES:
            body["color"] = color(body["color"], tokens)
        model = L.get("model") or {"android": "punch", "duo": "slab", "ipad": "slab"}.get(self.ctx.get("device"), "island")
        try:
            if "h" in L:
                probe = d3.Device(img.size, 1000.0, model=model, body=body)
                width = c.len_y(L["h"], "h") * probe.W / probe.Hb
            else:
                width = c.len_x(L.get("w", 0.8), "w")
            dev = d3.Device(img.size, width, float(r3.get("yaw", 0)), float(r3.get("pitch", 0)), float(r3.get("roll", 0)),
                            model, body, cam, limits=d3.CONTEXT_LIMITS if context else None)
        except d3.DeviceError as e:
            raise SceneError(str(e)) from None
        b = dev.rel_bbox
        x, y = c.place_x(L, b[2] - b[0]), c.place_y(L, b[3] - b[1])
        dev.place(x - b[0], y - b[1])
        raster, (X0, Y0) = dev.render(img, ss=int(L.get("supersample", 3)))
        shadow = L.get("shadow", "auto")
        if shadow == "auto":  # falls away from the light, so every device in the set agrees with it
            lx, ly = dev.light[0], dev.light[1]
            shadow = {"blur": 0.05, "dx": -lx * 0.045, "dy": -ly * 0.045 + 0.012, "opacity": 0.38}
        sh = shadow_spec(shadow if shadow not in ("none", False) else None, c.U)
        if sh:
            simg, (sx, sy) = d3.shadow_for(raster, sh, 2)
            ox, oy = min(0, sx), min(0, sy)
            comp = Image.new("RGBA", (max(raster.width, sx + simg.width) - ox, max(raster.height, sy + simg.height) - oy), (0, 0, 0, 0))
            comp.alpha_composite(simg, (sx - ox, sy - oy))
            comp.alpha_composite(raster, (-ox, -oy))
            raster, X0, Y0 = comp, X0 + ox, Y0 + oy
        quad = dev.screen_quad()
        op = {"op": "device3d", "img": raster, "at": (X0, Y0), "src": img, "H": dev.H(), "quad": quad, "box": dev.bbox()}
        self.common(L, op, dev.bbox())
        ratio = dev.scale_min / dev.scale_max
        op["meta"].update(role=L.get("role", "proof"), kind="screen", evidence=eid, sha256=item.get("sha256"), file=path,
                          crop=[0.0, 0.0, 1.0, 1.0], screen_bbox=(min(p[0] for p in quad), min(p[1] for p in quad),
                                                                 max(p[0] for p in quad), max(p[1] for p in quad)),
                          px_scale=dev.scale_max, foreshortening=ratio, angles=dev.angles, model=model,
                          camera={"fov": float(dev.cam["fov"]), "light": [round(v, 3) for v in dev.light],
                                  "rim": [str(cam["rim"]["color"])[:7].upper(), round(dev.rim[2], 2)] if dev.rim else None},
                          shadow=bool(sh), context=context)
        if ratio < d3.READABLE and not context:
            self.warnings.append(f"the 3D device {eid!r} shrinks the far side of its screen to {ratio:.0%} of the near side - "
                                 "turn it less (or use a smaller fov) so the UI still reads")
        if not sh:
            self.warnings.append(f"the 3D device {eid!r} has no shadow, so it floats - give it a \"shadow\" that agrees with "
                                 "the light")
        ops.append(op)

    def image(self, L, ops):
        self.screen(L, ops, kind="asset")

    def shape(self, L, ops):
        c = self.c
        w, h = c.len_x(L.get("w", 0.2), "w"), c.len_y(L.get("h", L.get("w", 0.2)), "h")
        x, y = c.place_x(L, w), c.place_y(L, h)
        op = {"op": L["type"], "box": (x, y, x + w, y + h), "radius": c.len_x(L.get("radius", 0)) if L["type"] == "rect" else 0,
              "fill": resolve_fill(L.get("fill"), self.ctx["tokens"]), "stroke": color(L.get("stroke"), self.ctx["tokens"]),
              "stroke_w": c.len_x(L.get("stroke_width", 0.006)), "shadow": shadow_spec(L.get("shadow"), c.U),
              "glow": glow_spec(L.get("glow"), c.U, self.ctx["tokens"]),
              "glass": glass_spec(L.get("glass"), c.U, self.ctx["tokens"]) if L["type"] == "rect" else None}
        if L.get("glass") not in (None, False) and L["type"] != "rect":
            raise SceneError('"glass" works on a rect (the panel behind floating content)')
        if op["glass"] and self._depth:
            raise SceneError('"glass" works on top-level layers only (not inside a group)')
        self.common(L, op, op["box"])
        op["meta"]["colors"] = fill_colors(op["fill"]) + ([op["stroke"]] if op["stroke"] else [])
        ops.append(op)

    def path(self, L, ops):
        c = self.c
        cmds = path_to_px(parse_path(L["d"]), c.U, c.len_x(L.get("x", 0)), c.len_y(L.get("y", 0)))
        pts = [p for _, ps in cmds for p in ps]
        if not pts:
            raise SceneError("empty path")
        box = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
        op = {"op": "path", "cmds": cmds, "fill": resolve_fill(L.get("fill"), self.ctx["tokens"]),
              "stroke": color(L.get("stroke"), self.ctx["tokens"]), "stroke_w": c.len_x(L.get("stroke_width", 0.01)),
              "cap": L.get("cap", "round"), "box": box}
        self.common(L, op, box)
        op["meta"]["colors"] = fill_colors(op["fill"]) + ([op["stroke"]] if op["stroke"] else [])
        ops.append(op)

    SVG_FORBIDDEN = re.compile(r"<\s*(text|tspan|textPath|image|foreignObject|script|use|iframe)\b", re.I)

    def svg(self, L, ops):
        """Free vector drawing (a motif, a custom shape, a pattern) as SVG markup in units: the canvas is
        1u wide per slot and 2.174u tall, stroke widths are in units too, "$token" is replaced by its colour.
        No <text> (words go in text layers, so they are checked) and no <image> (pixels come from evidence)."""
        c = self.c
        markup = L.get("markup")
        if L.get("file"):
            fp = L["file"] if os.path.isabs(L["file"]) else os.path.join(self.ctx["spec_dir"], L["file"])
            with open(fp, encoding="utf-8") as f:
                markup = f.read()
        if not markup:
            raise SceneError('svg layer: give "markup" (SVG elements) or "file"')
        markup = re.sub(r"<\?xml[^>]*>|<!DOCTYPE[^>]*>", "", markup)
        markup = re.sub(r"</?svg\b[^>]*>", "", markup)
        if self.SVG_FORBIDDEN.search(markup):
            raise SceneError("svg layers draw shapes only - text goes in a text layer (so it is checked) and app pixels "
                             "in a screen layer (so they come from the evidence)")
        tokens = self.ctx["tokens"]
        cols = []

        def tok(m):
            col = color("$" + m.group(1), tokens)
            cols.append(col)
            return col[:7]
        markup = re.sub(r"\$([A-Za-z_][\w-]*)", tok, markup)
        cols += [m.upper() for m in re.findall(r"#[0-9A-Fa-f]{6}\b", markup)]
        ox, oy = c.len_x(L.get("x", 0), "x"), c.len_y(L.get("y", 0), "y")
        frag = f'<g transform="translate({ox:.2f} {oy:.2f}) scale({c.U:.5f})">{markup}</g>'
        if not have_resvg():
            raise SceneError("svg layers need resvg (pip install resvg-py)")
        img = rasterize(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
                        f'width="{int(c.W)}" height="{int(c.H)}">{frag}</svg>', [])
        box = img.getchannel("A").getbbox()
        if not box:
            raise SceneError("svg layer draws nothing inside the canvas")
        op = {"op": "svg", "markup": frag, "img": img, "box": box}
        self.common(L, op, box)
        op["meta"]["colors"] = sorted(set(cols))
        ops.append(op)

    def group(self, L, ops):
        sub = []
        self._depth += 1
        try:
            for child in L.get("layers") or []:
                if child is not None:
                    self.layer(child, sub)
        finally:
            self._depth -= 1
        if not sub:
            return
        boxes = [o["meta"]["bbox"] for o in sub]
        box = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
        op = {"op": "group", "ops": sub}
        self.common(L, op, box)
        ops.append(op)

    def mark(self, L, ops):
        c = self.c
        col = color(L.get("color", "#FF4D2E"), self.ctx["tokens"])
        wd = max(3, int(c.U * L.get("width", 0.009)))
        pad = c.U * L.get("pad", 0.02)
        bx = None
        if "on" in L:
            src = self.by_id.get(L["on"])
            if not src or src["op"] not in ("image", "device3d"):
                raise SceneError('mark: "on" must name an earlier screen or device3d layer')
            if isinstance(L.get("region"), str):  # a named region of that screen (evidence.py name)
                named = ((self.ctx["evidence"]["screens"].get(src["meta"].get("evidence")) or {}).get("regions") or {})
                if L["region"] not in named:
                    raise SceneError(f"mark region {L['region']!r} isn't named on {src['meta'].get('evidence')!r} "
                                     f"({', '.join(named) or 'no named regions'})")
                L = dict(L, region=named[L["region"]])
            if src["op"] == "device3d":  # through the device's perspective
                r = L.get("region") or [0, 0, 1, 1]
                w, h = src["src"].size
                pts = [d3.hmap(src["H"], u * w, v * h) for u, v in ((r[0], r[1]), (r[2], r[1]), (r[2], r[3]), (r[0], r[3]))]
                bx = [min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)]
            else:
                r = L.get("region") or src["crop"]
                sr, sb = src["crop"], src["src_box"]
                if r[0] < sr[0] - 0.005 or r[1] < sr[1] - 0.005 or r[2] > sr[2] + 0.005 or r[3] > sr[3] + 0.005:
                    self.warnings.append(f"the mark on {L['on']!r} points at {list(r)}, outside what that layer shows ({list(sr)}) - "
                                         "a mark's region is in fractions of the whole screen, not of the crop "
                                         "(use the region's name or its numbers from evidence.json)")
                pts = [(sb[0] + (px - sr[0]) / (sr[2] - sr[0]) * (sb[2] - sb[0]), sb[1] + (py - sr[1]) / (sr[3] - sr[1]) * (sb[3] - sb[1]))
                       for px, py in ((r[0], r[1]), (r[2], r[3]))]
                pts = [rot_point(p, src["rotate"], src["centre"]) for p in pts]
                bx = [min(pts[0][0], pts[1][0]), min(pts[0][1], pts[1][1]), max(pts[0][0], pts[1][0]), max(pts[0][1], pts[1][1])]
        elif "box" in L:
            b = L["box"]
            bx = [c.len_x(b[0]), c.len_y(b[1]), c.len_x(b[2]), c.len_y(b[3])]
        rec = Recorder()
        kind = L.get("kind", "circle")
        seed = sum(map(ord, str(L.get("id") or L.get("on") or kind))) % 97 + 1
        if kind == "circle" and bx:
            design.hand_ellipse(rec, [bx[0] - pad, bx[1] - pad, bx[2] + pad, bx[3] + pad], col, wd, seed=seed)
        elif kind == "underline" and bx:
            design.hand_underline(rec, bx[0], bx[2], bx[3] + pad * 0.6, col, wd, seed=seed)
        elif kind == "arrow":
            a = (c.len_x(L["from"][0]), c.len_y(L["from"][1]))
            b = (c.len_x(L["to"][0]), c.len_y(L["to"][1])) if "to" in L else ((bx[0] + bx[2]) / 2, bx[1] - pad) if bx else None
            if not b:
                raise SceneError('mark arrow: give "to", or "on"/"box" to point at')
            design.hand_arrow(rec, a, b, col, wd, L.get("curve", 0.25), seed=seed)
        else:
            raise SceneError(f'mark kind {kind!r} needs "on" or "box" (circle, underline) or "from" (arrow)')
        pts = [p for ln in rec.lines for p in ln["points"]]
        box = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
        op = {"op": "lines", "lines": rec.lines}
        self.common(L, op, box)
        op["meta"]["role"] = "annotation"
        op["meta"]["colors"] = [col]
        ops.append(op)


# ------------------------------------------------------------------ Pillow backend

def gradient_image(fill, size, box_origin=(0, 0)):
    w, h = max(1, int(size[0])), max(1, int(size[1]))
    if isinstance(fill, str):
        return Image.new("RGBA", (w, h), rgba(fill))
    g = fill.get("linear") or fill.get("radial")
    stops = sorted(g["stops"])
    lut = []
    for i in range(256):
        t = i / 255
        lo = max([s for s in stops if s[0] <= t], key=lambda s: s[0], default=stops[0])
        hi = min([s for s in stops if s[0] >= t], key=lambda s: s[0], default=stops[-1])
        a, b = rgba(lo[1]), rgba(hi[1])
        f = 0 if hi[0] == lo[0] else (t - lo[0]) / (hi[0] - lo[0])
        lut.append(tuple(int(a[k] + (b[k] - a[k]) * f) for k in range(4)))
    if "linear" in fill:
        ang = g.get("angle", 180)
        size_max = int(math.hypot(w, h)) + 2
        base = Image.linear_gradient("L").resize((size_max, size_max))
        base = base.rotate(180 - ang, resample=Image.BICUBIC)
        left, top = (size_max - w) // 2, (size_max - h) // 2
        base = base.crop((left, top, left + w, top + h))
    else:  # same geometry as SVG's objectBoundingBox radial: centre cx/cy and radius r as fractions of the box
        cx, cy, r = g.get("cx", 0.5), g.get("cy", 0.5), g.get("r", 0.5)
        gw, gh = max(2, int(2 * r * w)), max(2, int(2 * r * h))
        base = Image.new("L", (w, h), 255)
        base.paste(Image.radial_gradient("L").resize((gw, gh)), (int(cx * w - gw / 2), int(cy * h - gh / 2)))
    chans = [base.point([lut[i][k] for i in range(256)]) for k in range(4)]
    return Image.merge("RGBA", chans)


def shape_mask(op, size):
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    x0, y0, x1, y1 = op["box"]
    if op["op"] == "ellipse":
        d.ellipse([x0, y0, x1, y1], fill=255)
    else:
        d.rounded_rectangle([x0, y0, x1, y1], radius=int(op.get("radius", 0)), fill=255)
    return m


def draw_shadow(layer, box, radius, sh):
    if not sh:
        return
    w, h = layer.size
    m = Image.new("L", (w, h), 0)
    x0, y0, x1, y1 = box
    ImageDraw.Draw(m).rounded_rectangle([x0 + sh["dx"], y0 + sh["dy"], x1 + sh["dx"], y1 + sh["dy"]], radius=int(radius), fill=int(255 * sh["opacity"]))
    m = m.filter(ImageFilter.GaussianBlur(max(1, sh["blur"] / 2)))
    layer.alpha_composite(Image.composite(Image.new("RGBA", (w, h), rgba(sh["color"])), Image.new("RGBA", (w, h), (0, 0, 0, 0)), m))


def paste_rgba(canvas, img, x, y):
    """alpha_composite that accepts a source reaching past the canvas edges."""
    x, y = int(x), int(y)
    sx0, sy0 = max(0, -x), max(0, -y)
    sx1, sy1 = min(img.width, canvas.width - x), min(img.height, canvas.height - y)
    if sx1 > sx0 and sy1 > sy0:
        canvas.alpha_composite(img.crop((sx0, sy0, sx1, sy1)), (x + sx0, y + sy0))


def pil_op(canvas, op, fonts):
    W, H = canvas.size
    o = op["op"]
    needs_layer = op.get("rotate") or op.get("opacity", 1) < 1 or o in ("group", "text", "lines", "image", "rect", "ellipse", "path", "svg", "device3d")
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)) if needs_layer else None
    tgt = layer
    if o == "rect" or o == "ellipse":
        rr = op.get("radius", 0) if o == "rect" else (op["box"][2] - op["box"][0]) / 2
        if op.get("glow"):
            draw_shadow(tgt, grown(op["box"], op["glow"]["spread"]), rr + op["glow"]["spread"], op["glow"])
        draw_shadow(tgt, op["box"], rr, op.get("shadow"))
        if op.get("glass_img") is not None:
            tgt.alpha_composite(op["glass_img"], dest=tuple(int(v) for v in op["glass_at"]))
        if op["fill"]:
            x0, y0, x1, y1 = [int(round(v)) for v in op["box"]]
            g = gradient_image(op["fill"], (max(1, x1 - x0), max(1, y1 - y0)))
            full = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            full.paste(g, (x0, y0))
            a = ImageChops.multiply(full.split()[3], shape_mask(op, (W, H)))
            full.putalpha(a)
            tgt.alpha_composite(full)
        if op.get("stroke"):
            d = ImageDraw.Draw(tgt)
            if o == "ellipse":
                d.ellipse(op["box"], outline=rgba(op["stroke"]), width=max(1, int(op["stroke_w"])))
            else:
                d.rounded_rectangle(op["box"], radius=int(op.get("radius", 0)), outline=rgba(op["stroke"]), width=max(1, int(op["stroke_w"])))
    elif o == "raster":
        canvas.paste(op["img"].convert("RGB").resize((W, H)) if op["img"].size != (W, H) else op["img"].convert("RGB"), (0, 0))
        return canvas
    elif o == "glow":
        canvas.paste(op["img"], (0, 0), op["mask"])
        return canvas
    elif o == "grain":
        return design.add_grain(canvas.convert("RGB"), op["amount"]).convert("RGBA")
    elif o == "image":
        x0, y0, x1, y1 = op["box"]
        w, h = max(1, int(round(x1 - x0))), max(1, int(round(y1 - y0)))
        fr = op.get("frame")
        b = fr["border"] if fr else 0
        outer = (x0 - b, y0 - b, x1 + b, y1 + b)
        if op.get("glow"):
            draw_shadow(tgt, grown(outer, op["glow"]["spread"]), op["radius"] + b + op["glow"]["spread"], op["glow"])
        draw_shadow(tgt, outer, op["radius"] + b, op.get("shadow"))
        d = ImageDraw.Draw(tgt)
        if fr:
            d.rounded_rectangle(outer, radius=int(op["radius"] + b), fill=rgba(fr["color"]))
        piece = op["img"].resize((w, h), Image.LANCZOS).convert("RGBA")
        mask = rs.rounded_mask((w, h), int(op["radius"])) if op["radius"] > 0 else Image.new("L", (w, h), 255)
        if piece.mode == "RGBA" and op["meta"].get("kind") == "asset":
            mask = Image.composite(piece.split()[3], Image.new("L", (w, h), 0), mask)
        tgt.paste(piece, (int(round(x0)), int(round(y0))), mask)
        if fr and fr.get("island"):
            iw, ih = w * 0.305, w * 0.088
            cx, iy = (x0 + x1) / 2, y0 + w * 0.028
            d.rounded_rectangle([cx - iw / 2, iy, cx + iw / 2, iy + ih], radius=int(ih / 2), fill=(0, 0, 0, 255))
        if fr and fr.get("punch"):
            r = w * 0.017
            cx, cy = (x0 + x1) / 2, y0 + w * 0.034
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 0, 0, 255))
    elif o == "path":
        d = ImageDraw.Draw(tgt)
        polys = flatten(op["cmds"])
        if op["fill"]:
            m = Image.new("L", (W, H), 0)
            md = ImageDraw.Draw(m)
            for pts, _ in polys:
                if len(pts) > 2:
                    md.polygon(pts, fill=255)
            bx = [int(v) for v in op["box"]]
            g = gradient_image(op["fill"], (max(1, bx[2] - bx[0]), max(1, bx[3] - bx[1])))
            full = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            full.paste(g, (bx[0], bx[1]))
            full.putalpha(ImageChops.multiply(full.split()[3], m))
            tgt.alpha_composite(full)
        if op.get("stroke"):
            wd = max(1, int(op["stroke_w"]))
            for pts, closed in polys:
                d.line(pts + ([pts[0]] if closed else []), fill=rgba(op["stroke"]), width=wd, joint="curve")
                if op.get("cap", "round") == "round" and not closed:
                    for p in (pts[0], pts[-1]):
                        d.ellipse([p[0] - wd / 2, p[1] - wd / 2, p[0] + wd / 2, p[1] + wd / 2], fill=rgba(op["stroke"]))
    elif o == "text":
        d = ImageDraw.Draw(tgt)
        for r in op["rects"]:
            d.rounded_rectangle(r["box"], radius=int(r.get("radius", 0)), fill=rgba(r["fill"]))
        for ln in op["marks"]:
            d.line(ln["points"], fill=rgba(ln["color"]), width=ln["width"], joint="curve")
        for r in op["runs"]:
            f = fonts.get({"path": r["path"], "weight": r["weight"]}, r["size"])
            rs.draw_tracked(d, (r["x"], r["y"]), r["text"], f, rgba(r["fill"]), r["tracking"])
    elif o == "lines":
        d = ImageDraw.Draw(tgt)
        for ln in op["lines"]:
            d.line(ln["points"], fill=rgba(ln["color"]), width=ln["width"], joint="curve")
    elif o == "svg":
        tgt.alpha_composite(op["img"])
    elif o == "device3d":
        paste_rgba(tgt, op["img"], *op["at"])
    elif o == "group":
        for child in op["ops"]:
            tgt = pil_op(tgt, child, fonts)
    if layer is not None:
        if op.get("rotate"):
            layer = layer.rotate(-op["rotate"], resample=Image.BICUBIC, center=op["centre"])
        if op.get("opacity", 1) < 1:
            a = layer.split()[3].point(lambda v: int(v * op["opacity"]))
            layer.putalpha(a)
        canvas.alpha_composite(layer)
    return canvas


def render_pillow(scene, fonts):
    c = scene.c
    canvas = Image.new("RGBA", (int(c.W), int(c.H)), (255, 255, 255, 255))
    for op in scene.ops:
        canvas = pil_op(canvas, op, fonts)
    return canvas.convert("RGB")


# ------------------------------------------------------------------ SVG backend

def _img_href(img, lossless):
    buf = io.BytesIO()
    if lossless or img.mode == "RGBA":
        img.save(buf, "PNG", optimize=img.width * img.height < 1_000_000)
        mime = "image/png"
    else:
        img.convert("RGB").save(buf, "JPEG", quality=94)
        mime = "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(buf.getvalue()).decode()}"


class SVGWriter:
    def __init__(self, W, H):
        self.W, self.H = W, H
        self.defs, self.body, self.n = [], [], 0
        self.fonts = set()

    def uid(self, p):
        """Ids for the renderer's own defs (clips, gradients, filters). Layer ids are written as element ids too
        (Figma shows them as layer names), so these carry a prefix no layer id may take."""
        self.n += 1
        return f"_ss-{p}{self.n}"

    def fill_attr(self, fill, box):
        if fill is None:
            return 'fill="none"'
        if isinstance(fill, str):
            a = rgba(fill)
            return f'fill="{fill[:7]}"' + (f' fill-opacity="{a[3] / 255:.3f}"' if a[3] < 255 else "")
        gid = self.uid("g")
        g = fill.get("linear") or fill.get("radial")
        stops = "".join(f'<stop offset="{o:.4f}" stop-color="{c[:7]}" stop-opacity="{rgba(c)[3] / 255:.3f}"/>' for o, c in g["stops"])
        if "linear" in fill:
            ang = math.radians(g.get("angle", 180) - 90)
            x0, y0, x1, y1 = box
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            half = (abs((x1 - x0) * math.cos(ang)) + abs((y1 - y0) * math.sin(ang))) / 2
            self.defs.append(f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="{cx - math.cos(ang) * half:.1f}" '
                             f'y1="{cy - math.sin(ang) * half:.1f}" x2="{cx + math.cos(ang) * half:.1f}" y2="{cy + math.sin(ang) * half:.1f}">{stops}</linearGradient>')
        else:
            self.defs.append(f'<radialGradient id="{gid}" cx="{g.get("cx", 0.5)}" cy="{g.get("cy", 0.5)}" r="{g.get("r", 0.5)}">{stops}</radialGradient>')
        return f'fill="url(#{gid})"'

    def shadow(self, box, radius, sh, out):
        if not sh:
            return
        fid = self.uid("s")
        self.defs.append(f'<filter id="{fid}" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="{max(1, sh["blur"] / 2):.1f}"/></filter>')
        x0, y0, x1, y1 = box
        out.append(f'<rect x="{x0 + sh["dx"]:.1f}" y="{y0 + sh["dy"]:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" rx="{radius:.1f}" '
                   f'fill="{sh["color"][:7]}" fill-opacity="{sh["opacity"]:.3f}" filter="url(#{fid})"/>')

    def op(self, op, out):
        o = op["op"]
        inner = []
        if o in ("rect", "ellipse"):
            x0, y0, x1, y1 = op["box"]
            if o == "rect":
                if op.get("glow"):
                    self.shadow(grown(op["box"], op["glow"]["spread"]), op.get("radius", 0) + op["glow"]["spread"], op["glow"], inner)
                self.shadow(op["box"], op.get("radius", 0), op.get("shadow"), inner)
                if op.get("glass_img") is not None:
                    gx, gy = op["glass_at"]
                    inner.append(f'<image x="{gx}" y="{gy}" width="{op["glass_img"].width}" height="{op["glass_img"].height}" '
                                 f'xlink:href="{_img_href(op["glass_img"], True)}"/>')
                stroke = f' stroke="{op["stroke"][:7]}" stroke-width="{op["stroke_w"]:.1f}"' if op.get("stroke") else ""
                inner.append(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" rx="{op.get("radius", 0):.1f}" '
                             f'{self.fill_attr(op["fill"], op["box"])}{stroke}/>')
            else:
                stroke = f' stroke="{op["stroke"][:7]}" stroke-width="{op["stroke_w"]:.1f}"' if op.get("stroke") else ""
                inner.append(f'<ellipse cx="{(x0 + x1) / 2:.1f}" cy="{(y0 + y1) / 2:.1f}" rx="{(x1 - x0) / 2:.1f}" ry="{(y1 - y0) / 2:.1f}" '
                             f'{self.fill_attr(op["fill"], op["box"])}{stroke}/>')
        elif o == "raster":
            x0, y0, x1, y1 = op["box"]
            inner.append(f'<image x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" preserveAspectRatio="none" '
                         f'xlink:href="{_img_href(op["img"], False)}"/>')
        elif o == "glow":
            rgba_img = op["img"].convert("RGBA")
            rgba_img.putalpha(op["mask"])
            inner.append(f'<image x="0" y="0" width="{self.W}" height="{self.H}" xlink:href="{_img_href(rgba_img, True)}"/>')
        elif o == "grain":
            fid = self.uid("n")
            self.defs.append(f'<filter id="{fid}" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" '
                             f'baseFrequency="0.9" numOctaves="2" seed="7"/><feColorMatrix type="saturate" values="0"/></filter>')
            inner.append(f'<rect width="{self.W}" height="{self.H}" filter="url(#{fid})" opacity="{min(1.0, op["amount"] * 2.2):.3f}" style="mix-blend-mode:overlay"/>')
        elif o == "image":
            x0, y0, x1, y1 = op["box"]
            fr = op.get("frame")
            b = fr["border"] if fr else 0
            if op.get("glow"):
                gb = grown((x0 - b, y0 - b, x1 + b, y1 + b), op["glow"]["spread"])
                self.shadow(gb, op["radius"] + b + op["glow"]["spread"], op["glow"], inner)
            self.shadow((x0 - b, y0 - b, x1 + b, y1 + b), op["radius"] + b, op.get("shadow"), inner)
            if fr:
                inner.append(f'<rect x="{x0 - b:.1f}" y="{y0 - b:.1f}" width="{x1 - x0 + 2 * b:.1f}" height="{y1 - y0 + 2 * b:.1f}" '
                             f'rx="{op["radius"] + b:.1f}" fill="{fr["color"][:7]}"/>')
            clip = ""
            if op["radius"] > 0:
                cid = self.uid("c")
                self.defs.append(f'<clipPath id="{cid}"><rect x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" rx="{op["radius"]:.1f}"/></clipPath>')
                clip = f' clip-path="url(#{cid})"'
            ev = op["meta"].get("evidence") or ""
            inner.append(f'<image x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" preserveAspectRatio="none"{clip} '
                         f'data-evidence="{escape(str(ev))}" xlink:href="{_img_href(op["img"], op.get("lossless"))}"/>')
            w = x1 - x0
            if fr and fr.get("island"):
                iw, ih = w * 0.305, w * 0.088
                cx, iy = (x0 + x1) / 2, y0 + w * 0.028
                inner.append(f'<rect x="{cx - iw / 2:.1f}" y="{iy:.1f}" width="{iw:.1f}" height="{ih:.1f}" rx="{ih / 2:.1f}" fill="#000000"/>')
            if fr and fr.get("punch"):
                inner.append(f'<circle cx="{(x0 + x1) / 2:.1f}" cy="{y0 + w * 0.034:.1f}" r="{w * 0.017:.1f}" fill="#000000"/>')
        elif o == "path":
            stroke = (f' stroke="{op["stroke"][:7]}" stroke-width="{op["stroke_w"]:.1f}" stroke-linecap="{op.get("cap", "round")}" '
                      f'stroke-linejoin="round"') if op.get("stroke") else ""
            inner.append(f'<path d="{path_d(op["cmds"])}" {self.fill_attr(op["fill"], op["box"])}{stroke}/>')
        elif o == "text":
            for r in op["rects"]:
                x0, y0, x1, y1 = r["box"]
                inner.append(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" rx="{r.get("radius", 0):.1f}" fill="{r["fill"][:7]}"/>')
            for ln in op["marks"]:
                inner.append(self.polyline(ln))
            for r in op["runs"]:
                fam, weight, italic = face(r["path"])
                self.fonts.add(r["path"])
                style = ' font-style="italic"' if italic else ""
                ls = f' letter-spacing="{r["tracking"]:.2f}"' if abs(r["tracking"]) > 0.05 else ""
                inner.append(f'<text x="{r["x"]:.1f}" y="{r["y"]:.1f}" font-family="\'{escape(fam)}\'" font-weight="{weight}"{style} '
                             f'font-size="{r["size"]}" fill="{r["fill"][:7]}"{ls} xml:space="preserve">{escape(r["text"])}</text>')
        elif o == "lines":
            for ln in op["lines"]:
                inner.append(self.polyline(ln))
        elif o == "svg":
            inner.append(op["markup"])
        elif o == "device3d":
            x0, y0 = op["at"]
            ev = op["meta"].get("evidence") or ""
            inner.append(f'<image x="{x0}" y="{y0}" width="{op["img"].width}" height="{op["img"].height}" data-evidence="{escape(str(ev))}" '
                         f'xlink:href="{_img_href(op["img"], True)}"/>')
        elif o == "group":
            for child in op["ops"]:
                self.op(child, inner)
        attrs = []
        if op.get("rotate"):
            attrs.append(f'transform="rotate({op["rotate"]:.2f} {op["centre"][0]:.1f} {op["centre"][1]:.1f})"')
        if op.get("opacity", 1) < 1:
            attrs.append(f'opacity="{op["opacity"]:.3f}"')
        role = op.get("meta", {}).get("role")
        if role:
            attrs.append(f'data-role="{escape(str(role))}"')
        if op.get("meta", {}).get("id"):
            attrs.append(f'id="{escape(str(op["meta"]["id"]))}"')
        out.append(f'<g {" ".join(attrs)}>' + "".join(inner) + "</g>")

    def polyline(self, ln):
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in ln["points"])
        return (f'<polyline points="{pts}" fill="none" stroke="{ln["color"][:7]}" stroke-width="{ln["width"]}" '
                f'stroke-linecap="round" stroke-linejoin="round"/>')

    def svg(self, ops):
        body = []
        for op in ops:
            self.op(op, body)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{self.W}" '
                f'height="{self.H}" viewBox="0 0 {self.W} {self.H}"><defs>{"".join(self.defs)}</defs>{"".join(body)}</svg>')


def to_svg(scene):
    c = scene.c
    w = SVGWriter(int(c.W), int(c.H))
    return w.svg(scene.ops), sorted(w.fonts)


def have_resvg():
    try:
        import resvg_py  # noqa: F401
        return True
    except ImportError:
        return False


def rasterize(svg, font_files):
    import resvg_py
    png = resvg_py.svg_to_bytes(svg_string=svg, skip_system_fonts=True, font_files=list(font_files),
                                shape_rendering="geometric_precision", text_rendering="optimize_legibility",
                                image_rendering="optimize_quality")
    return Image.open(io.BytesIO(png)).convert("RGBA")


def prepare_glass(scene, fonts):
    """Frosted-glass panels need what is drawn behind them: render the layers below each panel, blur and tint
    that patch inside the panel's shape, add the hairline edge - one raster that both backends paste."""
    c = scene.c
    for i, op in enumerate(scene.ops):
        g = op.get("glass")
        if not g:
            continue
        below = Image.new("RGBA", (int(c.W), int(c.H)), (255, 255, 255, 255))
        for prev in scene.ops[:i]:
            below = pil_op(below, prev, fonts)
        x0, y0, x1, y1 = [int(round(v)) for v in op["box"]]
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(int(c.W), x1), min(int(c.H), y1)
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue
        m = int(g["blur"] * 2) + 2
        patch = below.crop((max(0, x0 - m), max(0, y0 - m), min(int(c.W), x1 + m), min(int(c.H), y1 + m)))
        patch = patch.filter(ImageFilter.GaussianBlur(max(1, g["blur"] / 2)))
        patch = patch.crop((x0 - max(0, x0 - m), y0 - max(0, y0 - m), x0 - max(0, x0 - m) + (x1 - x0), y0 - max(0, y0 - m) + (y1 - y0)))
        tint = Image.new("RGBA", patch.size, rgba(g["tint"], g["opacity"]))
        patch = Image.alpha_composite(patch.convert("RGBA"), tint)
        k = 3  # anti-aliased shape and edge
        r = int(op.get("radius", 0) * k)
        big = Image.new("L", (patch.width * k, patch.height * k), 0)
        ImageDraw.Draw(big).rounded_rectangle([0, 0, big.width - 1, big.height - 1], radius=r, fill=255)
        mask = big.resize(patch.size, Image.LANCZOS)
        edge = Image.new("L", big.size, 0)
        ew = max(1, int(g["edge_w"] * k))
        ImageDraw.Draw(edge).rounded_rectangle([0, 0, big.width - 1, big.height - 1], radius=r, outline=255, width=ew)
        edge = edge.resize(patch.size, Image.LANCZOS).point(lambda v: int(v * g["edge_opacity"]))
        patch.putalpha(mask)
        patch.alpha_composite(Image.composite(Image.new("RGBA", patch.size, rgba(g["edge"])), Image.new("RGBA", patch.size, (0, 0, 0, 0)), edge))
        op["glass_img"], op["glass_at"] = patch, (x0, y0)


def render(scene, fonts, backend="auto"):
    """-> (RGB image, svg text, backend used)"""
    if any(op.get("glass") for op in scene.ops):
        prepare_glass(scene, fonts)
    svg, font_files = to_svg(scene)
    use = backend
    if backend == "auto":
        use = "svg" if have_resvg() else "pillow"
    if use == "svg":
        img = rasterize(svg, font_files)
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        bg.alpha_composite(img)
        return bg.convert("RGB"), svg, "svg"
    return render_pillow(scene, fonts), svg, "pillow"


# ------------------------------------------------------------------ x-ray

def xray(img, scene, ctx):
    """Overlay layer boxes, roles, the safe margin and a thumbnail inset - for looking at structure."""
    im = img.convert("RGB").copy()
    d = ImageDraw.Draw(im, "RGBA")
    c = scene.c
    cols = {"headline": (255, 80, 60), "sub": (255, 160, 60), "proof": (60, 160, 255), "brand": (160, 90, 255),
            "decor": (120, 200, 120), "annotation": (255, 220, 0), "label": (255, 120, 200)}
    f = ctx["fonts"].get("sans-bold", max(14, int(c.U * 0.022)))

    def walk(ops):
        for op in ops:
            m = op.get("meta", {})
            if m.get("role") == "background":
                continue
            if op["op"] == "group":
                walk(op["ops"])
            b = m.get("bbox")
            if not b:
                continue
            col = cols.get(m.get("role"), (200, 200, 200))
            d.rectangle(b, outline=col + (255,), width=max(2, int(c.U * 0.003)))
            d.text((b[0] + 6, b[1] + 4), f"{m.get('role')}{' · ' + str(m['id']) if m.get('id') else ''}", font=f, fill=col + (255,))
    walk(scene.ops)
    m = c.U * 0.045
    d.rectangle([m, m, c.W - m, c.H - m], outline=(255, 255, 255, 120), width=1)
    if scene.span == 2:
        d.line([(c.slot_w, 0), (c.slot_w, c.H)], fill=(255, 0, 255, 200), width=max(2, int(c.U * 0.004)))
    thumb_w = int(c.slot_w * 200 / 1206)
    t = img.crop((0, 0, int(c.slot_w), int(c.H))).resize((thumb_w, int(c.H * thumb_w / c.slot_w)), Image.LANCZOS)
    im.paste(t, (int(c.W - thumb_w - m), int(c.H - t.height - m)))
    return im


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):  # Windows consoles and pipes default to a legacy code page
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    print(__doc__)
