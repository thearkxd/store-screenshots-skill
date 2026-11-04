#!/usr/bin/env python3
"""Compare a fresh chart collection with the library: what's new, what dropped out, whose screenshots changed.

  python3 tools/library_diff.py --raw raw/ --out refresh/       # writes refresh/report.md and refresh/new-apps.json

Used by .github/workflows/library-refresh.yml. Classification stays human-in-the-loop: the report lists the
apps to label in skills/store-screenshots/assets/library/classifications.json, then
`build_catalog.py extract --raw raw/` and `merge` add them.
"""
import argparse
import json
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, "skills", "store-screenshots", "assets", "library", "catalog.json")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--raw", required=True)
    p.add_argument("--out", default="refresh")
    a = p.parse_args()
    with open(CATALOG, encoding="utf-8") as f:
        lib = json.load(f)
    with open(os.path.join(a.raw, "manifest.json"), encoding="utf-8") as f:
        fresh = json.load(f)

    lib_chart = defaultdict(set)  # (country, category) -> app ids in the library chart slots
    lib_shots = defaultdict(set)  # app id -> source urls are not stored in catalog; use image ids via manifest
    names = {}
    for r in lib:
        if r.get("source", "chart") == "chart":
            lib_chart[(r["country"], r["category"])].add(r["app_id"])
        names[r["app_id"]] = r["app"]
        lib_shots[r["app_id"]].add(r["position"])
    known_ids = {r["app_id"] for r in lib}

    fresh_chart = defaultdict(set)
    fresh_info = {}
    fresh_shot_count = defaultdict(int)
    for r in fresh:
        fresh_chart[(r["country"], r["category"])].add(r["app_id"])
        fresh_info[r["app_id"]] = r
        fresh_shot_count[(r["country"], r["app_id"])] += 1

    new_apps, lines = [], []
    lines.append("# Library refresh report\n")
    for key in sorted(set(lib_chart) | set(fresh_chart)):
        added = fresh_chart[key] - lib_chart[key]
        dropped = lib_chart[key] - fresh_chart[key]
        if not added and not dropped:
            continue
        lines.append(f"## {key[0]} · {key[1]}")
        for i in sorted(added):
            r = fresh_info[i]
            status = "already in library (other slot)" if i in known_ids else "**new - needs classification**"
            lines.append(f"- + {r['app']} (id {i}, rank {r['chart_rank']}) - {status}")
            if i not in known_ids:
                new_apps.append({"app_id": i, "app": r["app"], "country": key[0], "category": key[1],
                                 "chart_rank": r["chart_rank"], "store_url": r.get("store_url")})
        for i in sorted(dropped):
            lines.append(f"- − {names.get(i, i)} (id {i}) left the top 4")
        lines.append("")
    if len(lines) == 1:
        lines.append("No chart changes since the last library build.")
    lines += ["", f"**{len(new_apps)} new apps** to classify. Steps:",
              "1. Download the `raw` artifact of this run (or run collect_examples.py locally).",
              "2. `python3 skills/store-screenshots/scripts/build_catalog.py extract --raw raw/`",
              "3. Add one object per new app to `classifications.json` → `apps` (see library-guide.md §7),",
              "   optionally add new ids to `lite`.",
              "4. `build_catalog.py merge && build_catalog.py check`, commit, push - the release workflow ships it."]
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(a.out, "new-apps.json"), "w", encoding="utf-8") as f:
        json.dump(new_apps, f, ensure_ascii=False, indent=1)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
