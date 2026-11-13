#!/usr/bin/env python3
"""Checks on resolved scenes - truth, claims, legibility, campaign coherence, monotony, decoration.

Used by compose.py on every render (warnings land in _render.json, which check_set.py prints). Because a
scene knows where every element is and where it came from, these checks look at the design, not at a guess
from pixels: what covers the app's UI, which number a headline uses and whether the screen shows it, whether
three shots share one composition, which colours are off the campaign palette.
"""
import hashlib
import json
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
        if m.get("sha256") and m.get("file") and file_sha(m["file"]) != m["sha256"]:
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
    screens = [(i, op) for i, op in enumerate(ops) if op["op"] in ("image", "device3d") and op["meta"].get("kind") == "screen"]
    for i, sop in screens:
        sb = sop["meta"].get("screen_bbox", sop["meta"]["bbox"])
        for op in ops[i + 1:]:
            m = op.get("meta", {})
            role = m.get("role")
            if op["op"] in ("image", "lines", "group", "device3d") or role in ("annotation", "label", "background"):
                continue
            ov = area(inter(sb, m.get("bbox", (0, 0, 0, 0))))
            if role == "callout" and ov <= CALLOUT_OVERLAP * area(sb):
                continue  # a callout may reach over the screen's edge to point at something
            if ov > 0.02 * area(sb):
                what = "text" if op["op"] == "text" else op["op"]
                out.append(f"{what} ({role}{' ' + m['id'] if m.get('id') else ''}) covers {ov / area(sb):.0%} of the "
                           f"screen {sop['meta'].get('evidence')!r} - keep the app's UI visible (or mark it role \"label\")")
    # --- a screen drawn over words placed before it hides them
    for i, sop in screens:
        sb = sop["meta"].get("screen_bbox", sop["meta"]["bbox"])
        for t in ops[:i]:
            if t["op"] != "text" or t["meta"].get("role") == "background":
                continue
            tb = t["meta"].get("ink", t["meta"]["bbox"])
            ov = area(inter(tb, sb))
            if area(tb) and ov > 0.02 * area(tb):
                out.append(f"the screen {sop['meta'].get('evidence')!r} covers {ov / area(tb):.0%} of \"{snip(t['meta'])}\" - the "
                           "words were placed under it; move or shrink one of them")
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
    # --- crops and lifts that look broken: words sliced by a crop edge, a lifted piece with no visible edge
    for _, sop in screens:
        m = sop["meta"]
        crop = m.get("crop") or [0, 0, 1, 1]
        item = ctx["evidence"]["screens"].get(m.get("evidence")) or {}
        if tuple(crop) != (0.0, 0.0, 1.0, 1.0):
            cut = crop_cuts(item, crop)
            if cut:
                out.append(f"the crop of {m.get('evidence')!r} slices through {', '.join(repr(w) for w in cut[:3])} - move its "
                           "edge to a gap between components, so nothing reads half-cut")
            elif not m.get("lift"):
                through = edge_through_content(m.get("file"), crop)
                if through:
                    sides = ", ".join(f"{sd} ({sh:.0%} of it is UI)" for sd, sh in through)
                    out.append(f"the crop of {m.get('evidence')!r} cuts through the UI at its {sides} - move the edge to a gap "
                               "between components (or to the screen's own edge), so no component reads half-cut")
        if m.get("lift"):
            snapped = lift_margin(m.get("file"), crop)
            if snapped:
                out.append(f"the lifted piece of {m.get('evidence')!r} includes a margin around the component, so its own edge "
                           f"shows inside the lifted one (a double edge) - cut it to the component: {snapped} "
                           "(evidence.py name … --snap also keeps its corner radius)")
        if m.get("lift") and img is not None:
            sep = edge_separation(img, sop["box"], sop.get("radius", 0), U)
            if sep is not None and sep < 12:
                out.append(f"the lifted piece of {m.get('evidence')!r} has no visible edge (its background runs into what is "
                           "behind it), so it reads as misaligned UI, not a raised card - lift a whole component cut to its "
                           "own edges (evidence.py name … --snap keeps its corner radius), give it a keyline (\"frame\": "
                           "plain), or mark the element instead")
    # --- context devices set a scene; something in the shot still has to prove the headline
    if screens and all(sop["meta"].get("context") for _, sop in screens):
        out.append("every device in this shot is a \"context\" device - nobody can read a screen turned that far, so add "
                   "a screen (flat, or a device3d at a readable angle) that proves the headline")
    # --- UI look-alikes: small rounded boxes with text inside
    shapes = [op for op in ops if op["op"] == "rect" and op.get("meta", {}).get("role") != "background" and op["meta"].get("bbox")]
    texts = [op for op in ops if op["op"] == "text"]
    callout_styles = {k for k in (campaign.get("type") or {}) if k.startswith("callout")}
    for r in shapes:
        b = r["meta"]["bbox"]
        if (b[3] - b[1]) > 0.14 * U:
            continue
        for t in texts:
            tb = t["meta"]["bbox"]
            if t["meta"].get("role") in ("headline", "sub") or area(tb) == 0:
                continue
            if t["meta"].get("role") == "callout" and t["meta"].get("style") in callout_styles and r["meta"].get("role") == "callout":
                continue  # the campaign's own callout: it looks like the campaign, not like the app
            if area(inter(tb, b)) > 0.8 * area(tb):
                out.append(f"\"{snip(t['meta'])}\" on a small rounded box looks like app UI - if the app shows it, "
                           "crop it from a screen; a marketing sticker must not look like a real button or badge")
    # --- callouts: labels that point at the UI - they must look like the campaign, not like the app
    callouts = [t for t in texts if t["meta"].get("role") == "callout"]
    for t in callouts:
        if t["meta"].get("style") not in callout_styles:
            out.append(f"callout \"{snip(t['meta'])}\" doesn't use a campaign callout style - add \"callout\" to the campaign's "
                       "\"type\" (and a callout shape style), so a callout reads as the campaign pointing at the app, never as "
                       "the app's own UI")
    boxes = [r for r in shapes if r["meta"].get("role") == "callout"]
    for t in callouts:
        ink = t["meta"].get("ink", t["meta"]["bbox"])
        for r in boxes:
            rb = r["meta"]["bbox"]
            if area(inter(ink, rb)) > 0 and (ink[0] < rb[0] - 2 or ink[1] < rb[1] - 2 or ink[2] > rb[2] + 2 or ink[3] > rb[3] + 2):
                out.append(f"callout \"{snip(t['meta'])}\" runs out of its box - widen the box, shorten the words, or place "
                           "the text inside it (\"cx\"/\"cy\" on the box's centre)")
    for op in ops:  # a hand mark that leaves the canvas was aimed at the wrong place
        if op["op"] == "lines":
            b = op["meta"]["bbox"]
            outside = area(b) - area(inter(b, (0, 0, c.W, c.H)))
            if area(b) and outside > 0.1 * area(b):
                out.append(f"a hand mark runs {outside / area(b):.0%} off the canvas - check what it is meant to circle")
    for slot in range(scene.span):
        n = sum(1 for t in callouts if slot_of(scene, t["meta"]["bbox"]) == slot)
        if n > CALLOUT_MAX:
            out.append(f"{n} callouts in one shot - more than {CALLOUT_MAX} turns the shot into a manual; keep the ones "
                       "the headline needs")
    # --- claims: proof and numbers
    heads = [t for t in texts if t["meta"].get("role") == "headline"]
    if heads and not shot.get("proof"):
        out.append("no \"proof\" for this shot - name the evidence (and region) that proves the headline")
    words = []
    shown = [p.get("evidence") for p in shot.get("proof") or []] + [op[1]["meta"].get("evidence") for op in screens
                                                                      if not op[1]["meta"].get("context")]
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
        if role == "callout" and m["size"] < 0.03 * U:
            out.append(f"callout at {m['size'] / U:.3f}u is too small to read in the store (≥ 0.03u)")
        if role == "footnote" and not 0.02 * U <= m["size"] <= 0.03 * U:
            out.append(f"footnote at {m['size'] / U:.3f}u - a footnote is small but readable at full size (0.02-0.03u); "
                       "anything bigger competes with the sub-line")
        b = m["bbox"]
        pad = 0.03 * U
        if b[0] < pad or b[2] > c.W - pad or b[1] < pad or b[3] > c.H - pad:
            out.append(f"text \"{snip(m)}\" runs into the edge (keep ≥ 0.03u)")
        if scene.span == 2 and b[0] < c.slot_w - 0.012 * U and b[2] > c.slot_w + 0.012 * U:
            out.append(f"text \"{snip(m)}\" crosses the seam - the store's gap will cut it")
        if img is not None and role in ("headline", "sub", "label", "callout"):
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
    out += material_warnings(scene, ctx)
    return out


