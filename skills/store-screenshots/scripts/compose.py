#!/usr/bin/env python3
"""Render a design-driven set: every shot is a free composition (a scene), not a template.

  python3 compose.py render set.json --out out/                 # every locale x size; PNG + SVG + _render.json
  python3 compose.py render set.json --out out/ --size ios --shots promise collections
  python3 compose.py xray set.json --shot promise -o x.png      # layer boxes, roles, margins, seam, thumbnail
  python3 compose.py concepts a.json b.json c.json --board dna-board.jpg -o review.jpg   # the concept checkpoint
  python3 compose.py render set.json --out out/ --history       # opt-in: compare with your earlier sets, then log this one
  python3 compose.py history                                    # what the log holds (~/.store-screenshots/history.jsonl)

set.json (version 2) - see references/scene-format.md:
  {"version": 2, "evidence": "evidence.json", "campaign": {...} | "campaign.json",
   "locales": ["tr", "en"], "sizes": ["ios", "ios-large", "android"], "promise_words": [...],
   "concept": {"name": "...", "idea": "..."}, "dna": "dna.json",
   "shots": [{"id": "promise", "message": "...", "alt": "...", "proof": [{"evidence": "discover"}], "span": 1,
              "background": {"fill": "$surface"}, "layers": [ ... ]}],
   "feature_graphic": {"background": ..., "layers": [...]}}

Drawn with resvg (pip install resvg-py) when available, otherwise with the Pillow backend; the SVG is always
written next to the PNG so the set can be opened and edited in Figma or Illustrator. Every render runs the
scene checks (validate.py) and the store/set rules; check_set.py reads the results from _render.json.
"""
import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design  # noqa: E402
import render_set as rs  # noqa: E402
import scene as sc  # noqa: E402
import validate as va  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

FG = (1024, 500)


def load_json(path, base):
    p = path if os.path.isabs(path) else os.path.join(base, path)
    with open(p, encoding="utf-8") as f:
        return json.load(f), os.path.dirname(os.path.abspath(p))


def setup(spec_path):
    spec_dir = os.path.dirname(os.path.abspath(spec_path))
    with open(spec_path, encoding="utf-8") as f:
        raw = json.load(f)
    if raw.get("version") != 2:
        sys.exit("compose.py renders version-2 sets (scenes); use render_set.py for preset/direction specs")
    return raw, spec_dir


def context(spec, spec_dir, lang, fonts, preset=None, W=None, H=None):
    ev_ref = spec.get("evidence")
    if not ev_ref:
        raise sc.SceneError('the set needs "evidence": "evidence.json" (evidence.py build screens/)')
    evidence, ev_dir = load_json(ev_ref, spec_dir) if isinstance(ev_ref, str) else (ev_ref, spec_dir)
    camp = spec.get("campaign") or {}
    camp_dir = spec_dir
    if isinstance(camp, str):
        camp, camp_dir = load_json(camp, spec_dir)
    tokens = dict(design.tokens_from_brand(spec.get("brand") or camp.get("brand"))) if (spec.get("brand") or camp.get("brand")) else {}
    tokens.update({k: v for k, v in (camp.get("tokens") or {}).items() if isinstance(v, str)})
    fonts_abs = {}
    for k, v in (camp.get("fonts") or {}).items():
        fonts_abs[k] = v if (v in rs.FONT_ALIASES or os.path.isabs(v)) else os.path.join(camp_dir, v)
    camp = dict(camp, fonts=fonts_abs)
    dev = rs.device_class(preset, W, H) if preset else None
    dna = None
    if spec.get("dna"):  # the materials, palette and references the campaign is checked against
        dna = load_json(spec["dna"], spec_dir)[0] if isinstance(spec["dna"], str) else spec["dna"]
    return {"fonts": fonts, "lang": lang, "tokens": tokens, "campaign": camp, "evidence": evidence, "evidence_dir": ev_dir,
            "spec_dir": spec_dir, "preset": preset, "device": dev, "store": rs.store_of(preset, W, H) if preset else None,
            "dna": dna}


def shot_list(spec, name, W, H):
    shots = [sh for sh in spec.get("shots", []) if rs.keep_shot(sh, name, W, H)]
    return shots


