#!/usr/bin/env python3
"""Maintainers only: turn collected screenshots into the skill's library.

  extract   dedupe raw screenshots, convert to WebP, OCR the headline, measure colour/text features
            -> assets/library/auto.json            (needs Pillow + tesseract with eng and tur)
  merge     auto.json + classifications.json -> catalog.json + stats.json   (Pillow not needed)
  check     report records without a classification, missing files, lite coverage

Typical run after collect_examples.py:
  python3 build_catalog.py extract --raw ../../../raw
  # edit assets/library/classifications.json (one object per app, see references/library-guide.md §5)
  python3 build_catalog.py merge
"""
import argparse
import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.normpath(os.path.join(HERE, "..", "assets", "library"))
WIDTH = 480
QUALITY = 72

TR_CHARS = set("şğıİŞĞçÇöÖüÜ")
TR_WORDS = {"ve", "ile", "için", "bir", "her", "daha", "kolay", "hemen", "tüm", "sen", "seni", "senin",
            "kolayca", "hızlı", "yeni", "ücretsiz", "artık", "tek", "bu", "da", "de", "ile", "en", "çok"}
EN_WORDS = {"the", "and", "your", "you", "with", "for", "to", "in", "on", "all", "get", "more", "easy",
            "new", "free", "any", "one", "of", "a", "every", "from", "share", "find", "make"}


# ---------------------------------------------------------------- extract

LETTER = r"[A-Za-zÇĞİÖŞÜçğıöşü]"


def ocr_words(img, tmpdir):
    """Run tesseract (sparse text) on a PIL image, return plausible words with geometry."""
    path = os.path.join(tmpdir, f"ocr-{os.getpid()}.png")
    img.save(path)
    out = subprocess.run(["tesseract", path, "stdout", "-l", "eng+tur", "--psm", "11", "tsv"],
                         capture_output=True, encoding="utf-8", errors="replace", timeout=120).stdout
    words = []
    for line in out.splitlines()[1:]:
        p = line.split("\t")
        if len(p) < 12 or not p[11].strip():
            continue
        try:
            conf = float(p[10])
        except ValueError:
            continue
        text = p[11].strip()
        if conf < 55:
            continue
        if len(re.findall(LETTER, text)) < 2 and not re.fullmatch(r"\d+[+%x]?", text) and text not in ("&", "a", "A", "I"):
            continue
        words.append({"text": text, "left": int(p[6]), "top": int(p[7]), "w": int(p[8]), "h": int(p[9])})
    return words


def join_lines(words):
    words = sorted(words, key=lambda w: w["top"] + w["h"] / 2)
    lines = []
    for w in words:
        c = w["top"] + w["h"] / 2
        if lines and abs(c - lines[-1]["c"]) < 0.55 * max(w["h"], lines[-1]["h"]):
            lines[-1]["ws"].append(w)
            lines[-1]["h"] = max(lines[-1]["h"], w["h"])
        else:
            lines.append({"c": c, "h": w["h"], "ws": [w]})
    return " ".join(" ".join(x["text"] for x in sorted(l["ws"], key=lambda w: w["left"])) for l in lines)


def zone_text(gray, box, tmpdir):
    """OCR one caption zone at 2x with auto-contrast; return (largest word height in source px, text)."""
    from PIL import Image, ImageOps
    crop = gray.crop(box)
    w, h = crop.size
    crop = ImageOps.autocontrast(crop.resize((w * 2, h * 2), Image.LANCZOS))
    words = ocr_words(crop, tmpdir)
    if not words:
        return 0, "", 0
    hmax = max(x["h"] for x in words)
    big = [x for x in words if x["h"] >= 0.55 * hmax]
    return hmax / 2, join_lines(big), sum(len(x["text"]) for x in words)


