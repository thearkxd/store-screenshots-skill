#!/usr/bin/env python3
"""Check a finished screenshot set against store rules and copy rules. Requires Pillow.

  python3 check_set.py out/ios --store ios --lang tr
  python3 check_set.py out/android --store android --lang en
  python3 check_set.py out/duo-inner --store duo
  python3 check_set.py my-pngs/ --store ios --headlines "Line one" "Line two" ...

Reads headlines from _render.json (written by render_set.py) or --headlines. Writes into the folder:
  _search-preview.jpg   shots 1-3 at search-result size, next to each other (look at it!)
  _overview.jpg         the whole set at a glance
Exit code 1 if there are errors (size/alpha/count), 0 otherwise (warnings don't fail).
"""
import argparse
import glob
import json
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_set import PLAY_PROMO, PLAY_REC, PLAY_REQ  # noqa: E402

PLAY_LEGEND = (f"{PLAY_REQ}: the listing can be removed or suspended. {PLAY_REC}: the listing still publishes, but Google "
               f"may change how the assets appear or limit promotion. {PLAY_PROMO}: required only to appear in Play's "
               "screenshot-based recommendation formats. (support.google.com/googleplay/android-developer/answer/9866151)")
ALT_MAX = 140  # Play: alt text "using 140 characters or less"

IOS_SIZES = {(1398, 2034), (2007, 2853), (1260, 2736), (1290, 2796), (1320, 2868), (1179, 2556), (1206, 2622),
             (1284, 2778), (1242, 2688), (1170, 2532), (1125, 2436), (1080, 2340), (1242, 2208), (750, 1334),
             (640, 1096), (640, 1136), (640, 920), (640, 960)}
IOS_REQUIRED = {(1179, 2556), (1206, 2622)}                       # Dynamic Island medium
IOS_LARGE = {(1260, 2736), (1290, 2796), (1320, 2868), (1284, 2778), (1242, 2688)}  # DI large / Face ID large
DUO_SIZES = {(1398, 2034), (2007, 2853)}                           # iPhone Duo outer / inner
IPAD_SIZES = {(2064, 2752), (2048, 2732), (1488, 2266), (1668, 2420), (1668, 2388), (1640, 2360), (1668, 2224),
              (1536, 2008), (1536, 2048), (768, 1004), (768, 1024)}

BANNED = {
    "en": ["seamless", "effortless", "unlock", "elevate", "empower", "revolutioniz", "supercharge", "unleash",
           "harness", "next-level", "next level", "game-changer", "game changer", "cutting-edge", "state-of-the-art",
           "world-class", "ultimate", "immersive", "stunning", "magical", "like never before", "all-in-one",
           "all in one", "ai-powered", "ai powered", "intuitive", "user-friendly", "user friendly", "powerful",
           "discover the power", "experience the", "your journey", "at your fingertips", "amazing", "awesome"],
    "tr": ["kusursuz", "zahmetsiz", "yeni nesil", "yeniden keşfet", "potansiyel", "sınırları zorla", "fark yarat",
           "her şey tek", "tek uygulamada", "hayatını kolaylaştır", "hayatınızı kolaylaştır", "yapay zekâ destekli",
           "yapay zeka destekli", "benzersiz", "eşsiz", "üst düzey", "en iyi", "kullanıcı dostu", "keyifli hale",
           "artık çok kolay", "yenilendi", "yeniledik"],
}
PLAY_FORBIDDEN = [r"#\s?1\b", r"\bno\.?\s?1\b", r"\bbest\b", r"\bapp of the year\b", r"\bpopular\b", r"\btop[- ]rated\b",
                  r"\d+\s?%\s?(off|indirim)", r"\bfree\b", r"\bücretsiz\b", r"\bindirim\b", r"\bdiscount\b",
                  r"[$€£₺]\s?\d", r"\d\s?(tl|₺)\b", r"\baward", r"\bödül", r"\ben iyi\b", r"\bpopüler\b"]
PLAY_FORBIDDEN += [r"\btop\s?\d+\b", r"\btop[- ](app|charts?|seller|grossing)", r"\bsale\b", r"\bkampanya",
                   r"\bmillion downloads\b", r"\b\d+([.,]\d+)?\s?(m|k|million|milyon|bin)\+?\s?(downloads?|installs?|users?|indirme|kullanıcı)",
                   r"\bnew!", r"\b(all[- ]|brand[- ])?new\s+(app|feature|version|update|look)\b",
                   r"\byeni!", r"\byeni\s+(uygulama|özellik|sürüm|versiyon|güncelleme|tasarım)"]