def headlines_by_slot(scene):
    out = [[] for _ in range(scene.span)]
    subs = [[] for _ in range(scene.span)]
    for op in va.walk(scene.ops):
        m = op.get("meta", {})
        if op["op"] == "text" and m.get("role") in ("headline", "sub"):
            (out if m["role"] == "headline" else subs)[va.slot_of(scene, m["bbox"])].append(m["text"].replace("*", ""))
    return [" ".join(x) for x in out], [" ".join(x) for x in subs]


def proof_units(shot, scene):
    """For the repeat check: what each slot shows as proof (screen + crop)."""
    units = []
    for op in va.walk(scene.ops):
        m = op.get("meta", {})
        if op["op"] == "image" and m.get("kind") == "screen":
            units.append((va.slot_of(scene, m["bbox"]), m["evidence"], tuple(round(v, 3) for v in m["crop"])))
    return units


def render_shot(shot, W, H, ctx, backend, keep=None):
    scene = sc.Scene(shot, W, H, ctx).build()
    errs = va.truth_errors(scene)
    if errs:
        raise sc.SceneError("; ".join(errs))
    img, svg, used = sc.render(scene, ctx["fonts"], backend)
    warnings = list(scene.warnings) + va.scene_warnings(scene, img, ctx) + va.store_warnings(scene, ctx)
    if keep is not None:
        keep.update(scene=scene, svg=svg)
    return scene, img, svg, used, warnings


