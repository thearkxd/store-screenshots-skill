#!/usr/bin/env python3
"""Collect App Store screenshots of top free apps per category, as study examples.

Dependency-free (Python 3 stdlib only). Needs network access to:
  itunes.apple.com, is1-ssl.mzstatic.com

Examples:
  python3 collect_examples.py --countries tr us --per-category 4
  python3 collect_examples.py --countries tr --categories entertainment --per-category 6
  python3 collect_examples.py --countries us --app-ids 431946152 1196327880 --label competitors

Output (default ./raw):
  raw/<country>/<category>/<rank>-<app-slug>/<NN>.jpg
  raw/manifest.json   one record per screenshot, ready to be classified into catalog.json

The screenshots are the property of their app publishers. Keep them as private study
material; do not redistribute them or use them in your own store listings.
"""
import argparse
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

# App Store categories (genre IDs). A category may list several genres; ranks are interleaved.
CATEGORIES = {
    "books": {"label": "Kitaplar", "genres": [6018]},
    "business": {"label": "İş", "genres": [6000]},
    "developer-tools": {"label": "Geliştirici Araçları", "genres": [6026]},
    "education": {"label": "Eğitim", "genres": [6017]},
    "entertainment": {"label": "Eğlence", "genres": [6016]},
    "finance": {"label": "Finans", "genres": [6015]},
    "food-drink": {"label": "Yemek ve İçecek", "genres": [6023]},
    "games": {"label": "Oyunlar", "genres": [6014]},
    "graphics-design": {"label": "Grafik ve Tasarım", "genres": [6027]},
    "health-fitness": {"label": "Sağlık ve Fitness", "genres": [6013]},
    "lifestyle": {"label": "Yaşam Tarzı", "genres": [6012]},
    "magazines-newspapers": {"label": "Dergiler ve Gazeteler", "genres": [6021]},
    "medical": {"label": "Tıp", "genres": [6020]},
    "music": {"label": "Müzik", "genres": [6011]},
    "navigation": {"label": "Navigasyon", "genres": [6010]},
    "news": {"label": "Haberler", "genres": [6009]},
    "photo-video": {"label": "Fotoğraf ve Video", "genres": [6008]},
    "productivity": {"label": "Verimlilik", "genres": [6007]},
    "reference": {"label": "Başvuru", "genres": [6006]},
    "shopping": {"label": "Alışveriş", "genres": [6024]},
    "social-networking": {"label": "Sosyal Ağ", "genres": [6005]},
    "sports": {"label": "Spor", "genres": [6004]},
    "stickers": {"label": "Çıkartmalar", "genres": [6025]},
    "travel": {"label": "Seyahat", "genres": [6003]},
    "utilities": {"label": "Yardımcı Araçlar", "genres": [6002]},
    "weather": {"label": "Hava Durumu", "genres": [6001]},
}

UA = "store-screenshots-skill/1.0"


def get(url, retries=3, timeout=30):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last


def get_json(url):
    return json.loads(get(url).decode("utf-8"))


def slugify(text, maxlen=40):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:maxlen].strip("-") or "app"


def top_ids(country, genre, limit):
    url = f"https://itunes.apple.com/{country}/rss/topfreeapplications/limit={limit}/genre={genre}/json"
    feed = get_json(url).get("feed", {})
    entries = feed.get("entry", [])
    if isinstance(entries, dict):
        entries = [entries]
    return [e["id"]["attributes"]["im:id"] for e in entries]


def lookup(app_id, country):
    data = get_json(f"https://itunes.apple.com/lookup?id={app_id}&country={country}")
    res = data.get("results", [])
    return res[0] if res else None


def resize_url(url, width):
    # mzstatic URLs end in "<w>x<h>bb.<ext>"; asking for "<width>x0w.jpg" returns a scaled JPG.
    return re.sub(r"/[^/]+$", f"/{width}x0w.jpg", url)


def interleave(lists):
    out, seen = [], set()
    for i in range(max((len(l) for l in lists), default=0)):
        for l in lists:
            if i < len(l) and l[i] not in seen:
                seen.add(l[i])
                out.append(l[i])
    return out


