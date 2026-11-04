# The reference library - guide and insights

The library holds the App Store screenshots of the **top 4 free iPhone apps in 25 App Store categories**, in
the **Turkish (tr)** and **US (us)** stores, collected on 2026-11-04: **1,366 screenshot records**
(1,267 unique images) from **197 chart slots / 173 unique apps**. Every app is classified by a reviewer
(layout, techniques, first-shot type, quality, AI smell, a note on why); every screenshot has OCR'd headline
text, position, language, palette and background type. 243 lite screenshots have **human-verified headlines**.

> **The screenshots are the property of their publishers.** They are included as study material only.
> Never ship them, trace them, or copy a set's copy or design system closely.

## Contents
1. What's inside & where
2. Full vs lite package
3. How to search
4. Data-driven insights
5. Curated lessons (with app names to search)
6. Limits and biases
7. Catalog schema & refreshing the library

---

## 1. What's inside & where

```
assets/library/
  catalog.json          one record per screenshot (app labels + per-image features), the file scripts read
  classifications.json  source of truth for the labels: apps[], verified shots[], lite[] ids
  stats.json            distributions overall, per country, per category, first shots
  img/<country>/<category>/<rank>-<app>/<NN>.webp   480 px wide images (full package: all; lite: 549)
  auto.json             (full package / maintainers) raw OCR + features before merging
```

Categories (`--category`): books · business · developer-tools · education · entertainment · finance ·
food-drink · games · graphics-design · health-fitness · lifestyle · magazines-newspapers · medical · music ·
navigation · news · photo-video · productivity · reference · shopping · social-networking · sports · travel ·
utilities · weather. (Stickers has no iPhone screenshots and is absent.)

## 2. Full vs lite package

| | Full | Lite |
|---|---|---|
| Text catalog (all 1,366 records, labels, notes, OCR headlines) | ✓ | ✓ |
| Images | all 1,267 | 549: every shot of the 42 exemplary apps, the first shot of every app, and shots 1–3 of 26 instructive weak/AI-smell apps |
| Verified headlines | 243 | same |
| Size | ~36 MB zipped | ~16 MB zipped, ~17 MB unpacked (fits a 20 MB upload limit) |

Scripts detect missing images and only offer what's on disk (`img` column / `--has-image`).

## 3. How to search

```bash
python3 scripts/search_library.py --list-values                  # categories, techniques, layouts…
python3 scripts/search_library.py --category navigation --summary   # conventions of a category
python3 scripts/search_library.py --category finance --country tr --position 1 --format headlines
python3 scripts/search_library.py --quality exemplary --technique stat-number --format headlines
python3 scripts/search_library.py --ai-smell --position 1 --format table
python3 scripts/search_library.py --query "rain" --format headlines            # text in headline/note/app
python3 scripts/search_library.py --app "Flo" --format paths                     # then open the images
python3 scripts/search_library.py --quality exemplary --has-image --position 1 --format paths --limit 8
```
Filters combine with AND. `--format table|headlines|paths|json|apps`. `--verified` keeps only
human-checked headlines (use it before quoting a headline to the user).

## 4. Data-driven insights

All from this library; the quality labels are a reviewer's judgement, so treat correlations as taste
signals, not causal proof.

**Quality** - 42 apps exemplary, 79 solid, 52 weak. The US top charts skew better (249 exemplary shots vs
133 in TR): many Turkish top apps are government, banking and betting apps with dated or text-heavy sets.

**Layout** - device frame 72 % of shots, full-bleed UI 11 %, mixed 11 %, photo-led 3 %, illustration-led 2 %.
Full-bleed UI *without captions* is almost always weak (15 of 15 `no-caption` apps).

**First shots** - 27 of 42 exemplary apps open with a benefit headline; 26 of 52 weak apps open with a logo,
splash or bare UI.

**Headlines** - 86 % sit at the top. In the verified sample, exemplary headlines have a median of 5 words,
weak ones 7.

**Techniques, exemplary vs weak apps** (count of apps):

| More often in exemplary | ex / weak | More often in weak | ex / weak |
|---|---|---|---|
| verb-led headlines | 11 / 0 | no captions | 0 / 15 |
| emphasis word | 11 / 1 | generic claims | 0 / 16 |
| real people photography | 10 / 1 | tilted floating devices | 0 / 12 |
| serif type | 7 / 1 | paragraph copy | 0 / 8 |
| colour per shot (brand rotation) | 7 / 2 | outdated UI | 0 / 8 |
| UI cards pulled out of the frame | 4 / 0 | locale mismatch | 0 / 8 |
| specific use case / named pain | 7 / 0 | Title Case slogans | 0 / 7 |
| testimonials / spoken rhythm | 6 / 0 | small captions | 0 / 7 |
| | | default gradients | 2 / 8 |