def cmd_render(a):
    raw, spec_dir = setup(a.spec)
    locales = raw.get("locales")
    runs = [(loc, os.path.join(a.out, loc)) for loc in locales] if locales else [(None, a.out)]
    if a.locale:
        runs = [r for r in runs if r[0] == a.locale] or sys.exit(f"locale {a.locale!r} not in {locales}")
    fonts = rs.Fonts(spec_dir)
    exit_code = 0
    logged = False
    if a.backend in ("auto", "svg") and not sc.have_resvg():
        msg = "resvg isn't installed (pip install resvg-py) - drawing with the Pillow backend"
        if a.backend == "svg":
            sys.exit(msg)
        print(f"! {msg}")
    for loc, out_root in runs:
        spec_l = rs.localize(raw, loc, locales) if loc else raw
        lang = loc.split("-")[0] if loc else spec_l.get("lang", "en")
        sizes = [a.size] if a.size else spec_l.get("sizes", rs.DEFAULT_SIZES)
        for name in sizes:
            W, H = rs.preset_size(name)
            spec = rs.resolve_variants(spec_l, name, W, H)
            try:
                ctx = context(spec, spec_dir, lang, fonts, name, W, H)
            except sc.SceneError as e:
                sys.exit(str(e))
            shots = shot_list(spec, name, W, H)
            if a.shots and not any(s.get("id") in a.shots for s in shots):
                sys.exit(f"no shot {a.shots} in this set: {', '.join(str(s.get('id')) for s in shots)}")
            out_dir = os.path.join(out_root, name)
            os.makedirs(out_dir, exist_ok=True)
            report = {"preset": name, "size": [W, H], "lang": lang, "locale": loc, "device": rs.device_class(name, W, H),
                      "store": rs.store_of(name, W, H), "renderer": "compose", "shots": [], "set_warnings": []}
            slot, fps, scenes, pseudo, units, contents = 0, [], [], [], [], []
            for i, shot in enumerate(shots, start=1):
                span = shot.get("span", 1)
                label = f"{slot + 1:02d}" + (f"-{slot + span:02d}" if span > 1 else "")
                if a.shots and shot.get("id") not in a.shots:  # keep the numbering of the whole set
                    slot += span
                    continue
                try:
                    scene, img, svg, used, warnings = render_shot(shot, W, H, ctx, a.backend)
                except (sc.SceneError, FileNotFoundError) as e:
                    print(f"x {loc or ''} {name} {label} ({shot.get('id', i)}): {e}", file=sys.stderr)
                    exit_code = 1
                    slot += span
                    continue
                scenes.append(scene)
                heads, subs = headlines_by_slot(scene)
                with open(os.path.join(out_dir, f"{label}.svg"), "w", encoding="utf-8") as f:
                    f.write(svg)
                for j in range(span):
                    slot += 1
                    piece = img.crop((j * W, 0, (j + 1) * W, H)) if span > 1 else img
                    piece.convert("RGB").save(os.path.join(out_dir, f"{slot:02d}.png"), optimize=True)
                    fps.append((f"{slot:02d}", va.fingerprint(scene, j)))
                    pseudo.append({"headline": heads[j]})
                    alt = shot.get("alt")
                    alt = alt[j] if isinstance(alt, list) and j < len(alt) else (alt if isinstance(alt, str) else None)
                    entry = {"file": f"{slot:02d}.png", "shot": shot.get("id", i), "headline": heads[j], "sub": subs[j],
                             "alt": alt, "layout": "scene", "backend": used, "warnings": warnings if j == 0 else []}
                    if span > 1:
                        entry["span"] = label
                    report["shots"].append(entry)
                for s_, ev_, crop_ in proof_units(shot, scene):
                    units.append((f"{slot - span + 1 + s_:02d}", ev_, crop_))
                for j in range(span):
                    words, evs = va.visible_words(scene, ctx, j)
                    contents.append((f"{slot - span + 1 + j:02d}", words, evs))
                for w in warnings:
                    print(f"! {loc or ''} {name} {label}: {w}")
            set_rules = []
            if not a.shots:  # set rules need the whole set
                set_rules = rs.set_warnings(shots, report["store"]) + va.set_warnings(fps) + va.headline_fonts(scenes)
                set_rules += rs.promise_warnings(pseudo, spec.get("promise_words"), lang)
                set_rules += repeat_units(units)
                set_rules += va.content_repeats(contents, ctx["evidence"])
                set_rules += va.campaign_material_warnings(ctx) + va.habit_warnings(scenes, ctx)
                set_rules += va.example_copies(shots, spec_dir)
                if a.history and not logged:
                    set_rules += history_warnings(raw, a.spec, scenes, ctx)
                    log_history(raw, a.spec, scenes, ctx, loc, name)
                    logged = True
                if report["device"] == "iphone" and not a.size:
                    set_rules += rs.iphone_size_warnings(sizes)
            for w in set_rules:
                report["set_warnings"].append(w)
                print(f"! {loc or ''} {name} set: {w}")
            rpath = os.path.join(out_dir, "_render.json")
            if a.shots and os.path.exists(rpath):  # a partial re-render keeps the rest of the set's report
                with open(rpath, encoding="utf-8") as f:
                    old = json.load(f)
                done = {e["shot"] for e in report["shots"]}
                report["shots"] = sorted([e for e in old.get("shots", []) if e["shot"] not in done] + report["shots"],
                                         key=lambda e: e["file"])
                report["set_warnings"] = old.get("set_warnings", [])
            with open(rpath, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=1)
            print(f"{(loc + ' ') if loc else ''}{name}: {len(report['shots'])} shots → {out_dir}")
        android = [n for n in sizes if rs.store_of(n, *rs.preset_size(n)) == "android"]
        if spec_l.get("feature_graphic") and (android or a.size is None) and not a.shots:
            fg_size = android[0] if android else "android"
            spec = rs.resolve_variants(spec_l, fg_size, *rs.preset_size(fg_size))
            ctx = context(spec, spec_dir, lang, fonts, fg_size, *rs.preset_size(fg_size))
            fg = dict(spec["feature_graphic"], id="feature-graphic", proof=spec["feature_graphic"].get("proof") or [{"evidence": "_"}])
            try:
                scene, img, svg, used, warnings = render_shot(fg, *FG, ctx, a.backend)
                if scene.c.W != FG[0] or scene.c.H != FG[1]:
                    raise sc.SceneError("feature graphic size")
                img.convert("RGB").save(os.path.join(out_root, "feature-graphic.png"), optimize=True)
                with open(os.path.join(out_root, "feature-graphic.svg"), "w", encoding="utf-8") as f:
                    f.write(svg)
                heads, subs = headlines_by_slot(scene)
                boxes = [{"role": op["meta"].get("role"), "kind": op["meta"].get("kind"), "bbox": [round(v, 1) for v in op["meta"]["bbox"]]}
                         for op in va.walk(scene.ops) if op.get("meta", {}).get("bbox") and op["meta"].get("role") in
                         ("headline", "sub", "display", "callout", "proof", "brand")]
                with open(os.path.join(out_root, "_feature-graphic.json"), "w", encoding="utf-8") as f:
                    json.dump({"headline": heads[0], "sub": subs[0], "lang": lang, "alt": fg.get("alt"), "size": list(FG),
                               "elements": boxes}, f, ensure_ascii=False, indent=1)
                for w in warnings:
                    if "no \"proof\"" not in w:
                        print(f"! {loc or ''} feature graphic: {w}")
                print(f"{(loc + ' ') if loc else ''}feature graphic → {os.path.join(out_root, 'feature-graphic.png')}")
            except sc.SceneError as e:
                print(f"x {loc or ''} feature graphic: {e}", file=sys.stderr)
                exit_code = 1
    sys.exit(exit_code)