CALLOUT_OVERLAP = 0.08
CALLOUT_MAX = 4
# The words for what a set is made of. An effect is never a default: each one used needs a source - the app's DNA,
# the concept, or the shot's message - written in the campaign's "materials" or on the layer as a "motive".
MATERIALS = ("flat", "elevated", "glass", "glow", "gradient", "texture", "paper", "3d", "tilt", "illustration", "photo")


def materials_used(scene):
    """-> [(material, what, motive)] for every effect the scene uses."""
    found = []

    def visit(ops, rot=0.0):
        for op in ops:
            m = op.get("meta", {})
            what = f"{op['op']}{' ' + m['id'] if m.get('id') else ''}"
            motive = m.get("motive")
            r = rot + (op.get("rotate") or 0)
            if op.get("glass"):
                found.append(("glass", what, motive))
            if op.get("glow"):
                found.append(("glow", what, motive))
            if m.get("kind") == "light":
                found.append(("glow", "background light", None))
            if op["op"] == "grain":
                found.append(("texture", "background grain", None))
            if isinstance(op.get("fill"), dict) and (op["fill"].get("linear") or op["fill"].get("radial")):
                found.append(("gradient", "background" if m.get("role") == "background" else what, motive))
            if m.get("kind") == "photo":
                found.append(("photo", "background photo", None))
            if op["op"] == "svg" and m.get("role") in ("decor", "illustration"):
                found.append(("illustration", what, motive))
            if m.get("kind") == "screen" and abs(r) > 0.5:
                found.append(("tilt", f"screen {m.get('evidence')}", motive))
            if op["op"] == "device3d":
                found.append(("3d", f"device {m.get('evidence')}", motive))
                if (m.get("camera") or {}).get("rim"):
                    found.append(("glow", f"the rim light on device {m.get('evidence')}", motive))
            if op["op"] == "group":
                visit(op["ops"], r)
    visit(scene.ops)
    return found


