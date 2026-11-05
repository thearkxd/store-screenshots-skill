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

Google's preview-asset page sorts its rules into three kinds, and the consequences differ. The checks keep them
apart too: `check_set.py --store android` and the renderers label every Play message `[Play requirement]`,
`[Play recommendation]` or `[Play promotion eligibility]`.

| Kind | What Google says happens if you miss it |
|---|---|
| **Requirement** | "mandatory; failure to meet requirements may result in removal or suspension from Google Play" |
| **Highly recommended** | "will not impact your store listing page, but may result in changes to how your preview assets appear on Google Play or limit promotional opportunities" |
| **Promotion eligibility** | required "to be eligible for recommendations in formats that use screenshots" |

**Phone** (presets `android` = 1080 × 1920, 9:16, promotion-eligible; `android-tall` = 1080 × 2160, allowed
but not promotion-eligible).

*Requirements* - `check_set.py` reports these as errors:
- At least **2 screenshots across device types** to publish; at most **8 per device type**.
- JPEG or 24-bit PNG, no alpha. Min side 320 px, max side 3840 px, long side ≤ 2× short side.
- Feature graphic: **1024 × 500**, JPEG or 24-bit PNG, no alpha.

*Promotion eligibility* - warnings, because a listing publishes without them:
- Apps: **at least 4 screenshots at ≥ 1080 px**, portrait 9:16 (≥ 1080 × 1920) or landscape 16:9 (≥ 1920 × 1080).
- Games: at least 3, 9:16 or 16:9, at the same minimums.

*Highly recommended* - warnings, which the skill follows by default:
- **Show the in-app experience.** Taglines take up **no more than 20 % of the image**. A type-only poster
  breaks both, so keep it out of the Play set with `"stores": ["ios"]` (the renderer warns otherwise). The
  renderers measure the words' ink, big type included; label, annotation and footnote text is left out.
- **No device imagery** ("can become obsolete quickly or alienate some users"). Android presets and scenes show
  the bare rounded screen; a frame renders with a warning.
- **No calls to action**: "Download now", "Install now", "Play now", "Try now" (TR: "hemen indir", "şimdi dene").
- **No Play performance, ranking, award, testimonial, price or promotion wording**: "Best", "#1", "Top", "New",
  "Discount", "Sale", "Million Downloads", "free", prices, "10% off", star ratings, quotes, store badges.
  Google's metadata policy forbids the same claims in the app's title, icon and developer name, and
  misleading metadata anywhere.
- Avoid small text and busy backgrounds behind it; localise per language.
- **Rotation:** "Do not upload images upside down, sideways, or otherwise skewed." This is about the image
  you upload, not about a phone turned inside the composition (that one falls under device imagery and the
  skill's materials rule).
- **Alt text**, 140 characters or fewer: what the image shows, for screen readers. Give it per shot as
  `"alt"`; `check_set.py` warns when shots have none.
- **Feature graphic:**
  - The focal point sits towards the centre.
  - Key elements (logo, app name, slogan, main UI) stay out of the cutoff zones near the edges. Google shows the
    zones only as a picture, without numbers. The skill keeps key elements out of the outer 7 % at the sides
    and 6 % at top and bottom. Missing this "may result in ineligibility to appear in these formats".
  - Background elements belong at the edges.
  - No pure white, black or dark gray ground: they blend into Play's own background.
  - Don't repeat the icon, no device imagery, no promo wording, and alt text of 140 characters or fewer.

A brand that needs an exception (a dark-gray identity, a phone frame its users know) can make one. Say what
it may cost: the listing still publishes, but the asset may be shown differently or promoted less.

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
- Many App Store examples in the library use "#1", awards, prices and offers. **Leave those out of the Google
  Play set** (Google recommends it; keeping them may limit promotion).
- Keep at least 6 of 10 iOS shots (and every Android shot) as real UI; one poster shot is plenty.

## Sources
- Apple: https://developer.apple.com/help/app-store-connect/reference/screenshot-specifications
- Apple: https://developer.apple.com/help/app-review/guideline-reference/2-3-3-screenshots
- Google: https://support.google.com/googleplay/android-developer/answer/9866151
- Google: https://support.google.com/googleplay/android-developer/answer/13393723
