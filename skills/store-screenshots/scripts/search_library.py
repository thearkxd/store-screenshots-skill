#!/usr/bin/env python3
"""Search the screenshot library (assets/library/catalog.json). Dependency-free.

Examples:
  search_library.py --list-values
  search_library.py --category navigation --summary
  search_library.py --category finance --country tr --position 1 --format headlines
  search_library.py --quality exemplary --technique stat-number --format headlines
  search_library.py --ai-smell --position 1
  search_library.py --app "Flo" --format paths
  search_library.py --quality exemplary --has-image --position 1 --format paths --limit 8

Filters combine with AND. Text matches are case-insensitive substrings.
"""
import argparse
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.normpath(os.path.join(HERE, "..", "assets", "library"))


def load():
    path = os.path.join(LIB, "catalog.json")
    if not os.path.exists(path):
        sys.exit(f"catalog not found: {path}")
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)
    for r in rows:
        r["has_image"] = os.path.exists(os.path.join(LIB, r["image"]))
        r["path"] = os.path.join(LIB, r["image"])
    return rows


def lower(x):
    return (x or "").lower()


def matches(r, a):
    if a.category and r["category"] not in a.category:
        return False
    if a.country and r["country"] not in a.country:
        return False
    if a.source and r.get("source", "chart") not in a.source:
        return False
    if a.quality and r["quality"] not in a.quality:
        return False
    if a.layout and r["layout"] not in a.layout:
        return False
    if a.first_shot and r["first_shot"] not in a.first_shot:
        return False
    if a.position and r["position"] not in a.position:
        return False
    if a.max_position and r["position"] > a.max_position:
        return False
    if a.technique and not all(t in (r["techniques"] or []) for t in a.technique):
        return False
    if a.ai_smell and not r["ai_smell"]:
        return False
    if a.no_ai_smell and r["ai_smell"]:
        return False
    if a.exemplary and not r["exemplary"]:
        return False
    if a.has_image and not r["has_image"]:
        return False
    if a.verified and not r["headline_verified"]:
        return False
    if a.has_headline and not r["headline"]:
        return False
    if a.language and r["language"] not in a.language:
        return False
    if a.background and r["background"] not in a.background:
        return False
    if a.dark and not r["dark"]:
        return False
    if a.app and lower(a.app) not in lower(r["app"]):
        return False
    if a.query:
        hay = " ".join([lower(r["headline"]), lower(r["note"]), lower(r["app"]), lower(r.get("shot_note"))])
        if lower(a.query) not in hay:
            return False
    return True