RANKING = {r"\bbest\b", r"\bpopular\b", r"\ben iyi\b", r"\bpopüler\b", r"\btop[- ]rated\b"}
PLAY_CTA = [r"\b(download|install|play|try|get)\s+(it\s+)?now\b", r"\b(hemen|şimdi)\s+(indir|yükle|dene|oyna|kaydol|üye ol)",
            r"\b(indir|yükle)\s+(hemen|şimdi)\b"]
TESTIMONIAL = r'^\s*["“„«‘\'].+["”»’\']\s*$|[★⭐]|\b5\s?(stars?|yıldız)\b'
NEGATION = r"\b(not|no|never|isn't|aren't|değil|olmayan|yerine)\b"
EN_STOP = {"the", "and", "your", "you", "with", "for", "to", "in", "on", "all", "get", "of", "every", "from"}
TR_CHARS = set("şğıİŞĞçÇöÖüÜ")


def font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf",
              "C:/Windows/Fonts/arial.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def has_alpha(im):
    return im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)


def is_title_case(h):
    words = [w for w in re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü']+", h) if len(w) > 3]
    return len(words) >= 3 and all(w[0].isupper() for w in words) and not h.isupper()


# Turkish suffixes after a foreign word follow how it is SAID: carousel ("karusel") -> carousel'in, carousel'ler;
# hook ("huk") -> hook'u; TikTok'ta, Instagram'a, YouTube'da. Last vowel of the pronunciation:
LOANWORDS = {"carousel": "e", "karusel": "e", "hook": "u", "story": "i", "stories": "i", "reels": "i", "feed": "i",
             "post": "o", "tiktok": "o", "instagram": "a", "youtube": "u", "netflix": "i", "spotify": "ı",
             "iphone": "o", "google": "ı", "app": "e", "web": "e", "link": "i", "playlist": "i", "widget": "ı"}
TR_VOWELS = "aeıioöuü"


def tr_lower(text):
    return text.replace("I", "ı").replace("İ", "i").lower()


def harmonize(prev, suffix):
    """Rewrite a suffix's vowels by Turkish vowel harmony after a word whose last vowel is `prev`."""
    out = []
    for ch in suffix:
        if ch in "ae":
            ch = "e" if prev in "eiöü" else "a"
        elif ch in "ıiuü":
            ch = {"e": "i", "i": "i", "ö": "ü", "ü": "ü", "a": "ı", "ı": "ı", "o": "u", "u": "u"}[prev]
        if ch in TR_VOWELS:
            prev = ch
        out.append(ch)
    return "".join(out)


def suffix_checks(h):
    out = []
    for m in re.finditer(r"([A-Za-zÇĞİÖŞÜçğıöşü]+)['’]([a-zçğıöşüA-ZÇĞİÖŞÜ]+)", h):
        word, suf = m.group(1), m.group(2)
        last = LOANWORDS.get(tr_lower(word))
        if not last:
            continue
        good = harmonize(last, tr_lower(suf))
        if good != tr_lower(suf):
            out.append(f"\"{word}'{suf}\" - the suffix follows how the word is said: {word}'{good}")
    return out


def copy_checks(h, lang, store):
    out = []
    low = h.lower()
    n = len(h.split())
    if n > 7:
        out.append(f"{n} words - aim for 3-6")
    for w in BANNED["en"] + (BANNED["tr"] if lang == "tr" else []):
        if w in low:
            out.append(f"banned/tired phrase: '{w}'")
    if h.count("!") >= 1:
        out.append("exclamation mark")
    if is_title_case(h):
        out.append("Title Case slogan - use sentence case")
    if lang == "tr" and h and not any(c in TR_CHARS for c in h) and set(re.findall(r"[a-z]+", low)) & EN_STOP:
        out.append("looks English in a Turkish set")
    if lang == "tr":
        out += suffix_checks(h)
    if store == "android":
        for pat in PLAY_FORBIDDEN:
            m = re.search(pat, low)
            if not m:
                continue
            # "not what's popular", "popüler olanı değil" are the opposite of a ranking claim
            ctx = low[max(0, m.start() - 16): m.end() + 22]
            if pat in RANKING and re.search(NEGATION, ctx):
                continue
            out.append(f"{PLAY_REC} ranking, award, price or promotion wording (matches {pat!r}) - Google's guidelines say "
                       "to leave it out of preview assets")
            break
        if any(re.search(p_, low) for p_ in PLAY_CTA):
            out.append(f"{PLAY_REC} call to action (\"download now\", \"hemen indir\"…) - Google's guidelines say to leave them out")
        if re.search(TESTIMONIAL, h):
            out.append(f"{PLAY_REC} looks like a user testimonial or rating - Google's guidelines advise against them in screenshots")
    return out


def ground_colour(im):
    """The colour that dominates the graphic's border - its ground."""
    rgb = im.convert("RGB")
    w, h = rgb.size
    px = [rgb.getpixel((x, y)) for x in range(0, w, 8) for y in (2, h - 3)] + [rgb.getpixel((x, y)) for y in range(0, h, 8) for x in (2, w - 3)]
    q = {}
    for p in px:
        k = tuple(v // 8 * 8 for v in p)
        q[k] = q.get(k, 0) + 1
    k, n = max(q.items(), key=lambda kv: kv[1])
    return tuple(min(255, v + 4) for v in k) if n / len(px) >= 0.45 else None


def plain_ground(rgb):
    lo, hi = min(rgb), max(rgb)
    if hi - lo > 14:
        return False  # a colour, not white/black/gray
    return hi >= 245 or hi <= 70  # pure white, black or dark gray


FG_MARGIN = (0.07, 0.06)  # sides, top/bottom - the skill's reading of Google's cutoff-zone picture


def fg_zone_checks(fgd):
    """Google: keep the focal point towards the centre and key elements (logo, app name, slogan, main UI) out of
    the cutoff zones. It shows the zones only as a picture, without numbers, so the check keeps key elements out
    of the outer 7% at the sides and 6% at top and bottom."""
    W, H = fgd.get("size") or (1024, 500)
    mx, my = FG_MARGIN
    out = []
    for el in fgd.get("elements") or []:
        x0, y0, x1, y1 = el["bbox"]
        if el.get("role") in ("headline", "brand", "callout") or el.get("kind") == "screen":
            if x0 < mx * W - 1 or x1 > (1 - mx) * W + 1 or y0 < my * H - 1 or y1 > (1 - my) * H + 1:
                what = "the main UI" if el.get("kind") == "screen" else f"the {el.get('role')}"
                out.append(f"{PLAY_REC} feature graphic: {what} reaches into the cutoff zone near the edge - keep key elements "
                           f"towards the centre (out of the outer {mx:.0%} at the sides, {my:.0%} at top and bottom); Google says "
                           "missing the focal-point and cutoff-zone guidance can make the graphic ineligible for formats that crop it")
    return sorted(set(out))


def sibling_sizes(folder):
    """Screenshot sizes in the folders next to this one (render_set writes one folder per size)."""
    sizes = set()
    parent = os.path.dirname(os.path.abspath(folder))
    for d in glob.glob(os.path.join(parent, "*")):
        if not os.path.isdir(d) or os.path.abspath(d) == os.path.abspath(folder):
            continue
        rp = os.path.join(d, "_render.json")
        if os.path.exists(rp):
            try:
                with open(rp, encoding="utf-8") as f:
                    w, h = json.load(f)["size"]
                sizes.add((min(w, h), max(w, h)))
                continue
            except (KeyError, ValueError, TypeError):
                pass
        pngs = sorted(glob.glob(os.path.join(d, "[0-9]*.png")))
        if pngs:
            w, h = Image.open(pngs[0]).size
            sizes.add((min(w, h), max(w, h)))
    return sizes


def sheet(files, width, label, out, cols=None, gap=16):
    ims = []
    for f in files:
        im = Image.open(f).convert("RGB")
        ims.append(im.resize((width, round(im.height * width / im.width)), Image.LANCZOS))
    if not ims:
        return
    cols = cols or len(ims)
    rows = (len(ims) + cols - 1) // cols
    h = max(i.height for i in ims)
    W = gap + cols * (width + gap)
    canvas = Image.new("RGB", (W, 56 + rows * (h + gap)), (242, 242, 240))
    d = ImageDraw.Draw(canvas)
    d.text((gap, 16), label, fill=(60, 60, 60), font=font(18))
    for k, im in enumerate(ims):
        x = gap + (k % cols) * (width + gap)
        y = 50 + (k // cols) * (h + gap)
        canvas.paste(im, (x, y))
    canvas.save(out, quality=88)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("folder")
    p.add_argument("--store", choices=["ios", "duo", "ipad", "android"], default="ios")
    p.add_argument("--lang", choices=["tr", "en", "other"], default=None)
    p.add_argument("--headlines", nargs="+", help="headlines in order, if there is no _render.json")
    a = p.parse_args()

    files = sorted(f for f in glob.glob(os.path.join(a.folder, "*")) if re.search(r"\.(png|jpe?g)$", f, re.I)
                   and not os.path.basename(f).startswith("_"))
    if not files:
        sys.exit(f"no PNG/JPG files in {a.folder}")
    render = {}
    rp = os.path.join(a.folder, "_render.json")
    if os.path.exists(rp):
        with open(rp, encoding="utf-8") as f:
            render = json.load(f)
    lang = a.lang or render.get("lang", "en")
    heads = a.headlines or [s["headline"] for s in render.get("shots", [])]
    errors, warns = [], []

    # count
    limit = 8 if a.store == "android" else 10
    if len(files) > limit:
        errors.append(f"{PLAY_REQ + ' ' if a.store == 'android' else ''}{len(files)} screenshots - {a.store} allows at most {limit}"
                      f"{' per device type' if a.store == 'android' else ''}")
    if a.store == "android" and len(files) < 2:
        warns.append(f"{PLAY_REQ} fewer than 2 screenshots - Play needs at least two (across device types) to publish the listing")
    if a.store == "android" and len(files) < 4:
        warns.append(f"{PLAY_PROMO} fewer than 4 screenshots - apps need at least four (games three) to appear in "
                     "screenshot-based recommendation formats")
    if len(files) < 3:
        warns.append("fewer than 3 screenshots: search results will look empty")
    if a.store == "android":
        fg = next((p for p in (os.path.join(a.folder, "feature-graphic.png"),
                               os.path.join(os.path.dirname(os.path.abspath(a.folder)), "feature-graphic.png")) if os.path.exists(p)), None)
        if not fg:
            warns.append(f"{PLAY_REQ} no feature-graphic.png - Play needs a 1024x500 feature graphic to publish; add "
                         "\"feature_graphic\" to the spec")
        else:
            im = Image.open(fg)
            if im.size != (1024, 500):
                errors.append(f"{PLAY_REQ} feature graphic is {im.size[0]}x{im.size[1]}, must be 1024x500")
            if has_alpha(im):
                errors.append(f"{PLAY_REQ} feature graphic has an alpha channel (JPEG or 24-bit PNG)")
            ground = ground_colour(im)
            if ground and plain_ground(ground):
                warns.append(f"{PLAY_REC} feature graphic ground is {'#%02X%02X%02X' % ground} - Google advises against pure white, "
                             "black or dark gray, which blend into Play's own background")
            fj = os.path.join(os.path.dirname(fg), "_feature-graphic.json")
            if os.path.exists(fj):
                with open(fj, encoding="utf-8") as f:
                    fgd = json.load(f)
                for text in (fgd.get("headline"), fgd.get("sub")):
                    for msg in copy_checks(text or "", fgd.get("lang", lang), "android") if text else []:
                        warns.append(f"feature graphic \"{text}\": {msg}")
                for msg in fg_zone_checks(fgd):
                    warns.append(msg)
                if not fgd.get("alt"):
                    warns.append(f"{PLAY_REC} feature graphic has no alt text (\"alt\" in \"feature_graphic\", ≤ {ALT_MAX} characters)")
                elif len(fgd["alt"]) > ALT_MAX:
                    warns.append(f"{PLAY_REC} feature graphic alt text is {len(fgd['alt'])} characters (≤ {ALT_MAX})")

    sizes = set()
    for f in files:
        im = Image.open(f)
        w, h = im.size
        sizes.add((w, h))
        name = os.path.basename(f)
        if has_alpha(im):
            errors.append(f"{name}: has an alpha channel - stores reject transparency (save as RGB)")
        if a.store == "ios":
            if (min(w, h), max(w, h)) in DUO_SIZES:
                errors.append(f"{name}: {w}x{h} is an iPhone Duo size - Duo is its own device size; check it with --store duo")
            elif (w, h) not in IOS_SIZES and (h, w) not in IOS_SIZES:
                errors.append(f"{name}: {w}x{h} is not an accepted iPhone size")
        elif a.store == "duo":
            if (min(w, h), max(w, h)) not in DUO_SIZES:
                errors.append(f"{name}: {w}x{h} is not an iPhone Duo size (outer 1398x2034, inner 2007x2853)")
        elif a.store == "ipad":
            if (w, h) not in IPAD_SIZES and (h, w) not in IPAD_SIZES:
                errors.append(f"{name}: {w}x{h} is not an accepted iPad size")
        else:
            lo, hi = min(w, h), max(w, h)
            if lo < 320 or hi > 3840 or hi > 2 * lo:
                errors.append(f"{PLAY_REQ} {name}: {w}x{h} breaks Play's limits (min 320, max 3840, long side ≤ 2× short side)")
            elif lo < 1080 or round(hi / lo, 2) not in (1.78, 1.77):
                warns.append(f"{PLAY_PROMO} {name}: {w}x{h} - recommendation formats want ≥ 1080 px at 9:16 (1080x1920) "
                             "or 16:9 (1920x1080)")
    if len(sizes) > 1:
        warns.append(f"mixed sizes in one set: {sorted(sizes)}")
    if a.store == "ios":
        here = {(min(w, h), max(w, h)) for w, h in sizes}
        near = here | sibling_sizes(a.folder)
        if not near & IOS_REQUIRED:
            warns.append("no 1206x2622 / 1179x2556 set here or next to it - App Store Connect requires iPhone with "
                         "Dynamic Island (medium display) (store-specs.md)")
        if not near & IOS_LARGE:
            warns.append("no large iPhone set here or next to it (1320x2868 / 1290x2796 / 1260x2736, or Face ID 1284x2778) - "
                         "without a Dynamic Island large set Apple requires Face ID large; render \"ios-large\" too")

    # copy
    if heads:
        for i, h in enumerate(heads, start=1):
            if not (h or "").strip():  # e.g. the right half of a span that continues the picture
                continue
            for msg in copy_checks(h, lang, a.store):
                warns.append(f"{i:02d} \"{h}\": {msg}")
        filled = [h.lower() for h in heads if (h or "").strip()]
        if len(set(filled)) < len(filled):
            warns.append("duplicate headlines in the set")
    else:
        warns.append("no headlines given (no _render.json, no --headlines): copy checks skipped")
    if a.store == "android" and render.get("shots"):
        missing = [s["file"] for s in render["shots"] if not s.get("alt")]
        if missing:
            warns.append(f"{PLAY_REC} {len(missing)} of {len(render['shots'])} screenshots have no alt text - give each shot an "
                         f"\"alt\" (≤ {ALT_MAX} characters: what the screenshot shows, for screen readers)")
        for s in render["shots"]:
            if s.get("alt") and len(s["alt"]) > ALT_MAX:
                warns.append(f"{PLAY_REC} {s['file']}: alt text is {len(s['alt'])} characters (≤ {ALT_MAX})")
    for w in render.get("set_warnings", []):
        warns.append(f"set: {w}")
    for s in render.get("shots", []):
        for w in s.get("warnings", []):
            warns.append(f"{s.get('span', s['file'])}: {w}")

    sheet(files[:3], 200, "Search-result size: does the app make sense from these three?",
          os.path.join(a.folder, "_search-preview.jpg"))
    sheet(files, 300, f"Overview - {len(files)} shots, {a.store}", os.path.join(a.folder, "_overview.jpg"), cols=min(len(files), 5))

    print(f"{len(files)} screenshots, {a.store}, lang={lang}, sizes={sorted(sizes)}")
    for e in errors:
        print("ERROR ", e)
    for w in warns:
        print("WARN  ", w)
    if any("[Play " in x for x in errors + warns):
        print("      ", PLAY_LEGEND)
    if not errors and not warns:
        print("OK - no issues found. Still look at _search-preview.jpg and _overview.jpg.")
    print(f"wrote {os.path.join(a.folder, '_search-preview.jpg')} and _overview.jpg")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):  # Windows consoles and pipes default to a legacy code page
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    main()