# ------------------------------------------------------------------ history (opt-in)

def history_path():
    home = os.environ.get("STORE_SCREENSHOTS_HOME") or os.path.join(os.path.expanduser("~"), ".store-screenshots")
    return os.path.join(home, "history.jsonl")


def set_record(raw, spec_path, scenes, ctx):
    camp = ctx.get("campaign") or {}
    head = (camp.get("type") or {}).get("headline") or {}
    ground = None
    for op in scenes[0].ops if scenes else []:
        if op.get("meta", {}).get("role") == "background" and op["meta"].get("colors"):
            ground = op["meta"]["colors"][0][:7]
            break
    fps = []
    for scn in scenes:
        for j in range(scn.span):
            hb, vb = va.fingerprint(scn, j)
            fps.append([[round(v, 3) for v in hb] if hb else None, [round(v, 3) for v in vb] if vb else None])
    return {"time": datetime.datetime.now().isoformat(timespec="seconds"), "app": raw.get("app") or "",
            "spec": os.path.abspath(spec_path), "concept": (raw.get("concept") or {}).get("name") or "",
            "materials": sorted({m for scn in scenes for m, _, _ in va.materials_used(scn)}),
            "fonts": sorted({os.path.basename(str(v)) for v in (camp.get("fonts") or {}).values()}),
            "emphasis": (head.get("emphasis") or {}).get("style"), "ground": ground, "fingerprints": fps}


def read_history():
    p = history_path()
    if not os.path.exists(p):
        return []
    out = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def log_history(raw, spec_path, scenes, ctx, loc, preset):
    p = history_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    rec = dict(set_record(raw, spec_path, scenes, ctx), locale=loc, preset=preset)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def history_warnings(raw, spec_path, scenes, ctx):
    """Does this set look like one made earlier for another app? Same concept, faces, emphasis, ground,
    materials and compositions are what make a skill's output recognisable as the skill's."""
    me = set_record(raw, spec_path, scenes, ctx)
    out = []
    for rec in read_history():
        if rec.get("spec") == me["spec"] or (rec.get("app") and rec.get("app") == me["app"]):
            continue
        same = []
        if me["concept"] and rec.get("concept", "").lower() == me["concept"].lower():
            same.append("concept name")
        if me["fonts"] and rec.get("fonts") == me["fonts"]:
            same.append("fonts")
        if me["emphasis"] and rec.get("emphasis") == me["emphasis"]:
            same.append("emphasis device")
        if me["materials"] and rec.get("materials") == me["materials"]:
            same.append("materials (" + ", ".join(me["materials"]) + ")")
        if me["ground"] and rec.get("ground") and sum((x - y) ** 2 for x, y in zip(rs.hexrgb(me["ground"]), rs.hexrgb(rec["ground"]))) < 24 ** 2:
            same.append("ground colour")
        theirs = [tuple(tuple(b) if b else None for b in fp) for fp in rec.get("fingerprints") or []]
        mine = [tuple(tuple(b) if b else None for b in fp) for fp in me["fingerprints"]]
        alike = sum(1 for fp in mine if any(all((x is None and y is None) or (x and y and va.iou(x, y) > 0.7) for x, y in zip(fp, t))
                                            for t in theirs))
        if mine and alike / len(mine) >= 0.5:
            same.append(f"{alike} of {len(mine)} compositions")
        if len(same) >= 3:
            out.append(f"this set looks like your {rec.get('app') or os.path.basename(rec.get('spec', ''))!r} set from "
                       f"{rec.get('time', '')[:10]}, with the same {', '.join(same)} - a set should come from this app's DNA, not from "
                       "the last one")
    return out