def collect_app(app_id, country, category, rank, out_root, max_shots, width, records, source="chart"):
    info = lookup(app_id, country)
    if not info:
        print(f"    ! {app_id}: not found in {country}")
        return False
    shots = info.get("screenshotUrls") or []
    if not shots:
        print(f"    ! {info.get('trackName')}: no iPhone screenshots, skipped")
        return False
    name = info.get("trackName", str(app_id))
    folder = os.path.join(out_root, country, category, f"{rank:02d}-{slugify(name)}")
    os.makedirs(folder, exist_ok=True)
    def fetch(pos_src):
        pos, src = pos_src
        dest = os.path.join(folder, f"{pos:02d}.jpg")
        if not os.path.exists(dest):
            try:
                blob = get(resize_url(src, width))
            except Exception:
                blob = get(src)  # fall back to the original size/format
            with open(dest, "wb") as f:
                f.write(blob)
        return pos, src, dest

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(fetch, enumerate(shots[:max_shots], start=1)))
    saved = 0
    for pos, src, dest in results:
        saved += 1
        records.append({
            "file": os.path.relpath(dest, out_root).replace(os.sep, "/"),
            "country": country,
            "category": category,
            "chart_rank": rank,
            "app": name,
            "app_id": int(app_id),
            "seller": info.get("sellerName"),
            "genre": info.get("primaryGenreName"),
            "position": pos,
            "shots_total": len(shots),
            "store_url": info.get("trackViewUrl", "").split("?")[0],
            "source": source,
            "source_url": src,
        })
    print(f"    {rank:>2}. {name} — {saved}/{len(shots)} screenshots")
    return True


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--countries", nargs="+", default=["tr", "us"])
    p.add_argument("--categories", nargs="+", default=list(CATEGORIES), choices=list(CATEGORIES))
    p.add_argument("--per-category", type=int, default=4)
    p.add_argument("--max-shots", type=int, default=8, help="screenshots per app (store max is 10)")
    p.add_argument("--width", type=int, default=600, help="download width in px")
    p.add_argument("--app-ids", nargs="+", help="collect these App Store IDs instead of the charts")
    p.add_argument("--label", default="curated", help="category folder name used with --app-ids")
    p.add_argument("--source", default=None, help="record source tag (default: chart, or curated with --app-ids)")
    p.add_argument("--start-rank", type=int, default=1, help="first rank number used with --app-ids (keeps ids unique)")
    p.add_argument("--out", default="raw", help="output folder (default ./raw)")
    a = p.parse_args()

    out_root = os.path.abspath(a.out)
    os.makedirs(out_root, exist_ok=True)
    manifest_path = os.path.join(out_root, "manifest.json")
    records = []
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as f:
            records = json.load(f)
    existing = {r["file"] for r in records}
    new = []

    for country in a.countries:
        if a.app_ids:
            print(f"[{country}] {a.label}")
            for rank, app_id in enumerate(a.app_ids, start=a.start_rank):
                collect_app(app_id, country, a.label, rank, out_root, a.max_shots, a.width, new, a.source or "curated")
            continue
        for cat in a.categories:
            print(f"[{country}] {CATEGORIES[cat]['label']} ({cat})")
            try:
                ranked = interleave([top_ids(country, g, 25) for g in CATEGORIES[cat]["genres"]])
            except Exception as e:
                print(f"    ! chart not available: {e}")
                continue
            got = 0
            for app_id in ranked:
                if got >= a.per_category:
                    break
                try:
                    if collect_app(app_id, country, cat, got + 1, out_root, a.max_shots, a.width, new):
                        got += 1
                except Exception as e:
                    print(f"    ! {app_id}: {e}")
            if got < a.per_category:
                print(f"    ! only {got} apps with screenshots")

    records += [r for r in new if r["file"] not in existing]
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=1)
    apps = {(r["country"], r["app_id"]) for r in new}
    print(f"\nDone: {len(new)} screenshots from {len(apps)} apps → {out_root}")


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):  # Windows consoles and pipes default to a legacy code page
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
