#!/usr/bin/env python3
"""Peer test: your set next to exemplary sets from the same category, at the same size. Requires Pillow.

  python3 peer_test.py out/ios --category navigation -o peer.jpg
  python3 peer_test.py out/ios --category weather --country tr --n 3 --shots 4
  python3 peer_test.py out/ios --apps "Waze" "Flo" -o peer.jpg

Looks only at library images that are on disk (lite ships every shot of every exemplary app).
"""
import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_sheet import build  # noqa: E402

LIB = os.path.normpath(os.path.join(HERE, "..", "assets", "library"))

# where to look when a category has too few exemplary sets
RELATED = {
    "entertainment": ["music", "photo-video", "books", "social-networking", "lifestyle"],
    "games": ["entertainment", "food-drink", "lifestyle"],
    "developer-tools": ["productivity", "utilities", "business"],
    "graphics-design": ["photo-video", "productivity", "lifestyle"],
    "medical": ["health-fitness", "weather", "finance"],
    "reference": ["books", "education", "news"],
    "sports": ["health-fitness", "news", "finance"],
    "utilities": ["productivity", "weather", "navigation"],
    "business": ["productivity", "finance", "news"],
    "navigation": ["travel", "weather"],
    "travel": ["navigation", "food-drink", "lifestyle"],
    "magazines-newspapers": ["news", "books"],
    "news": ["magazines-newspapers", "books"],
    "education": ["books", "productivity"],
    "shopping": ["food-drink", "lifestyle", "finance"],
    "food-drink": ["shopping", "lifestyle"],
    "social-networking": ["lifestyle", "photo-video", "news"],
    "photo-video": ["social-networking", "music", "graphics-design"],
    "music": ["entertainment", "photo-video", "books"],
    "books": ["magazines-newspapers", "education", "music"],
    "finance": ["shopping", "business"],
    "health-fitness": ["medical", "lifestyle", "sports"],
    "lifestyle": ["social-networking", "shopping", "health-fitness"],
    "productivity": ["utilities", "business", "education"],
    "weather": ["navigation", "utilities"],
}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("folder", help="your screenshots (PNG/JPG)")
    p.add_argument("--category")
    p.add_argument("--country", choices=["tr", "us"])
    p.add_argument("--apps", nargs="+", help="pick reference apps by name instead")
    p.add_argument("--n", type=int, default=3, help="number of reference sets")
    p.add_argument("--shots", type=int, default=4, help="shots per row")
    p.add_argument("-o", "--output", default="peer.jpg")
    a = p.parse_args()

    with open(os.path.join(LIB, "catalog.json"), encoding="utf-8") as f:
        cat = json.load(f)
    on_disk = [r for r in cat if os.path.exists(os.path.join(LIB, r["image"]))]
    by_app = {}
    for r in on_disk:
        by_app.setdefault((r["country"], r["app_id"]), []).append(r)

    def ok(key):
        rows = by_app[key]
        return len(rows) >= min(3, a.shots)

    if a.apps:
        keys = [k for k in by_app if any(n.lower() in by_app[k][0]["app"].lower() for n in a.apps) and ok(k)]
    else:
        keys = [k for k in by_app if by_app[k][0]["exemplary"] and ok(k)]
        if a.category:
            same = [k for k in keys if by_app[k][0]["category"] == a.category]
            if a.country:
                same.sort(key=lambda k: k[0] != a.country)
            if len(same) < a.n:
                related = RELATED.get(a.category, [])
                print(f"# only {len(same)} exemplary sets on disk in '{a.category}'; adding related categories: "
                      f"{', '.join(related) or 'any'}", file=sys.stderr)
                for cat in related:
                    same += [k for k in keys if by_app[k][0]["category"] == cat and k not in same]
                same += [k for k in keys if k not in same]
            keys = same
    seen, picked = set(), []
    for k in keys:
        if k[1] in seen:
            continue
        seen.add(k[1])
        picked.append(k)
        if len(picked) >= a.n:
            break
    if not picked:
        sys.exit("no reference sets found on disk")

    mine = sorted(f for f in glob.glob(os.path.join(a.folder, "*")) if re.search(r"\.(png|jpe?g|webp)$", f, re.I)
                  and not os.path.basename(f).startswith("_"))[: a.shots]
    rows = [("YOURS", mine)]
    for k in picked:
        rs = sorted(by_app[k], key=lambda r: r["position"])[: a.shots]
        r0 = rs[0]
        rows.append((f"{r0['app']} ({r0['country']}, {r0['category']}, {r0['quality']})",
                     [os.path.join(LIB, r["image"]) for r in rs]))
        print(f"ref: {r0['app']} - {r0['note']}")
        for r in rs:
            v = "" if r["headline_verified"] else " (ocr)"
            print(f"     #{r['position']} {r['headline'] or '(no headline)'}{v}")
    build(rows, "Peer test - same width, same order. Does yours look equally resolved?", a.output)
    print(a.output)


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):  # Windows consoles and pipes default to a legacy code page
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    main()