def campaign_materials(ctx):
    mats = (ctx.get("campaign") or {}).get("materials") or {}
    if isinstance(mats, list):  # ["glass", ...] without reasons
        return {m: "" for m in mats}
    return {k: v for k, v in mats.items() if not k.startswith("_")}


def dna_materials(ctx):
    mats = ((ctx.get("dna") or {}).get("materials")) or {}
    if isinstance(mats, list):
        return set(mats)
    return {k for k, v in mats.items() if not k.startswith("_") and v}


def campaign_material_warnings(ctx):
    """Once per set: every material the campaign lists says where it comes from."""
    out = []
    camp = campaign_materials(ctx)
    for name, why in camp.items():
        if name not in MATERIALS:
            out.append(f"campaign material {name!r} isn't one of {', '.join(MATERIALS)}")
        elif not str(why).strip():
            out.append(f"campaign material {name!r} has no reason - write where it comes from: \"dna: the tab bar is "
                       "frosted glass\", \"concept: …\" or \"brand guide: …\"")
        elif ctx.get("dna") and str(why).strip().lower().startswith("dna") and name not in dna_materials(ctx):
            out.append(f"campaign material {name!r} says it comes from the DNA, but the DNA's \"materials\" don't list it - "
                       "add it there with where the app shows it, or give the concept as the reason")
    return out + reference_copy_warnings(ctx)


