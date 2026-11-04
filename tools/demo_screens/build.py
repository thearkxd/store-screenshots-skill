#!/usr/bin/env python3
"""Build the placeholder app screens used by templates/set.example.json.

The screens belong to a fictional TV tracker ("Dizilog") and are drawn with HTML/CSS, then captured at
iPhone resolution (402x874 pt @3x = 1206x2622 px) with Playwright. Maintainers only:

  python3 tools/demo_screens/build.py
"""
import json
import os

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "..", "skills", "store-screenshots", "templates", "example-screens"))

POSTERS = {
    "gece": ("Gece Vardiyası", "linear-gradient(160deg,#0f3b44 0%,#081b21 55%,#020607 100%)", "#ff3d7f", "stripe"),
    "kuzey": ("Kuzey Hattı", "linear-gradient(180deg,#b9d6e8 0%,#5f8fb0 55%,#1d3346 100%)", "#ffffff", "peaks"),
    "mahalle": ("Mahalle", "linear-gradient(170deg,#f2a541 0%,#d9692e 60%,#7a2f1c 100%)", "#2b130a", "windows"),
    "durak": ("Son Durak", "linear-gradient(180deg,#2a0f14 0%,#7c1f26 60%,#d94b3f 100%)", "#ffd9a8", "sun"),
    "ada": ("Ada", "linear-gradient(180deg,#0c2a4a 0%,#1b5e8a 60%,#57b3c9 100%)", "#ffffff", "island"),
    "kat": ("Dördüncü Kat", "linear-gradient(160deg,#2c2c34 0%,#15151a 100%)", "#c8ff3c", "grid"),
    "mavi": ("Mavi Saat", "linear-gradient(180deg,#1b1f5e 0%,#3e48b8 55%,#9aa7ff 100%)", "#ffffff", "moon"),
}

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{width:402px;height:874px;background:#0e0e11;color:#f4f2ee;font-family:Inter,'Inter Display',sans-serif;
 -webkit-font-smoothing:antialiased;overflow:hidden;position:relative;letter-spacing:-.01em}