**Language in the Turkish store** - by OCR, most caption text on Turkish listings is English (global apps),
and about one in eight Turkish top apps shows English captions or a foreign-language UI on a Turkish listing.

## 5. Curated lessons (search with `--app`)

- **Copy with a voice:** HIRKA ("Not degrees, a decision."), The Pour Over, Tinder, McDonald's, Lyft, TaraGör.
- **Specific numbers:** Indeed (30 % faster*), Cash App, PayPal, Capital One Shopping, Cleanup.
- **Named pain / use case:** Ground News, Waze, WeatherX, Google Gemini, ChatGPT.
- **One visual system:** Waze (flat cyan), Flo (lilac + white box), Spotify (pink/green frame), Kindle
  (overline + serif), NYT ("X Today" series), Threads (yellow marker).
- **Ownable motif:** HIRKA (rope), Moovit (transit lines), Bible and Instagram (hand-drawn marks),
  Reddit (sticker captions, colour per shot).
- **Journey structure:** Uber. **Photo-led:** Lyft, Tinder, Pinterest. **Pulled-out callouts:** Indeed,
  Moovit, Gmail. **Zoom crop:** Flo, Capital One, ParkMobile.
- **Turkish copy done well:** TaraGör, Trendyol Go, Tıkla Gelsin, Bookios, HAYAT 112 Acil.
- **What not to do:** Otobüsüm Nerede (paragraphs), Ziraat/Halkbank ("renewed!"), NetShort/DramaBox
  (template slogans), Kling AI (spec sheet + typo), Microsoft Teams (3D blobs, tilted phones),
  Music Creator (neon AI template), MAC+ (five type sizes), fatsecret (wrong-market copy), e-Nabız
  (splash and login as screenshots).

## 6. Limits and biases

- Top charts = big brands. Big brands can rely on recognition (Google, YouTube, Instagram); a small app can't.
  Weigh the exemplary sets of challengers (HIRKA, TaraGör, WeatherX, Ground News, The Pour Over) higher.
- iPhone screenshots only; no iPad, no Google Play images, no preview videos.
- A single snapshot in time; seasonal campaigns (Pinterest's Halloween set, Hepsiburada's "Efsane Kasım") are
  included as they were that day.
- Several categories are dominated by one kind of app (sports = betting in TR; entertainment = short dramas).
- OCR headlines are imperfect: measured against the 225 verified ones, about 6 in 10 are near-exact and
  7 in 10 close. Quote only `headline_verified` headlines, or open the image and read it yourself.

## 7. Catalog schema & refreshing the library

Each record in `catalog.json`:

| Field | Meaning |
|---|---|
| `id`, `image`, `image_id`, `in_lite` | identity, image path (relative to `assets/library/`), shipped in lite? |
| `country`, `category`, `chart_rank`, `app`, `app_id`, `seller`, `position`, `shots_total`, `store_url` | where it came from |
| `headline`, `headline_verified`, `headline_words`, `headline_pos`, `headline_px`, `language` | caption text (OCR unless verified), position, size (‰ of height), language |
| `text_chars`, `palette`, `dark`, `background` | visual features (`background`: flat · flat-top · gradient · image) |
| `layout`, `techniques`, `first_shot`, `quality`, `ai_smell`, `note` | app-level labels (same for every shot of an app) |
| `exemplary`, `shot_note` | per-shot flag and note |

`layout`: device-frame · full-bleed-ui · mixed · photo-led · illustration-led · panorama · type-led.
`first_shot`: benefit · feature · brand · content · ui-only · social-proof · offer · hook.
`quality`: exemplary · solid · weak.

**Refresh or extend** (needs network access to `itunes.apple.com` and `is1-ssl.mzstatic.com`, Pillow and
tesseract with `eng`+`tur`):
```bash
python3 scripts/collect_examples.py --countries tr us --per-category 4 --out raw/
python3 scripts/collect_examples.py --countries us --app-ids 123 456 --label competitors --out raw/
python3 scripts/build_catalog.py extract --raw raw/
# classify new apps in assets/library/classifications.json (apps[]), verify headlines (shots[])
python3 scripts/build_catalog.py merge && python3 scripts/build_catalog.py check
```