def cmd_history(a):
    recs = read_history()
    if a.clear:
        if os.path.exists(history_path()):
            os.remove(history_path())
        print(f"cleared {history_path()}")
        return
    if not recs:
        print(f"no history yet ({history_path()}) - render with --history to start one")
        return
    for rec in recs[-a.last:]:
        print(f"{rec.get('time', '')[:16]}  {rec.get('app') or '?':<18} {rec.get('concept') or '-':<22} "
              f"{rec.get('emphasis') or '-':<10} {rec.get('ground') or '-':<8} {', '.join(rec.get('materials') or []) or 'flat'}  "
              f"[{', '.join(rec.get('fonts') or [])}]")
    print(f"{len(recs)} sets in {history_path()}")


def repeat_units(units):
    out, seen, by_ev = [], {}, {}
    for label, ev, crop in units:
        key = (ev, crop)
        if key in seen and seen[key] != label:
            out.append(f"shots {seen[key]} and {label} show {ev!r} with the same crop - each shot should prove something new")
            continue
        seen.setdefault(key, label)
        first = by_ev.setdefault(ev, label)
        if first != label and crop == (0.0, 0.0, 1.0, 1.0):
            out.append(f"shots {first} and {label} both show the whole {ev!r} screen - one proof shown twice")
    return sorted(set(out))


def one_scene(a, raw, spec_dir, shot_id=None, size=None, index=None):
    locales = raw.get("locales")
    loc = a.locale or (locales[0] if locales else None)
    spec_l = rs.localize(raw, loc, locales) if loc else raw
    lang = loc.split("-")[0] if loc else spec_l.get("lang", "en")
    name = size or a.size
    W, H = rs.preset_size(name)
    spec = rs.resolve_variants(spec_l, name, W, H)
    fonts = rs.Fonts(spec_dir)
    ctx = context(spec, spec_dir, lang, fonts, name, W, H)
    shots = shot_list(spec, name, W, H)
    if shot_id is not None:
        match = [s for s in shots if s.get("id") == shot_id]
        if not match:
            sys.exit(f"no shot {shot_id!r}: {', '.join(str(s.get('id')) for s in shots)}")
        shot = match[0]
    else:
        shot = shots[index]
    return shot, W, H, ctx


def cmd_xray(a):
    raw, spec_dir = setup(a.spec)
    shot, W, H, ctx = one_scene(a, raw, spec_dir, shot_id=a.shot)
    scene, img, svg, used, warnings = render_shot(shot, W, H, ctx, a.backend)
    sc.xray(img, scene, ctx).save(a.output)
    for w in warnings:
        print(f"! {w}")
    print(a.output)


