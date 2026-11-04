#!/usr/bin/env python3
"""Maintainers: pick well-made small/mid-size apps per category - the "challengers" - for the library.

Top charts are dominated by giants who can rely on their brand. Challengers are closer to what most users of
this skill are building. Selection per App Store category (top 100 free, one country):
  - not already in the library, not from a giant seller (Google, Meta, Apple, Microsoft, Amazon, ...)
  - chart rank 15-100, average rating >= --min-rating, ratings between --min-count and --max-count
  - at least 4 iPhone screenshots
  - best rating x log(count) first

  python3 find_challengers.py --country us --per-category 2 > challengers.json
  python3 collect_examples.py --countries us --app-ids $(jq -r '.[].id' challengers.json) --label challengers --out raw/
"""
import argparse
import json
import math
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from collect_examples import CATEGORIES  # noqa: E402

GIANTS = ("google", "meta platforms", "facebook", "apple", "microsoft", "amazon", "bytedance", "tiktok", "netflix",
          "spotify", "snap", "x corp", "twitter", "uber", "openai", "anthropic", "adobe", "disney", "warner",
          "pinterest", "linkedin", "paypal", "yahoo", "zoom", "whatsapp", "telegram", "samsung", "tencent")


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "store-screenshots-skill/1.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read())


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--country", default="us")
    p.add_argument("--per-category", type=int, default=2)
    p.add_argument("--min-rating", type=float, default=4.6)
    p.add_argument("--min-count", type=int, default=800)
    p.add_argument("--max-count", type=int, default=400000)
    p.add_argument("--catalog", default=os.path.join(HERE, "..", "assets", "library", "catalog.json"))
    a = p.parse_args()
    known = set()
    if os.path.exists(a.catalog):
        known = {r["app_id"] for r in json.load(open(a.catalog, encoding="utf-8"))}
    picked = []
    for cat, meta in CATEGORIES.items():
        ids = []
        for g in meta["genres"]:
            feed = get_json(f"https://itunes.apple.com/{a.country}/rss/topfreeapplications/limit=100/genre={g}/json").get("feed", {})
            entries = feed.get("entry", [])
            ids += [(rank, e["id"]["attributes"]["im:id"]) for rank, e in enumerate(entries, 1)]
        ids = [(r, i) for r, i in ids if r >= 15 and int(i) not in known]
        if not ids:
            continue
        rank_of = {i: r for r, i in ids}
        res = []
        for k in range(0, len(ids), 50):
            chunk = ",".join(i for _, i in ids[k:k + 50])
            res += get_json(f"https://itunes.apple.com/lookup?id={chunk}&country={a.country}").get("results", [])
        cands = []
        for r in res:
            seller = (r.get("sellerName") or "").lower()
            cnt, rating = r.get("userRatingCount") or 0, r.get("averageUserRating") or 0
            if any(g in seller for g in GIANTS) or len(r.get("screenshotUrls") or []) < 4:
                continue
            if rating < a.min_rating or not (a.min_count <= cnt <= a.max_count):
                continue
            cands.append((rating * math.log10(cnt), r))
        cands.sort(key=lambda x: -x[0])
        for score, r in cands[: a.per_category]:
            picked.append({"category": cat, "id": str(r["trackId"]), "name": r["trackName"], "seller": r.get("sellerName"),
                           "rating": round(r.get("averageUserRating") or 0, 2), "rating_count": r.get("userRatingCount"),
                           "chart_rank": rank_of.get(str(r["trackId"]))})
        print(f"{cat:22} {len(cands):3} candidates → " + ", ".join(x["name"][:28] for x in picked if x["category"] == cat), file=sys.stderr)
    print(json.dumps(picked, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
