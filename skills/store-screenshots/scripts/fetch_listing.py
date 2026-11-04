#!/usr/bin/env python3
"""Fetch a live store listing so the brief starts from facts, not questions. Dependency-free (Pillow optional).

  python3 fetch_listing.py https://apps.apple.com/tr/app/seenfy-ne-izlesem-film-dizi/id6764370964
  python3 fetch_listing.py "https://play.google.com/store/apps/details?id=com.example.app&hl=tr"
  python3 fetch_listing.py <app-store-url> <play-url> --search "film dizi takip" --out listing/
  python3 fetch_listing.py --lookup-json saved.json        # parse a saved iTunes lookup response (offline)

Writes <out>/<store>-<country>-<id>/:
  listing.json     raw facts (name, seller, category, description, release notes, version, rating, languages…)
  listing.md       readable summary for the brief + critique (current headlines via OCR if tesseract exists)
  screenshots/     the CURRENT store screenshots (marketing images - study them, never cut UI out of them)
  icon.png         app icon (+ dominant colours in listing.md)
  current.jpg      contact sheet of the current set (needs Pillow)

App Store: iTunes Lookup API (itunes.apple.com + is1-ssl.mzstatic.com). Google Play has no public API: the
page is parsed best-effort (play.google.com + play-lh.googleusercontent.com). If the network is blocked, the
script says so and exits 2 - then use a web-fetch tool or ask the user to paste the listing text
(references/intake.md §3).
"""
import argparse
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"


class Blocked(Exception):
    pass


def get(url, timeout=30, retries=3):
    """Fetch bytes. A proxy/firewall refusal raises Blocked; Apple's own 403/429 (rate limiting) is retried."""
    import time
    # Apple's APIs reject browser-looking agents; store web pages want one
    ua = UA if ("play.google.com" in url or "apps.apple.com" in url) else "store-screenshots-skill/1.0"
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Language": "en,tr;q=0.8"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (403, 429, 503) and attempt < retries - 1:
                time.sleep(3 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            raise Blocked(f"{url}: {e}")


def slug(text, n=40):
    import unicodedata
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()[:n] or "app"


# ---------------------------------------------------------------- App Store

def parse_appstore_url(u):
    m = re.search(r"apps\.apple\.com/([a-z]{2})/.*?id(\d+)", u) or re.search(r"apps\.apple\.com/.*?id(\d+)", u)
    if not m:
        return None
    if len(m.groups()) == 2:
        return {"store": "appstore", "country": m.group(1), "id": m.group(2)}
    return {"store": "appstore", "country": "us", "id": m.group(1)}


def appstore_from_lookup(r, country):
    return {
        "store": "appstore",
        "country": country,
        "id": str(r.get("trackId")),
        "name": r.get("trackName"),
        "subtitle": None,  # not in the Lookup API; filled from the web page when reachable
        "seller": r.get("sellerName"),
        "category": r.get("primaryGenreName"),
        "genres": r.get("genres", []),
        "genre_id": r.get("primaryGenreId"),
        "description": r.get("description", ""),
        "release_notes": r.get("releaseNotes", ""),
        "version": r.get("version"),
        "updated": (r.get("currentVersionReleaseDate") or "")[:10],
        "released": (r.get("releaseDate") or "")[:10],
        "rating": r.get("averageUserRating"),
        "rating_count": r.get("userRatingCount"),
        "languages": r.get("languageCodesISO2A", []),
        "price": r.get("formattedPrice"),
        "age_rating": r.get("contentAdvisoryRating"),
        "url": (r.get("trackViewUrl") or "").split("?")[0],
        "icon_url": r.get("artworkUrl512") or r.get("artworkUrl100"),
        "screenshots": r.get("screenshotUrls", []),
        "ipad_screenshots": r.get("ipadScreenshotUrls", []),
    }


def fetch_appstore(ref):
    data = json.loads(get(f"https://itunes.apple.com/lookup?id={ref['id']}&country={ref['country']}"))
    if not data.get("results"):
        sys.exit(f"App Store: id {ref['id']} not found in the {ref['country']} store")
    info = appstore_from_lookup(data["results"][0], ref["country"])
    try:  # subtitle lives only in the page HTML
        page = get(f"https://apps.apple.com/{ref['country']}/app/id{ref['id']}", timeout=15).decode("utf-8", "ignore")
        m = re.search(r'<h2[^>]*class="[^"]*subtitle[^"]*"[^>]*>\s*(.*?)\s*</h2>', page, re.S)
        if m:
            info["subtitle"] = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
    except Exception:
        pass
    return info


def appstore_competitors(info, n):
    if not info.get("genre_id"):
        return []
    url = f"https://itunes.apple.com/{info['country']}/rss/topfreeapplications/limit={n + 5}/genre={info['genre_id']}/json"
    try:
        feed = json.loads(get(url)).get("feed", {})
    except Blocked:
        return []
    out = []
    for e in feed.get("entry", []) if isinstance(feed.get("entry"), list) else [feed.get("entry")] if feed.get("entry") else []:
        app_id = e["id"]["attributes"]["im:id"]
        if app_id != info["id"]:
            out.append({"name": e["im:name"]["label"], "id": app_id, "seller": e.get("im:artist", {}).get("label")})
    return out[:n]


def appstore_search(info, term, n):
    """Apps that match a keyword in the same store - usually closer competitors than the top chart."""
    url = (f"https://itunes.apple.com/search?term={urllib.parse.quote(term)}&entity=software"
           f"&country={info['country']}&limit={n + 3}")
    try:
        res = json.loads(get(url)).get("results", [])
    except Exception as e:
        print(f"! keyword search failed ({e}); skipped", file=sys.stderr)
        return []
    out = [{"name": r["trackName"], "id": str(r["trackId"]), "seller": r.get("sellerName"),
            "rating": r.get("averageUserRating"), "rating_count": r.get("userRatingCount")}
           for r in res if str(r.get("trackId")) != info["id"]]
    return out[:n]


def appstore_shot_url(u, width=1290):
    return re.sub(r"/[^/]+$", f"/{width}x0w.png", u)


# ---------------------------------------------------------------- Google Play

def parse_play_url(u):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(u).query)
    if "play.google.com" not in u or "id" not in q:
        return None
    return {"store": "play", "id": q["id"][0], "country": (q.get("gl", ["us"])[0]).lower(), "hl": q.get("hl", ["en"])[0]}