def material_warnings(scene, ctx):
    out = []
    camp = campaign_materials(ctx)
    seen = set()
    for name, what, motive in materials_used(scene):
        if name in camp and str(camp[name]).strip():
            continue
        if motive and str(motive).strip():
            continue
        if (name, what) in seen:
            continue
        seen.add((name, what))
        out.append(f"{name} on {what} has no source - effects are never a default: list {name!r} in the campaign's "
                   "\"materials\" with where it comes from (the app's DNA, the concept, the shot's message), or give the layer "
                   "a \"motive\"; an effect without a source is what makes a set look like a template")
    return out


def reference_copy_warnings(ctx, tol=22):
    """A reference the user liked is for principles; its palette must not become the campaign's."""
    dna = ctx.get("dna") or {}
    refs = dna.get("references") or []
    if not refs:
        return []
    app = [hexrgb(v) for v in (dna.get("palette") or {}).values() if isinstance(v, str) and v.startswith("#")]
    app += [hexrgb(p["hex"]) for p in ((dna.get("measured") or {}).get("palette") or [])]
    toks = [hexrgb(v) for v in (ctx.get("tokens") or {}).values() if isinstance(v, str) and v.startswith("#")]

    def near(a, pool):
        return any(sum((x - y) ** 2 for x, y in zip(a, p)) <= tol ** 2 for p in pool)
    out = []
    for ref in refs:
        pal = [hexrgb(h) for h in ref.get("palette") or []]
        copied = [t for t in toks if near(t, pal) and not near(t, app) and max(t) - min(t) > 18]  # greys are everyone's
        if len(copied) >= 2:
            out.append(f"{len(copied)} campaign colours come from the reference {os.path.basename(ref.get('file', ''))!r}, not from "
                       "the app - take the reference's principles (hierarchy, density, rhythm), never its palette, fonts or "
                       "illustrations")
    return out


UPSCALE_LIMIT = 1.8


def store_warnings(scene, ctx):
    """Device and store rules: soft (over-enlarged) screens, a screen from the wrong kind of device, and
    Google Play's rules (no device frames, taglines under 20% of the image)."""
    out = []
    c = scene.c
    ops = list(walk(scene.ops))
    screens = [op for op in ops if op["op"] in ("image", "device3d") and op["meta"].get("kind") == "screen"]
    for op in screens:
        b = op["box"]
        k = op["meta"]["px_scale"] if op["op"] == "device3d" else (b[2] - b[0]) / max(1, op["img"].width)
        if k > UPSCALE_LIMIT:
            out.append(f"screen {op['meta'].get('evidence')!r} is drawn at {k:.1f}x its pixels and will look soft - show it "
                       f"smaller or a bigger part of it, or capture the screen at a higher resolution")
    dev = ctx.get("device")
    if dev in rs.SCREEN_SHAPES:
        lo, hi = rs.SCREEN_SHAPES[dev]
        for op in screens:
            if tuple(op["meta"]["crop"]) != (0.0, 0.0, 1.0, 1.0):
                continue
            src = op.get("src") or op["img"]
            r = src.height / max(1, src.width)
            if not lo <= r <= hi:
                out.append(f"screen {op['meta'].get('evidence')!r} ({src.width}x{src.height}) isn't {rs.CLASS_NAMES[dev]} "
                           f"screen - capture it on that device and give it per size (\"layers\": {{\"default\": …, "
                           f"\"{ctx.get('preset')}\": …}})")
    if scene.shot.get("id") == "feature-graphic" and any(op["op"] == "device3d" or (op.get("frame") and op["frame"]["style"] in ("phone", "android"))
                                                       for op in screens):
        out.append(f"{rs.PLAY_REC} device frame in the feature graphic - Play advises against device imagery")
    if ctx.get("store") == "android" and scene.shot.get("id") != "feature-graphic":
        any3d = any(op["op"] == "device3d" for op in screens)
        if any3d or any(op.get("frame") and op["frame"]["style"] in ("phone", "android") for op in screens):
            out.append(f"{rs.PLAY_REC} device frame in a Google Play set{' (a 3D device is one too)' if any3d else ''} - Play "
                       "advises against device imagery (it dates quickly): the listing still publishes, but the assets may be "
                       "shown differently or promoted less. Flat screens are the default; keep it if the user chose it")
        for slot in range(scene.span):
            hs = [op["meta"].get("ink", op["meta"]["bbox"]) for op in ops if op["op"] == "text" and op["meta"].get("role") not in ("label", "annotation", "footnote")
                  and slot_of(scene, op["meta"]["bbox"]) == slot]  # a giant number is tagline text too
            share = sum(b[3] - b[1] for b in hs) / c.H
            if share > rs.PLAY_TEXT_SHARE:
                out.append(f"{rs.PLAY_REC} caption covers {share:.0%} of the height - Google Play recommends taglines take up no more "
                           f"than 20% (shorter headline, no sub-line, or a smaller size in the android variant)")
    return out


