# Store specifications

Checked 2026-11-04 against Apple's App Store Connect help and Google's Play Console help. Stores change
these; verify on the pages below before uploading, and update this file (and `PRESETS` in
`scripts/render_set.py`) if they differ.

## Apple App Store (iPhone)

| Display class | Portrait px | Required? |
|---|---|---|
| iPhone Duo, outer display | 1398 × 2034 | No (required from April 2027 for apps built with the iOS 27.1 SDK or later) |
| iPhone Duo, inner display | 2007 × 2853 | No (same as above) |
| Dynamic Island, large | 1260 × 2736 · 1290 × 2796 · 1320 × 2868 | No |
| **Dynamic Island, medium** | **1179 × 2556 · 1206 × 2622** | **Yes** |
| Face ID, large | 1284 × 2778 · 1242 × 2688 | Only if the app runs on iPhone and no Dynamic Island (large) set is provided |
| Face ID, medium | 1170 × 2532 · 1125 × 2436 · 1080 × 2340 | No |
| Home button, large | 1242 × 2208 | No |

Landscape is the same sizes rotated. iPad: **13"** 2064 × 2752 or 2048 × 2732 portrait is required if the
app runs on iPad.

- Formats: `.png`, `.jpg`, `.jpeg`; **no alpha channel / transparency**.
- Count: 1 to **10** per device size.
- Apple scales a larger set down to smaller sizes when the UI is the same, so one set at the required size is
  usually enough.
- **Guideline 2.3.3:** screenshots must show the app in use, not merely title art, a login page or a splash
  screen; App Review approves a device's set only if **more than half** of its screenshots show the app in use.
  Text and image overlays are fine as long as they don't obscure the app.

`render_set.py` presets: `ios` = 1206 × 2622 (default), `ios-1179` = 1179 × 2556, `ios-large` = 1320 × 2868,
`ios-faceid` = 1284 × 2778, `ipad` = 2064 × 2752.

## Google Play (phone)

- Count: up to **8** per device type; at least 2 across device types to publish.
- Formats: JPEG or 24-bit PNG, no alpha.
- Dimensions: min side 320 px, max side 3840 px, and the long side can't be more than twice the short side.
- To be eligible for screenshot-based promotion formats (apps): **at least 4 screenshots at ≥ 1080 px**,
  portrait ≥ 1080 × 1920 (9:16) or landscape ≥ 1920 × 1080 (16:9). Games: at least 3, showing gameplay.
- Feature graphic: 1024 × 500, JPEG or 24-bit PNG, no alpha.
- Listing guidance: keep text to a minimum; provide separate screenshots per language when they contain text;
  **don't include ranking or performance claims** ("App of the year", "#1", "Best of Play", "Popular"),
  **prices or promotions** ("10% off", "free for a limited time"), award icons, or graphics that misrepresent
  the app or imitate other products.

`render_set.py` presets: `android` = 1080 × 1920 (default, promotion-eligible), `android-tall` = 1080 × 2160
(2:1, the tallest allowed ratio).

## Practical consequences

- Make the iOS set at 1206 × 2622 and an Android set at 1080 × 1920 from the same spec (`"size"` per output;
  the layout is proportional). Check both with `check_set.py --store ios` / `--store android`.
- Many App Store examples in the library use "#1", awards, prices and offers. **Strip those for Google Play.**
- Keep at least 6 of 10 iOS shots (and most Android shots) as real UI; one poster shot is plenty.

## Sources
- Apple: https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications
- Apple: https://developer.apple.com/help/app-review/guideline-reference/2-3-3-screenshots
- Google: https://support.google.com/googleplay/android-developer/answer/9866151
- Google: https://support.google.com/googleplay/android-developer/answer/13393723