def headline_from(gray, tmpdir):
    """Captions sit outside the device: OCR the top 30 % and bottom 22 %, keep the biggest text block.
    The top zone wins unless the bottom clearly carries larger type."""
    W, H = gray.size
    th, tt, tc = zone_text(gray, (0, 0, W, int(H * 0.30)), tmpdir)
    bh, bt, bc = zone_text(gray, (0, int(H * 0.78), W, H), tmpdir)
    if th >= 16 and not (bh > 1.3 * th and bh >= 24):
        return tt, "top", th, tc + bc
    if bh >= 22:
        return bt, "bottom", bh, tc + bc
    return "", None, max(th, bh), tc + bc


def language(text):
    t = text.lower()
    toks = set(re.findall(r"[a-zçğıöşü]+", t))
    if any(c in text for c in TR_CHARS) or len(toks & TR_WORDS) >= 1 and len(toks & EN_WORDS) == 0:
        return "tr"
    if toks & EN_WORDS or re.search(r"[a-z]", t):
        return "en"
    return None


def colour_features(im):
    from PIL import Image
    small = im.convert("RGB").resize((48, 104))
    q = small.quantize(colors=4, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[:12]
    counts = sorted(q.getcolors(), reverse=True)
    palette = ["#%02x%02x%02x" % tuple(pal[i * 3:i * 3 + 3]) for _, i in counts[:3]]
    lum = small.convert("L")
    px = list(lum.get_flattened_data() if hasattr(lum, 'get_flattened_data') else lum.getdata())
    brightness = sum(px) / len(px) / 255
    # background: the four corners are almost always background (outside the device and the caption)
    def stats(box):
        region = small.crop(box)
        d = list(region.get_flattened_data() if hasattr(region, 'get_flattened_data') else region.getdata())
        means = [sum(c[k] for c in d) / len(d) for k in range(3)]
        sd = sum(sum((c[k] - means[k]) ** 2 for c in d) / len(d) for k in range(3)) ** 0.5
        return means, sd

    corners = [stats(b) for b in ((0, 0, 5, 5), (43, 0, 48, 5), (0, 99, 5, 104), (43, 99, 48, 104))]
    flat = sum(1 for _, sd in corners if sd < 14)
    top_mean = [(corners[0][0][k] + corners[1][0][k]) / 2 for k in range(3)]
    bot_mean = [(corners[2][0][k] + corners[3][0][k]) / 2 for k in range(3)]
    diff = sum((top_mean[k] - bot_mean[k]) ** 2 for k in range(3)) ** 0.5
    if flat >= 3:
        bg = "gradient" if diff > 35 else "flat"
    elif flat == 2 and corners[0][1] < 14 and corners[1][1] < 14:
        bg = "flat-top"  # plain caption area, photo or device bleeds at the bottom
    else:
        bg = "image"
    return palette, round(brightness, 2), bg


def extract_one(args):
    src, dest = args
    import tempfile
    from PIL import Image
    im = Image.open(src).convert("RGB")
    w, h = im.size
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if not os.path.exists(dest):
        im.resize((WIDTH, round(h * WIDTH / w)), Image.LANCZOS).save(dest, "WEBP", quality=QUALITY, method=6)
    with tempfile.TemporaryDirectory() as tmp:
        headline, pos, hmax, text_chars = headline_from(im.convert("L"), tmp)
    palette, brightness, bg = colour_features(im)
    return {
        "headline_ocr": headline,
        "headline_words": len(headline.split()) if headline else 0,
        "headline_pos": pos,
        "headline_px": round(hmax * 1000 / h, 1) if hmax else 0,  # per mille of image height
        "text_chars": text_chars,
        "language": language(headline) if headline else None,
        "palette": palette,
        "brightness": brightness,
        "dark": brightness < 0.35,
        "background": bg,
        "aspect": round(h / w, 3),
        "landscape": w > h,
    }


def cmd_extract(a):
    with open(os.path.join(a.raw, "manifest.json"), encoding="utf-8") as f:
        records = json.load(f)
    by_src, jobs = {}, []
    for r in records:
        key = hashlib.sha1(r["source_url"].encode()).hexdigest()
        if key not in by_src:
            rel = "img/" + re.sub(r"\.jpg$", ".webp", r["file"])
            by_src[key] = rel
            jobs.append((os.path.join(a.raw, r["file"]), os.path.join(LIB, rel), key))
        r["image"] = by_src[key]
        r["image_id"] = key[:12]
    auto_path = os.path.join(LIB, "auto.json")
    done = {}
    if os.path.exists(auto_path):
        done = {x["image_id"]: x for x in json.load(open(auto_path, encoding="utf-8")).get("images", [])}
    todo = [j for j in jobs if j[2][:12] not in done]
    print(f"{len(records)} records, {len(jobs)} unique images, {len(todo)} to process")
    with Pool(a.workers) as pool:
        for i, ((src, dest, key), feats) in enumerate(zip(todo, pool.imap(extract_one, [(s, d) for s, d, _ in todo])), 1):
            done[key[:12]] = {"image_id": key[:12], **feats}
            if i % 50 == 0:
                print(f"  {i}/{len(todo)}", flush=True)
    os.makedirs(LIB, exist_ok=True)
    with open(auto_path, "w", encoding="utf-8") as f:
        json.dump({"records": records, "images": list(done.values())}, f, ensure_ascii=False, indent=0)
    print(f"wrote {auto_path}")


# ---------------------------------------------------------------- merge

APP_FIELDS = ["layout", "techniques", "first_shot", "story", "quality", "ai_smell", "note"]


def cmd_merge(a):
    auto = json.load(open(os.path.join(LIB, "auto.json"), encoding="utf-8"))
    images = {x["image_id"]: x for x in auto["images"]}
    cls_path = os.path.join(LIB, "classifications.json")
    cls = json.load(open(cls_path, encoding="utf-8")) if os.path.exists(cls_path) else {"apps": [], "shots": []}
    apps = {(c["app_id"]): c for c in cls.get("apps", [])}
    shots = {c["image_id"]: c for c in cls.get("shots", [])}
    lite = set(cls.get("lite", []))
    catalog = []
    for r in auto["records"]:
        img = images[r["image_id"]]
        app = apps.get(r["app_id"], {})
        shot = shots.get(r["image_id"], {})
        rec = {
            "id": f'{r["country"]}-{r["category"]}-{r["chart_rank"]:02d}-{r["position"]:02d}',
            "image": r["image"],
            "image_id": r["image_id"],
            "in_lite": r["image_id"] in lite,
            "country": r["country"],
            "category": r["category"],
            "chart_rank": r["chart_rank"],
            "source": r.get("source", "chart"),
            "app": r["app"],
            "app_id": r["app_id"],
            "seller": r["seller"],
            "position": r["position"],
            "shots_total": r["shots_total"],
            # copy: a verified headline (from classifications) wins over OCR
            "headline": shot.get("headline", img["headline_ocr"]),
            "headline_verified": "headline" in shot,
            "headline_words": len(shot["headline"].split()) if "headline" in shot else img["headline_words"],
            "headline_pos": img["headline_pos"],
            "headline_px": img["headline_px"],
            "language": shot.get("language", img["language"]),
            "text_chars": img["text_chars"],
            "palette": img["palette"],
            "dark": img["dark"],
            "background": img["background"],
            "landscape": img["landscape"],
        }
        for k in APP_FIELDS:
            rec[k] = app.get(k)
        rec["shot_note"] = shot.get("note", "")
        if "exemplary" in shot:
            rec["exemplary"] = shot["exemplary"]
        else:
            rec["exemplary"] = app.get("quality") == "exemplary"
        rec["store_url"] = r["store_url"]
        catalog.append(rec)
    catalog.sort(key=lambda x: x["id"])
    with open(os.path.join(LIB, "catalog.json"), "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, separators=(",", ":"))
    stats = build_stats(catalog)
    with open(os.path.join(LIB, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)
    print(f"catalog.json: {len(catalog)} records ({sum(r['in_lite'] for r in catalog)} in lite); stats.json written")


def pct(values, q):
    v = sorted(values)
    if not v:
        return None
    k = (len(v) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(v) - 1)
    return round(v[lo] + (v[hi] - v[lo]) * (k - lo), 1)


def build_stats(catalog):
    def dist(rows):
        words = [r["headline_words"] for r in rows if r["headline_words"]]
        return {
            "shots": len(rows),
            "apps": len({(r["country"], r["app_id"]) for r in rows}),
            "headline_words": {"p25": pct(words, .25), "median": pct(words, .5), "p75": pct(words, .75)},
            "no_headline_share": round(sum(1 for r in rows if not r["headline_words"]) / max(len(rows), 1), 2),
            "headline_top_share": round(sum(1 for r in rows if r["headline_pos"] == "top") / max(len(rows), 1), 2),
            "dark_share": round(sum(1 for r in rows if r["dark"]) / max(len(rows), 1), 2),
            "background": dict(Counter(r["background"] for r in rows).most_common()),
            "layout": dict(Counter(r["layout"] for r in rows if r["layout"]).most_common()),
            "quality": dict(Counter(r["quality"] for r in rows if r["quality"]).most_common()),
        }

    out = {"all": dist(catalog), "by_country": {}, "by_category": {}, "first_shots": dist([r for r in catalog if r["position"] == 1])}
    for c in sorted({r["country"] for r in catalog}):
        out["by_country"][c] = dist([r for r in catalog if r["country"] == c])
        rows = [r for r in catalog if r["country"] == c and r["language"]]
        out["by_country"][c]["headline_language"] = dict(Counter(r["language"] for r in rows).most_common())
    for cat in sorted({r["category"] for r in catalog}):
        out["by_category"][cat] = dist([r for r in catalog if r["category"] == cat])
    techs = Counter(t for r in catalog if r["position"] == 1 for t in (r["techniques"] or []))
    out["techniques_per_app"] = dict(Counter(t for app in {(r["country"], r["app_id"]): r for r in catalog}.values()
                                             for t in (app["techniques"] or [])).most_common())
    return out


# ---------------------------------------------------------------- check

def cmd_check(a):
    cat = json.load(open(os.path.join(LIB, "catalog.json"), encoding="utf-8"))
    missing_cls = sorted({r["app"] for r in cat if not r["quality"]})
    missing_files = [r["image"] for r in cat if not os.path.exists(os.path.join(LIB, r["image"]))]
    missing_lite = [r["image"] for r in cat if r["in_lite"] and not os.path.exists(os.path.join(LIB, r["image"]))]
    lite_pkg = missing_files and not missing_lite and len(missing_files) == sum(1 for r in cat if not r["in_lite"])
    print(f"records: {len(cat)}  apps without classification: {len(missing_cls)}  "
          + ("lite package: only lite images present (expected)" if lite_pkg else f"missing image files: {len(missing_files)}"))
    for name in missing_cls[:20]:
        print("  unclassified:", name)
    if not lite_pkg:
        for p in missing_files[:20]:
            print("  missing file:", p)
    lite = [r for r in cat if r["in_lite"]]
    uniq = {r["image_id"]: r for r in lite}
    print(f"lite: {len(uniq)} unique images ({len(lite)} records); exemplary {sum(1 for r in uniq.values() if r['exemplary'])}, "
          f"ai-smell {sum(1 for r in uniq.values() if r['ai_smell'])}; categories {len({r['category'] for r in lite})}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract")
    e.add_argument("--raw", required=True, help="folder with manifest.json from collect_examples.py")
    e.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    sub.add_parser("merge")
    sub.add_parser("check")
    a = p.parse_args()
    {"extract": cmd_extract, "merge": cmd_merge, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):  # Windows consoles and pipes default to a legacy code page
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