def fetch_play(ref):
    url = f"https://play.google.com/store/apps/details?id={ref['id']}&hl={ref['hl']}&gl={ref['country'].upper()}"
    page = get(url).decode("utf-8", "ignore")
    info = {"store": "play", "country": ref["country"], "id": ref["id"], "url": url, "name": None, "subtitle": None,
            "seller": None, "category": None, "description": "", "release_notes": "", "version": None, "updated": None,
            "rating": None, "rating_count": None, "languages": [ref["hl"]], "icon_url": None, "screenshots": [],
            "parse_note": "Google Play page parsed best-effort; check fields against the page."}
    for blob in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S):
        try:
            ld = json.loads(blob)
        except ValueError:
            continue
        if isinstance(ld, dict) and ld.get("@type") in ("SoftwareApplication", "MobileApplication"):
            info["name"] = ld.get("name")
            info["category"] = ld.get("applicationCategory")
            info["seller"] = (ld.get("author") or {}).get("name")
            info["icon_url"] = ld.get("image")
            ar = ld.get("aggregateRating") or {}
            info["rating"] = float(ar["ratingValue"]) if ar.get("ratingValue") else None
            info["rating_count"] = int(ar["ratingCount"]) if ar.get("ratingCount") else None
            info["description"] = ld.get("description") or ""
    m = re.search(r'data-g-id="description"[^>]*>(.*?)</div>', page, re.S)
    if m:
        info["description"] = html.unescape(re.sub(r"<br\s*/?>", "\n", m.group(1)))
        info["description"] = re.sub(r"<[^>]+>", "", info["description"]).strip()
    if not info["name"]:
        m = re.search(r'<meta property="og:title" content="([^"]+)"', page)
        info["name"] = html.unescape(m.group(1)).split(" - ")[0] if m else ref["id"]
    m = re.search(r'itemprop="description"[^>]*>(.*?)</div>', page, re.S)  # "What's new"
    if m and not info["release_notes"]:
        info["release_notes"] = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()[:1500]
    shots = []
    for tag in re.findall(r"<img[^>]+>", page):
        src = re.search(r'src="(https://play-lh\.googleusercontent\.com/[^"]+)"', tag)
        if not src:
            continue
        if "data-screenshot-index" in tag or re.search(r'alt="[^"]*(Screenshot|Ekran görüntüsü)', tag, re.I):
            u = re.sub(r"=w\d+-h\d+.*$|=s\d+.*$|=h\d+.*$", "", html.unescape(src.group(1)))
            if u not in shots:
                shots.append(u)
    info["screenshots"] = [u + "=w1440-h2560" for u in shots]
    return info


