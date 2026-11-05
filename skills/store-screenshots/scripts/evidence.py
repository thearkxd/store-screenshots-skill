#!/usr/bin/env python3
"""The evidence manifest: the only pixels of the app a scene may show, and the text on them.

  python3 evidence.py build screens/ --assets icon.png photo.jpg -o evidence.json   # register screens + assets
  python3 evidence.py show evidence.json discover -o discover.grid.png               # grid + OCR boxes, to read crops
  python3 evidence.py name evidence.json discover match-badge 0.06,0.18,0.5,0.24     # name a region (and read its text)
  python3 evidence.py name evidence.json discover pick-card 0.02,0.2,0.98,0.6 --snap # ...tightened to the card inside, radius kept

Every raw screen gets an id (from its file name), its size, a SHA-256 of the file (scenes are checked against
it, so an edited screen is caught) and - when tesseract is installed - the words on it with their boxes, so
headline numbers and claims can be checked against what the app really shows. Assets are brand images that
aren't UI (icon, logo, product photo). Nothing else may appear as app UI in a scene.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
EXT = re.compile(r"\.(png|jpe?g|webp)$", re.I)
FONT = os.path.normpath(os.path.join(HERE, "..", "assets", "fonts", "InterDisplay-SemiBold.otf"))


def find_tesseract():
    """tesseract on PATH, or where the Windows installer puts it (then PATH is extended for this process)."""
    import shutil
    exe = shutil.which("tesseract")
    if exe or os.name != "nt":
        return exe
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                 os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")):
        cand = os.path.join(base, "Tesseract-OCR", "tesseract.exe")
        if os.path.exists(cand):
            os.environ["PATH"] = os.path.dirname(cand) + os.pathsep + os.environ.get("PATH", "")
            return cand
    return None


TESSERACT_HINT = ("install tesseract with Turkish: Windows - winget install --id tesseract-ocr.tesseract, then tur.traineddata "
                  "from github.com/tesseract-ocr/tessdata into C:\\Program Files\\Tesseract-OCR\\tessdata; "
                  "macOS - brew install tesseract tesseract-lang; Linux - apt install tesseract-ocr tesseract-ocr-tur")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def slug(name):
    s = re.sub(r"[^a-z0-9]+", "-", os.path.splitext(os.path.basename(name))[0].lower()).strip("-")
    return re.sub(r"^\d+-", "", s) or s


def tesseract():
    exe = find_tesseract()
    if not exe:
        return None, None
    try:
        langs = subprocess.run([exe, "--list-langs"], capture_output=True, encoding="utf-8", errors="replace", timeout=20).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return None, None
    return exe, "+".join(l for l in ("eng", "tur") if l in langs) or None


def ocr_words(path, exe, langs):
    im = Image.open(path).convert("L")
    k = 2 if im.width < 1400 else 1
    if k > 1:
        im = im.resize((im.width * k, im.height * k))
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "s.png")
        im.save(p)
        try:
            out = subprocess.run([exe, p, "-", "-l", langs, "--psm", "11", "tsv"], capture_output=True, encoding="utf-8", errors="replace", timeout=180).stdout
        except (OSError, subprocess.SubprocessError):
            return []
    words = []
    for line in out.splitlines()[1:]:
        f = line.split("\t")
        if len(f) < 12 or not f[11].strip():
            continue
        try:
            conf = float(f[10])
        except ValueError:
            continue
        if conf < 40:
            continue
        x, y, w, h = (int(v) for v in f[6:10])
        W, H = im.size
        words.append({"t": f[11].strip(), "b": [round(x / W, 4), round(y / H, 4), round((x + w) / W, 4), round((y + h) / H, 4)],
                      "c": round(conf)})
    return words


def region_ocr(path, box, exe, langs):
    """The words in one region, read at 3x (small UI text - a badge, a chip - is often missed on the whole screen)."""
    im = Image.open(path).convert("L")
    W, H = im.size
    piece = im.crop((round(box[0] * W), round(box[1] * H), round(box[2] * W), round(box[3] * H)))
    piece = piece.resize((piece.width * 3, piece.height * 3), Image.LANCZOS)
    if piece.resize((1, 1)).getpixel((0, 0)) < 128:  # light text on a dark UI reads better inverted
        piece = Image.eval(piece, lambda v: 255 - v)
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "r.png")
        piece.save(p)
        try:
            out = subprocess.run([exe, p, "-", "-l", langs, "--psm", "6"], capture_output=True, encoding="utf-8", errors="replace", timeout=60).stdout
        except (OSError, subprocess.SubprocessError):
            return ""
    return " ".join(out.split())


def build(a):
    out_dir = os.path.dirname(os.path.abspath(a.output))
    old = {}
    if os.path.exists(a.output):
        with open(a.output, encoding="utf-8") as f:
            old = json.load(f)
    files = []
    for i in a.inputs:
        files += sorted(os.path.join(i, f) for f in os.listdir(i) if EXT.search(f)) if os.path.isdir(i) else [i]
    if not files:
        sys.exit("no screens found")
    exe, langs = (None, None) if a.no_ocr else tesseract()
    ev = {"_doc": "Evidence manifest (evidence.py). Scenes may show only these screens and assets. Paths are relative to this file.",
          "screens": {}, "assets": {}}
    seen = set()

    def add(path, pool):
        sid = slug(path)
        base = sid
        n = 2
        while sid in seen:
            sid = f"{base}-{n}"
            n += 1
        seen.add(sid)
        im = Image.open(path)
        item = {"path": os.path.relpath(os.path.abspath(path), out_dir), "size": list(im.size), "sha256": sha256(path)}
        prev = old.get(pool, {}).get(sid, {})
        if prev.get("regions"):
            item["regions"] = prev["regions"]  # keep names given earlier
            if prev.get("region_text") and prev.get("sha256") == item["sha256"]:
                item["region_text"] = prev["region_text"]
            elif pool == "screens" and exe and langs:
                item["region_text"] = {k: region_ocr(path, b, exe, langs) for k, b in prev["regions"].items()}
        if pool == "screens" and exe and langs:
            words = ocr_words(path, exe, langs)
            item["ocr"] = words
            item["text"] = " ".join(w["t"] for w in words)
        ev[pool][sid] = item
        return sid
    for f in files:
        sid = add(f, "screens")
        it = ev["screens"][sid]
        print(f"screen {sid:24} {it['size'][0]}x{it['size'][1]}  {len(it.get('ocr', []))} words")
    for f in a.assets or []:
        sid = add(f, "assets")
        print(f"asset  {sid:24} {ev['assets'][sid]['size'][0]}x{ev['assets'][sid]['size'][1]}")
    if not (exe and langs) and not a.no_ocr:
        print("(no tesseract: words not recorded - headline numbers, repeated content and sliced words can't be checked "
              "against the screens; " + TESSERACT_HINT + ")")
    elif exe and langs and "tur" not in langs.split("+") and not a.no_ocr:
        print("(tesseract has no Turkish data, so Turkish words are misread - " + TESSERACT_HINT + ")")
    with open(a.output, "w", encoding="utf-8") as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print(f"→ {a.output}")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def show(a):
    ev = load(a.manifest)
    base = os.path.dirname(os.path.abspath(a.manifest))
    item = ev["screens"].get(a.id) or ev["assets"].get(a.id)
    if not item:
        sys.exit(f"{a.id!r} not in the manifest: {', '.join(list(ev['screens']) + list(ev['assets']))}")
    im = Image.open(os.path.join(base, item["path"])).convert("RGB")
    W, H = im.size
    d = ImageDraw.Draw(im, "RGBA")
    f = ImageFont.truetype(FONT, max(12, W // 70)) if os.path.exists(FONT) else ImageFont.load_default()
    for i in range(1, 20):
        x, y = W * i / 20, H * i / 20
        strong = i % 2 == 0
        d.line([(x, 0), (x, H)], fill=(255, 40, 120, 150 if strong else 60), width=2 if strong else 1)
        d.line([(0, y), (W, y)], fill=(255, 40, 120, 150 if strong else 60), width=2 if strong else 1)
        if strong:
            d.text((x + 3, 3), f"{i / 20:.1f}", font=f, fill=(255, 40, 120, 255))
            d.text((3, y + 3), f"{i / 20:.1f}", font=f, fill=(255, 40, 120, 255))
    for w in item.get("ocr", []):
        b = w["b"]
        d.rectangle([b[0] * W, b[1] * H, b[2] * W, b[3] * H], outline=(40, 200, 255, 200), width=1)
    for name, b in (item.get("regions") or {}).items():
        d.rectangle([b[0] * W, b[1] * H, b[2] * W, b[3] * H], outline=(255, 220, 0, 255), width=3)
        d.text((b[0] * W + 4, b[1] * H + 2), name, font=f, fill=(255, 220, 0, 255))
    out = a.output or os.path.splitext(item["path"])[0] + ".grid.png"
    im.save(out)
    print(out)


def snap(path, box, tol=7, full=False):
    """Tighten a rough box to the component inside it - the pixels that differ from the background around
    it - and measure the component's corner radius. -> (box as fractions, radius in source px)."""
    from PIL import ImageChops
    im = Image.open(path).convert("RGB")
    W, H = im.size
    x0, y0, x1, y1 = (int(round(v)) for v in (box[0] * W, box[1] * H, box[2] * W, box[3] * H))
    x1, y1 = min(W, max(x1, x0 + 2)), min(H, max(y1, y0 + 2))
    border = ([im.getpixel((x, y0)) for x in range(x0, x1)] + [im.getpixel((x, y1 - 1)) for x in range(x0, x1)]
              + [im.getpixel((x0, y)) for y in range(y0, y1)] + [im.getpixel((x1 - 1, y)) for y in range(y0, y1)])
    bg = tuple(sorted(p[k] for p in border)[len(border) // 2] for k in range(3))
    piece = im.crop((x0, y0, x1, y1))
    r, g, b = ImageChops.difference(piece, Image.new("RGB", piece.size, bg)).split()
    mask = ImageChops.lighter(r, ImageChops.lighter(g, b)).point(lambda v: 255 if v > tol else 0)
    w, h = mask.size
    px = mask.load()
    def flat(im):
        return list(im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata())
    rows = [v / 255 * w for v in flat(mask.resize((1, h), Image.BOX))]
    cols = [v / 255 * h for v in flat(mask.resize((w, 1), Image.BOX))]
    # a component with its own background fills most of each row and column it spans; plain content (text,
    # an icon) doesn't - then its ink is the component
    kind = "component"
    ys = [y for y, n in enumerate(rows) if n >= 0.25 * w]
    xs = [x for x, n in enumerate(cols) if n >= 0.25 * h]
    if not ys or not xs:
        kind = "content"
        ys = [y for y, n in enumerate(rows) if n >= max(3, 0.02 * w)]
        xs = [x for x, n in enumerate(cols) if n >= max(3, 0.02 * h)]
    if not ys or not xs:
        return (box, 0.0, None) if full else (box, 0.0)
    tx0, tx1, ty0, ty1 = xs[0], xs[-1] + 1, ys[0], ys[-1] + 1
    radii = []
    for cx, cy, sx, sy in ((tx0, ty0, 1, 1), (tx1 - 1, ty0, -1, 1), (tx0, ty1 - 1, 1, -1), (tx1 - 1, ty1 - 1, -1, -1)):
        for k in range(0, min(tx1 - tx0, ty1 - ty0) // 2):
            if px[cx + sx * k, cy + sy * k]:
                radii.append(k / (1 - 2 ** -0.5))
                break
    radius = sorted(radii)[len(radii) // 2] if radii else 0.0
    out = [round((x0 + tx0) / W, 4), round((y0 + ty0) / H, 4), round((x0 + tx1) / W, 4), round((y0 + ty1) / H, 4)]
    radius = round(radius if radius >= 2 else 0.0, 1)
    if kind == "component":  # a card is filled with its own background; bars and text inside a bigger card aren't
        inner = mask.crop((tx0, ty0, tx1, ty1)).resize((1, 1), Image.BOX)
        fill = (inner.get_flattened_data() if hasattr(inner, "get_flattened_data") else inner.getdata())[0] / 255
        if fill < 0.8:
            kind = "content"
    return (out, radius, kind) if full else (out, radius)


def name(a):
    ev = load(a.manifest)
    item = ev["screens"].get(a.id)
    if not item:
        sys.exit(f"screen {a.id!r} not in the manifest")
    box = [float(v) for v in a.box.split(",")]
    if len(box) != 4 or not (0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1):
        sys.exit("box: x0,y0,x1,y1 as fractions, x0 < x1, y0 < y1")
    base = os.path.dirname(os.path.abspath(a.manifest))
    path = item["path"] if os.path.isabs(item["path"]) else os.path.join(base, item["path"])
    radius = None
    if a.snap:
        box, radius = snap(path, box)
    item.setdefault("regions", {})[a.name] = box
    if radius is not None:
        item.setdefault("region_radius", {})[a.name] = radius
    exe, langs = tesseract()
    text = ""
    if exe and langs:
        text = region_ocr(path, box, exe, langs)
        item.setdefault("region_text", {})[a.name] = text
    with open(a.manifest, "w", encoding="utf-8") as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print(f"{a.id}#{a.name} = {box}" + (f"  corner radius {radius:g}px" if radius else "") + (f"  reads: {text!r}" if text else ""))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="register raw screens (and brand assets)")
    b.add_argument("inputs", nargs="+")
    b.add_argument("--assets", nargs="*")
    b.add_argument("-o", "--output", default="evidence.json")
    b.add_argument("--no-ocr", action="store_true")
    s = sub.add_parser("show", help="grid + OCR boxes + named regions on one screen")
    s.add_argument("manifest")
    s.add_argument("id")
    s.add_argument("-o", "--output")
    n = sub.add_parser("name", help="name a region of a screen (fractions x0,y0,x1,y1)")
    n.add_argument("manifest")
    n.add_argument("id")
    n.add_argument("name")
    n.add_argument("box")
    n.add_argument("--snap", action="store_true", help="tighten the box to the component inside it and record its corner "
                   "radius - for anything you'll lift or show as a card")
    a = p.parse_args()
    {"build": build, "show": show, "name": name}[a.cmd](a)


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):  # Windows consoles and pipes default to a legacy code page
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    main()
