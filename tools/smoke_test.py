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
        quality_tests(tmp)
        design_tests(tmp)
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