.status{position:relative;z-index:5;height:54px;display:flex;justify-content:space-between;align-items:flex-end;padding:0 30px 8px 34px;font-weight:600;font-size:16px}
.status .r{display:flex;gap:6px;align-items:center}
.bat{width:25px;height:12px;border:1.5px solid #f4f2ee;border-radius:4px;position:relative;opacity:.9}
.bat:after{content:'';position:absolute;left:1.5px;top:1.5px;width:17px;height:6px;background:#f4f2ee;border-radius:1.5px}
.bars{display:flex;gap:2px;align-items:flex-end}.bars i{width:3px;background:#f4f2ee;border-radius:1px}
.wrap{padding:0 18px}
.top{display:flex;justify-content:space-between;align-items:center;margin:10px 2px 16px}
h1{font-family:'Inter Display';font-weight:700;font-size:32px;letter-spacing:-.025em}
.sub{color:#9a98a3;font-size:14px;margin-top:2px}
.av{width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;color:#fff}
.card{background:#19191e;border-radius:22px;overflow:hidden}
.poster{position:relative;overflow:hidden;border-radius:12px}
.poster .t{position:absolute;left:10px;right:10px;bottom:10px;font-family:'Inter Display';font-weight:800;letter-spacing:-.03em;line-height:.95;text-transform:uppercase}
.sec{display:flex;justify-content:space-between;align-items:baseline;margin:22px 2px 10px}
.sec b{font-family:'Inter Display';font-size:19px;letter-spacing:-.02em}.sec span{color:#ff5a3c;font-size:14px;font-weight:600}
.row{display:flex;gap:10px}
.prog{height:5px;background:#2b2b33;border-radius:3px;overflow:hidden}.prog i{display:block;height:100%;background:#ff5a3c;border-radius:3px}
.btn{background:#ff5a3c;color:#140805;font-weight:700;border-radius:14px;padding:12px 16px;font-size:15px;display:inline-flex;gap:8px;align-items:center}
.muted{color:#9a98a3}
.tab{position:absolute;left:0;right:0;bottom:0;height:86px;background:rgba(18,18,22,.96);border-top:1px solid #24242b;display:flex;justify-content:space-around;padding-top:10px}
.tab div{display:flex;flex-direction:column;align-items:center;gap:4px;font-size:10.5px;color:#7d7b86;font-weight:500}
.tab div.on{color:#ff5a3c}.tab svg{width:24px;height:24px}
.chip{background:#222229;border-radius:999px;padding:7px 12px;font-size:13px;font-weight:600;color:#d8d6de}
.home-ind{position:absolute;bottom:8px;left:50%;transform:translateX(-50%);width:134px;height:5px;border-radius:3px;background:#f4f2ee;opacity:.9}
"""

ICONS = {
    "home": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/></svg>',
    "cal": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>',
    "stats": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 20V11M12 20V4M19 20v-6"/></svg>',
    "friends": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5"/><circle cx="17" cy="9" r="2.6"/><path d="M16.5 14.6c2.6.2 4.4 1.9 5 5.4"/></svg>',
}


def status():
    return ('<div class="status"><span>21:41</span><span class="r"><span class="bars"><i style="height:5px"></i>'
            '<i style="height:7px"></i><i style="height:9px"></i><i style="height:11px"></i></span>'
            '<svg width="17" height="12" viewBox="0 0 17 12"><path d="M8.5 2.5c2.4 0 4.6.9 6.2 2.5l1.2-1.2A10.4 10.4 0 0 0 8.5.8 10.4 10.4 0 0 0 1.1 3.8l1.2 1.2a8.7 8.7 0 0 1 6.2-2.5zm0 3.4c1.5 0 2.8.5 3.8 1.5l1.2-1.2a7 7 0 0 0-10 0l1.2 1.2c1-1 2.3-1.5 3.8-1.5zm0 3.3c.6 0 1.1.2 1.5.6L8.5 11.3 7 9.8c.4-.4.9-.6 1.5-.6z" fill="#f4f2ee"/></svg>'
            '<span class="bat"></span></span></div>')


def tabbar(active):
    items = [("home", "Ana sayfa"), ("cal", "Takvim"), ("stats", "İstatistik"), ("friends", "Arkadaşlar")]
    return '<div class="tab">' + "".join(
        f'<div class="{"on" if k == active else ""}">{ICONS[k]}<span>{t}</span></div>' for k, t in items) + '</div><div class="home-ind"></div>'


def poster(key, w, h, title_size=None, radius=12):
    name, bg, ink, motif = POSTERS[key]
    ts = title_size or max(12, int(w * 0.17))
    art = {
        "stripe": f'<div style="position:absolute;left:-20%;top:38%;width:140%;height:9%;background:{ink};transform:rotate(-14deg);opacity:.9;box-shadow:0 0 24px {ink}"></div>',
        "peaks": '<div style="position:absolute;left:-10%;bottom:18%;width:0;height:0;border-left:60px solid transparent;border-right:60px solid transparent;border-bottom:90px solid #0f2233;transform:scale(1.6)"></div><div style="position:absolute;right:-6%;bottom:18%;width:0;height:0;border-left:50px solid transparent;border-right:50px solid transparent;border-bottom:70px solid #18324a;transform:scale(1.5)"></div>',
        "windows": "".join(f'<div style="position:absolute;left:{12 + (i % 3) * 28}%;top:{14 + (i // 3) * 20}%;width:18%;height:13%;background:{"#ffe2a6" if i in (1, 5, 6) else "#5a2414"};border-radius:2px"></div>' for i in range(9)),
        "sun": '<div style="position:absolute;left:50%;top:30%;width:58%;aspect-ratio:1;transform:translateX(-50%);border-radius:50%;background:radial-gradient(circle,#ffd9a8 0,#ff8a5b 60%,transparent 62%)"></div><div style="position:absolute;left:0;right:0;bottom:0;height:42%;background:#1a070a"></div>',
        "island": '<div style="position:absolute;left:18%;top:46%;width:64%;height:16%;border-radius:50% 50% 0 0;background:#0a1d33"></div><div style="position:absolute;left:0;right:0;top:60%;bottom:0;background:linear-gradient(180deg,#2f7fa6,#0c2a4a)"></div>',
        "grid": "".join(f'<div style="position:absolute;left:0;right:0;top:{8 + i * 11}%;height:1px;background:#c8ff3c;opacity:{0.15 + i * 0.07}"></div>' for i in range(8)),
        "moon": '<div style="position:absolute;right:16%;top:12%;width:30%;aspect-ratio:1;border-radius:50%;box-shadow:-10px 6px 0 0 #fff6d6"></div>',
    }[motif]
    return (f'<div class="poster" style="width:{w}px;height:{h}px;background:{bg};border-radius:{radius}px;flex:none">{art}'
            f'<div class="t" style="font-size:{ts}px;color:{ink if motif != "stripe" else "#f4f2ee"}">{name}</div></div>')


def page(body):
    return f'<!doctype html><html lang="tr"><head><meta charset="utf-8"><style>{CSS}</style></head><body>{status()}{body}</body></html>'


def home():
    return page(f'''<div class="wrap">
<div class="top"><div><h1>İyi akşamlar, Elif</h1><div class="sub">Bu akşam 2 yeni bölüm var</div></div>
<div class="av" style="background:linear-gradient(135deg,#ff5a3c,#ff9a5a)">E</div></div>
<div data-region="hero" class="card"><div style="position:relative">{poster("gece", 366, 206, 34, 0)}
<div style="position:absolute;left:14px;top:14px" class="chip">Yeni bölüm</div></div>
<div style="padding:16px 16px 18px"><div style="display:flex;justify-content:space-between;align-items:baseline">
<b style="font-family:'Inter Display';font-size:20px;letter-spacing:-.02em">Gece Vardiyası</b><span class="muted" style="font-size:13px">S2 · B6</span></div>
<div class="muted" style="font-size:14px;margin:4px 0 12px">“Son Çıkış” · 18 dk kaldı</div>
<div class="prog"><i style="width:72%"></i></div>
<div style="display:flex;gap:10px;margin-top:14px"><span class="btn">▶ Kaldığın yerden</span><span class="chip" style="padding:12px 14px">İzledim</span></div></div></div>
<div class="sec"><b>Sırada</b><span>Tümü</span></div>
<div class="row">{"".join(f'<div style="width:112px">{poster(k, 112, 160)}<div style="font-size:13px;font-weight:600;margin-top:8px">{t}</div><div class="muted" style="font-size:12px">{e}</div></div>' for k, t, e in [("kuzey", "Kuzey Hattı", "S1 · B9"), ("mahalle", "Mahalle", "S4 · B3"), ("ada", "Ada", "S3 · B10")])}</div>
<div class="sec"><b>Bu hafta yeni</b><span>Takvim</span></div>
<div class="row">{"".join(f'<div style="width:112px">{poster(k, 112, 70, 13)}</div>' for k in ["durak", "kat", "mavi"])}</div>
</div>{tabbar("home")}''')


def calendar():
    days = [("Pzt", "3", False), ("Sal", "4", True), ("Çar", "5", False), ("Per", "6", False), ("Cum", "7", False), ("Cmt", "8", False), ("Paz", "9", False)]
    chips = "".join(
        f'<div style="flex:1;text-align:center;padding:10px 0;border-radius:14px;background:{"#ff5a3c" if on else "#19191e"};color:{"#140805" if on else "#d8d6de"}">'
        f'<div style="font-size:12px;font-weight:600;opacity:.8">{d}</div><div style="font-family:\'Inter Display\';font-size:20px;font-weight:700">{n}</div></div>'
        for d, n, on in days)
    items = [("kuzey", "Kuzey Hattı", "S1 · B9 · “Buz”", "Yarın · 20:00", False), ("mahalle", "Mahalle", "S4 · B3", "Perşembe · 22:00", True),
             ("durak", "Son Durak", "2. sezon başlıyor", "Cuma", False), ("ada", "Ada", "S3 · B10 · Final", "Pazar · 21:00", True)]
    rows = "".join(
        f'<div class="card" style="display:flex;gap:14px;padding:12px;margin-bottom:10px;align-items:center">{poster(k, 64, 88, 10, 10)}'
        f'<div style="flex:1"><div class="muted" style="font-size:12px;font-weight:600">{when}</div><div style="font-weight:700;font-size:16px;margin:2px 0">{t}</div><div class="muted" style="font-size:13px">{e}</div></div>'
        f'<div style="width:46px;height:28px;border-radius:14px;background:{"#ff5a3c" if on else "#2b2b33"};position:relative"><div style="position:absolute;top:3px;{"right" if on else "left"}:3px;width:22px;height:22px;border-radius:50%;background:#fff"></div></div></div>'
        for k, t, e, when, on in items)
    return page(f'''<div class="wrap"><div class="top"><div><h1>Bu hafta</h1><div class="sub">Takip ettiğin 9 dizide 6 yeni bölüm</div></div></div>
<div style="display:flex;gap:6px;margin-bottom:18px">{chips}</div>
<div class="muted" style="font-size:13px;font-weight:600;margin:0 2px 8px">BU AKŞAM</div>
<div data-region="tonight" class="card" style="display:flex;gap:14px;padding:14px;align-items:center;background:linear-gradient(135deg,#2a1410,#19191e);border:1px solid #4a2219;margin-bottom:22px">{poster("gece", 70, 98, 11, 10)}
<div style="flex:1"><div style="color:#ff5a3c;font-size:13px;font-weight:700">21:00 · 1 sa 19 dk sonra</div><div style="font-weight:700;font-size:18px;margin:3px 0">Gece Vardiyası</div><div class="muted" style="font-size:13px">S2 · B7 · “Kırmızı Işık”</div></div>
<div class="chip" style="background:#ff5a3c;color:#140805;display:flex;gap:5px;align-items:center"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#140805" stroke-width="2.6"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 8 3 8H3s3-1 3-8M10 21h4"/></svg>Açık</div></div>
<div class="muted" style="font-size:13px;font-weight:600;margin:0 2px 8px">YAKINDA</div>{rows}</div>{tabbar("cal")}''')


def stats():
    months = [14, 22, 18, 30, 26, 19, 34, 41, 28, 37, 43, 0]
    m = max(months)
    bars = "".join(
        f'<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:6px"><div style="width:100%;height:{int(120 * v / m)}px;border-radius:6px;background:{"#ff5a3c" if i == 10 else "#3a3a44"}"></div>'
        f'<span class="muted" style="font-size:10px">{"OŞMNMHTAEEKA"[i]}</span></div>' for i, v in enumerate(months))
    genres = "".join(f'<span class="chip" style="{s}">{g}</span>' for g, s in [("Polisiye · %38", "background:#ff5a3c;color:#140805"), ("Dram · %24", ""), ("Gerilim · %17", ""), ("Komedi · %11", "")])
    top = "".join(f'<div style="display:flex;gap:12px;align-items:center;margin-bottom:12px"><span class="muted" style="width:14px;font-weight:700">{i}</span>{poster(k, 44, 60, 8, 8)}<div style="flex:1"><div style="font-weight:700">{t}</div><div class="muted" style="font-size:13px">{h}</div></div></div>'
                  for i, (k, t, h) in enumerate([("gece", "Gece Vardiyası", "48 saat · 2 sezon"), ("mahalle", "Mahalle", "41 saat · 4 sezon"), ("kuzey", "Kuzey Hattı", "22 saat · 1 sezon")], 1))
    return page(f'''<div class="wrap"><div class="top"><div><h1>2026 özetin</h1><div class="sub">1 Ocak'tan bugüne</div></div></div>
<div data-region="total" class="card" style="padding:20px 18px 18px;background:linear-gradient(160deg,#25140f,#19191e 60%)">
<div class="muted" style="font-size:14px;font-weight:600">Toplam izleme</div>
<div style="font-family:'Inter Display';font-weight:800;font-size:64px;letter-spacing:-.045em;line-height:1.05">312 <span style="font-size:30px;letter-spacing:-.02em">saat</span></div>
<div style="font-size:14px;color:#ffb39f;margin:2px 0 18px">Gece kuşusun: en çok 23:00'te izliyorsun</div>
<div style="display:flex;gap:6px;align-items:flex-end;height:142px">{bars}</div></div>
<div data-region="tiles" style="display:flex;gap:10px;margin:12px 0"><div class="card" style="flex:1;padding:14px"><div class="muted" style="font-size:13px">Biten dizi</div><div style="font-family:'Inter Display';font-size:28px;font-weight:700">14</div></div>
<div class="card" style="flex:1;padding:14px"><div class="muted" style="font-size:13px">Bölüm</div><div style="font-family:'Inter Display';font-size:28px;font-weight:700">426</div></div>
<div class="card" style="flex:1;padding:14px"><div class="muted" style="font-size:13px">Seri</div><div style="font-family:'Inter Display';font-size:28px;font-weight:700">23 gün</div></div></div>
<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:18px">{genres}</div>
<div data-region="top" style="padding:4px 0"><div class="sec" style="margin-top:0"><b>En çok izlediklerin</b></div>{top}</div></div>{tabbar("stats")}''')


def friends():
    feed = [("Mert", "#3e48b8,#9aa7ff", "Gece Vardiyası'nda S2 · B6'yı bitirdi", "“O son sahne… kimse bana spoiler vermesin.”", "gece", "4 dk", "12"),
            ("Zeynep", "#d9692e,#f2a541", "Mahalle'yi 5 üzerinden 5 ile puanladı", "★★★★★", "mahalle", "38 dk", "8"),
            ("Can", "#1b5e8a,#57b3c9", "Ada'yı listesine ekledi", "Senin listende de var · birlikte başlayın", "ada", "1 sa", "3"),
            ("Deniz", "#7c1f26,#d94b3f", "Son Durak'ın 2. sezonunu bekliyor", "Cuma 20:00 · hatırlatıcı açık", "durak", "2 sa", "5")]
    items = "".join(
        f'<div class="card" style="padding:14px;margin-bottom:10px"><div style="display:flex;gap:12px">'
        f'<div class="av" style="background:linear-gradient(135deg,{g});width:42px;height:42px;font-size:16px;flex:none">{n[0]}</div>'
        f'<div style="flex:1"><div style="font-size:15px"><b>{n}</b> <span class="muted">· {t}</span></div><div style="font-size:15px;margin-top:3px;line-height:1.35">{a}</div>'
        f'<div style="color:#d8d6de;font-size:14px;margin-top:6px">{q}</div>'
        f'<div class="muted" style="font-size:13px;margin-top:10px;display:flex;gap:16px"><span>♥ {likes}</span><span>Yanıtla</span></div></div>'
        f'{poster(k, 52, 72, 8, 8)}</div></div>' for n, g, a, q, k, t, likes in feed)
    return page(f'''<div class="wrap"><div class="top"><div><h1>Arkadaşlar</h1><div class="sub">Şu an 3 arkadaşın izliyor</div></div>
<div style="display:flex">{"".join(f'<div class="av" style="background:linear-gradient(135deg,{g});margin-left:-8px;border:2px solid #0e0e11">{c}</div>' for c, g in [("M", "#3e48b8,#9aa7ff"), ("Z", "#d9692e,#f2a541"), ("C", "#1b5e8a,#57b3c9")])}</div></div>
<div style="display:flex;gap:8px;margin-bottom:16px"><span class="chip" style="background:#ff5a3c;color:#140805">Akış</span><span class="chip">Ortak listeler</span><span class="chip">Öneriler</span></div>
{items}</div>{tabbar("friends")}''')


def detail():
    eps = [("1", "Pilot", "52 dk", True), ("2", "Gölge", "48 dk", True), ("3", "Dönüş Yolu", "50 dk", True), ("4", "Tanık", "47 dk", True),
           ("5", "Kör Nokta", "51 dk", True), ("6", "Son Çıkış", "49 dk", False), ("7", "Kırmızı Işık", "Bu akşam 21:00", False)]
    rows = "".join(
        f'<div style="display:flex;align-items:center;gap:14px;padding:13px 4px;border-bottom:1px solid #222229">'
        f'<span class="muted" style="width:18px;font-weight:700">{n}</span><div style="flex:1"><div style="font-weight:600;font-size:15px">{t}</div><div class="muted" style="font-size:13px">{d}</div></div>'
        f'<div style="width:28px;height:28px;border-radius:50%;{"background:#ff5a3c" if w else "border:2px solid #4a4a55"};display:flex;align-items:center;justify-content:center;color:#140805;font-weight:900;font-size:15px">{"✓" if w else ""}</div></div>'
        for n, t, d, w in eps)
    return page(f'''<div style="position:relative;margin-top:-54px">{poster("gece", 402, 330, 48, 0)}
<div style="position:absolute;inset:0;background:linear-gradient(180deg,rgba(14,14,17,0) 45%,#0e0e11 100%)"></div></div>
<div class="wrap" style="margin-top:6px;position:relative"><div style="display:flex;gap:8px;margin-bottom:10px"><span class="chip">Polisiye</span><span class="chip">2 sezon</span><span class="chip">★ 8.7</span></div>
<div style="display:flex;justify-content:space-between;align-items:center;margin:8px 2px 6px"><b style="font-family:'Inter Display';font-size:22px;letter-spacing:-.02em">2. Sezon</b><span class="muted" style="font-size:14px">5 / 8 izlendi</span></div>
<div class="prog" style="margin:0 2px 8px"><i style="width:62%"></i></div>{rows}</div>{tabbar("home")}''')


def main():
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.endswith((".png", ".jpg")):
            os.remove(os.path.join(OUT, f))
    pages = {"01-home": home(), "02-calendar": calendar(), "03-stats": stats(), "04-friends": friends(), "05-detail": detail()}
    regions = {}
    js = """() => [...document.querySelectorAll('[data-region]')].map(e => {const r = e.getBoundingClientRect();
        return [e.dataset.region, r.left / 402, r.top / 874, r.right / 402, r.bottom / 874]})"""
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 402, "height": 874}, device_scale_factor=3)
        for name, html in pages.items():
            pg.set_content(html)
            pg.wait_for_timeout(150)
            # JPEG keeps the lite package small; store uploads are rendered as PNG by render_set.py
            pg.screenshot(path=os.path.join(OUT, f"{name}.jpg"), type="jpeg", quality=88)
            for key, *box in pg.evaluate(js):
                regions[f"{name}.jpg#{key}"] = [round(v, 4) for v in box]
            print(name)
        b.close()
    # crop boxes (fractions) for callouts / zoom cards in set.example.json
    with open(os.path.join(OUT, "regions.json"), "w") as f:
        json.dump(regions, f, indent=1)
    print(json.dumps(regions))


if __name__ == "__main__":
    main()
