#!/usr/bin/env python3
"""Checks on resolved scenes - truth, claims, legibility, campaign coherence, monotony, decoration.

Used by compose.py on every render (warnings land in _render.json, which check_set.py prints). Because a
scene knows where every element is and where it came from, these checks look at the design, not at a guess
from pixels: what covers the app's UI, which number a headline uses and whether the screen shows it, whether
three shots share one composition, which colours are off the campaign palette.
"""
import hashlib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_set as rs  # noqa: E402


def walk(ops):
    for op in ops:
        yield op
        if op["op"] == "group":
            yield from walk(op["ops"])


def area(b):
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def inter(a, b):
    return (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))


def iou(a, b):
    i = area(inter(a, b))
    u = area(a) + area(b) - i
    return i / u if u else 0.0


def hexrgb(c):
    h = c.lstrip("#")
    return tuple(int(h[k:k + 2], 16) for k in (0, 2, 4))


_SHA = {}


def file_sha(path):
    if path not in _SHA:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 16), b""):
                h.update(chunk)
        _SHA[path] = h.hexdigest()
    return _SHA[path]


def snip(meta):
    return " ".join(meta.get("text", "").replace("*", "").split())[:28]


def norm_num(s):
    return re.sub(r"[\s.,]", "", s)


def truth_errors(scene):
    """Hard failures: a screen that changed since the evidence was recorded."""
    out = []
    for op in walk(scene.ops):
        m = op.get("meta", {})
        if op["op"] == "image" and m.get("sha256") and file_sha(m["file"]) != m["sha256"]:
            out.append(f"{m.get('kind')} {m.get('evidence')!r} changed since evidence.json was built - rebuild it "
                       "(evidence.py build) so the set shows what is on disk")
    return out


def slot_of(scene, box):
    if scene.span == 1:
        return 0
    return 0 if (box[0] + box[2]) / 2 < scene.c.slot_w else 1


