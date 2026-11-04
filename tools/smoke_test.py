#!/usr/bin/env python3
"""Smoke test for CI and local use: every script runs and the example set renders and passes checks.

  python3 tools/smoke_test.py            # exits non-zero on the first failure
"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "skills", "store-screenshots")
SCRIPTS = os.path.join(SKILL, "scripts")
PY = sys.executable


def run(*args, expect=0):
    cmd = [PY, "-I", *args]
    print("$", " ".join(os.path.relpath(a, ROOT) if os.path.isabs(a) else a for a in cmd[2:]), flush=True)
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != expect:
        print(p.stdout[-3000:], p.stderr[-3000:], sep="\n")
        sys.exit(f"FAILED (exit {p.returncode}, expected {expect})")
    return p.stdout


def s(name):
    return os.path.join(SCRIPTS, name)


def main():
    for name in sorted(os.listdir(SCRIPTS)):
        if name.endswith(".py"):
            run(s(name), "--help")
    out = run(s("build_catalog.py"), "check")
    assert "apps without classification: 0" in out, out
    run(s("search_library.py"), "--list-values")
    out = run(s("search_library.py"), "--category", "weather", "--summary")
    assert "weather" in out
    out = run(s("search_library.py"), "--quality", "exemplary", "--verified", "--position", "1", "--format", "headlines")
    assert out.strip(), "no verified exemplary headlines"
    with tempfile.TemporaryDirectory() as tmp:
        # listing intake, offline: parse a saved iTunes lookup response
        run(s("fetch_listing.py"), "--lookup-json", os.path.join(ROOT, "tools", "fixtures", "appstore-lookup-seenfy.json"),
            "--country", "tr", "--out", os.path.join(tmp, "listing"))
        md = open(os.path.join(tmp, "listing", "appstore-tr-seenfy-ne-izlesem-film-dizi", "listing.md"), encoding="utf-8").read()
        assert "Seenfy" in md and "## Description" in md, md[:500]
        run(s("fetch_listing.py"), "not-a-store-url", expect=1)
        run(s("render_set.py"), os.path.join(SKILL, "templates", "set.example.json"), "--out", tmp)
        for preset, store in (("ios", "ios"), ("android", "android")):
            folder = os.path.join(tmp, preset)
            assert len([f for f in os.listdir(folder) if f.endswith(".png")]) == 6, f"{preset}: expected 6 PNGs"
            run(s("check_set.py"), folder, "--store", store)
            assert os.path.exists(os.path.join(folder, "_search-preview.jpg"))
        run(s("peer_test.py"), os.path.join(tmp, "ios"), "--category", "navigation", "-o", os.path.join(tmp, "peer.jpg"))
        run(s("make_sheet.py"), "--rows", os.path.join(tmp, "ios"), "-o", os.path.join(tmp, "sheet.jpg"))
        # multi-locale spec with a feature graphic (the real Seenfy example)
        ex = os.path.join(tmp, "seenfy")
        run(s("render_set.py"), os.path.join(ROOT, "examples", "seenfy", "set.json"), "--out", ex, "--size", "android")
        for loc in ("tr", "en"):
            assert len([f for f in os.listdir(os.path.join(ex, loc, "android")) if f.endswith(".png")]) == 6, loc
            from PIL import Image
            assert Image.open(os.path.join(ex, loc, "feature-graphic.png")).size == (1024, 500)
            out = run(s("check_set.py"), os.path.join(ex, loc, "android"), "--store", "android")
            assert "Google Play disallows" not in out, out  # "Popüler olanı değil" / "Not what's popular" are negated
        # screen preparation and crop helpers
        prep = os.path.join(tmp, "prep")
        run(s("prepare_screens.py"), os.path.join(ROOT, "examples", "seenfy", "screens"), "--out", prep, "--status-bar", "9:41",
            "--cover", "05-anasayfa.png:0.626,0.086,0.878,0.13")
        assert os.path.exists(os.path.join(prep, "report.json"))
        run(s("crop_helper.py"), "grid", os.path.join(prep, "01-kesfet.png"))
        run(s("crop_helper.py"), "check", os.path.join(ROOT, "examples", "seenfy", "set.json"), "-o", os.path.join(tmp, "crops.jpg"))
        run(s("search_library.py"), "--source", "challenger", "--quality", "exemplary", "--format", "apps")
        # design directions: every preset renders the demo set, no missing glyphs, concept sheet for a category
        out = run(s("concepts.py"), "--list")
        names = sorted(f[:-5] for f in os.listdir(os.path.join(SKILL, "assets", "directions")) if f.endswith(".json"))
        assert len(names) >= 7 and all(n in out for n in names), out
        out = run(s("concepts.py"), os.path.join(SKILL, "templates", "set.example.json"), "--directions", *names,
                  "--shots", "1", "2", "-o", os.path.join(tmp, "concepts-all.jpg"))
        assert "lacks glyphs" not in out, out
        out = run(s("concepts.py"), os.path.join(ROOT, "examples", "seenfy", "set.json"), "--locale", "tr",
                  "-o", os.path.join(tmp, "concepts.jpg"))
        assert "cinematic" in out and "lacks glyphs" not in out, out
        assert os.path.getsize(os.path.join(tmp, "concepts.jpg")) > 20000
        # every bundled font covers Turkish
        sys.path.insert(0, SCRIPTS)
        import render_set
        for alias, (fname, _) in render_set.FONT_ALIASES.items():
            cmap = render_set.font_cmap(os.path.join(SKILL, "assets", "fonts", fname))
            if cmap is not None:
                miss = [ch for ch in "İıŞşĞğÜüÖöÇç" if ord(ch) not in cmap]
                assert not miss, f"{alias} ({fname}) lacks {''.join(miss)}"
        # copy checks must catch an obviously bad headline
        out = run(s("check_set.py"), os.path.join(tmp, "android"), "--store", "android", "--lang", "tr",
                  "--headlines", "Kusursuz Dizi Deneyimi", "#1 dizi uygulaması!", "a", "b", "c")
        assert "kusursuz" in out and "Google Play" in out, out
    print("smoke test passed")


if __name__ == "__main__":
    main()