def cmd_concepts(a):
    """One review image: the DNA board (optional) on top, then each concept's first shots, with its idea."""
    rows = []
    fonts_ui = rs.Fonts(HERE)
    for path in a.sets:
        raw, spec_dir = setup(path)
        locales = raw.get("locales")
        loc = a.locale or (locales[0] if locales else None)
        spec_l = rs.localize(raw, loc, locales) if loc else raw
        W, H = rs.preset_size(a.size)
        spec = rs.resolve_variants(spec_l, a.size, W, H)
        lang = loc.split("-")[0] if loc else spec.get("lang", "en")
        ctx = context(spec, spec_dir, lang, rs.Fonts(spec_dir), a.size, W, H)
        shots = shot_list(spec, a.size, W, H)[:a.count]
        thumbs = []
        for shot in shots:
            try:
                scene, img, svg, used, warnings = render_shot(shot, W, H, ctx, a.backend)
            except sc.SceneError as e:
                print(f"x {path} {shot.get('id')}: {e}", file=sys.stderr)
                continue
            for w in warnings:
                print(f"! {os.path.basename(path)} {shot.get('id')}: {w}")
            for j in range(scene.span):
                piece = img.crop((j * W, 0, (j + 1) * W, H)) if scene.span > 1 else img
                thumbs.append(piece.resize((a.width, round(H * a.width / W)), Image.LANCZOS))
        concept = spec.get("concept") or {}
        rows.append((concept.get("name") or os.path.basename(path), concept.get("idea", ""), thumbs))
    gap = 22
    th = max((t.height for r in rows for t in r[2]), default=200)
    cols = max(len(r[2]) for r in rows) if rows else 1
    W_sheet = gap + cols * (a.width + gap)
    fb, fr = fonts_ui.get("sans-bold", 28), fonts_ui.get("text", 19)

    def wrap_idea(text):
        lines, line = [], ""
        for w in text.split():
            if line and fr.getlength(line + " " + w) > W_sheet - 2 * gap:
                lines.append(line)
                line = w
            else:
                line = (line + " " + w).strip()
        return lines + ([line] if line else [])
    wrapped = [wrap_idea(idea) for _, idea, _ in rows]
    label_hs = [48 + 24 * len(w) + 10 for w in wrapped]
    board = Image.open(a.board).convert("RGB") if a.board else None
    if board:
        board = board.resize((W_sheet - 2 * gap, round(board.height * (W_sheet - 2 * gap) / board.width)), Image.LANCZOS)
    top = (board.height + 2 * gap) if board else 0
    sheet = Image.new("RGB", (W_sheet, top + gap + sum(th + lh + gap for lh in label_hs)), (241, 239, 235))
    if board:
        sheet.paste(board, (gap, gap))
    d = ImageDraw.Draw(sheet)
    y = top + gap
    for k, ((name, idea, thumbs), lines, label_h) in enumerate(zip(rows, wrapped, label_hs)):
        d.text((gap, y + 4), f"{chr(65 + k)} — {name}", font=fb, fill=(20, 20, 20))
        for i, line in enumerate(lines):
            d.text((gap, y + 44 + 24 * i), line, font=fr, fill=(80, 80, 80))
        x = gap
        for t in thumbs:
            sheet.paste(t, (x, y + label_h))
            x += a.width + gap
        y += th + label_h + gap
    sheet.save(a.output, quality=88)
    print(a.output)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render", help="render every locale and size of a set")
    r.add_argument("spec")
    r.add_argument("--out", default="out")
    r.add_argument("--size")
    r.add_argument("--locale")
    r.add_argument("--shots", nargs="+", help="only these shot ids")
    r.add_argument("--backend", choices=["auto", "svg", "pillow"], default="auto")
    r.add_argument("--history", action="store_true", help="opt-in: warn if this set looks like an earlier one for another "
                   "app, then log it (~/.store-screenshots/history.jsonl, or $STORE_SCREENSHOTS_HOME)")
    hi = sub.add_parser("history", help="list the sets logged with --history")
    hi.add_argument("--last", type=int, default=20)
    hi.add_argument("--clear", action="store_true", help="delete the log")
    x = sub.add_parser("xray", help="one shot with layer boxes, roles, margins and a thumbnail inset")
    x.add_argument("spec")
    x.add_argument("--shot", required=True)
    x.add_argument("--size", default="ios")
    x.add_argument("--locale")
    x.add_argument("--backend", choices=["auto", "svg", "pillow"], default="auto")
    x.add_argument("-o", "--output", default="xray.png")
    c = sub.add_parser("concepts", help="the concept checkpoint: first shots of each concept (+ the DNA board)")
    c.add_argument("sets", nargs="+")
    c.add_argument("--board", help="dna-board image to put on top (dna.py board)")
    c.add_argument("--count", type=int, default=3, help="shots per concept (spec entries)")
    c.add_argument("--size", default="ios")
    c.add_argument("--locale")
    c.add_argument("--width", type=int, default=250)
    c.add_argument("--backend", choices=["auto", "svg", "pillow"], default="auto")
    c.add_argument("-o", "--output", default="review.jpg")
    a = p.parse_args()
    {"render": cmd_render, "xray": cmd_xray, "concepts": cmd_concepts, "history": cmd_history}[a.cmd](a)


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):  # Windows consoles and pipes default to a legacy code page
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    main()