def scene_warnings(scene, img, ctx):
    c = scene.c
    U = c.U
    out = []
    ops = list(walk(scene.ops))
    shot = scene.shot
    campaign = ctx.get("campaign") or {}
    # --- the app's UI: nothing painted over it
    screens = [(i, op) for i, op in enumerate(ops) if op["op"] == "image" and op["meta"].get("kind") == "screen"]
    for i, sop in screens:
        sb = sop["meta"]["bbox"]
        for op in ops[i + 1:]:
            m = op.get("meta", {})
            role = m.get("role")
            if op["op"] in ("image", "lines", "group") or role in ("annotation", "label", "background"):
                continue
            ov = area(inter(sb, m.get("bbox", (0, 0, 0, 0))))
            if ov > 0.02 * area(sb):
                what = "text" if op["op"] == "text" else op["op"]
                out.append(f"{what} ({role}{' ' + m['id'] if m.get('id') else ''}) covers {ov / area(sb):.0%} of the "
                           f"screen {sop['meta'].get('evidence')!r} - keep the app's UI visible (or mark it role \"label\")")
    # --- breathing room: words pressed against a screen read as part of the UI
    for t in [op for op in ops if op["op"] == "text" and op["meta"].get("role") in ("headline", "sub", "display")]:
        tb = t["meta"]["bbox"]
        for _, sop in screens:
            sb = sop["meta"]["bbox"]
            gx = max(sb[0] - tb[2], tb[0] - sb[2])
            gy = max(sb[1] - tb[3], tb[1] - sb[3])
            if max(gx, gy) < 0.025 * U and area(inter(tb, sb)) <= 0.02 * area(sb):
                out.append(f"text \"{snip(t['meta'])}\" touches the screen {sop['meta'].get('evidence')!r} - leave "
                           "at least 0.025u (anchor it with \"below\"/\"above\" and a \"gap\")")
                break
    # --- UI look-alikes: small rounded boxes with text inside
    shapes = [op for op in ops if op["op"] == "rect" and op.get("meta", {}).get("role") != "background" and op["meta"].get("bbox")]
    texts = [op for op in ops if op["op"] == "text"]
    for r in shapes:
        b = r["meta"]["bbox"]
        if (b[3] - b[1]) > 0.14 * U:
            continue
        for t in texts:
            tb = t["meta"]["bbox"]
            if t["meta"].get("role") in ("headline", "sub") or area(tb) == 0:
                continue
            if area(inter(tb, b)) > 0.8 * area(tb):
                out.append(f"\"{snip(t['meta'])}\" on a small rounded box looks like app UI - if the app shows it, "
                           "crop it from a screen; a marketing sticker must not look like a real button or badge")
    # --- claims: proof and numbers
    heads = [t for t in texts if t["meta"].get("role") == "headline"]
    if heads and not shot.get("proof"):
        out.append("no \"proof\" for this shot - name the evidence (and region) that proves the headline")
    words = []
    shown = [p.get("evidence") for p in shot.get("proof") or []] + [op[1]["meta"].get("evidence") for op in screens]
    for eid in shown:
        ev = ctx["evidence"]["screens"].get(eid)
        if ev:
            words += [ev.get("text") or ""] + list((ev.get("region_text") or {}).values())
    words = [w for w in words if w]
    seen_text = norm_num(" ".join(words))
    if words:
        for t in texts:  # every word on the canvas, not only the headline: a big number is a claim too
            for n in re.findall(r"\d+(?:[.,]\d+)?", t["meta"].get("text", "")):
                if len(norm_num(n)) >= 2 and norm_num(n) not in seen_text:
                    out.append(f"number {n!r} isn't in the text read from the screens this shot shows - claims must match "
                               "what the app shows; if the screen does show it, name that region (evidence.py name) so "
                               "it is read up close")
    # --- legibility
    for t in texts:
        m = t["meta"]
        role = m.get("role")
        if role == "headline" and m["size"] < 0.06 * U:
            out.append(f"headline at {m['size'] / U:.3f}u is too small for search results (≥ 0.06u)")
        if role == "sub" and m["size"] < 0.03 * U:
            out.append(f"sub-line at {m['size'] / U:.3f}u is too small (≥ 0.03u)")
        b = m["bbox"]
        pad = 0.03 * U
        if b[0] < pad or b[2] > c.W - pad or b[1] < pad or b[3] > c.H - pad:
            out.append(f"text \"{snip(m)}\" runs into the edge (keep ≥ 0.03u)")
        if scene.span == 2 and b[0] < c.slot_w - 0.012 * U and b[2] > c.slot_w + 0.012 * U:
            out.append(f"text \"{snip(m)}\" crosses the seam - the store's gap will cut it")
        if img is not None and role in ("headline", "sub", "label"):
            ratio = text_contrast(img, t)
            need = 3.0 if m["size"] >= 0.075 * U else 4.5
            if ratio is not None and ratio < need:
                out.append(f"low contrast {ratio:.1f}:1 behind \"{snip(m)}\" (aim ≥ {need})")
    if scene.span == 2:
        for _, sop in screens:
            b = sop["meta"]["bbox"]
            if b[0] < c.slot_w - 0.012 * U and b[2] > c.slot_w + 0.012 * U and abs((b[0] + b[2]) / 2 - c.slot_w) > 0.01 * c.slot_w:
                out.append(f"screen {sop['meta'].get('evidence')!r} crosses the seam off-centre - a split screen is cut exactly in "
                           "the middle (cx \"50%\"), so both screenshots get the same half")
        for op in ops:
            if op["op"] == "lines":
                b = op["meta"]["bbox"]
                if b[0] < c.slot_w - 0.012 * U and b[2] > c.slot_w + 0.012 * U:
                    out.append("a hand mark crosses the seam - the gap between screenshots will break it")
    # --- decoration and palette
    decor = [op for op in ops if op.get("meta", {}).get("role") == "decor"]
    for op in decor:
        if not op["meta"].get("motive"):
            out.append(f"decorative {op['op']} without a \"motive\" - every shape must come from the app's DNA or the concept; "
                       "say which (or remove it)")
    if len(decor) > 5:
        out.append(f"{len(decor)} decorative layers - decoration is competing with the product")
    palette = [hexrgb(v) for v in (ctx.get("tokens") or {}).values() if isinstance(v, str) and v.startswith("#")]
    palette += [(255, 255, 255), (0, 0, 0)]
    off = set()
    for op in ops:
        m = op.get("meta", {})
        cols = list(m.get("colors", []))
        if op["op"] == "text":
            cols += [r["fill"] for r in op["runs"]] + [r["fill"] for r in op["rects"]]
        for col in cols:
            rgb = hexrgb(col)
            if min(sum((a - b) ** 2 for a, b in zip(rgb, p)) for p in palette) > 34 ** 2:
                off.add(col[:7])
    if off and ctx.get("tokens"):
        out.append(f"colours outside the campaign palette: {', '.join(sorted(off))} - add them to the campaign tokens if they're "
                   "the app's, otherwise use a token")
    cf = campaign.get("fonts") or {}
    if cf:
        allowed = {os.path.abspath(ctx["fonts"].resolve(v)[0]) for v in cf.values()}
        used = {os.path.abspath(r["path"]) for t in texts for r in t["runs"]}
        stray = sorted(os.path.basename(p) for p in used - allowed)
        if stray:
            out.append(f"fonts outside the campaign: {', '.join(stray)}")
    return out


UPSCALE_LIMIT = 1.8


