#!/usr/bin/env python3
"""Smoke test for CI and local use: every script runs and the example set renders and passes checks.

  python3 tools/smoke_test.py            # exits non-zero on the first failure
"""
import math
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
    assert '"Yeni özellik: takvim": [Play recommendation] ranking' in out and '"1M+ downloads": [Play recommendation] ranking' in out, out
    assert "[Play requirement]: the listing can be removed" in out, out  # the legend says what each label costs
    assert '05 "Yeni bölüm' not in out, out
    # concept sheets at other sizes
    run(s("concepts.py"), fx, "--size", "duo-inner", "--directions", "editorial", "cinematic", "-o", os.path.join(tmp, "duo-concepts.jpg"))
    run(s("concepts.py"), fx, "--size", "android", "--directions", "poster", "-o", os.path.join(tmp, "android-concepts.jpg"))


def design_tests(tmp):
    """The design route: evidence, DNA, scenes on both backends, every size, and the truth/claim/campaign/store
    checks - each warning is provoked once on purpose."""
    import json
    import shutil
    from PIL import Image, ImageChops, ImageStat
    sys.path.insert(0, SCRIPTS)
    import scene as sc
    tdir = os.path.join(SKILL, "templates")
    ex = os.path.join(tdir, "scene.example.json")
    ev_path = os.path.join(tdir, "scene-evidence.json")
    d = os.path.join(tmp, "design")
    os.makedirs(d)
    # evidence: ids, hashes, kept regions, named regions, the grid view
    ev = os.path.join(d, "ev.json")
    run(s("evidence.py"), "build", DEMO, "-o", ev, "--no-ocr")
    e = json.load(open(ev, encoding="utf-8"))
    assert sorted(e["screens"]) == ["calendar", "detail", "friends", "home", "stats"], e["screens"].keys()
    assert all(len(v["sha256"]) == 64 for v in e["screens"].values())
    run(s("evidence.py"), "name", ev, "home", "hero", "0.04,0.15,0.95,0.57")
    run(s("evidence.py"), "build", DEMO, "-o", ev, "--no-ocr")
    assert json.load(open(ev, encoding="utf-8"))["screens"]["home"]["regions"]["hero"] == [0.04, 0.15, 0.95, 0.57]
    run(s("evidence.py"), "name", ev, "home", "bad", "0.5,0.5,0.4,0.6", expect=1)
    run(s("evidence.py"), "show", ev, "home", "-o", os.path.join(d, "grid.png"))
    # --snap: a rough box around a card tightens to the card and keeps its corner radius
    run(s("evidence.py"), "name", ev, "friends", "post", "0.015,0.198,0.985,0.396", "--snap")
    fe = json.load(open(ev, encoding="utf-8"))["screens"]["friends"]
    assert all(abs(a - b) < 0.004 for a, b in zip(fe["regions"]["post"], [0.0448, 0.2105, 0.9552, 0.3902])), fe["regions"]["post"]
    assert fe["region_radius"]["post"] > 20, fe["region_radius"]
    shipped = json.load(open(ev_path, encoding="utf-8"))
    if shutil.which("tesseract"):
        assert "312" in shipped["screens"]["stats"]["region_text"]["total"], shipped["screens"]["stats"]["region_text"]
    # DNA: the demo app's orange accent and dark UI are found; font sheet and board render
    dna = os.path.join(d, "dna.json")
    run(s("dna.py"), "measure", ev, "--app", "Dizilog", "-o", dna)
    m = json.load(open(dna, encoding="utf-8"))["measured"]
    assert m["ui"] == "dark", m["ui"]
    acc = [c for c in m["palette"] if c["role"] == "accent"]
    assert acc and int(acc[0]["hex"][1:3], 16) > 200 and int(acc[0]["hex"][3:5], 16) < 140, m["palette"]
    run(s("dna.py"), "fonts", ev, "home", "--region", "0.05,0.035,0.8,0.06", "--text", "İyi akşamlar, Elif",
        "--candidates", "sans", "serif", "grotesk", "-o", os.path.join(d, "fonts.jpg"))
    run(s("dna.py"), "board", dna, "-o", os.path.join(d, "board.jpg"))
    # the bundled scene example: every size, PNG + SVG, feature graphic, clean report
    out_dir = os.path.join(d, "out")
    out = run(s("compose.py"), "render", ex, "--out", out_dir, both=True)
    assert "!" not in out.replace("!=", ""), out  # the example renders without a single warning
    for preset, store, size in (("ios", "ios", (1206, 2622)), ("ios-large", "ios", (1320, 2868)), ("android", "android", (1080, 1920))):
        folder = os.path.join(out_dir, preset)
        pngs = sorted(f for f in os.listdir(folder) if f.endswith(".png"))
        assert pngs == [f"{i:02d}.png" for i in range(1, 6)], pngs
        assert all(Image.open(os.path.join(folder, p)).size == size for p in pngs)
        assert len([f for f in os.listdir(folder) if f.endswith(".svg")]) == 5
        rep = json.load(open(os.path.join(folder, "_render.json"), encoding="utf-8"))
        assert rep["renderer"] == "compose" and not rep["set_warnings"], rep["set_warnings"]
        out = run(s("check_set.py"), folder, "--store", store, "--lang", "tr")
        assert "WARN" not in out and "ERROR" not in out, out
    assert Image.open(os.path.join(out_dir, "feature-graphic.png")).size == (1024, 500)
    svg = open(os.path.join(out_dir, "ios", "01.svg"), encoding="utf-8").read()
    assert 'data-evidence="home"' in svg and "<text" in svg and "font-family=" in svg
    # both backends draw the same picture
    if sc.have_resvg():
        pil_dir = os.path.join(d, "pil")
        run(s("compose.py"), "render", ex, "--out", pil_dir, "--size", "ios", "--backend", "pillow")
        for i in range(1, 6):
            a = Image.open(os.path.join(out_dir, "ios", f"{i:02d}.png")).convert("RGB")
            b = Image.open(os.path.join(pil_dir, "ios", f"{i:02d}.png")).convert("RGB")
            diff = sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3
            assert diff < 6, f"shot {i}: backends differ by {diff:.1f}"
    # a partial re-render keeps the numbering and the rest of the report
    run(s("compose.py"), "render", ex, "--out", out_dir, "--size", "ios", "--shots", "friends")
    rep = json.load(open(os.path.join(out_dir, "ios", "_render.json"), encoding="utf-8"))
    assert [e["shot"] for e in rep["shots"]] == ["resume", "tonight", "year", "friends", "episodes"], rep["shots"]
    run(s("compose.py"), "xray", ex, "--shot", "year", "-o", os.path.join(d, "xray.png"))
    run(s("compose.py"), "concepts", ex, ex, "--board", os.path.join(d, "board.jpg"), "-o", os.path.join(d, "concepts.jpg"))
    assert Image.open(os.path.join(d, "concepts.jpg")).width > 600
    # the Seenfy pilot (three concepts + the chosen set)
    v2 = os.path.join(ROOT, "examples", "seenfy-v2")
    run(s("compose.py"), "render", os.path.join(v2, "set.json"), "--out", os.path.join(d, "seenfy"), "--size", "android")
    run(s("compose.py"), "concepts", *[os.path.join(v2, "concepts", f) for f in sorted(os.listdir(os.path.join(v2, "concepts")))],
        "-o", os.path.join(d, "seenfy-concepts.jpg"))

    # --- in-process: anchors, kept line breaks, the ink box
    base = json.load(open(ex, encoding="utf-8"))
    import compose
    fonts = __import__("render_set").Fonts(tdir)
    ctx = compose.context(base, tdir, "tr", fonts, "ios", 1206, 2622)

    def scene_of(layers, W=1206, H=2622, span=1, **shot):
        return sc.Scene(dict({"id": "t", "proof": [{"evidence": "home"}], "background": {"fill": "$ground"}, "layers": layers,
                              "span": span}, **shot), W, H, ctx).build()
    t = scene_of([{"type": "text", "id": "h", "role": "headline", "style": "headline", "text": "Bir iki üç\naltı", "w": 0.45, "x": 0.08, "y": 0.1},
                  {"type": "text", "id": "sub", "role": "sub", "style": "sub", "text": "alt satır", "x": 0.08, "below": "h", "gap": 0.05}])
    h, sub = t.by_id["h"], t.by_id["sub"]
    assert h["meta"]["lines"] == 2, "a written line break must be kept (shrink, don't re-wrap)"
    assert abs(sub["meta"]["bbox"][1] - (h["meta"]["bbox"][3] + 0.05 * t.c.U)) < 2
    assert h["meta"]["ink"][1] >= h["meta"]["bbox"][1] and h["meta"]["ink"][3] <= h["meta"]["bbox"][3] + 1

    # --- refused: these must not render
    def bad_set(name, shots, **extra):
        p = os.path.join(d, f"bad-{name}.json")
        json.dump(dict(base, evidence=ev_path, sizes=["ios"], shots=shots, **extra), open(p, "w", encoding="utf-8"), ensure_ascii=False)
        return p
    head = {"type": "text", "id": "head", "role": "headline", "style": "headline", "text": "Kaldığın *bölüm* hazır", "x": 0.08, "y": 0.12, "w": 0.84}
    refusals = {
        "stretch": ({"type": "screen", "evidence": "home", "w": 0.8, "h": 1.0}, "not both"),
        "filter": ({"type": "screen", "evidence": "home", "w": 0.8, "blur": 4}, "isn't allowed"),
        "fade": ({"type": "screen", "evidence": "home", "w": 0.8, "opacity": 0.5}, "isn't allowed"),
        "unknown": ({"type": "screen", "evidence": "settings", "w": 0.8}, "isn't in the evidence"),
        "svgtext": ({"type": "svg", "role": "decor", "motive": "x", "markup": "<text x='0.1' y='0.2'>99</text>"}, "shapes only"),
        "svgimage": ({"type": "svg", "role": "decor", "motive": "x", "markup": "<image href='a.png'/>"}, "shapes only"),
    }
    for name, (layer, msg) in refusals.items():
        out = run(s("compose.py"), "render", bad_set(name, [{"id": name, "proof": [{"evidence": "home"}], "background": {"fill": "$ground"},
                                                                "layers": [head, layer]}]),
                  "--out", os.path.join(d, "bad", name), expect=1, both=True)
        assert msg in out, (name, out)
    # an edited screen: the hash no longer matches
    edited = os.path.join(d, "edited")
    shutil.copytree(DEMO, edited)
    ev2 = os.path.join(d, "ev-edited.json")
    run(s("evidence.py"), "build", edited, "-o", ev2, "--no-ocr")
    im = Image.open(os.path.join(edited, "01-home.jpg"))
    im.putpixel((10, 10), (255, 0, 255))
    im.save(os.path.join(edited, "01-home.jpg"), quality=95)
    p = bad_set("edited", [{"id": "e", "proof": [{"evidence": "home"}], "background": {"fill": "$ground"},
                            "layers": [head, {"type": "screen", "evidence": "home", "w": 0.8, "cx": "50%", "y": 0.5}]}])
    j = json.load(open(p, encoding="utf-8"))
    j["evidence"] = ev2
    json.dump(j, open(p, "w", encoding="utf-8"))
    assert "changed since evidence.json" in run(s("compose.py"), "render", p, "--out", os.path.join(d, "bad", "edited"), expect=1, both=True)

    # --- warned: one shot per rule
    shot = lambda i, layers, **kw: dict({"id": i, "proof": [{"evidence": "stats"}], "background": {"fill": "$ground"}, "layers": layers}, **kw)
    scr = {"type": "screen", "id": "s", "evidence": "stats", "w": 0.8, "cx": "50%", "y": 0.62, "radius": 0.06}
    cases = [
        shot("paint", [head, scr, {"type": "text", "role": "headline", "style": "headline", "text": "Üstüne yazı", "x": 0.2, "y": 0.9}]),
        shot("claim", [dict(head, text="Bu yıl *999 saat* izledin"), scr]),
        shot("motive", [head, scr, {"type": "ellipse", "role": "decor", "x": 0.6, "y": 0.3, "w": 0.2, "fill": "$accent"}]),
        shot("palette", [head, scr, {"type": "rect", "role": "decor", "motive": "test", "x": 0.08, "y": 0.45, "w": 0.3, "h": 0.01, "fill": "#00FF00"}]),
        shot("contrast", [dict(head, color="#26252B"), scr]),
        shot("small", [dict(head, size=0.04, min_size=0.04), scr]),
        shot("lift", [head, scr, {"type": "screen", "evidence": "stats", "crop": "tiles", "lift": {"from": "s", "scale": 1.05, "dx": 0.3}}]),
        shot("soft", [head, {"type": "screen", "evidence": "stats", "crop": [0.1, 0.6, 0.3, 0.65], "w": 0.84, "x": 0.08, "y": 0.6}]),
        shot("touch", [head, dict(scr, below="head", gap=0.0)]),
        shot("lookalike", [head, scr, {"type": "rect", "role": "decor", "motive": "test", "x": 0.1, "y": 0.45, "w": 0.4, "h": 0.08, "radius": 0.04, "fill": "$accent"},
                           {"type": "text", "role": "label", "style": "sub", "text": "Hemen izle", "x": 0.13, "y": 0.465, "w": 0.35, "color": "$ink"}]),
        shot("seam", [dict(head, text="Bir resim iki slot boyunca uzanıyor", w=1.8), dict(scr, cx="42%")], span=2),
        shot("cut", [head, dict(scr, evidence="calendar", crop=[0, 0.02, 1, 0.66], y=0.5)], proof=[{"evidence": "calendar"}]),
        shot("margin", [head, dict(scr, evidence="friends", id="f"),
                        {"type": "screen", "evidence": "friends", "crop": [0.015, 0.198, 0.985, 0.396], "lift": {"from": "f", "scale": 1.1}}],
             proof=[{"evidence": "friends"}]),
        shot("noedge", [head, dict(scr, evidence="detail", id="dl"),
                        {"type": "screen", "evidence": "detail", "crop": [0.03, 0.43, 0.97, 0.48], "lift": {"from": "dl", "scale": 1.12}}],
             proof=[{"evidence": "detail"}]),
    ]
    p = bad_set("warn", cases, promise_words=["kitap"])
    out = run(s("compose.py"), "render", p, "--out", os.path.join(d, "warn"), both=True)
    for msg in ("covers", "number '999'", 'without a "motive"', "outside the campaign palette: #00FF00", "low contrast",
                "too small for search results", "doesn't cover its place", "will look soft", "touches the screen",
                "looks like app UI", "crosses the seam", "off-centre", "names what the app does",
                "includes a margin around the component", "has no visible edge"):
        assert msg in out, (msg, out)
    assert "cuts through the UI" in out or "slices through 'Perşembe'" in out, out  # pixels, or the OCR words
    # the same items on two different screens (the same posts on the calendar and on the home screen)
    ev_dup = json.load(open(ev_path, encoding="utf-8"))
    for sid in ev_dup["screens"]:
        ev_dup["screens"][sid]["path"] = os.path.join(os.path.dirname(ev_path), ev_dup["screens"][sid]["path"])
    items = ["Sabahlamayı", "bıraktım", "Toplantılar", "kaybolan", "saatleri", "Finaller", "haftası", "alışkanlıkla"]
    for sid in ("stats", "friends"):
        ev_dup["screens"][sid]["ocr"] = (ev_dup["screens"][sid].get("ocr") or []) + [
            {"t": t, "b": [0.1, 0.4 + k * 0.03, 0.4, 0.42 + k * 0.03], "c": 95} for k, t in enumerate(items)]
    ev_dup_path = os.path.join(d, "ev-dup.json")
    json.dump(ev_dup, open(ev_dup_path, "w", encoding="utf-8"), ensure_ascii=False)
    p = bad_set("dup", [shot("d1", [head, dict(scr, evidence="stats")]), shot("d2", [head, dict(scr, evidence="friends", y=0.5)],
                                                                            proof=[{"evidence": "friends"}])])
    j = json.load(open(p, encoding="utf-8"))
    j["evidence"] = ev_dup_path
    json.dump(j, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    out = run(s("compose.py"), "render", p, "--out", os.path.join(d, "dup"), both=True)
    assert "show the same content on different screens" in out, out
    # a footnote is small but readable, and not part of the caption
    p = bad_set("foot", [shot("f1", [head, scr, {"type": "text", "role": "footnote", "style": "sub", "text": "Örnek veriler",
                                                  "x": 0.08, "bottom": 0.05, "size": 0.045}])])
    assert "footnote at 0.045u" in run(s("compose.py"), "render", p, "--out", os.path.join(d, "foot"), both=True)
    same = [shot(f"m{i}", [head, dict(scr, evidence=ev_id)]) for i, ev_id in enumerate(("stats", "home", "calendar"))]
    out = run(s("compose.py"), "render", bad_set("same", same), "--out", os.path.join(d, "same"), both=True)
    assert "share one composition" in out, out
    # Google Play: no device frame, taglines under 20 % - big type counts
    play = [shot("frame", [head, dict(scr, frame={"style": "phone"})]),
            shot("tall", [head, {"type": "text", "role": "display", "style": "headline", "text": "312", "size": 0.6, "x": 0.08, "y": 0.5}, dict(scr, y=1.3)])]
    p = bad_set("play", play)
    j = json.load(open(p, encoding="utf-8"))
    j["sizes"] = ["android"]
    json.dump(j, open(p, "w", encoding="utf-8"))
    out = run(s("compose.py"), "render", p, "--out", os.path.join(d, "play"), both=True)
    assert "device frame in a Google Play set" in out and "caption covers" in out, out
    # free vector work: an svg layer in units, drawn by resvg in both backends
    if sc.have_resvg():
        mot = {"type": "svg", "role": "decor", "motive": "the app's progress bar", "x": 0.08, "y": 0.5,
               "markup": "<rect x='0' y='0' width='0.84' height='0.012' rx='0.006' fill='$accent'/>"}
        p = bad_set("svg", [shot("svg", [head, mot, scr])], promise_words=["bölüm"])
        for backend in ("svg", "pillow"):
            o = os.path.join(d, "svg-" + backend)
            out = run(s("compose.py"), "render", p, "--out", o, "--backend", backend, both=True)
            px = Image.open(os.path.join(o, "ios", "01.png")).convert("RGB").getpixel((600, round(0.506 * 1206)))
            assert px[0] > 200 and px[1] < 140, (backend, px, out)


def device3d_tests(tmp):
    """3D devices must never be wrong: every pixel of the screen lands where the camera puts it, the body has no
    holes or seams, the faces we see are the right ones, the picture is symmetric and repeatable - on both
    backends - and the rules (angle limits, foreshortening, shadow, one camera per set, Play) hold."""
    import json
    import time
    from PIL import Image, ImageChops, ImageDraw, ImageOps, ImageStat
    sys.path.insert(0, SCRIPTS)
    import compose
    import device3d as d3
    import render_set as rs
    import scene as sc
    d = os.path.join(tmp, "d3")
    os.makedirs(os.path.join(d, "screens"))
    # a screen of known marks: coloured squares at known places, a fine grid, text
    W, H = 1206, 2622
    marks = {(255, 0, 0): (0.12, 0.12), (0, 200, 0): (0.88, 0.12), (0, 90, 255): (0.5, 0.5), (255, 220, 0): (0.12, 0.88),
             (255, 0, 255): (0.88, 0.88), (0, 230, 230): (0.3, 0.7)}
    scr = Image.new("RGB", (W, H), (32, 32, 36))
    dr = ImageDraw.Draw(scr)
    for x in range(0, W, 60):
        dr.line([(x, 0), (x, H)], fill=(52, 52, 58), width=2)
    for y in range(0, H, 60):
        dr.line([(0, y), (W, y)], fill=(52, 52, 58), width=2)
    for col, (u, v) in marks.items():
        dr.rectangle([u * W - 14, v * H - 14, u * W + 14, v * H + 14], fill=col)
    dr.text((120, 1500), "Kaldığın bölüm hep hazır", font=rs.Fonts(SKILL).get("text", 60), fill=(240, 240, 240))
    scr.save(os.path.join(d, "screens", "01-marks.png"))
    sym = Image.new("RGB", (W, H), (30, 30, 34))
    sd = ImageDraw.Draw(sym)
    for i in range(12):
        sd.rectangle([60 + i * 40, 200 + i * 170, 300 + i * 25, 320 + i * 170], fill=(40 + i * 15, 120, 220 - i * 12))
    sym.paste(ImageOps.mirror(sym.crop((0, 0, W // 2, H))), (W - W // 2, 0))
    sym.save(os.path.join(d, "screens", "02-sym.png"))
    ev = os.path.join(d, "ev.json")
    run(s("evidence.py"), "build", os.path.join(d, "screens"), "-o", ev, "--no-ocr")
    base = json.load(open(os.path.join(SKILL, "templates", "scene.example.json"), encoding="utf-8"))
    base["evidence"] = ev
    fonts = rs.Fonts(os.path.join(SKILL, "templates"))

    def ctx_for(size="ios", camera=None):
        b = dict(base, campaign=dict(base["campaign"], camera=camera) if camera else base["campaign"])
        return compose.context(b, os.path.join(SKILL, "templates"), "tr", fonts, size, *rs.preset_size(size))

    def build(layer, size="ios", camera=None, extra=None):
        Wc, Hc = rs.preset_size(size)
        shot = {"id": "t", "proof": [{"evidence": "marks"}], "background": {"fill": "#808080"}, "layers": [layer] + (extra or [])}
        return sc.Scene(shot, Wc, Hc, ctx_for(size, camera)).build()

    def dev_layer(**kw):
        return dict({"type": "device3d", "id": "ph", "evidence": "marks", "w": 0.78, "cx": "50%", "cy": "50%"}, **kw)

    def centroid(img, col, box):
        px = img.crop(box).load()
        xs = ys = n = 0
        for yy in range(box[3] - box[1]):
            for xx in range(box[2] - box[0]):
                p = px[xx, yy]
                if sum((p[k] - col[k]) ** 2 for k in range(3)) < 40 ** 2:
                    xs, ys, n = xs + xx, ys + yy, n + 1
        return (box[0] + xs / n, box[1] + ys / n, n) if n else None

    # 1. every mark lands where the camera says - several angles, both backends
    poses = [(0, 0, 0), (-25, 0, 0), (24, 8, 0), (-15, -12, 9), (35, 5, -4), (0, 22, 0), (10, 0, 20)]
    backends = ["pillow"] + (["svg"] if sc.have_resvg() else [])
    for yaw, pitch, roll in poses:
        scn = build(dev_layer(rotate3d={"yaw": yaw, "pitch": pitch, "roll": roll}))
        op = scn.by_id["ph"]
        for be in backends:
            img, _, _ = sc.render(scn, fonts, be)
            for col, (u, v) in marks.items():
                ex, ey = d3.hmap(op["H"], u * W, v * H)
                got = centroid(img, col, (int(ex) - 40, int(ey) - 40, int(ex) + 40, int(ey) + 40))
                assert got and got[2] > 60, (yaw, pitch, roll, be, col, "mark missing")
                err = math.dist((ex, ey), got[:2])
                assert err < 1.2, f"pose {(yaw, pitch, roll)} {be}: mark {col} off by {err:.2f}px"
    # 2. facing the camera, the 3D screen is the flat screen: same pixels at the same size
    scn = build(dev_layer())
    op = scn.by_id["ph"]
    q = op["quad"]
    assert abs(q[0][1] - q[1][1]) < 0.01 and abs(q[0][0] - q[3][0]) < 0.01, q  # an upright rectangle
    img, _, _ = sc.render(scn, fonts, "pillow")
    x0, y0, x1, y1 = q[0][0], q[0][1], q[2][0], q[2][1]
    flat = scr.resize((round(x1 - x0), round(y1 - y0)), Image.LANCZOS)
    got = img.crop((round(x0), round(y0), round(x0) + flat.width, round(y0) + flat.height))
    inner = (40, 260, flat.width - 40, flat.height - 200)  # away from the rounded corners and the island
    diff = sum(ImageStat.Stat(ImageChops.difference(flat.crop(inner), got.crop(inner))).mean) / 3
    assert diff < 3.5, f"front view differs from the flat screen by {diff:.2f}"
    # 3. no holes, no seams: the body is opaque inside its silhouette, at every pose; the homography is the camera
    for yaw, pitch, roll in poses:
        dev = d3.Device((W, H), 900, yaw, pitch, roll, "island").place(1000, 1500)
        corners = [dev.proj((sx * dev.sw / 2, sy * dev.sh / 2, -dev.T / 2)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        assert all(math.dist(a, b) < 1e-6 for a, b in zip(corners, dev.screen_quad())), "homography disagrees with the camera"
        front = [dev.proj((x, y, -dev.T / 2)) for x, y in dev.outline]
        poly = Image.new("L", (2400, 3200), 0)
        ImageDraw.Draw(poly).polygon(front, fill=255)
        edge, _ = d3.rounded_outline(dev.sw, dev.sh, dev.r_screen)
        edge = [dev.proj((x, y, -dev.T / 2)) for x, y in edge]
        assert all(poly.getpixel((round(x + (1000 - x) * 0.004), round(y + (1500 - y) * 0.004))) == 255 for x, y in edge), \
            "the screen reaches past the front of the body"
        body, (X0, Y0) = dev.render(scr)
        a = body.getchannel("A")
        bb = a.getbbox()
        inside = Image.new("L", a.size, 0)
        hull = d3.convex_hull([((p[0] - X0), (p[1] - Y0)) for p in
                               [dev.proj((x, y, z)) for x, y in dev.outline for z in (-dev.T / 2, dev.T / 2)]])
        cx_, cy_ = sum(p[0] for p in hull) / len(hull), sum(p[1] for p in hull) / len(hull)
        shrunk = [(cx_ + (x - cx_) * 0.995 - (2 if x > cx_ else -2), cy_ + (y - cy_) * 0.995 - (2 if y > cy_ else -2)) for x, y in hull]
        ImageDraw.Draw(inside).polygon(shrunk, fill=255)
        holes = ImageChops.multiply(ImageChops.invert(a), inside).getextrema()[1]
        assert holes < 8, f"pose {(yaw, pitch, roll)}: a gap in the body (alpha {255 - holes})"
        assert bb and bb[0] <= 4 and bb[1] <= 4, (bb, "raster too tight")
    # 4. the right faces: turned right, the left side shows; turned left, the right side
    for yaw, side in ((25, "left"), (-25, "right")):
        dev = d3.Device((W, H), 900, yaw, 0, 0, "slab").place(600, 1300)
        qd, bx = dev.screen_quad(), dev.bbox()
        left_gap, right_gap = min(p[0] for p in qd) - bx[0], bx[2] - max(p[0] for p in qd)
        assert (left_gap > right_gap * 1.6) if side == "left" else (right_gap > left_gap * 1.6), (yaw, left_gap, right_gap)
    for pitch, side in ((20, "bottom"), (-20, "top")):
        dev = d3.Device((W, H), 900, 0, pitch, 0, "slab").place(600, 1300)
        qd, bx = dev.screen_quad(), dev.bbox()
        top_gap, bot_gap = min(p[1] for p in qd) - bx[1], bx[3] - max(p[1] for p in qd)
        assert (bot_gap > top_gap * 1.4) if side == "bottom" else (top_gap > bot_gap * 1.4), (pitch, top_gap, bot_gap)
    # 5. symmetric: a symmetric screen turned right is the mirror image of it turned left (light from the front)
    flat_light = {"fov": 22, "light": [0, 0, -1]}
    renders = []
    for yaw in (18, -18):
        dev = d3.Device((W, H), 900, yaw, 0, 0, "slab", {"buttons": None, "cutout": None}, flat_light).place(700, 1300)
        body, at = dev.render(sym)
        canvas = Image.new("RGBA", (1400, 2600), (128, 128, 128, 255))
        canvas.alpha_composite(body, at)
        renders.append(canvas.convert("RGB"))
    mdiff = sum(ImageStat.Stat(ImageChops.difference(ImageOps.mirror(renders[0]), renders[1])).mean) / 3
    assert mdiff < 1.0, f"yaw ±18 aren't mirror images ({mdiff:.2f})"
    # 6. repeatable to the byte
    a1 = d3.Device((W, H), 900, 21, 7, -3).place(600, 1300).render(scr)[0].tobytes()
    a2 = d3.Device((W, H), 900, 21, 7, -3).place(600, 1300).render(scr)[0].tobytes()
    assert a1 == a2, "two renders of the same pose differ"
    # 7. speed: the largest iPhone size stays quick
    t0 = time.time()
    scn = build(dev_layer(rotate3d={"yaw": -20, "pitch": 6}, w=0.84), size="ios-large")
    sc.render(scn, fonts, "pillow")
    assert time.time() - t0 < 12, f"device3d at 1320x2868 took {time.time() - t0:.1f}s"
    # 8. rules - refused
    for layer, msg in ((dev_layer(rotate3d={"yaw": 45}), "past 40"), (dev_layer(rotate3d={"pitch": -31}), "past 30"),
                       (dev_layer(crop=[0, 0, 1, 0.5]), "whole screen"), (dev_layer(rotate=10), "rotate3d"),
                       (dev_layer(opacity=0.5), "shown as they are"), (dev_layer(w=0.7, h=1.4), "not both"),
                       (dev_layer(camera={"fov": 90}), "fov"), (dev_layer(model="foldable"), "model")):
        try:
            build(layer)
        except sc.SceneError as e:
            assert msg in str(e), (msg, str(e))
        else:
            raise AssertionError(f"not refused: {layer}")
    try:
        build(dev_layer(), extra=[{"type": "screen", "evidence": "marks", "crop": [0.1, 0.1, 0.4, 0.2], "lift": {"from": "ph"}}])
    except sc.SceneError as e:
        assert "can't be lifted" in str(e), e
    else:
        raise AssertionError("lift from a 3D device not refused")
    # rules - warned
    scn = build(dev_layer(rotate3d={"yaw": 38}, camera={"fov": 55}, shadow="none"))
    w = " ".join(scn.warnings)
    assert "far side" in w and "floats" in w, scn.warnings
    scn = build(dev_layer(rotate3d={"yaw": 15}))
    assert not scn.warnings, scn.warnings
    # a hand mark on a 3D screen follows its perspective
    scn = build(dev_layer(rotate3d={"yaw": 22, "pitch": 6}),
                extra=[{"type": "mark", "id": "m", "kind": "circle", "on": "ph", "region": [0.5 - 0.02, 0.5 - 0.01, 0.5 + 0.02, 0.5 + 0.01]}])
    mb = scn.by_id["m"]["meta"]["bbox"]
    ex, ey = d3.hmap(scn.by_id["ph"]["H"], 0.5 * W, 0.5 * H)
    assert abs((mb[0] + mb[2]) / 2 - ex) < 12 and abs((mb[1] + mb[3]) / 2 - ey) < 12, (mb, ex, ey)
    # set rules through compose: Play, paint-over, one camera, not every shot turned
    head = {"type": "text", "id": "head", "role": "headline", "style": "headline", "text": "Kaldığın *bölüm* hazır", "x": 0.08, "y": 0.12, "w": 0.84}
    shots = [{"id": f"s{i}", "proof": [{"evidence": "marks"}], "background": {"fill": "$ground"},
              "layers": [head, dev_layer(rotate3d={"yaw": y}, camera={"fov": f}, cy=None, y=0.55)]}
             for i, (y, f) in enumerate(((-20, 22), (18, 22), (-15, 30)))]
    for sh in shots:
        sh["layers"][1].pop("cy")
    shots[0]["layers"].append({"type": "text", "role": "headline", "style": "headline", "text": "Üstünde yazı", "x": 0.2, "y": 1.0})
    p = os.path.join(d, "set.json")
    json.dump(dict(base, sizes=["ios", "android"], shots=shots, feature_graphic=None), open(p, "w", encoding="utf-8"), ensure_ascii=False)
    out = run(s("compose.py"), "render", p, "--out", os.path.join(d, "out"), both=True)
    for msg in ("different lenses", "turned 3D phones in 3 of 3", "device frame in a Google Play set", "covers"):
        assert msg in out, (msg, out)
    svg = open(os.path.join(d, "out", "ios", "01.svg"), encoding="utf-8").read()
    assert 'data-evidence="marks"' in svg
    out = run(s("check_set.py"), os.path.join(d, "out", "ios"), "--store", "ios")
    assert "different lenses" in out, out
    # context devices: wider limits, no far-side warning, never the proof; a shot of only context devices is warned
    scn = build(dev_layer(role="context", rotate3d={"yaw": 55, "pitch": 40}))
    assert not any("far side" in w for w in scn.warnings), scn.warnings
    for layer, msg in ((dev_layer(rotate3d={"yaw": 55}), "past 40"), (dev_layer(role="context", rotate3d={"yaw": 65}), "past 60")):
        try:
            build(layer)
        except sc.SceneError as e:
            assert msg in str(e), (msg, str(e))
        else:
            raise AssertionError(f"not refused: {layer}")
    import validate as va
    ctx_ios = ctx_for()
    only = build(dev_layer(role="context", rotate3d={"yaw": 50}))
    assert any('every device in this shot is a "context" device' in w for w in va.scene_warnings(only, None, ctx_ios))
    both = build(dev_layer(rotate3d={"yaw": 12}), extra=[dev_layer(id="bg", role="context", rotate3d={"yaw": -50}, w=0.5, cx="70%")])
    assert not any("context" in w for w in va.scene_warnings(both, None, ctx_ios))
    assert not va.visible_words(only, ctx_ios, 0)[1], "a context device's words counted as content"
    # sheen: a reflection on the bezel only - the screen's pixels are identical with and without it
    outs = []
    for sh_ in (0, 0.5):
        dev = d3.Device((W, H), 900, -14, 6, 0, "island", {"sheen": sh_}).place(700, 1300)
        body, at = dev.render(scr)
        canvas = Image.new("RGBA", (1400, 2600), (128, 128, 128, 255))
        canvas.alpha_composite(body, at)
        outs.append(canvas.convert("RGB"))
    q = dev.screen_quad()
    inner = (int(min(p[0] for p in q)) + 30, int(min(p[1] for p in q)) + 80, int(max(p[0] for p in q)) - 30, int(max(p[1] for p in q)) - 60)
    diff = ImageChops.difference(*outs)
    assert diff.crop(inner).getbbox() is None, "the sheen touched the screen"
    assert diff.getbbox() is not None, "no sheen drawn"
    # rim light: lights the band in its colour, counts as coloured light (glow), joins the set's one camera
    plain = d3.Device((W, H), 900, -30, 0, 0, "slab").place(700, 1300).render(scr)[0]
    rim = d3.Device((W, H), 900, -30, 0, 0, "slab", camera={"fov": 22, "light": [-0.45, -0.75, -0.5],
                                                            "rim": {"color": "#FF5A3C", "strength": 1.0}}).place(700, 1300).render(scr)[0]
    band = ImageChops.difference(plain, rim).convert("RGB").getbbox()
    assert band is not None, "the rim light drew nothing"
    try:
        d3.Device((W, H), 900, camera={"fov": 22, "light": [0, 0, -1], "rim": {"strength": 1}})
    except d3.DeviceError as e:
        assert "camera rim" in str(e)
    else:
        raise AssertionError("rim without a colour not refused")
    scn = build(dev_layer(rotate3d={"yaw": -20}), camera={"fov": 22, "light": [-0.45, -0.75, -0.5], "rim": {"color": "$accent"}})
    assert scn.by_id["ph"]["meta"]["camera"]["rim"][0] == "#FF5A3C", scn.by_id["ph"]["meta"]["camera"]
    mats = {m for m, _, _ in va.materials_used(scn)}
    assert {"3d", "glow"} <= mats, mats
    # the 3D fixture (two devices facing each other, one laid back, flat shots between) renders clean on both sizes
    fx = os.path.join(ROOT, "tools", "fixtures", "device3d-set.json")
    out = run(s("compose.py"), "render", fx, "--out", os.path.join(d, "fx"), both=True)
    assert "!" not in out, out
    for size in ("ios", "ios-large"):
        out = run(s("check_set.py"), os.path.join(d, "fx", size), "--store", "ios", "--lang", "tr")
        assert "WARN" not in out and "ERROR" not in out, out


def guardrail_tests(tmp):
    """Nothing is a default: effects need a source, the skill's own habits and the bundled examples are caught,
    callouts stay the campaign's, references lend principles not colours, Google Play's three kinds of rule are
    labelled apart - and glass and glow draw the same on both backends."""
    import json
    from PIL import Image, ImageChops, ImageStat
    sys.path.insert(0, SCRIPTS)
    import scene as sc
    tdir = os.path.join(SKILL, "templates")
    ex = os.path.join(tdir, "scene.example.json")
    ev_path = os.path.join(tdir, "scene-evidence.json")
    d = os.path.join(tmp, "guard")
    os.makedirs(d)
    base = json.load(open(ex, encoding="utf-8"))

    def write(name, shots, campaign=None, **extra):
        p = os.path.join(d, name, "set.json")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        camp = dict(base["campaign"], **(campaign or {}))
        bare = {k: v for k, v in base.items() if k != "feature_graphic"}
        spec = dict(bare, evidence=ev_path, sizes=["ios"], shots=shots, campaign=camp, app=extra.pop("app", "Test " + name), **extra)
        json.dump(spec, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        return p

    def render(p, *args, expect=0, out="out"):
        return run(s("compose.py"), "render", p, "--out", os.path.join(os.path.dirname(p), out), *args, expect=expect, both=True)
    head = {"type": "text", "id": "head", "role": "headline", "style": "headline", "text": "Kaldığın *bölüm* hazır", "x": 0.08, "y": 0.12, "w": 0.84}
    shot = lambda i, layers, **kw: dict({"id": i, "alt": "Test görseli", "proof": [{"evidence": "stats"}], "background": {"fill": "$ground"},
                                         "layers": layers}, **kw)
    scr = {"type": "screen", "id": "s", "evidence": "stats", "w": 0.7, "x": 0.15, "y": 0.5, "radius": 0.06}
    blob = {"type": "ellipse", "role": "decor", "motive": "the accent as the one light", "x": 0.05, "y": 1.6, "w": 0.5, "fill": "$accent"}
    panel = {"type": "rect", "role": "decor", "motive": "the app's frosted sheet", "x": 0.1, "y": 1.75, "w": 0.6, "h": 0.2, "radius": 0.04,
             "fill": None, "glass": {"blur": 0.03, "opacity": 0.14}}
    glow_scr = dict(scr, glow={"color": "$accent", "blur": 0.1, "opacity": 0.6})

    # --- glass and glow draw, and both backends agree
    if sc.have_resvg():
        p = write("fx", [shot("fx", [head, blob, glow_scr, panel])])
        render(p)
        render(p, "--backend", "pillow", out="pil")
        a = Image.open(os.path.join(d, "fx", "out", "ios", "01.png")).convert("RGB")
        b = Image.open(os.path.join(d, "fx", "pil", "ios", "01.png")).convert("RGB")
        diff = sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3
        assert diff < 6, f"glass/glow: backends differ by {diff:.1f}"
        U = 1206
        halo = a.getpixel((int(0.15 * U) - 12, int(0.9 * U)))  # just left of the screen: lit by the accent glow
        ground = a.getpixel((int(0.02 * U), int(0.3 * U)))
        assert halo[0] > ground[0] + 25, (halo, ground)
        # the glass panel blurs the edge of the accent ellipse behind it: a soft ramp, not a hard step
        y = int(1.85 * U)
        row = [a.getpixel((x, y))[0] for x in range(int(0.45 * U), int(0.62 * U))]
        steps = max(abs(row[i + 1] - row[i]) for i in range(len(row) - 1))
        assert steps < 40, steps
    # --- effects without a source are warned; with one, they're a choice
    p = write("nosrc", [shot("n", [head, dict(blob, motive=None), dict(glow_scr), dict(panel, motive=None)])])
    out = render(p)
    assert "glass on rect has no source" in out and "glow on image s has no source" in out, out
    p = write("src", [shot("n", [head, dict(blob, motive=None), glow_scr, dict(panel, motive=None)])],
              campaign={"materials": {"glass": "concept: the sheets of the app, frosted", "glow": "concept: the accent is the only light"}})
    out = render(p)
    assert "has no source" not in out, out
    p = write("noreason", [shot("n", [head, scr])], campaign={"materials": {"gradient": "", "sparkle": "x"}})
    out = render(p)
    assert "'gradient' has no reason" in out and "'sparkle' isn't one of" in out, out
    dna = {"materials": {"flat": "flat cards"}, "measured": {"ui": "light", "palette": [{"hex": "#FF5A3C"}]},
           "references": [{"file": "liked.png", "palette": ["#2B6CFF", "#19C37D", "#0E0E10"]}]}
    json.dump(dna, open(os.path.join(d, "dna.json"), "w", encoding="utf-8"))
    p = write("dnasrc", [shot("n", [head, scr, dict(panel, motive=None)])], dna=os.path.join(d, "dna.json"),
              campaign={"materials": {"glass": "dna: frosted tab bar"},
                        "tokens": dict(base["campaign"]["tokens"], blue="#2B6CFF", green="#19C37D")})
    out = render(p)
    assert "says it comes from the DNA" in out and "come from the reference" in out, out
    for name, layer, msg in (("glassgroup", {"type": "group", "layers": [panel]}, "top-level layers only"),
                             ("glassellipse", dict(blob, glass={}), "works on a rect")):
        assert msg in render(write(name, [shot("g", [head, scr, layer])]), expect=1), name
    # --- callouts: the campaign's own style is not app UI; anything else is
    box = {"type": "rect", "role": "callout", "x": 0.55, "y": 0.42, "w": 0.4, "h": 0.08, "radius": 0.04, "fill": "$accent"}
    label = {"type": "text", "role": "callout", "style": "callout", "text": "Spoiler gizli", "x": 0.58, "y": 0.44, "w": 0.35}
    callout_style = {"type": dict(base["campaign"]["type"], callout={"font": "display", "size": 0.034, "color": "$ground"})}
    out = render(write("callout", [shot("c", [head, scr, box, label])], campaign=callout_style))
    assert "looks like app UI" not in out and "callout style" not in out and "covers" not in out, out
    out = render(write("callout-nostyle", [shot("c", [head, scr, box, dict(label, style="sub")])]))
    assert "doesn't use a campaign callout style" in out and "looks like app UI" in out, out
    many = [head, scr] + [dict(label, y=0.3 + 0.1 * k, x=0.08, w=0.3) for k in range(5)]
    assert "5 callouts in one shot" in render(write("callouts", [shot("c", many)], campaign=callout_style))
    # --- the skill's own habits, across a set
    lifted = [shot(f"h{k}", [head, dict(scr, evidence=e, id="m", y=0.7 + 0.05 * k),
                             {"type": "screen", "evidence": e, "crop": r, "lift": {"from": "m", "scale": 1.08}}],
                   proof=[{"evidence": e}])
              for k, (e, r) in enumerate((("stats", "tiles"), ("home", "resume"), ("calendar", "tonight"), ("friends", "first-post")))]
    out = render(write("habits", lifted, campaign={"materials": {"glow": "concept: one light"}}))
    assert "a lifted card in 4 of 4 shots" in out and "every shot crops its main screen" in out, out
    glowing = [shot(f"g{k}", [head, dict(glow_scr, evidence=e, y=0.5 + 0.1 * k)], proof=[{"evidence": e}])
               for k, e in enumerate(("stats", "home", "calendar", "friends"))]
    out = render(write("glowing", glowing, campaign={"materials": {"glow": "concept: one light"}}, dna=os.path.join(d, "dna.json")))
    assert "glow in every shot" in out and "the app's UI is light but every shot is on a dark ground" in out, out
    out = render(write("glowing-dna", glowing, campaign={"materials": {"glow": "dna: the app's neon accent"}}))
    assert "glow in every shot" not in out, out
    # --- the bundled example is the format, not a look
    out = render(write("copy", base["shots"]))
    assert "repeats the layout of the bundled example 'templates/resume'" in out, out
    # --- opt-in history: a set that looks like the last one for another app
    os.environ["STORE_SCREENSHOTS_HOME"] = os.path.join(d, "home")
    try:
        render(write("hist-a", base["shots"][:3], app="App A"), "--history")
        out = render(write("hist-b", base["shots"][:3], app="App B"), "--history")
        assert "looks like your 'App A' set" in out, out
        out = run(s("compose.py"), "history")
        assert "App A" in out and "App B" in out and "2 sets" in out, out
        run(s("compose.py"), "history", "--clear")
        assert "no history yet" in run(s("compose.py"), "history")
    finally:
        os.environ.pop("STORE_SCREENSHOTS_HOME", None)
    # --- Google Play: requirement, recommendation, promotion eligibility - and alt text
    p = write("play", [shot("p1", [head, scr]), shot("p2", [head, dict(scr, evidence="home")], alt="x" * 150, proof=[{"evidence": "home"}]),
                       shot("p3", [head, dict(scr, evidence="calendar")], alt=None, proof=[{"evidence": "calendar"}])],
              feature_graphic={"background": {"fill": "$ground"}, "layers": [dict(head, x=0.02, y=0.2, w=2.0)]})
    j = json.load(open(p, encoding="utf-8"))
    j["sizes"] = ["android"]
    json.dump(j, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    render(p)
    rep = json.load(open(os.path.join(d, "play", "out", "android", "_render.json"), encoding="utf-8"))
    assert rep["shots"][0]["alt"] == "Test görseli", rep["shots"][0]
    out = run(s("check_set.py"), os.path.join(d, "play", "out", "android"), "--store", "android", "--lang", "tr")
    for msg in ("[Play promotion eligibility] fewer than 4 screenshots", "[Play recommendation] 1 of 3 screenshots have no alt text",
                "02.png: alt text is 150 characters", "[Play recommendation] feature graphic ground is",
                "the headline reaches into the cutoff zone", "feature graphic has no alt text", "[Play requirement]: the listing"):
        assert msg in out, (msg, out)
    assert "ERROR" not in out, out
    # --- layer ids never collide with the renderer's own (a layer "c1" once took over clip "c1" and vanished)
    if sc.have_resvg():
        pics = []
        for name, lid in (("ids", "c1"), ("ids2", "plain")):
            render(write(name, [shot("ids", [head, dict(scr, id=lid)])]))
            pics.append(Image.open(os.path.join(d, name, "out", "ios", "01.png")).convert("RGB"))
        diff = sum(ImageStat.Stat(ImageChops.difference(*pics)).mean) / 3
        assert diff < 0.5, f"a layer id that matches an internal def id changed the picture ({diff:.1f})"
    assert "renderer's own" in render(write("idres", [shot("r", [head, dict(scr, id="_ss-c1")])]), expect=1)
    # --- marks: a named region works; a region outside the layer's crop is warned (it was given in crop fractions)
    card = dict(scr, id="card", crop="tiles", w=0.8, x=0.1, y=0.6)
    out = render(write("markname", [shot("m", [head, card, {"type": "mark", "kind": "circle", "on": "card", "region": "tiles"}])]))
    assert "outside what that layer shows" not in out and "off the canvas" not in out, out
    out = render(write("markoff", [shot("m", [head, card, {"type": "mark", "kind": "circle", "on": "card", "region": [0.7, 0.0, 1.0, 0.1]}])]))
    assert "outside what that layer shows" in out, out
    # --- words under a screen, and a callout spilling out of its box
    out = render(write("under", [shot("u", [dict(head, y=0.9), dict(scr, y=0.7)])]))
    assert "covers" in out and "were placed under it" in out, out
    spill = [head, scr, dict(box, w=0.2), dict(label, text="Spoiler gizli, hep gizli", w=0.5)]
    assert "runs out of its box" in render(write("spill", [shot("c", spill)], campaign=callout_style))
    # --- the 2.2 Seenfy example renders clean on every size
    out = run(s("compose.py"), "render", os.path.join(ROOT, "examples", "seenfy-v2", "afisin-isigi.json"), "--out",
              os.path.join(d, "afisin"), both=True)
    assert "!" not in out, out
    for size, store in (("ios", "ios"), ("ios-large", "ios"), ("android", "android")):
        out = run(s("check_set.py"), os.path.join(d, "afisin", size), "--store", store, "--lang", "tr")
        assert "WARN" not in out and "ERROR" not in out, out
    # --- dna: materials on the board, a reference recorded with its palette
    ev = json.load(open(ev_path, encoding="utf-8"))
    dna_path = os.path.join(d, "dna-m.json")
    run(s("dna.py"), "measure", ev_path, "--app", "Dizilog", "-o", dna_path)
    m = json.load(open(dna_path, encoding="utf-8"))
    assert "_doc" in m["materials"] and m["references"] == [], m
    m["materials"]["flat"] = "flat cards"
    json.dump(m, open(dna_path, "w", encoding="utf-8"))
    run(s("dna.py"), "board", dna_path, "-o", os.path.join(d, "board.jpg"))
    ref = os.path.join(d, "liked.png")
    Image.new("RGB", (400, 800), (43, 108, 255)).save(ref)
    run(s("dna.py"), "reference", ref, "--dna", dna_path, "-o", os.path.join(d, "reference.jpg"))
    m = json.load(open(dna_path, encoding="utf-8"))
    assert m["references"][0]["palette"][0].upper().startswith("#2"), m["references"]
    assert ev  # the shipped evidence was readable


def console_tests(tmp):
    """Windows consoles and pipes default to a legacy code page (cp1254 / cp857 in Turkey): the scripts must
    print arrows, ≥ and Turkish letters there without crashing, with no PYTHONUTF8 needed."""
    env = dict(os.environ, PYTHONIOENCODING="cp1254")
    env.pop("PYTHONUTF8", None)
    out_dir = os.path.join(tmp, "console")
    calls = [[s("search_library.py"), "--category", "weather", "--summary"],
             [s("render_set.py"), os.path.join(SKILL, "templates", "set.example.json"), "--out", out_dir, "--size", "ios"],
             [s("check_set.py"), os.path.join(out_dir, "ios"), "--store", "ios", "--lang", "tr", "--headlines", "Kaldığın bölüm → hazır"]]
    if os.path.exists(s("compose.py")):
        calls += [[s("evidence.py"), "build", DEMO, "-o", os.path.join(tmp, "console-ev.json"), "--no-ocr"],
                  [s("compose.py"), "render", os.path.join(SKILL, "templates", "scene.example.json"), "--out",
                   os.path.join(tmp, "console-scene"), "--size", "ios"]]
    for args in calls:
        p = subprocess.run([PY, *args], capture_output=True, env=env)  # no -I: it would ignore PYTHONIOENCODING
        assert p.returncode == 0, (args[0], p.stderr.decode("utf-8", "replace")[-1500:])


def quality_tests(tmp):
    """The checks that catch a set that looks fine but doesn't sell: no promise in shots 1-3, the same proof
    twice, thin demo data."""
    import json
    import shutil
    from PIL import Image, ImageDraw
    tpl = os.path.join(SKILL, "templates", "set.example.json")
    d = json.load(open(tpl, encoding="utf-8"))
    d["shots"] = [dict(sh, screen=os.path.join(SKILL, "templates", sh["screen"])) if sh.get("screen") else sh for sh in d["shots"]]

    def render(extra, name, shots=None):
        path = os.path.join(tmp, f"q-{name}.json")
        json.dump(dict(d, sizes=["ios"], shots=shots or d["shots"], **extra), open(path, "w", encoding="utf-8"), ensure_ascii=False)
        return run(s("render_set.py"), path, "--out", os.path.join(tmp, "q", name), both=True)
    good = render({}, "good")
    assert "first three headlines" not in good and "the same way" not in good and "both use" not in good, good
    assert "promise_words" not in good, good
    assert "none of the first three headlines names what the app does" in render({"promise_words": ["carousel", "TikTok"]}, "promise")
    assert 'no "promise_words" in the spec' in render({"promise_words": []}, "no-promise")
    twice = [dict(sh) for sh in d["shots"]]
    twice[4] = dict(twice[4], screen=twice[0]["screen"])
    assert "shots 01 and 05 show 01-home.jpg the same way" in render({}, "twice", twice)
    again = [dict(sh) for sh in d["shots"]]
    again[4] = dict(again[4], screen=again[2]["screen"])  # 03 zooms into stats, 05 shows the whole stats screen
    assert "shots 03 and 05 both use 03-stats.jpg" in render({}, "again", again)
    # Turkish suffixes after loanwords
    out = run(s("check_set.py"), os.path.join(tmp, "q", "good", "ios"), "--store", "ios", "--lang", "tr", "--headlines",
              "Carousel'ın hazır. Son söz sende.", "En iyi carousel'ler", "Hook'u sen değil, veri seçsin", "TikTok'ta ve Instagram'a")
    assert "Carousel'in" in out and out.count("suffix follows") == 1, out
    # thin demo data: one figure three times on a screen
    raw = os.path.join(tmp, "thin")
    os.makedirs(raw)
    im = Image.new("RGB", (1206, 2622), (246, 244, 240))
    dr = ImageDraw.Draw(im)
    sys.path.insert(0, SCRIPTS)
    import render_set as rs
    f = rs.Fonts(SKILL).get("text", 56)
    for i, (label, fig) in enumerate([("Hikaye", "48,2 B"), ("Liste", "11,8 B"), ("Grotesk", "48,2 B"),
                                      ("Teknik", "27,5 B"), ("Sekiller", "48,2 B")]):
        dr.text((90, 300 + i * 260), label, font=f, fill=(20, 20, 20))
        dr.text((860, 300 + i * 260), fig, font=f, fill=(20, 20, 20))
    im.save(os.path.join(raw, "01-analytics.png"))
    out = run(s("prepare_screens.py"), raw, "--out", os.path.join(tmp, "thin-out"), both=True)
    if shutil.which("tesseract"):
        assert "demo data looks thin" in out and "appears 3 times" in out, out
    else:
        assert "demo-data check skipped" in out, out
    out = run(s("prepare_screens.py"), os.path.join(ROOT, "examples", "seenfy", "screens"), "--out", os.path.join(tmp, "seenfy-prep"), both=True)
    assert "demo data looks thin" not in out, out  # real, varied data stays quiet


def frontmatter_test():
    """SKILL.md's frontmatter must parse as strict YAML: agents are lenient, but installers (npx skills, the
    claude.ai upload) skip a skill whose description holds an unquoted ": " or " #"."""
    text = open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8").read()
    assert text.startswith("---\n"), "SKILL.md must open with frontmatter"
    fm = text.split("---\n", 2)[1]
    keys = {}
    for line in fm.splitlines():
        if not line.strip():
            continue
        k, sep, v = line.partition(": ")
        assert sep and k.strip() in ("name", "description", "license", "metadata", "compatibility", "allowed-tools"), f"frontmatter line: {line[:80]}"
        v = v.strip()
        if not (v[:1] in "\"'" and v[-1:] == v[:1]):  # a plain scalar: no ": ", no " #", no leading indicator
            assert ": " not in v and " #" not in v and not v.endswith(":") and v[:1] not in "&*!|>%@`{[", f"{k}: needs quoting ({v[:60]}…)"
        keys[k.strip()] = v
    assert keys.get("name") == "store-screenshots", keys
    assert 0 < len(keys.get("description", "")) <= 1024, len(keys.get("description", ""))
    try:
        import yaml
    except ImportError:
        return
    data = yaml.safe_load(fm)
    assert data["name"] == "store-screenshots" and len(data["description"]) <= 1024


def main():
    frontmatter_test()
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
            assert "ranking, award, price" not in out, out  # "Popüler olanı değil" / "Not what's popular" are negated
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
        quality_tests(tmp)
        console_tests(tmp)
        design_tests(tmp)
        device3d_tests(tmp)
        guardrail_tests(tmp)
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
        assert "kusursuz" in out and "[Play recommendation] ranking" in out, out
    print("smoke test passed")


if __name__ == "__main__":
    main()
