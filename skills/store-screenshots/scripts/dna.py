#!/usr/bin/env python3
"""The app's visual DNA: measured from its real screens (and website), completed by looking, shown as a board.

  python3 dna.py measure evidence.json --site https://example.com -o dna.json   # palette roles, type scale, website fonts/colours
  python3 dna.py fonts evidence.json home --region 0.05,0.08,0.6,0.12 --text "Merhaba" -o font-match.jpg
  python3 dna.py board dna.json -o dna-board.jpg                                # the board the user confirms
  python3 dna.py reference liked.png --dna dna.json -o reference.jpg            # a reference: principles only, never its look

measure fills what a script can know: the UI palette (flat pixels only, so posters and photos don't count)
with roles (surface, ink, accent, semantic), dark or light UI, the type scale from the words on screen, and -
with --site - the fonts and colours the website's CSS declares. It leaves the rest for the designer (you) to
complete by looking: the fonts (from the user's files, the website, or the closest match on the font-match
sheet), the shape language, the signature elements (with their evidence crops), the voice, what the app makes,
what to avoid. Then render the board and show it with the concepts.
"""
import argparse
import colorsys
import json
import os
import re
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render_set as rs  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402

MATERIALS = {
    "flat": "solid fills, no depth",
    "elevated": "cards on shadows",
    "glass": "frosted, translucent panels (iOS materials, Liquid Glass)",
    "glow": "coloured light: halos, lit accents, neon",
    "gradient": "colour ramps in the UI itself",
    "texture": "grain, noise, paper",
    "paper": "print feel: off-white, ink, rules",
    "3d": "rendered objects or devices",
    "tilt": "rotated or perspective UI",
    "illustration": "drawn art the app itself uses",
    "photo": "photography or posters as content",
}
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"


def hexs(rgb):
    return "#%02X%02X%02X" % tuple(int(v) for v in rgb[:3])


def lum(rgb):
    return rs.luminance(rgb)


def sat_hue(rgb):
    h, l, s = colorsys.rgb_to_hls(*(v / 255 for v in rgb[:3]))
    return s if 0.08 < l < 0.92 else 0.0, h * 360


