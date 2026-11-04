# Store specifications

Checked 2026-11-04 against Apple's App Store Connect help and Google's Play Console help. Stores change
these; verify on the pages below before uploading, and update this file (and `PRESETS` in
`scripts/render_set.py`) if they differ.

## Apple App Store (iPhone, iPhone Duo, iPad)

| Display class | Portrait px | Required? | `render_set.py` preset |
|---|---|---|---|
| **Dynamic Island, medium** | **1206 × 2622** · 1179 × 2556 | **Yes** - "at least one screenshot" | `ios` · `ios-1179` |
| Dynamic Island, large | 1320 × 2868 · 1290 × 2796 · 1260 × 2736 | No, but see the next row | `ios-large` |
| Face ID, large | 1284 × 2778 · 1242 × 2688 | "Required if app runs on iPhone and screenshots for iPhone with Dynamic Island (large display) aren't provided" | `ios-faceid` |
| iPhone Duo, outer display | 1398 × 2034 | From **April 2027** for apps built with the iOS 27.1 SDK or later; optional before. A Duo set adds an "optimized for iPhone Duo" badge | `duo-outer` |
| iPhone Duo, inner display | 2007 × 2853 | Same as outer | `duo-inner` |
| Face ID, medium | 1170 × 2532 · 1125 × 2436 · 1080 × 2340 | No (scaled from the medium Dynamic Island set) | - |
| Home button, large / medium | 1242 × 2208 · 750 × 1334 | No | - |
| **iPad 13"** | **2064 × 2752** · 2048 × 2732 | **Yes, if the app runs on iPad** | `ipad` |

Landscape is the same sizes rotated.

**What to deliver for iPhone: two sets from one spec** - `"sizes": ["ios", "ios-large"]` (the default when a
spec has no `"sizes"`). The medium set is the one App Store Connect requires; the large set means Apple doesn't
fall back to requiring Face ID large. `render_set.py` warns when a spec has only one of them, and
`check_set.py --store ios` looks at the folders next to the one it checks.

**iPhone Duo** sets need screens captured on iPhone Duo (each display has its own shape: outer ≈ 1:1.46, inner
≈ 1:1.42). Give them per size: `"screen": {"default": "screens/01.png", "duo-outer": "screens/duo-outer/01.png",
"duo-inner": "screens/duo-inner/01.png"}` - crops and callouts the same way, since UI sits at other fractions
on a wider screen. Phone screens in a Duo set render (shrunk to fit) with a warning. Check with
`check_set.py out/duo-inner --store duo`. The Duo and iPad presets show the bare rounded screen (no phone
bezel), and all type and spacing is scaled to the wider canvas.

- Formats: `.png`, `.jpg`, `.jpeg`; **no alpha channel / transparency**.
- Count: 1 to **10** per device size.
- Apple scales a larger set down to smaller sizes when the UI is the same.
- **Guideline 2.3.3:** screenshots must show the app in use, not merely title art, a login page or a splash
  screen; App Review approves a device's set only if **more than half** of its screenshots show the app in use.
  Text and image overlays are fine as long as they don't obscure the app.

## Google Play

**Phone** (presets `android` = 1080 × 1920, 9:16, promotion-eligible; `android-tall` = 1080 × 2160, allowed
but not promotion-eligible):
- Count: up to **8** per device type; at least 2 across device types to publish.
- Formats: JPEG or 24-bit PNG, no alpha. Dimensions: min side 320 px, max side 3840 px, long side ≤ 2× short.
- Promotion formats (apps): **at least 4 screenshots at ≥ 1080 px**, portrait 9:16 (≥ 1080 × 1920) or
  landscape 16:9 (≥ 1920 × 1080). Games: at least 3, showing gameplay.
- Feature graphic: **1024 × 500**, JPEG or 24-bit PNG, no alpha.

**Content rules** (Play Console help, "Highly recommended" + metadata policy) - `check_set.py --store
android` and `render_set.py` flag the ones a script can see:
- No ranking, performance, award or price/promo claims: "Best", "#1", "Top", "New", "Discount", "Sale",
  "Million Downloads", "free", prices, "10% off" (also in the feature graphic).
- No calls to action: "Download now", "Install now", "Play now", "Try now" (TR: "hemen indir", "şimdi dene").
- No user testimonials or star ratings, no store badges.
- **Avoid device imagery** in screenshots and the feature graphic ("can become obsolete quickly or alienate
  some users"). Android presets and the feature graphic therefore show the bare rounded screen; a frame
  (`"device": {"android_style": "android"}`) renders with a warning.
- **Taglines take up no more than 20% of the image**, and screenshots show the actual in-app experience. A
  type-only poster breaks both: keep it out of the Play set with `"stores": ["ios"]` on that shot (the
  renderer warns otherwise). Captions are measured; over 20% of the height warns.
- Localise text per language; avoid small text and busy backgrounds behind it.

**Other device types** (no presets; render with `--size WxH` and that device's own screens): tablets and
Chromebooks - at least 4 screenshots, 1080-7680 px, 16:9 or 9:16; Android XR - 4 to 8, 8:5, ≤ 8 MB; Wear OS -
1:1, ≥ 384 × 384; Android Automotive - at least 2 portrait 800 × 1280 and 2 landscape 1024 × 768; Android TV -
at least one TV screenshot.

## One spec, every store

- `"sizes": ["ios", "ios-large", "android"]` renders all of them; add `"duo-outer", "duo-inner"` when the app
  supports iPhone Duo and `"ipad"` when it runs on iPad.
- Anything can vary per size: `{"default": …, "android": …, "duo-inner": …}` picks the exact preset, then the
  device class (`iphone`, `duo`, `ipad`, `android`), then the store (`ios`, `android`), then `"default"`.
- `"stores": ["ios"]` (or `"android"`, `"iphone"`, `"duo"`, `"ipad"`) keeps a shot in those sets only.
- Many App Store examples in the library use "#1", awards, prices and offers. **Strip those for Google Play.**
- Keep at least 6 of 10 iOS shots (and every Android shot) as real UI; one poster shot is plenty.

## Sources
- Apple: https://developer.apple.com/help/app-store-connect/reference/screenshot-specifications
- Apple: https://developer.apple.com/help/app-review/guideline-reference/2-3-3-screenshots
- Google: https://support.google.com/googleplay/android-developer/answer/9866151
- Google: https://support.google.com/googleplay/android-developer/answer/13393723