# ---------------------------------------------------------------- output

def save_images(info, folder, max_shots):
    os.makedirs(os.path.join(folder, "screenshots"), exist_ok=True)
    files = []
    urls = info["screenshots"][:max_shots]
    for i, u in enumerate(urls, start=1):
        src = appstore_shot_url(u) if info["store"] == "appstore" else u
        dest = os.path.join(folder, "screenshots", f"{i:02d}.png")
        try:
            blob = get(src)
        except Exception:
            blob = get(u)
        with open(dest, "wb") as f:
            f.write(blob)
        files.append(dest)
    if info.get("icon_url"):
        try:
            with open(os.path.join(folder, "icon.png"), "wb") as f:
                f.write(get(info["icon_url"]))
        except Exception:
            pass
    return files


def icon_colours(folder):
    try:
        from PIL import Image
    except ImportError:
        return []
    p = os.path.join(folder, "icon.png")
    if not os.path.exists(p):
        return []
    im = Image.open(p).convert("RGB").resize((64, 64))
    q = im.quantize(colors=5, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[:15]
    return ["#%02X%02X%02X" % tuple(pal[i * 3:i * 3 + 3]) for _, i in sorted(q.getcolors(), reverse=True)]


def current_headlines(files):
    """OCR the caption of each current screenshot (best effort, needs tesseract + Pillow)."""
    import shutil
    if not shutil.which("tesseract"):
        return []
    try:
        import importlib.util
        import tempfile
        from PIL import Image
        spec = importlib.util.spec_from_file_location("bc", os.path.join(HERE, "build_catalog.py"))
        bc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bc)
        out = []
        with tempfile.TemporaryDirectory() as tmp:
            for f in files:
                text, pos, _, _ = bc.headline_from(Image.open(f).convert("L"), tmp)
                out.append((os.path.basename(f), text, pos))
        return out
    except Exception:
        return []


def sheet(files, folder):
    try:
        sys.path.insert(0, HERE)
        from make_sheet import build
        build([("current store screenshots", files)], "Current listing", os.path.join(folder, "current.jpg"), width=220)
        return True
    except Exception:
        return False


def sizes(files):
    try:
        from PIL import Image
        return sorted({Image.open(f).size for f in files})
    except Exception:
        return []


