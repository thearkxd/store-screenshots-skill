#!/usr/bin/env python3
"""Concept checkpoint: render the first shots of a set in several design directions, side by side.

Show this to the user BEFORE rendering the whole set, so the look is a choice, not a default.

  python3 concepts.py set.json -o concepts.jpg                          # 3 directions picked for the category
  python3 concepts.py set.json --directions cinematic poster editorial -o concepts.jpg
  python3 concepts.py set.json --shots 1 2 3 --locale tr --list         # --list shows every direction

--shots counts spec entries: a span (two slots) shows as both halves. The spec's "brand" tokens are used; its "style" and per-shot look keys (background, colours, fonts,
emphasis, device) are dropped so each direction shows its own system. Copy, screens, crops, callouts,
annotations and stickers are kept. Pick a direction, then set "direction" in the spec and render it.
"""
import argparse
import copy
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design  # noqa: E402
import render_set as rs  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

LOOK_KEYS = {"background", "text_color", "sub_color", "emphasis", "device", "card", "font", "case", "align",
             "tracking", "weight", "style", "band_color", "shapes", "text_x", "text_width", "headline_size",
             "line_height", "overline_style", "stickers_style", "annotation_style"}


# safe · bold · unexpected - kept in sync with references/categories.md
CATEGORY_PICKS = {
    "books": ["editorial", "cinematic", "crafted"],
    "business": ["native", "poster", "editorial"],
    "developer-tools": ["utility", "native", "poster"],
    "education": ["playful", "native", "crafted"],
    "entertainment": ["cinematic", "poster", "editorial"],
    "finance": ["native", "poster", "editorial"],
    "food-drink": ["poster", "playful", "crafted"],
    "games": ["playful", "poster", "cinematic"],
    "graphics-design": ["cinematic", "editorial", "poster"],
    "health-fitness": ["native", "poster", "crafted"],
    "lifestyle": ["editorial", "playful", "crafted"],
    "magazines-newspapers": ["editorial", "native", "poster"],
    "medical": ["native", "crafted", "editorial"],
    "music": ["cinematic", "playful", "poster"],
    "navigation": ["crafted", "native", "poster"],
    "news": ["editorial", "poster", "playful"],
    "photo-video": ["cinematic", "native", "playful"],
    "productivity": ["native", "editorial", "crafted"],
    "reference": ["editorial", "crafted", "native"],
    "shopping": ["poster", "editorial", "playful"],
    "social-networking": ["playful", "poster", "editorial"],
    "sports": ["poster", "utility", "cinematic"],
    "travel": ["poster", "native", "crafted"],
    "utilities": ["native", "utility", "playful"],
    "weather": ["crafted", "utility", "cinematic"],
    "kids": ["playful", "crafted", "native"],
}


def suggest(category, n=3):
    """One safe pick, one bold pick, one unexpected pick for the category."""
    dirs = design.list_directions()
    if category in CATEGORY_PICKS:
        picks = [k for k in CATEGORY_PICKS[category] if k in dirs]
        picks += [k for k in dirs if k not in picks]
        return picks[:n]
    fit = [k for k, v in dirs.items() if category and category in v.get("fits", [])]
    rest = [k for k in dirs if k not in fit]
    order = {"native": 0, "editorial": 1, "crafted": 2, "cinematic": 3, "utility": 4, "playful": 5, "poster": 6}
    fit.sort(key=lambda k: order.get(k, 9))
    picks = []
    if fit:
        picks.append(fit[0])                      # safest fitting
        bold = [k for k in fit if k in ("poster", "playful", "cinematic") and k not in picks]
        picks += bold[:1]
        picks += [k for k in fit if k not in picks][:1]
    for k in rest:                                # something the category doesn't usually do
        if len(picks) >= n:
            break
        picks.append(k)
    for k in dirs:
        if len(picks) >= n:
            break
        if k not in picks:
            picks.append(k)
    return picks[:n]


