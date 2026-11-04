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
        # copy checks must catch an obviously bad headline
        out = run(s("check_set.py"), os.path.join(tmp, "android"), "--store", "android", "--lang", "tr",
                  "--headlines", "Kusursuz Dizi Deneyimi", "#1 dizi uygulaması!", "a", "b", "c")
        assert "kusursuz" in out and "Google Play" in out, out
    print("smoke test passed")


if __name__ == "__main__":
    main()