def store_warnings(scene, ctx):
    """Device and store rules: soft (over-enlarged) screens, a screen from the wrong kind of device, and
    Google Play's rules (no device frames, taglines under 20% of the image)."""
    out = []
    c = scene.c
    ops = list(walk(scene.ops))
    screens = [op for op in ops if op["op"] == "image" and op["meta"].get("kind") == "screen"]
    for op in screens:
        b = op["box"]
        k = (b[2] - b[0]) / max(1, op["img"].width)
        if k > UPSCALE_LIMIT:
            out.append(f"screen {op['meta'].get('evidence')!r} is drawn at {k:.1f}x its pixels and will look soft - show it "
                       f"smaller or a bigger part of it, or capture the screen at a higher resolution")
    dev = ctx.get("device")
    if dev in rs.SCREEN_SHAPES:
        lo, hi = rs.SCREEN_SHAPES[dev]
        for op in screens:
            if tuple(op["meta"]["crop"]) != (0.0, 0.0, 1.0, 1.0):
                continue
            r = op["img"].height / max(1, op["img"].width)
            if not lo <= r <= hi:
                out.append(f"screen {op['meta'].get('evidence')!r} ({op['img'].width}x{op['img'].height}) isn't {rs.CLASS_NAMES[dev]} "
                           f"screen - capture it on that device and give it per size (\"layers\": {{\"default\": …, "
                           f"\"{ctx.get('preset')}\": …}})")
    if ctx.get("store") == "android" and scene.shot.get("id") != "feature-graphic":
        if any(op.get("frame") and op["frame"]["style"] in ("phone", "android") for op in screens):
            out.append("device frame in a Google Play set - Play advises against device imagery; show the bare screen "
                       "(radius, no \"frame\") in the android variant")
        for slot in range(scene.span):
            hs = [op["meta"].get("ink", op["meta"]["bbox"]) for op in ops if op["op"] == "text" and op["meta"].get("role") not in ("label", "annotation")
                  and slot_of(scene, op["meta"]["bbox"]) == slot]  # a giant number is tagline text too
            share = sum(b[3] - b[1] for b in hs) / c.H
            if share > rs.PLAY_TEXT_SHARE:
                out.append(f"caption covers {share:.0%} of the height - Google Play recommends taglines take up no more "
                           f"than 20% (shorter headline, no sub-line, or a smaller size in the android variant)")
    return out


def text_contrast(img, t):
    """Contrast between the text colour and what is really behind it (pixels in its box that aren't text)."""
    b = [int(v) for v in t["meta"]["bbox"]]
    b = [max(0, b[0]), max(0, b[1]), min(img.width, b[2]), min(img.height, b[3])]
    if b[2] - b[0] < 4 or b[3] - b[1] < 4:
        return None
    crop = img.crop(b).convert("RGB").resize((max(4, (b[2] - b[0]) // 4), max(4, (b[3] - b[1]) // 4)))
    fills = {r["fill"][:7] for r in t["runs"]}
    tc = hexrgb(sorted(fills)[0])
    px = list(crop.getdata()) if not hasattr(crop, "get_flattened_data") else list(crop.get_flattened_data())
    rest = [p for p in px if sum((a - b2) ** 2 for a, b2 in zip(p, tc)) > 60 ** 2]
    rects = [hexrgb(r["fill"]) for r in t["rects"]]
    if not rest:
        return None
    rest.sort(key=lambda p: sum(p))
    bg = rest[len(rest) // 2]
    if rects:  # emphasis boxes are part of the background of their words
        bg = min([bg] + rects, key=lambda p: rs.contrast(tc, p))
    return rs.contrast(tc, bg)


def fingerprint(scene, slot):
    """Where the headline and the dominant visual sit in a slot, normalised to it."""
    c = scene.c
    x0 = slot * c.slot_w
    ops = [op for op in walk(scene.ops) if op.get("meta", {}).get("role") != "background"]

    def norm(b):
        return ((b[0] - x0) / c.slot_w, b[1] / c.H, (b[2] - x0) / c.slot_w, b[3] / c.H)
    in_slot = [op for op in ops if slot_of(scene, op["meta"]["bbox"]) == slot or scene.span == 1]
    head = [op for op in in_slot if op["op"] == "text" and op["meta"].get("role") == "headline"]
    vis = [op for op in in_slot if op["op"] == "image"]
    hb = norm(head[0]["meta"]["bbox"]) if head else None
    vb = norm(max(vis, key=lambda o: area(o["meta"]["bbox"]))["meta"]["bbox"]) if vis else None
    return hb, vb


def set_warnings(fps):
    """fps: [(label, (headline box, visual box))]. Three or more slots with the same composition -> monotony."""
    out = []
    n = len(fps)
    groups = []
    used = set()
    for i in range(n):
        if i in used:
            continue
        g = [i]
        for j in range(i + 1, n):
            a, b = fps[i][1], fps[j][1]
            same = all((x is None and y is None) or (x is not None and y is not None and iou(x, y) > 0.7) for x, y in zip(a, b))
            if same and a != (None, None):
                g.append(j)
        if len(g) >= 3:
            used.update(g)
            groups.append(g)
    for g in groups:
        out.append(f"shots {', '.join(fps[k][0] for k in g)} share one composition (headline and main visual in the same place, "
                   "same scale) - vary scale, crop or placement; let the campaign system, not a layout, hold the set together")
    return out


def headline_fonts(scenes):
    fams = set()
    for sc in scenes:
        for op in walk(sc.ops):
            if op["op"] == "text" and op["meta"].get("role") == "headline" and op["runs"]:
                fams.add(os.path.basename(op["runs"][0]["path"]))
    return [f"headlines use {len(fams)} different fonts ({', '.join(sorted(fams))}) - one campaign, one headline face"] if len(fams) > 1 else []


if __name__ == "__main__":
    print(__doc__)