def edge_separation(img, box, radius, U=1206):
    """How visible the edge of a piece is: the colour step between a band just inside its edge and the ground
    just outside, median over the straight parts of its four sides (a keyline inside the edge counts)."""
    if img is None:
        return None
    px = img.convert("RGB").load()
    W, H = img.size
    x0, y0, x1, y1 = box
    r = max(radius, 6)
    depth = max(5, int(0.012 * U))  # a card edge or keyline just inside the cut still counts
    steps = []

    def at(x, y):
        return px[min(W - 1, max(0, int(x))), min(H - 1, max(0, int(y)))]

    def dist(a, b):
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5
    sides = [((x0 + r, y0), (x1 - r, y0), (0, -1)), ((x0 + r, y1), (x1 - r, y1), (0, 1)),
             ((x0, y0 + r), (x0, y1 - r), (-1, 0)), ((x1, y0 + r), (x1, y1 - r), (1, 0))]
    for (ax, ay), (bx, by), (nx, ny) in sides:
        n = max(2, int(max(abs(bx - ax), abs(by - ay)) / 10))
        for i in range(n):
            t = (i + 0.5) / n
            x, y = ax + (bx - ax) * t, ay + (by - ay) * t
            ox, oy = x + nx * 6, y + ny * 6
            if not (0 <= ox < W and 0 <= oy < H):
                continue  # an edge on the canvas border needs no separation
            outside = at(ox, oy)
            steps.append(max(dist(at(x - nx * k, y - ny * k), outside) for k in range(1, depth + 1, 2)))
    if len(steps) < 6:
        return None
    steps.sort()
    return steps[len(steps) // 2]


_SNAP = {}


def lift_margin(path, crop):
    """If a lifted crop is a component plus a margin around it, the component's own box (else None)."""
    if not path or tuple(crop) == (0.0, 0.0, 1.0, 1.0):
        return None
    key = (path, tuple(crop))
    if key not in _SNAP:
        import evidence
        m = 0.012  # look a little outside the crop, so a crop cut exactly to its component snaps to itself
        wide = [max(0.0, crop[0] - m), max(0.0, crop[1] - m), min(1.0, crop[2] + m), min(1.0, crop[3] + m)]
        try:
            box, _, kind = evidence.snap(path, wide, full=True)
        except (OSError, ValueError):
            box, kind = crop, None
        loose = kind == "component" and max(box[0] - crop[0], box[1] - crop[1], crop[2] - box[2], crop[3] - box[3]) > 0.006
        _SNAP[key] = [round(v, 4) for v in box] if loose else None
    return _SNAP[key]


_BG = {}


def edge_through_content(path, crop):
    """Crop edges (inside the screen) that run through UI instead of through a gap: for each such edge, the share
    of its line that isn't the screen's background colour. -> [(side, share)]"""
    from PIL import Image as _Image
    if not path:
        return []
    if path not in _BG:
        im = _Image.open(path).convert("RGB")
        small = im.resize((max(1, im.width // 4), max(1, im.height // 4)))
        cols = small.getcolors(small.width * small.height) or []
        _BG[path] = (im, max(cols)[1] if cols else (0, 0, 0))
    im, bg = _BG[path]
    W, H = im.size
    px = im.load()
    out = []
    x0, y0, x1, y1 = crop[0] * W, crop[1] * H, crop[2] * W, crop[3] * H
    for side, inside, (a, b, fixed, step, horizontal) in (("top", crop[1] > 0.002, (x0, x1, y0, 1, True)),
                                                          ("bottom", crop[3] < 0.998, (x0, x1, y1, -1, True)),
                                                          ("left", crop[0] > 0.002, (y0, y1, x0, 1, False)),
                                                          ("right", crop[2] < 0.998, (y0, y1, x1, -1, False))):
        if not inside:
            continue
        lo, hi = a + (b - a) * 0.04, b - (b - a) * 0.04
        n = max(8, int((hi - lo) / 3))

        def share(offset):
            hits = 0
            for i in range(n):
                t = lo + (hi - lo) * i / (n - 1)
                x, y = (t, fixed + offset) if horizontal else (fixed + offset, t)
                p = px[min(W - 1, max(0, int(x))), min(H - 1, max(0, int(y)))]
                if max(abs(p[k] - bg[k]) for k in range(3)) > 18:
                    hits += 1
            return hits / n
        # UI on both sides of the edge = a component cut in two; background just outside = cut on its border
        inside_share, outside_share = share(2 * step), share(-3 * step)
        if inside_share > 0.35 and outside_share > 0.35:
            out.append((side, inside_share))
    return out


def crop_cuts(item, crop, min_conf=60):
    """Words on the screen (OCR) that the crop's edge slices through."""
    out = []
    for w in item.get("ocr") or []:
        t = w.get("t", "")
        if w.get("c", 0) < min_conf or sum(ch.isalnum() for ch in t) < 2:
            continue
        b = w["b"]
        a = area(b)
        if a <= 0:
            continue
        f = area(inter(b, crop)) / a
        if 0.12 < f < 0.88:
            out.append(t)
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
    vis = [op for op in in_slot if op["op"] in ("image", "device3d") and not op["meta"].get("context")]
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


def device3d_set_warnings(scenes):
    """3D devices across a set: one lens and one light, and turned phones only where depth means something."""
    out = []
    devs = [(sc.shot.get("id"), op["meta"]) for sc in scenes for op in walk(sc.ops) if op["op"] == "device3d"]
    if not devs:
        return out
    cams = {(m["camera"]["fov"], tuple(m["camera"]["light"]), json.dumps(m["camera"].get("rim"))) for _, m in devs}
    if len(cams) > 1:
        out.append(f"the 3D devices use {len(cams)} different lenses/lights - one camera for the set (campaign \"camera\": "
                   "{\"fov\", \"light\"}), or the shots look like they come from different shoots")
    turned = {sid for sid, m in devs if abs(m["angles"][0]) > 3 or abs(m["angles"][1]) > 3}
    if len(turned) > 2 or (len(scenes) >= 3 and len(turned) * 2 > len(scenes)):
        out.append(f"turned 3D phones in {len(turned)} of {len(scenes)} shots - tilted phones in every shot read as a "
                   "template (and as AI); keep depth for the shots where it means something, show the rest flat")
    return out


def norm_word(t):
    return "".join(ch for ch in rs.tr_lower(t) if ch.isalnum())


def visible_words(scene, ctx, slot):
    """The app's words (OCR of the evidence) that one slot actually shows: inside each screen's crop and inside
    the canvas, lifted copies left out. -> (words, evidence ids)"""
    c = scene.c
    x_lo, x_hi = (slot * c.slot_w, (slot + 1) * c.slot_w) if scene.span == 2 else (0, c.W)
    words, evs = set(), set()
    for op in walk(scene.ops):
        m = op.get("meta", {})
        if op["op"] not in ("image", "device3d") or m.get("kind") != "screen" or m.get("lift") or m.get("context"):
            continue  # a context device is too turned to read: its words aren't content
        item = ctx["evidence"]["screens"].get(m.get("evidence")) or {}
        crop = m.get("crop") or [0, 0, 1, 1]
        bx0, by0, bx1, by1 = op["box"] if op["op"] == "image" else m.get("screen_bbox", m["bbox"])
        if bx1 <= bx0 or by1 <= by0:
            continue

        def fx(x):
            return crop[0] + (x - bx0) / (bx1 - bx0) * (crop[2] - crop[0])

        def fy(y):
            return crop[1] + (y - by0) / (by1 - by0) * (crop[3] - crop[1])
        vis = (fx(max(bx0, x_lo)), fy(max(by0, 0)), fx(min(bx1, x_hi)), fy(min(by1, c.H)))
        if vis[2] <= vis[0] or vis[3] <= vis[1]:
            continue
        evs.add(m.get("evidence"))
        for w in item.get("ocr") or []:
            t = norm_word(w.get("t", ""))
            if w.get("c", 0) < 60 or len(t) < 4:
                continue
            cx, cy = (w["b"][0] + w["b"][2]) / 2, (w["b"][1] + w["b"][3]) / 2
            if vis[0] <= cx <= vis[2] and vis[1] <= cy <= vis[3]:
                words.add(t)
    return words, evs


def content_repeats(contents, evidence, min_shared=6, share=0.2):
    """contents: [(slot label, words, evidence ids)]. Two slots that show the same items through different
    screens (the same posts on the calendar and on the home screen) prove one thing twice. Words on most
    screens (tab bars, the app's own labels) don't count."""
    screens = evidence.get("screens", {})
    n = len(screens)
    df = {}
    for item in screens.values():
        for t in {norm_word(w.get("t", "")) for w in item.get("ocr") or [] if w.get("c", 0) >= 60}:
            df[t] = df.get(t, 0) + 1
    chrome = {t for t, k in df.items() if n >= 3 and k / n >= 0.5}
    out = []
    for i in range(len(contents)):
        for j in range(i + 1, len(contents)):
            (la, wa, ea), (lb, wb, eb) = contents[i], contents[j]
            if ea & eb:
                continue  # the same screen twice is the crop check's job
            a, b = wa - chrome, wb - chrome
            shared = a & b
            if a and b and len(shared) >= min_shared and (len(shared) / min(len(a), len(b)) >= share or len(shared) >= 10):
                out.append(f"shots {la} and {lb} show the same content on different screens ({', '.join(sorted(shared)[:5])}, …) - "
                           "each shot should prove something new; one item carried through the set is fine, the same list "
                           "twice isn't")
    return out


def habit_warnings(scenes, ctx):
    """The looks this skill itself falls into (references/anti-ai.md, "The skill's own habits"). Each is fine once;
    on every shot of every set they make all sets look alike."""
    n = len(scenes)
    if n < 3:
        return []
    out = []
    camp = campaign_materials(ctx)
    lifts = marks = bleeds = darks = 0
    mats = {}
    for sc_ in scenes:
        ops = list(walk(sc_.ops))
        lifts += any(op.get("meta", {}).get("lift") for op in ops)
        marks += any(op["op"] == "lines" for op in ops)
        screens = [op for op in ops if op.get("meta", {}).get("kind") == "screen" and not op["meta"].get("lift")]
        if screens:
            main = max(screens, key=lambda o: area(o["meta"]["bbox"]))
            bleeds += main["meta"]["bbox"][3] > sc_.c.H + 0.01 * sc_.c.U
        bg = next((op for op in sc_.ops if op.get("meta", {}).get("role") == "background"), None)
        if bg is not None:
            cols = bg["meta"].get("colors") or []
            dark = bool(cols) and all(rs.luminance(rs.hexrgb(col)) < 0.06 for col in cols)
            darks += dark or bg["meta"].get("kind") == "sample"
        for name in {m for m, _, _ in materials_used(sc_)}:
            mats[name] = mats.get(name, 0) + 1
    most = max(3, (n * 2 + 2) // 3)
    if lifts >= most:
        out.append(f"a lifted card in {lifts} of {n} shots - a lift is the move for the shot whose message is that one element, "
                   "not a house style")
    if marks >= most:
        out.append(f"hand-drawn marks in {marks} of {n} shots - mark the one detail a shot is about, where the headline needs it")
    if bleeds == n and n >= 4:
        out.append("every shot crops its main screen at the bottom edge - vary it: a whole screen, a detail, a pair, "
                   "a screen that sits inside the canvas")
    for name, k in sorted(mats.items()):
        why = str(camp.get(name, "")).strip().lower()
        if k == n and n >= 4 and name not in ("flat",) and not why.startswith(("dna", "brand")):
            out.append(f"{name} in every shot - unless the app itself is made of it (a \"dna: …\" reason), an effect on "
                       "every shot is a template; keep it where a message needs it")
    ui = ((ctx.get("dna") or {}).get("measured") or {}).get("ui")
    if ui == "light" and darks == n:
        out.append("the app's UI is light but every shot is on a dark ground - a dark set is a choice the concept has to "
                   "make for a reason, not the default")
    return out


def example_copies(shots, spec_dir, here=None):
    """Shots whose layers repeat a bundled example's placement number for number: the examples show the format,
    not a look to reuse."""
    here = here or os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    files = [os.path.join(root, "templates", "scene.example.json")]
    ex = os.path.join(os.path.dirname(os.path.dirname(root)), "examples")  # the repo's examples (not in the lite zip)
    if os.path.isdir(ex):
        for d in sorted(os.listdir(ex)):
            for sub in ("", "concepts"):
                folder = os.path.join(ex, d, sub)
                if os.path.isdir(folder):
                    files += [os.path.join(folder, fn) for fn in sorted(os.listdir(folder)) if fn.endswith(".json")]
    mine = os.path.abspath(spec_dir)
    if mine == os.path.join(root, "templates") or mine.startswith(ex + os.sep):
        return []  # a bundled example itself

    def related(p):  # the example's own folder (a set and its concepts) isn't copying itself
        d = os.path.abspath(os.path.dirname(p))
        return mine in (d, os.path.dirname(d)) or d == os.path.dirname(mine)
    files = [p for p in files if not related(p)]

    def sig(sh):
        keys = []
        for L in sh.get("layers") or []:
            if not isinstance(L, dict) or L.get("type") not in ("text", "screen", "device3d"):
                continue
            pos = tuple(json.dumps(L.get(k), sort_keys=True) for k in ("x", "y", "cx", "cy", "w", "h", "right", "bottom", "crop", "rotate"))
            keys.append((L["type"], L.get("role"), pos))
        return keys
    known = {}
    for p in files:
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        for sh in data.get("shots") or []:
            for k in sig(sh):
                known.setdefault(k, f"{os.path.basename(os.path.dirname(p))}/{sh.get('id')}")
    out = []
    for sh in shots:
        hits, screens = {}, {}
        for k in sig(sh):
            if k in known and sum(v != "null" for v in k[2]) >= 2:
                hits[known[k]] = hits.get(known[k], 0) + 1
                if k[0] != "text":
                    screens[known[k]] = True
        best = max(((ex_, n) for ex_, n in hits.items() if screens.get(ex_)), key=lambda kv: kv[1], default=None)
        if best and best[1] >= 2:  # the main visual and the type placed exactly as in the example
            out.append(f"shot {sh.get('id')!r} repeats the layout of the bundled example {best[0]!r} number for number - the "
                       "examples show the format, not a look; compose this shot from its own message and the app's DNA")
    return out


def headline_fonts(scenes):
    fams = set()
    for sc in scenes:
        for op in walk(sc.ops):
            if op["op"] == "text" and op["meta"].get("role") == "headline" and op["runs"]:
                fams.add(os.path.basename(op["runs"][0]["path"]))
    return [f"headlines use {len(fams)} different fonts ({', '.join(sorted(fams))}) - one campaign, one headline face"] if len(fams) > 1 else []


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):  # Windows consoles and pipes default to a legacy code page
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    print(__doc__)