def summary(rows, label):
    apps = {}
    for r in rows:
        apps.setdefault((r["country"], r["app_id"]), r)
    uniq = {}
    for r in rows:
        uniq.setdefault(r["app_id"], r)
    first = [r for r in rows if r["position"] == 1]
    words = sorted(r["headline_words"] for r in rows if r["headline_words"])
    med = words[len(words) // 2] if words else 0
    out = [f"## {label}: {len(rows)} screenshots, {len(uniq)} apps"]
    out.append("quality (apps): " + ", ".join(f"{k} {v}" for k, v in Counter(r["quality"] for r in uniq.values()).most_common()))
    out.append("ai_smell apps: " + str(sum(1 for r in uniq.values() if r["ai_smell"])))
    out.append("layout (shots): " + ", ".join(f"{k} {v}" for k, v in Counter(r["layout"] for r in rows).most_common()))
    out.append("first shot type: " + ", ".join(f"{k} {v}" for k, v in Counter(r["first_shot"] for r in uniq.values()).most_common()))
    out.append("background: " + ", ".join(f"{k} {v}" for k, v in Counter(r["background"] for r in rows).most_common()))
    out.append(f"dark shots: {sum(r['dark'] for r in rows)} / {len(rows)}   headline median words (OCR): {med}")
    out.append("headline language: " + ", ".join(f"{k} {v}" for k, v in Counter(r["language"] or "-" for r in rows).most_common()))
    tech = Counter(t for r in uniq.values() for t in (r["techniques"] or []))
    out.append("techniques (apps): " + ", ".join(f"{k} {v}" for k, v in tech.most_common(18)))
    out.append("\napps:")
    for r in sorted(uniq.values(), key=lambda x: ({"exemplary": 0, "solid": 1, "weak": 2}.get(x["quality"], 3), x["app"])):
        flag = " [ai-smell]" if r["ai_smell"] else ""
        out.append(f"  {r['quality']:9} {r['app'][:34]:34} {r['layout']:16}{flag}  {r['note'][:150]}")
    out.append("\nfirst-shot headlines:")
    for r in sorted(first, key=lambda x: (x["quality"] != "exemplary", x["app"])):
        v = "" if r["headline_verified"] else " (ocr)"
        out.append(f"  [{r['country']}] {r['app'][:28]:28} {r['quality']:9} \"{r['headline'][:90]}\"{v}")
    return "\n".join(out)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--category", nargs="+")
    p.add_argument("--country", nargs="+", choices=["tr", "us"])
    p.add_argument("--source", nargs="+", choices=["chart", "challenger", "curated"],
                   help="chart = top-4 of the category chart; challenger = well-rated small/mid-size apps")
    p.add_argument("--quality", nargs="+", choices=["exemplary", "solid", "weak"])
    p.add_argument("--layout", nargs="+")
    p.add_argument("--first-shot", nargs="+")
    p.add_argument("--technique", nargs="+", help="all given techniques must be present")
    p.add_argument("--position", nargs="+", type=int, help="screenshot position(s) in the set, 1 = first")
    p.add_argument("--max-position", type=int)
    p.add_argument("--ai-smell", action="store_true")
    p.add_argument("--no-ai-smell", action="store_true")
    p.add_argument("--exemplary", action="store_true")
    p.add_argument("--has-image", action="store_true", help="only records whose image is on disk")
    p.add_argument("--verified", action="store_true", help="only human-verified headlines")
    p.add_argument("--has-headline", action="store_true")
    p.add_argument("--language", nargs="+", choices=["tr", "en"])
    p.add_argument("--background", nargs="+", choices=["flat", "flat-top", "gradient", "image"])
    p.add_argument("--dark", action="store_true")
    p.add_argument("--app", help="substring of the app name")
    p.add_argument("--query", help="substring of headline, note or app name")
    p.add_argument("--summary", action="store_true", help="conventions of the matching set")
    p.add_argument("--format", default="table", choices=["table", "headlines", "paths", "json", "apps"])
    p.add_argument("--limit", type=int, default=60)
    p.add_argument("--list-values", action="store_true")
    a = p.parse_args()

    rows = load()
    if a.list_values:
        for key in ("category", "country", "source", "layout", "first_shot", "quality", "background"):
            print(f"{key}: " + ", ".join(f"{k} ({v})" for k, v in sorted(Counter(r.get(key) for r in rows).items(), key=lambda kv: str(kv[0]))))
        tech = Counter(t for r in {x["app_id"]: x for x in rows}.values() for t in (r["techniques"] or []))
        print("technique (apps): " + ", ".join(f"{k} ({v})" for k, v in sorted(tech.items())))
        print(f"images on disk: {sum(r['has_image'] for r in rows)} / {len(rows)} records")
        return

    hits = [r for r in rows if matches(r, a)]
    hits.sort(key=lambda r: ({"exemplary": 0, "solid": 1, "weak": 2}.get(r["quality"], 3), r["category"], r["app"], r["country"], r["position"]))
    if a.summary:
        label = " / ".join(filter(None, [",".join(a.category or []), ",".join(a.country or []), ",".join(a.quality or [])])) or "all"
        print(summary(hits, label))
        return

    # de-duplicate identical images (same app in both stores) unless the user filtered by country
    if not a.country:
        seen, uniq = set(), []
        for r in hits:
            if r["image_id"] not in seen:
                seen.add(r["image_id"])
                uniq.append(r)
        hits = uniq
    total = len(hits)
    hits = hits[: a.limit]
    if a.format == "json":
        print(json.dumps(hits, ensure_ascii=False, indent=1))
    elif a.format == "paths":
        missing = 0
        for r in hits:
            if r["has_image"]:
                print(r["path"])
            else:
                missing += 1
        if missing:
            print(f"# {missing} matching records have no image in this package (lite); add --has-image", file=sys.stderr)
    elif a.format == "headlines":
        for r in hits:
            v = "" if r["headline_verified"] else " (ocr)"
            if r["headline"]:
                print(f"[{r['quality'][:3]}] {r['app'][:26]:26} #{r['position']}  {r['headline']}{v}")
    elif a.format == "apps":
        seen = set()
        for r in hits:
            if r["app_id"] in seen:
                continue
            seen.add(r["app_id"])
            flag = " [ai-smell]" if r["ai_smell"] else ""
            print(f"{r['quality']:9} {r['app'][:34]:34} {r['category']:20} {','.join(r['techniques'][:6])}{flag}\n          {r['note']}")
    else:
        print(f"{'q':4} {'cc':2} {'category':20} {'app':26} {'#':>2} {'img':3} headline")
        for r in hits:
            v = "" if r["headline_verified"] else "~"
            print(f"{r['quality'][:3]:4} {r['country']:2} {r['category'][:20]:20} {r['app'][:26]:26} {r['position']:>2} "
                  f"{'img' if r['has_image'] else '   '} {v}{r['headline'][:70]}")
    if total > len(hits):
        print(f"# {total - len(hits)} more; raise --limit", file=sys.stderr)


if __name__ == "__main__":
    main()