def flat_colors(img):
    """Colour counts of flat (UI) pixels: neighbourhood range small in every channel."""
    im = img.convert("RGB")
    w = 360
    im = im.resize((w, round(im.height * w / im.width)), Image.BILINEAR)
    top = int(im.height * 0.065)
    im = im.crop((0, top, im.width, im.height))
    rng = [ImageChopsRange(ch) for ch in im.split()]
    counts = {}
    px = im.load()
    masks = [r.load() for r in rng]
    for y in range(0, im.height):
        for x in range(0, im.width):
            if all(m[x, y] < 14 for m in masks):
                r, g, b = px[x, y]
                key = (r // 6 * 6, g // 6 * 6, b // 6 * 6)
                counts[key] = counts.get(key, 0) + 1
    return counts, im.width * im.height


def ImageChopsRange(ch):
    from PIL import ImageChops
    return ImageChops.subtract(ch.filter(ImageFilter.MaxFilter(3)), ch.filter(ImageFilter.MinFilter(3)))


def merge_colors(counts, total, tol=26):
    items = sorted(counts.items(), key=lambda kv: -kv[1])
    groups = []
    for rgb, n in items:
        for g in groups:
            if sum((a - b) ** 2 for a, b in zip(rgb, g["rgb"])) < tol ** 2:
                g["n"] += n
                break
        else:
            groups.append({"rgb": rgb, "n": n})
    for g in groups:
        g["share"] = g["n"] / total
    return [g for g in groups if g["share"] >= 0.0015]


def chroma(rgb):
    return (max(rgb[:3]) - min(rgb[:3])) / 255


def presence(groups, per_screen, tol=26):
    """On how many screens each colour shows up - UI colours repeat, poster colours don't."""
    for g in groups:
        g["screens"] = 0
        for counts, total in per_screen:
            n = sum(v for k, v in counts.items() if sum((a - b) ** 2 for a, b in zip(k, g["rgb"])) < tol ** 2)
            if n >= 0.0008 * total:
                g["screens"] += 1
    return groups


def roles(groups, n_screens=1):
    groups = sorted(groups, key=lambda g: -g["share"])
    if not groups:
        return []
    surface = groups[0]
    out = [{"hex": hexs(surface["rgb"]), "role": "surface", "share": round(surface["share"], 4)}]
    taken = {id(surface)}
    # a second surface: large and close in lightness to the first (cards on the ground)
    for g in groups[1:4]:
        if g["share"] > 0.04 and abs(lum(g["rgb"]) - lum(surface["rgb"])) < 0.12:
            out.append({"hex": hexs(g["rgb"]), "role": "surface-2", "share": round(g["share"], 4)})
            taken.add(id(g))
            break
    rest = [g for g in groups if id(g) not in taken]
    ink = max(rest, key=lambda g: rs.contrast(g["rgb"], surface["rgb"]) * (1 if g["share"] > 0.002 else 0.2), default=None)
    if ink:
        out.append({"hex": hexs(ink["rgb"]), "role": "ink", "share": round(ink["share"], 4)})
        taken.add(id(ink))
    need = max(2, round(0.4 * n_screens)) if n_screens > 2 else 1
    colourful = [g for g in groups if id(g) not in taken and chroma(g["rgb"]) > 0.27 and g.get("screens", n_screens) >= need]
    colourful.sort(key=lambda g: (-g.get("screens", 0), -g["share"]))
    hues = []
    for g in colourful:
        s, h = sat_hue(g["rgb"])
        if any(min(abs(h - h2), 360 - abs(h - h2)) < 25 for h2 in hues):
            continue
        role = "accent" if not hues else "accent-%d" % (len(hues) + 1)
        if 90 <= h <= 165 and hues:
            role = "success"
        elif (h >= 345 or h <= 12) and hues:
            role = "danger"
        out.append({"hex": hexs(g["rgb"]), "role": role, "share": round(g["share"], 4), "screens": g.get("screens")})
        hues.append(h)
        if len(hues) >= 4:
            break
    muted = [g for g in groups if id(g) not in taken and chroma(g["rgb"]) <= 0.27 and g.get("screens", n_screens) >= need]
    for g in muted[:2]:
        if not any(o["hex"] == hexs(g["rgb"]) for o in out):
            out.append({"hex": hexs(g["rgb"]), "role": "neutral", "share": round(g["share"], 4)})
    return out


def type_scale(ev):
    hs = []
    for item in ev["screens"].values():
        for w in item.get("ocr", []):
            b = w["b"]
            if len(w["t"]) >= 2 and w["c"] >= 70:
                hs.append((b[3] - b[1]) * item["size"][1] / item["size"][0])  # word height as a fraction of screen width
    if not hs:
        return None
    hs.sort()
    q = lambda p: round(hs[min(len(hs) - 1, int(p * len(hs)))], 4)  # noqa: E731
    return {"body": q(0.5), "large": q(0.9), "largest": q(0.99), "note": "word box height / screen width (OCR) - title vs body ratio"}


def fetch(url, limit=600_000):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,text/css,*/*"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read(limit).decode("utf-8", "replace")


def website(url):
    out = {"url": url}
    try:
        html = fetch(url)
    except Exception as e:  # network blocked, 404...
        return {"url": url, "error": f"{type(e).__name__}: {e}"[:200]}
    css = " ".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S | re.I))
    links = re.findall(r"<link[^>]+rel=[\"']?stylesheet[\"']?[^>]*>", html, re.I)
    hrefs = [m.group(1) for l in links for m in [re.search(r"href=[\"']([^\"']+)", l)] if m][:6]
    fetched = []
    for h in hrefs:
        try:
            css += " " + fetch(urllib.parse.urljoin(url, h))
            fetched.append(h)
        except Exception:
            pass
    fams = {}
    for m in re.findall(r"font-family\s*:\s*([^;}{]+)", css, re.I):
        first = m.split(",")[0].strip().strip("'\"")
        if first and not first.startswith("var(") and first.lower() not in ("inherit", "initial", "sans-serif", "serif", "monospace"):
            fams[first] = fams.get(first, 0) + 1
    gfonts = re.findall(r"fonts\.googleapis\.com/css2?\?family=([^\"'&>]+)", html)
    faces = re.findall(r"@font-face\s*{[^}]*font-family\s*:\s*['\"]?([^;'\"]+)", css, re.I)
    colors = {}
    for c in re.findall(r"#[0-9a-fA-F]{6}\b", css):
        colors[c.upper()] = colors.get(c.upper(), 0) + 1
    tm = re.search(r"<meta[^>]+name=[\"']theme-color[\"'][^>]+content=[\"']([^\"']+)", html, re.I)
    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    desc = re.search(r"<meta[^>]+name=[\"']description[\"'][^>]+content=[\"']([^\"']+)", html, re.I)
    out.update({
        "fonts": [f for f, _ in sorted(fams.items(), key=lambda kv: -kv[1])][:6],
        "google_fonts": [urllib.parse.unquote(g).replace("+", " ") for g in gfonts][:6],
        "font_faces": sorted(set(f.strip() for f in faces))[:8],
        "colors": [c for c, _ in sorted(colors.items(), key=lambda kv: -kv[1])][:10],
        "theme_color": tm.group(1) if tm else None,
        "title": re.sub(r"\s+", " ", title.group(1)).strip()[:120] if title else None,
        "description": desc.group(1)[:300] if desc else None,
        "stylesheets": fetched,
    })
    return out


def cmd_measure(a):
    with open(a.evidence, encoding="utf-8") as f:
        ev = json.load(f)
    base = os.path.dirname(os.path.abspath(a.evidence))
    counts, total, per_screen = {}, 0, []
    dark = 0
    for sid, item in ev["screens"].items():
        im = Image.open(os.path.join(base, item["path"]))
        c, t = flat_colors(im)
        per_screen.append((c, t))
        for k, v in c.items():
            counts[k] = counts.get(k, 0) + v
        total += t
    groups = presence(merge_colors(counts, total), per_screen)
    palette = roles(groups, len(per_screen))
    surf = next((p for p in palette if p["role"] == "surface"), None)
    if surf:
        dark = lum(rs.hexrgb(surf["hex"])) < 0.2
    dna = {
        "_doc": "Visual DNA (dna.py). measured = what the screens/website show; the rest is filled in by the designer after "
                "looking at the screens - then dna.py board renders it for the user to confirm.",
        "app": a.app or "",
        "measured": {"palette": palette, "ui": "dark" if dark else "light", "type_scale": type_scale(ev),
                     "screens": list(ev["screens"])},
        "website": website(a.site) if a.site else None,
        "fonts": {"display": None, "display_italic": None, "text": None, "source": "user file | website | closest match (say which)"},
        "palette": {p["role"]: p["hex"] for p in palette},
        "shape": {"radius": "", "elevation": "", "density": "", "icons": ""},
        "materials": {"_doc": "What the app's own screens are made of, each with where it shows: {\"glass\": \"tab bar and "
                              "sheets (home, detail)\"}. List only what the screens show; anything else (" + ", ".join(MATERIALS) +
                              ") is not the app's - a campaign may still use it, but only with the concept as its reason."},
        "references": [],
        "signatures": [],
        "voice": "",
        "output": "",
        "avoid": [],
    }
    with open(a.output, "w", encoding="utf-8") as f:
        json.dump(dna, f, ensure_ascii=False, indent=1)
    print(f"{len(palette)} palette roles: " + ", ".join(f"{p['role']} {p['hex']} ({p['share']:.1%})" for p in palette))
    if a.site:
        w = dna["website"]
        print("website: " + (w.get("error") or f"fonts {w.get('fonts')} google {w.get('google_fonts')} colours {w.get('colors', [])[:5]}"))
    print(f"→ {a.output}  (now complete fonts, shape, materials, signatures, voice, output, avoid by looking at the screens)")


def font_label(path):
    f = ImageFont.truetype(path, 20)
    return " ".join(f.getname())


def cmd_fonts(a):
    """The closest font, by eye: the app's own text next to the same words in each candidate."""
    with open(a.evidence, encoding="utf-8") as f:
        ev = json.load(f)
    base = os.path.dirname(os.path.abspath(a.evidence))
    item = ev["screens"][a.screen]
    im = Image.open(os.path.join(base, item["path"])).convert("RGB")
    r = [float(v) for v in a.region.split(",")]
    sample = im.crop((int(r[0] * im.width), int(r[1] * im.height), int(r[2] * im.width), int(r[3] * im.height)))
    H = 120
    sample = sample.resize((max(1, round(sample.width * H / sample.height)), H), Image.LANCZOS)
    fonts = rs.Fonts(base)
    cands = a.candidates or sorted({k for k, v in rs.FONT_ALIASES.items()}, key=lambda k: rs.FONT_ALIASES[k][0])
    seen, rows = set(), []
    for c in cands:
        path, w = fonts.resolve(c)
        if (path, w) in seen or not path:
            continue
        seen.add((path, w))
        rows.append((c, path, w))
    lum_bg = rs.luminance(sample.resize((1, 1)).getpixel((0, 0)))
    bg, fg = ((20, 20, 24), (240, 240, 240)) if lum_bg < 0.4 else ((250, 250, 248), (20, 20, 20))
    pad = 24
    Wd = max(sample.width + 2 * pad, 1400)
    sheet = Image.new("RGB", (Wd, pad * 3 + H + len(rows) * (H + 16) + 40), (238, 236, 232))
    d = ImageDraw.Draw(sheet)
    lab = fonts.get("sans-bold", 22)
    d.text((pad, pad - 4), f"the app ({a.screen})", font=lab, fill=(40, 40, 40))
    sheet.paste(sample, (pad + 260, pad))
    y = pad * 2 + H
    for c, path, w in rows:
        size = 40
        f = fonts.get({"path": path, "weight": w}, size)
        cap = -f.getbbox("H", anchor="ls")[1]
        # match the sample's x-height-ish scale: fill ~62% of the row height with caps
        size = max(10, int(size * (H * 0.46) / max(cap, 1)))
        f = fonts.get({"path": path, "weight": w}, size)
        tile = Image.new("RGB", (Wd - 260 - 2 * pad, H), bg)
        ImageDraw.Draw(tile).text((12, H * 0.78), a.text, font=f, fill=fg, anchor="ls")
        sheet.paste(tile, (pad + 260, y))
        d.text((pad, y + H / 2 - 12), os.path.basename(c) if os.sep in str(c) else c, font=lab, fill=(40, 40, 40))
        y += H + 16
    sheet.save(a.output, quality=90)
    print(a.output)


def cmd_board(a):
    with open(a.dna, encoding="utf-8") as f:
        dna = json.load(f)
    base = os.path.dirname(os.path.abspath(a.dna))
    fonts = rs.Fonts(base)
    W = 2400
    pad = 70
    sheet = Image.new("RGB", (W, 2800), (244, 242, 238))  # cropped to its content at the end
    d = ImageDraw.Draw(sheet)
    fb, fm, fr = fonts.get("sans-bold", 54), fonts.get("sans-bold", 30), fonts.get("text", 26)
    d.text((pad, pad), f"{dna.get('app') or 'App'} — visual DNA", font=fb, fill=(20, 20, 20))
    y = pad + 100
    # palette
    d.text((pad, y), "Palette (from the UI, by area)", font=fm, fill=(60, 60, 60))
    y += 50
    x = pad
    measured = {p["hex"]: p for p in (dna.get("measured") or {}).get("palette") or []}
    if dna.get("palette"):  # the designer's curated roles win; measured shares shown where they match
        pal = [{"hex": v, "role": k, "share": measured.get(v, {}).get("share", 0)} for k, v in dna["palette"].items()]
    else:
        pal = list(measured.values())
    for p in pal[:9]:
        d.rounded_rectangle([x, y, x + 220, y + 160], radius=22, fill=rs.hexrgb(p["hex"]), outline=(210, 205, 198), width=2)
        d.text((x, y + 175), p["role"], font=fm, fill=(30, 30, 30))
        d.text((x, y + 212), f"{p['hex']}  {p.get('share', 0):.1%}" if p.get("share") else p["hex"], font=fr, fill=(90, 90, 90))
        x += 245
    y += 280
    # type
    d.text((pad, y), "Type", font=fm, fill=(60, 60, 60))
    y += 46
    ftab = dna.get("fonts") or {}
    sample = (dna.get("type_sample") or dna.get("app") or "Aa Bb Çç Ğğ İı Şş").strip()
    for role in ("display", "display_italic", "text"):
        ref = ftab.get(role)
        if not ref:
            continue
        path, w = fonts.resolve(ref)
        f = fonts.get({"path": path, "weight": w}, 84 if role != "text" else 44)
        d.text((pad, y + (84 if role != "text" else 44)), sample, font=f, fill=(20, 20, 20), anchor="ls")
        d.text((W - pad - 700, y + 30), f"{role}: {os.path.basename(path)}", font=fr, fill=(110, 110, 110))
        y += (110 if role != "text" else 70)
    if ftab.get("source"):
        d.text((pad, y), f"source: {ftab['source']}", font=fr, fill=(110, 110, 110))
        y += 44
    y += 20
    # signatures
    sigs = dna.get("signatures") or []
    if sigs:
        d.text((pad, y), "Signatures (crops of the real screens)", font=fm, fill=(60, 60, 60))
        y += 50
        x = pad
        ev = {}
        if dna.get("evidence"):
            with open(os.path.join(base, dna["evidence"]), encoding="utf-8") as f:
                ev = json.load(f)
        ev_base = os.path.dirname(os.path.join(base, dna.get("evidence", "")))
        hmax = 0
        for s in sigs[:5]:
            item = (ev.get("screens") or {}).get(s.get("evidence"))
            if not item:
                continue
            im = Image.open(os.path.join(ev_base, item["path"])).convert("RGB")
            r = s.get("crop", [0, 0, 1, 1])
            piece = im.crop((int(r[0] * im.width), int(r[1] * im.height), int(r[2] * im.width), int(r[3] * im.height)))
            h = 260
            piece = piece.resize((max(1, round(piece.width * h / piece.height)), h), Image.LANCZOS)
            if piece.width > 600:
                piece = piece.resize((600, round(h * 600 / piece.width)), Image.LANCZOS)
            if x + piece.width > W - pad:
                break
            sheet.paste(piece, (x, y))
            label = s.get("name", "")
            while label and fr.getlength(label) > piece.width:
                label = label[:-2].rstrip() + "…" if len(label) > 2 else ""
                label = label.replace("……", "…")
            d.text((x, y + piece.height + 10), label, font=fr, fill=(40, 40, 40))
            x += piece.width + 40
            hmax = max(hmax, piece.height)
        y += hmax + 70
    # notes
    mats = {k: v for k, v in (dna.get("materials") or {}).items() if not k.startswith("_") and v}
    made = "; ".join(f"{k} ({v})" if isinstance(v, str) else k for k, v in mats.items())
    absent = ", ".join(m for m in MATERIALS if m not in mats)
    refs = [r for r in dna.get("references") or [] if r.get("principles")]
    borrowed = "; ".join(f"{os.path.basename(r.get('file', ''))}: " + ", ".join(f"{k} {v}" for k, v in r["principles"].items()
                                                                                 if v and k not in ("not",) and isinstance(v, str))
                         for r in refs)
    notes = [("Shape", ", ".join(f"{k} {v}" for k, v in (dna.get("shape") or {}).items() if v)),
             ("Made of", made or "(not filled in - look at the screens)"),
             ("Not in the app", (absent + " - only with a concept reason") if mats else ""),
             ("Voice", dna.get("voice")), ("Makes / shows", dna.get("output")), ("Avoid", "; ".join(dna.get("avoid") or [])),
             ("From references", (borrowed + " (principles only)") if borrowed else "")]
    for k, v in notes:
        if not v:
            continue
        d.text((pad, y), k, font=fm, fill=(60, 60, 60))
        line, ty = "", y
        for wd in str(v).split():
            if fr.getlength(line + " " + wd) > W - 2 * pad - 320:
                d.text((pad + 320, ty + 4), line.strip(), font=fr, fill=(40, 40, 40))
                ty += 36
                line = wd
            else:
                line += " " + wd
        d.text((pad + 320, ty + 4), line.strip(), font=fr, fill=(40, 40, 40))
        y = ty + 56
    sheet = sheet.crop((0, 0, W, min(sheet.height, y + pad)))
    sheet.save(a.output, quality=90)
    print(a.output)


def reference_palette(im, n=8):
    """The reference's colours by area - neutrals and the chromatic accents, even small ones."""
    small = im.convert("RGB")
    small = small.resize((240, max(1, round(small.height * 240 / small.width))), Image.BILINEAR)
    q = small.quantize(colors=32, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()
    total = small.width * small.height
    counts = {tuple(pal[3 * i: 3 * i + 3]): c for c, i in q.getcolors()}
    groups = merge_colors(counts, total)
    keep = [g for g in groups if g["share"] >= 0.03 or (chroma(g["rgb"]) > 0.35 and g["share"] >= 0.004)]
    keep.sort(key=lambda g: -g["share"])
    return [hexs(g["rgb"]) for g in keep[:n]]


def cmd_reference(a):
    im = Image.open(a.image)
    palette = reference_palette(im)
    entry = {"file": os.path.abspath(a.image), "palette": palette,
             "principles": {"hierarchy": "", "density": "", "rhythm": "", "type_and_screen": "", "why_it_works": "",
                            "not": "its palette, fonts, illustrations, 3D objects or layouts one to one"}}
    if a.dna:
        with open(a.dna, encoding="utf-8") as f:
            dna = json.load(f)
        refs = [r for r in dna.get("references") or [] if os.path.abspath(r.get("file", "")) != entry["file"]]
        old = next((r for r in dna.get("references") or [] if os.path.abspath(r.get("file", "")) == entry["file"]), None)
        if old and old.get("principles"):
            entry["principles"] = old["principles"]  # keep what the designer wrote
        dna["references"] = refs + [entry]
        with open(a.dna, "w", encoding="utf-8") as f:
            json.dump(dna, f, ensure_ascii=False, indent=1)
    # the sheet: the reference, its palette marked "not ours", the principles to fill in
    fonts = rs.Fonts(HERE)
    fb, fr = fonts.get("sans-bold", 30), fonts.get("text", 22)
    h = 900
    ref = im.convert("RGB")
    ref = ref.resize((max(1, round(ref.width * h / ref.height)), h), Image.LANCZOS)
    if ref.width > 1500:
        ref = ref.resize((1500, round(h * 1500 / ref.width)), Image.LANCZOS)
    W = ref.width + 900
    sheet = Image.new("RGB", (W, h + 140), (244, 242, 238))
    sheet.paste(ref, (40, 100))
    d = ImageDraw.Draw(sheet)
    d.text((40, 36), f"Reference — {os.path.basename(a.image)}", font=fb, fill=(20, 20, 20))
    x0, y = ref.width + 80, 100
    d.text((x0, y), "Its palette - NOT for the campaign", font=fb, fill=(150, 40, 30))
    y += 50
    for i, hx in enumerate(palette[:8]):
        d.rounded_rectangle([x0 + i * 92, y, x0 + i * 92 + 80, y + 80], radius=14, fill=rs.hexrgb(hx), outline=(200, 195, 190), width=2)
    y += 130
    d.text((x0, y), "Principles to take (the designer writes them)", font=fb, fill=(20, 20, 20))
    y += 50
    for k, v in entry["principles"].items():
        d.text((x0, y), f"{k.replace('_', ' ')}:", font=fr, fill=(90, 90, 90))
        line, words = "", (v or "…").split()
        for wd in words:
            if line and fr.getlength(line + " " + wd) > W - x0 - 270:
                d.text((x0 + 230, y), line, font=fr, fill=(30, 30, 30))
                y += 32
                line = wd
            else:
                line = (line + " " + wd).strip()
        d.text((x0 + 230, y), line, font=fr, fill=(30, 30, 30))
        y += 44
    sheet.save(a.output, quality=88)
    print(f"palette {', '.join(palette)} recorded{' in ' + a.dna if a.dna else ''} → {a.output}")
    print("write the principles (hierarchy, density, rhythm, how type and screen share the canvas) into dna.json; "
          "the campaign is checked for copying the palette")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("measure", help="palette roles, UI mode, type scale (+ website fonts/colours)")
    m.add_argument("evidence")
    m.add_argument("--site")
    m.add_argument("--app")
    m.add_argument("-o", "--output", default="dna.json")
    f = sub.add_parser("fonts", help="font-match sheet: the app's text next to each candidate font")
    f.add_argument("evidence")
    f.add_argument("screen")
    f.add_argument("--region", required=True, help="x0,y0,x1,y1 of a line of the app's text")
    f.add_argument("--text", required=True, help="the same words, to set in each candidate")
    f.add_argument("--candidates", nargs="+", help="aliases or font paths (default: every bundled font)")
    f.add_argument("-o", "--output", default="font-match.jpg")
    b = sub.add_parser("board", help="render the DNA board")
    b.add_argument("dna")
    b.add_argument("-o", "--output", default="dna-board.jpg")
    r = sub.add_parser("reference", help="record a reference the user likes: its palette (for the copy check) and principles")
    r.add_argument("image")
    r.add_argument("--dna", help="dna.json to add the reference to")
    r.add_argument("-o", "--output", default="reference.jpg")
    a = p.parse_args()
    {"measure": cmd_measure, "fonts": cmd_fonts, "board": cmd_board, "reference": cmd_reference}[a.cmd](a)


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):  # Windows consoles and pipes default to a legacy code page
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    main()