def write_md(info, folder, files, comps, heads, colours, similar=None, term=None):
    L = [f"# {info['name']}" + (f" - {info['subtitle']}" if info.get("subtitle") else ""), ""]
    L.append(f"- Store: {info['store']} ({info['country']}) · {info['url']}")
    L.append(f"- Seller: {info.get('seller')} · Category: {info.get('category')} · Price: {info.get('price') or '-'}")
    L.append(f"- Version {info.get('version') or '?'} · updated {info.get('updated') or '?'} · released {info.get('released') or '?'}")
    rc = info.get("rating_count")
    L.append(f"- Rating: {info.get('rating') or '-'} ({rc if rc is not None else '-'} ratings) · Languages: {', '.join(info.get('languages') or []) or '-'}")
    L.append(f"- Current screenshots: {len(files)} saved (iPhone sizes {sizes(files) or '?'})"
             + (f"; iPad screenshots: {len(info.get('ipad_screenshots') or [])}" if info["store"] == "appstore" else ""))
    if colours:
        L.append(f"- Icon colours (dominant first): {' '.join(colours)}")
    if info.get("parse_note"):
        L.append(f"- Note: {info['parse_note']}")
    if heads:
        L += ["", "## Current headlines (OCR - verify against current.jpg)", ""]
        L += [f"{i}. {t or '(no caption found)'}" for i, (_, t, _) in enumerate(heads, 1)]
    L += ["", "## Description", "", info.get("description") or "(empty)", ""]
    if info.get("release_notes"):
        L += ["## Release notes (latest version)", "", info["release_notes"], ""]
    if similar:
        L += [f"## Apps matching \"{term}\" (closest competitors - look at their screenshots)", ""]
        L += [f"- {c['name']} (id {c['id']}, {c.get('seller')}, ★ {c.get('rating') or '-'} / {c.get('rating_count') or 0})" for c in similar]
        L.append("")
    if comps:
        L += ["## Top free apps in the same category (what the chart looks like)", ""]
        L += [f"- {c['name']} (id {c['id']}{', ' + c['seller'] if c.get('seller') else ''})" for c in comps]
        L.append("")
    L += ["## Next (references/intake.md)", "",
          "1. Draft the brief from this file and confirm it with the user (plus: what changes in the upcoming version?).",
          "2. Critique the current set (references/critique.md) using current.jpg.",
          "3. Storyboard, then ask for the RAW app screens each shot needs. Never cut UI out of these marketing images.", ""]
    with open(os.path.join(folder, "listing.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("urls", nargs="*", help="App Store and/or Google Play URLs")
    p.add_argument("--out", default="listing")
    p.add_argument("--competitors", type=int, default=8, help="list top free apps in the same App Store category")
    p.add_argument("--search", help="also list apps matching this keyword (e.g. \"film dizi takip\"): closer competitors")
    p.add_argument("--max-shots", type=int, default=10)
    p.add_argument("--no-images", action="store_true")
    p.add_argument("--lookup-json", help="parse a saved iTunes lookup response instead of fetching (offline)")
    p.add_argument("--country", default="us", help="country for --lookup-json")
    a = p.parse_args()

    jobs = []
    if a.lookup_json:
        with open(a.lookup_json, encoding="utf-8") as f:
            jobs.append(("offline", appstore_from_lookup(json.load(f)["results"][0], a.country)))
    for u in a.urls:
        ref = parse_appstore_url(u) or parse_play_url(u)
        if not ref:
            sys.exit(f"not an App Store or Google Play URL: {u}")
        jobs.append(("fetch", ref))
    if not jobs:
        p.error("give at least one store URL (or --lookup-json)")

    status = 0
    for kind, item in jobs:
        try:
            if kind == "offline":
                info, comps, similar, files = item, [], [], []
            else:
                info = fetch_appstore(item) if item["store"] == "appstore" else fetch_play(item)
                comps = appstore_competitors(info, a.competitors) if info["store"] == "appstore" and a.competitors else []
                similar = appstore_search(info, a.search, a.competitors or 8) if info["store"] == "appstore" and a.search else []
                files = []
            folder = os.path.join(a.out, f"{info['store']}-{info['country']}-{slug(info['name'] or info['id'])}")
            os.makedirs(folder, exist_ok=True)
            if kind == "fetch" and not a.no_images:
                files = save_images(info, folder, a.max_shots)
            with open(os.path.join(folder, "listing.json"), "w", encoding="utf-8") as f:
                json.dump(dict(info, competitors=comps, similar=similar), f, ensure_ascii=False, indent=1)
            heads = current_headlines(files) if files else []
            if files:
                sheet(files, folder)
            write_md(info, folder, files, comps, heads, icon_colours(folder), similar, a.search)
            print(f"{info['store']}: {info['name']} → {folder}  ({len(files)} screenshots, {len(comps)} competitors)")
        except Blocked as e:
            status = 2
            print(f"NETWORK BLOCKED: {e}\n  → use a web-fetch tool on the listing page, or ask the user to paste the "
                  f"name, subtitle, description and release notes, and to attach the current screenshots "
                  f"(references/intake.md §3).", file=sys.stderr)
    sys.exit(status)


if __name__ == "__main__":
    main()
