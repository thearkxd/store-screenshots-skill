#!/usr/bin/env python3
"""Build the release zips from skills/store-screenshots.

  python3 tools/package_skill.py            # -> dist/store-screenshots.zip and dist/store-screenshots-lite.zip

full : everything (all library images, auto.json) - for Claude Code, Codex, Cursor, Gemini CLI, GitHub
lite : text catalog + only the images listed in classifications.json["lite"] - for claude.ai / ChatGPT uploads
       (fails if it grows past LITE_LIMIT_MB)
Each zip contains a single top-level folder `store-screenshots/`, which is what the uploaders expect.
"""
import json
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "skills", "store-screenshots")
DIST = os.path.join(ROOT, "dist")
LITE_LIMIT_MB = 20
SKIP_DIRS = {"__pycache__", ".git"}
SKIP_FILES = {".DS_Store"}


def walk():
    for base, dirs, files in os.walk(SKILL):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f in SKIP_FILES or f.endswith(".pyc"):
                continue
            full = os.path.join(base, f)
            yield full, os.path.relpath(full, SKILL).replace(os.sep, "/")


def build(name, keep):
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, name)
    n = raw = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for full, rel in walk():
            if keep(rel):
                z.write(full, "store-screenshots/" + rel)
                n += 1
                raw += os.path.getsize(full)
    mb = os.path.getsize(out) / 1e6
    print(f"{name}: {n} files, {mb:.1f} MB zipped, {raw / 1e6:.1f} MB unpacked")
    return max(mb, raw / 1e6)


def main():
    with open(os.path.join(SKILL, "assets", "library", "catalog.json"), encoding="utf-8") as f:
        catalog = json.load(f)
    lite_imgs = {r["image"] for r in catalog if r["in_lite"]}
    build("store-screenshots.zip", lambda rel: True)

    def lite(rel):
        if rel.startswith("assets/library/img/"):
            return rel[len("assets/library/"):] in lite_imgs
        return rel != "assets/library/auto.json"

    mb = build("store-screenshots-lite.zip", lite)
    if mb > LITE_LIMIT_MB:
        sys.exit(f"lite package is {mb:.1f} MB > {LITE_LIMIT_MB} MB")


if __name__ == "__main__":
    main()