def strip_look(spec, direction):
    sp = copy.deepcopy(spec)
    sp["direction"] = direction
    sp["style"] = {k: v for k, v in (spec.get("style") or {}).items() if k in ("sub_font",)}
    def strip(shot):
        out = {k: v for k, v in shot.items() if k not in LOOK_KEYS}
        if isinstance(out.get("halves"), list):
            out["halves"] = [{k: v for k, v in h.items() if k not in LOOK_KEYS} for h in out["halves"]]
        if isinstance(shot.get("device"), dict) and "x" in shot["device"] and shot.get("span") == 2:
            out["device"] = {"x": shot["device"]["x"]}  # where the phone crosses the seam is content, not look
        return out
    sp["shots"] = [dict(strip(s), _entry=i) for i, s in enumerate(spec["shots"], start=1)]
    sp.pop("feature_graphic", None)
    return sp


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("spec", nargs="?")
    p.add_argument("--directions", nargs="+")
    p.add_argument("--category", help="App Store category for automatic picks (default: spec 'category')")
    p.add_argument("--shots", nargs="+", type=int, default=[1, 2, 3])
    p.add_argument("--size", default="ios")
    p.add_argument("--locale")
    p.add_argument("--width", type=int, default=260, help="thumbnail width per shot")
    p.add_argument("-o", "--output", default="concepts.jpg")
    p.add_argument("--list", action="store_true")
    a = p.parse_args()
    dirs = design.list_directions()
    if a.list:
        for k, v in dirs.items():
            print(f"{k:10} {v['label']:16} fits: {', '.join(v.get('fits', []))}\n           {v['summary']}\n")
        return
    if not a.spec:
        p.error("spec is required")
    spec_dir = os.path.dirname(os.path.abspath(a.spec))
    with open(a.spec, encoding="utf-8") as f:
        spec = json.load(f)
    if spec.get("locales"):
        loc = a.locale or spec["locales"][0]
        spec = rs.localize(spec, loc, spec["locales"])
        lang = loc.split("-")[0]
    else:
        lang = spec.get("lang", "en")
    picks = a.directions or suggest(a.category or spec.get("category"))
    try:
        W, H = rs.preset_size(a.size)
    except ValueError as e:
        p.error(str(e))
    fonts = rs.Fonts(spec_dir)
    rows = []
    for name in picks:
        sp = strip_look(spec, name)
        # same pipeline as render_set: per-size screens, "stores", the device class's frame, canvas scaling
        W, H, style, shots, _, _ = rs.prepare(sp, a.size, spec_dir, fonts, lang)
        by_entry = {sh["_entry"]: sh for sh in shots}
        thumbs = []
        for i in a.shots:
            if i not in by_entry:
                continue
            imgs, warns, _ = rs.render_any(by_entry[i], style, W, H, fonts, spec_dir, lang)
            for w in warns:
                print(f"! {name} shot {i}: {w}")
            # a span shows as its two halves, with the same gap the store puts between screenshots
            thumbs += [img.resize((a.width, round(H * a.width / W)), Image.LANCZOS) for img in imgs]
        rows.append((name, dirs[name], thumbs))
    th = rows[0][2][0].height
    gap, label_h = 18, 64
    cols = max(len(r[2]) for r in rows)
    sheet = Image.new("RGB", (gap + cols * (a.width + gap) + 520, gap + len(rows) * (th + label_h + gap)), (240, 238, 234))
    d = ImageDraw.Draw(sheet)
    f_b = fonts.get("sans-bold", 26)
    f_r = fonts.get("text", 17)
    y = gap
    for idx, (name, meta, thumbs) in enumerate(rows):
        d.text((gap, y + 6), f"{chr(65 + idx)} — {meta['label']}  ({name})", font=f_b, fill=(20, 20, 20))
        x = gap
        for t in thumbs:
            sheet.paste(t, (x, y + label_h))
            x += a.width + gap
        # summary on the right
        words, line, ty = meta["summary"].split(), "", y + label_h
        for w in words:
            if f_r.getlength(line + " " + w) > 480:
                d.text((x + 10, ty), line.strip(), font=f_r, fill=(70, 70, 70))
                ty += 24
                line = w
            else:
                line += " " + w
        d.text((x + 10, ty), line.strip(), font=f_r, fill=(70, 70, 70))
        d.text((x + 10, ty + 40), "Refs: " + ", ".join(meta.get("references", [])[:4]), font=f_r, fill=(120, 120, 120))
        y += th + label_h + gap
    sheet.save(a.output, quality=88)
    print(f"{a.output}  directions: {', '.join(picks)}")


if __name__ == "__main__":
    main()
