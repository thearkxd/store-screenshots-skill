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


def run(*args, expect=0, both=False):
    cmd = [PY, "-I", *args]
    print("$", " ".join(os.path.relpath(a, ROOT) if os.path.isabs(a) else a for a in cmd[2:]), flush=True)
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != expect:
        print(p.stdout[-3000:], p.stderr[-3000:], sep="\n")
        sys.exit(f"FAILED (exit {p.returncode}, expected {expect})")
    return p.stdout + p.stderr if both else p.stdout


def s(name):
    return os.path.join(SCRIPTS, name)


DEMO = os.path.join(SKILL, "templates", "example-screens")


def span_tests(tmp):
    """Span pairs (one picture over two slots) must never misalign, misnumber or slip past a rule."""
    import json
    from PIL import Image, ImageChops
    fx = os.path.join(ROOT, "tools", "fixtures", "span-set.json")
    out_dir = os.path.join(tmp, "span")
    run(s("render_set.py"), fx, "--out", out_dir)
    sizes = {"ios": (1206, 2622), "android": (1080, 1920)}
    for loc in ("tr", "en"):
        for preset, (W, H) in sizes.items():
            folder = os.path.join(out_dir, loc, preset)
            files = sorted(f for f in os.listdir(folder) if f.endswith(".png"))
            assert files == [f"{i:02d}.png" for i in range(1, 9)], (loc, preset, files)  # 6 entries, 2 spans = 8 slots
            for f in files:
                im = Image.open(os.path.join(folder, f))
                assert im.size == (W, H) and im.mode == "RGB", (loc, preset, f, im.size, im.mode)
            rep = json.load(open(os.path.join(folder, "_render.json"), encoding="utf-8"))
            assert [e.get("span") for e in rep["shots"]] == [None, "02-03", "02-03", None, None, "06-07", "06-07", None], rep["shots"]
            assert not rep["set_warnings"], rep["set_warnings"]
            out = run(s("check_set.py"), folder, "--store", "android" if preset == "android" else "ios")
            assert "ERROR" not in out, out
    # the halves re-join to exactly the one canvas they were cut from, and the files on disk are those halves
    sys.path.insert(0, SCRIPTS)
    import render_set as rs
    raw = json.load(open(fx, encoding="utf-8"))
    spec_dir = os.path.dirname(fx)
    fonts = rs.Fonts(spec_dir)
    for loc in ("tr", "en"):
        spec = rs.localize(raw, loc, raw["locales"])
        for preset in sizes:
            W, H, style, shots, _, _ = rs.prepare(spec, preset, spec_dir, fonts, loc)  # the pipeline render_set uses
            for shot in shots:
                if shot.get("span") != 2:
                    continue
                keep = {}
                halves, warns, _ = rs.render_span(shot, style, W, H, fonts, spec_dir, loc, keep=keep)
                assert not warns, (loc, preset, warns)
                if shot.get("screen"):  # bridge: the phone's screen is cut exactly in half by the seam
                    sx, sw = keep["device"][0], keep["device"][3]
                    assert W - sx == sx + sw - W, f"{loc} {preset}: phone not centred on the seam ({W - sx} vs {sx + sw - W} px)"
                joined = Image.new("RGB", (2 * W, H))
                joined.paste(halves[0], (0, 0))
                joined.paste(halves[1], (W, 0))
                assert ImageChops.difference(joined, keep["canvas"].convert("RGB")).getbbox() is None, "halves don't re-join"
                for j, half in enumerate(halves):
                    on_disk = Image.open(os.path.join(out_dir, loc, preset, f"{shot['_index'] + j + 1:02d}.png")).convert("RGB")
                    assert ImageChops.difference(on_disk, half.convert("RGB")).getbbox() is None, \
                        f"{loc} {preset} slot {shot['_index'] + j + 1}: file differs from a fresh render (not deterministic?)"
    # broken specs fail loudly, with a message that says what to do
    def spec_with(shots, name):
        path = os.path.join(tmp, f"span-{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"lang": "tr", "sizes": ["ios"], "shots": shots}, f)
        return path
    scr = lambda n: os.path.join(DEMO, n)  # noqa: E731
    one = {"headline": "Kaldığın bölüm *hep hazır*", "screen": scr("01-home.jpg")}
    bad = {
        "span3": ({"span": 3, "headline": "a b c", "screen": scr("01-home.jpg")}, '"span" must be 2'),
        "halves-no-span": ({"halves": [{"headline": "a"}, {"headline": "b"}]}, 'add "span": 2'),
        "two-screens": ({"span": 2, "screen": scr("02-calendar.jpg"), "halves": [{"headline": "a"}, {"headline": "b", "screen": scr("01-home.jpg")}]},
                        "use one or the other"),
        "pair-callouts": ({"span": 2, "callouts": [{"crop": [0, 0, 1, 0.2]}], "halves": [{"headline": "a", "screen": scr("01-home.jpg")}, {"headline": "b"}]},
                          "put it inside the half"),
        "bridge-bottom": ({"span": 2, "screen": scr("02-calendar.jpg"), "halves": [{"headline": "a", "caption_position": "bottom"}, {"headline": "b"}]},
                          "captions go at the top"),
        "three-halves": ({"span": 2, "halves": [{}, {}, {}]}, "at most two"),
        "no-screen": ({"headline": "a b c"}, 'needs a "screen"'),
    }
    for name, (shot, msg) in bad.items():
        out = run(s("render_set.py"), spec_with([one, shot], name), "--out", os.path.join(tmp, "bad", name), expect=1, both=True)
        assert msg in out, (name, out)
    # rule breaks render, but warn
    bridge = lambda x: {"span": 2, "screen": scr("02-calendar.jpg"), "device": {"x": x},  # noqa: E731
                        "halves": [{"headline": "Yeni bölüm çıkınca"}, {"headline": "Takvim kendini doldurur"}]}
    pair = {"span": 2, "halves": [{"headline": "Arkadaşların ne izliyor?", "screen": scr("04-friends.jpg")},
                                  {"headline": "Bölüm bölüm işaretle", "screen": scr("05-detail.jpg")}]}
    warn_cases = {
        "no-cross": ([one, bridge(0.5)], "doesn't cross the seam"),
        "sticker": ([one, dict(pair, stickers=[{"text": "%88 match", "x": 1.0, "y": 0.5}])], "crosses the seam"),
        "no-headline": ([one, dict(pair, halves=[pair["halves"][0], {"screen": scr("05-detail.jpg")}])], "half 2 has no headline"),
        "search-cut": ([one, one, pair, one], "cut in half in search results"),
        "too-many": ([pair, pair, pair, one], "span pairs - use one"),
        "two-in-short": ([pair, one, pair], "two only in sets of 8"),
    }
    for name, (shots, msg) in warn_cases.items():
        out = run(s("render_set.py"), spec_with(shots, name), "--out", os.path.join(tmp, "warn", name), both=True)
        assert msg in out, (name, out)
    # concept sheets and crop previews understand spans, in every direction
    names = sorted(f[:-5] for f in os.listdir(os.path.join(SKILL, "assets", "directions")) if f.endswith(".json"))
    out = run(s("concepts.py"), fx, "--directions", *names, "--shots", "1", "2", "5", "-o", os.path.join(tmp, "span-concepts.jpg"))
    assert "lacks glyphs" not in out and "crosses the seam" not in out, out
    sheet = Image.open(os.path.join(tmp, "span-concepts.jpg"))
    assert sheet.width > 5 * 260, sheet.size  # 3 entries -> 5 thumbnails per row
    run(s("crop_helper.py"), "check", fx, "-o", os.path.join(tmp, "span-crops.jpg"))


def size_tests(tmp):
    """Every store size renders exactly, per-size screens and "stores" are honoured, and the store rules warn."""
    import json
    from PIL import Image
    fx = os.path.join(ROOT, "tools", "fixtures", "duo-set.json")
    out_dir = os.path.join(tmp, "sizes")
    out = run(s("render_set.py"), fx, "--out", out_dir, both=True)
    assert "not an iPhone Duo screen" not in out and "x " not in out.split("\n")[0], out
    expect = {"ios": ((1206, 2622), 6, "ios"), "ios-large": ((1320, 2868), 6, "ios"), "duo-outer": ((1398, 2034), 6, "duo"),
              "duo-inner": ((2007, 2853), 6, "duo"), "android": ((1080, 1920), 5, "android")}  # 5: the poster is iOS-only
    for preset, (size, n, store) in expect.items():
        folder = os.path.join(out_dir, preset)
        files = sorted(f for f in os.listdir(folder) if f.endswith(".png"))
        assert len(files) == n, (preset, files)
        for f in files:
            im = Image.open(os.path.join(folder, f))
            assert im.size == size and im.mode == "RGB", (preset, f, im.size, im.mode)
        res = run(s("check_set.py"), folder, "--store", store)
        assert "ERROR" not in res and ("no 1206x2622" not in res) and ("no large iPhone" not in res), (preset, res)
        rep = json.load(open(os.path.join(folder, "_render.json"), encoding="utf-8"))
        assert not any("device frame" in w for e in rep["shots"] for w in e["warnings"]), (preset, rep)
    # a Duo set checked as iPhone fails; an iPhone set alone warns about the missing large size
    run(s("check_set.py"), os.path.join(out_dir, "duo-inner"), "--store", "ios", expect=1)
    alone = os.path.join(tmp, "alone", "ios")
    os.makedirs(alone)
    for f in os.listdir(os.path.join(out_dir, "ios")):
        if f.endswith(".png"):
            Image.open(os.path.join(out_dir, "ios", f)).save(os.path.join(alone, f))
    assert "no large iPhone set" in run(s("check_set.py"), alone, "--store", "ios")
    # phone screens in a Duo set: rendered to fit, with a warning
    out = run(s("render_set.py"), os.path.join(SKILL, "templates", "set.example.json"), "--out", os.path.join(tmp, "duo-phone"),
              "--size", "duo-inner", both=True)
    assert "not an iPhone Duo screen" in out, out
    im = Image.open(os.path.join(tmp, "duo-phone", "duo-inner", "01.png"))
    assert im.size == (2007, 2853)

    def spec_with(extra, name):
        d = json.load(open(os.path.join(SKILL, "templates", "set.example.json"), encoding="utf-8"))
        d.update(extra)
        d["shots"] = [dict(sh, screen=os.path.join(SKILL, "templates", sh["screen"])) if sh.get("screen") else sh for sh in d["shots"]]
        path = os.path.join(tmp, f"sizes-{name}.json")
        json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False)
        return path
    # iPhone size rules
    assert "no large iPhone size" in run(s("render_set.py"), spec_with({"sizes": ["ios", "android"]}, "one-ios"),
                                         "--out", os.path.join(tmp, "one-ios"), both=True)
    assert "no iPhone Dynamic Island medium" in run(s("render_set.py"), spec_with({"sizes": ["ios-large"]}, "large-only"),
                                                    "--out", os.path.join(tmp, "large-only"), both=True)
    # Google Play: a framed device, a poster without "stores" and a long caption all warn
    d = json.load(open(os.path.join(SKILL, "templates", "set.example.json"), encoding="utf-8"))
    shots = [dict(sh, screen=os.path.join(SKILL, "templates", sh["screen"])) if sh.get("screen") else sh for sh in d["shots"]]
    for sh in shots:
        sh.pop("stores", None)
    shots[0] = dict(shots[0], headline="Kaldığın bölüm\n*hep hazır*\nher akşam", max_lines=3, headline_size=0.12,
                    sub="Kaldığın yerden devam et, yeni bölümleri kaçırma, listeni arkadaşlarınla paylaş.")
    play = os.path.join(tmp, "play.json")
    json.dump(dict(d, sizes=["android"], shots=shots, style=dict(d.get("style", {}), device=dict(d["style"]["device"], android_style="android"))),
              open(play, "w", encoding="utf-8"), ensure_ascii=False)
    out = run(s("render_set.py"), play, "--out", os.path.join(tmp, "play"), both=True)
    for msg in ("device frame in a Google Play set", "type-only poster in a Google Play set", "Google Play recommends taglines"):
        assert msg in out, (msg, out)
    # Play copy rules
    out = run(s("check_set.py"), os.path.join(out_dir, "android"), "--store", "android", "--lang", "tr", "--headlines",
              "Hemen indir, şimdi dene", "“Harika bir uygulama” ★★★★★", "Yeni özellik: takvim", "1M+ downloads",
              "Yeni bölüm çıkınca ilk sen bil")
    assert out.count("call to action") == 1 and "user testimonial" in out, out
    assert '"Yeni özellik: takvim": Google Play disallows' in out and '"1M+ downloads": Google Play disallows' in out, out
    assert '05 "Yeni bölüm' not in out, out
    # concept sheets at other sizes
    run(s("concepts.py"), fx, "--size", "duo-inner", "--directions", "editorial", "cinematic", "-o", os.path.join(tmp, "duo-concepts.jpg"))
    run(s("concepts.py"), fx, "--size", "android", "--directions", "poster", "-o", os.path.join(tmp, "android-concepts.jpg"))


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
        for preset, store, n in (("ios", "ios", 6), ("ios-large", "ios", 6), ("android", "android", 5)):  # poster is iOS-only
            folder = os.path.join(tmp, preset)
            assert len([f for f in os.listdir(folder) if f.endswith(".png")]) == n, f"{preset}: expected {n} PNGs"
            run(s("check_set.py"), folder, "--store", store)
            assert os.path.exists(os.path.join(folder, "_search-preview.jpg"))
        run(s("peer_test.py"), os.path.join(tmp, "ios"), "--category", "navigation", "-o", os.path.join(tmp, "peer.jpg"))
        run(s("make_sheet.py"), "--rows", os.path.join(tmp, "ios"), "-o", os.path.join(tmp, "sheet.jpg"))
        # multi-locale spec with a feature graphic (the real Seenfy example)
        ex = os.path.join(tmp, "seenfy")
        run(s("render_set.py"), os.path.join(ROOT, "examples", "seenfy", "set.json"), "--out", ex, "--size", "android")
        for loc in ("tr", "en"):
            assert len([f for f in os.listdir(os.path.join(ex, loc, "android")) if f.endswith(".png")]) == 5, loc
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
        span_tests(tmp)
        size_tests(tmp)
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
