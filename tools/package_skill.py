#!/usr/bin/env python3
"""Build the release zips from skills/store-screenshots.

  python3 tools/package_skill.py            # -> dist/store-screenshots.zip and dist/store-screenshots-lite.zip

full : everything (all library images at 480 px, auto.json) - Claude Code, Codex, Cursor, Gemini CLI, GitHub
lite : text catalog + the images listed in classifications.json["lite"], re-encoded at LITE_WIDTH px so the
       unpacked skill stays under LITE_LIMIT_MB (claude.ai / ChatGPT uploads). Needs Pillow for the re-encode;
       without it the images are copied as-is and the size check may fail.
Each zip contains a single top-level folder `store-screenshots/`, which is what the uploaders expect.
"""
import io
import json
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "skills", "store-screenshots")
DIST = os.path.join(ROOT, "dist")
LITE_LIMIT_MB = 20
LITE_WIDTH, LITE_QUALITY = 420, 66
SKIP_DIRS = {"__pycache__", ".git"}
SKIP_FILES = {".DS_Store"}


def walk():
    for base, dirs, files in os.walk(SKILL):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in sorted(files):
            if f in SKIP_FILES or f.endswith(".pyc"):
                continue
            full = os.path.join(base, f)
            yield full, os.path.relpath(full, SKILL).replace(os.sep, "/")


def shrink(path):
    try:
        from PIL import Image
    except ImportError:
        return None
    im = Image.open(path)
    if im.width > LITE_WIDTH:
        im = im.resize((LITE_WIDTH, round(im.height * LITE_WIDTH / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=LITE_QUALITY, method=6)
    return buf.getvalue()


def build(name, keep, transform=None):
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, name)
    n = raw = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for full, rel in walk():
            if not keep(rel):
                continue
            data = transform(rel, full) if transform else None
            if data is None:
                z.write(full, "store-screenshots/" + rel)
                raw += os.path.getsize(full)
            else:
                z.writestr("store-screenshots/" + rel, data)
                raw += len(data)
            n += 1
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

    def lite_transform(rel, full):
        return shrink(full) if rel.startswith("assets/library/img/") else None

    mb = build("store-screenshots-lite.zip", lite, lite_transform)
    if mb > LITE_LIMIT_MB:
        sys.exit(f"lite package is {mb:.1f} MB > {LITE_LIMIT_MB} MB")


if __name__ == "__main__":
    main()
