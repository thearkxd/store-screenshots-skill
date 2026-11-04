# Layouts, type and colour

## Contents
1. One visual system per set
2. Layout recipes (and what `render_set.py` calls them)
3. Typography
4. Colour and backgrounds
5. Emphasis devices
6. When the renderer isn't enough: the HTML route

---

## 1. One visual system per set

Decide these once and keep them for every shot:
- **Background rule:** one brand colour for all shots, *or* a fixed rotation of 2–4 brand colours
  (Storytel, Cash App, Duolingo). Not a new gradient per shot.
- **Type:** one family, two weights at most. Same size and position for every headline.
- **Emphasis device:** one (colour word, highlight box, italic, marker). Not three.
- **Device treatment:** same scale and vertical position on every shot so the set reads as a row.
- **One brand motif, optional:** HIRKA wraps every phone in a knitted rope; Moovit runs transit lines through
  every shot; Bible and Instagram use hand-drawn loops. A motif makes a set ownable without decoration.

## 2. Layout recipes

| Recipe | Spec `layout` | What it is | Use when | Library examples |
|---|---|---|---|---|
| **Device frame** | `device` | Headline top, real screen in a simple rounded frame, often bleeding off the bottom | Default for 70 % of shots | Waze, Kindle, Flo, ChatGPT |
| **Full-bleed UI** | `full` | The screen fills the canvas; caption in a band or pill | Content-rich apps, games, when the UI is the hero | Duolingo (coloured pill), Gardenscapes (banner) |
| **Zoom card** | `zoom` | A crop of the screen, enlarged as a card | The proof is one element on a busy screen | Flo, Capital One (720 score), ParkMobile (timer) |
| **Pulled-out callout** | `device` + `callouts` | Device plus one UI element lifted out, larger, with a soft shadow | Make the key element readable at thumbnail size | Indeed, Moovit ("Your bus is arriving NOW"), Gmail (Undo) |
| **Photo-led** | `device` + `background.image` | Real photo of the moment of use behind the device | Lifestyle, mobility, food, dating | Lyft, Tinder, Pinterest |
| **Poster** | `poster` | Giant type, no device | Max one per set, as a rhythm breaker | Uber "GO ANY-WHERE", Temu |
| **Panorama** | (design by hand) | One image continues across shots | Only if shot 1 still works alone | Bubilet, Garanti BBVA |

Rules of thumb:
- The **UI must stay big**: in exemplary sets the device usually spans 70–85 % of the canvas width.
- **Straight devices.** Tilted floating phones appear in 12 weak apps and 0 exemplary ones in the library.
  If you want energy, use a callout or a crop, not a 15° rotation.
- Don't draw a branded device bezel (Apple's or anyone's hardware artwork). A neutral rounded frame, or no
  frame, is cleaner and avoids trademark questions.
- Alternate caption position top/bottom only to make room for a photo or a tall element (Chick-fil-A,
  TaraGör), not for variety's sake.

## 3. Typography

- Use the **brand's font** if it has one. Otherwise one well-made sans that's installed; a serif can make a set
  feel editorial and human (Kindle, NYT, Tinder, Vinted, Suno - serif appears in 7 exemplary apps vs 1 weak).
- Headline size: big enough that 3–6 words fill 2 lines across ~80 % of the width. At 1206 px wide that's
  roughly 90–120 px. `render_set.py` auto-fits within your `max_lines`.
- Line height 1.05–1.15 for headlines; never justify; centre or left-align consistently.
- Left-aligned big headlines feel confident and modern (Cash App, Storytel); centred ones feel calm (Waze).
- Sub-lines at ~45–55 % of the headline size, same family, lighter weight or colour.
- Turkish capitals: `İ` / `I` - use `"case": "upper"` with `"lang": "tr"` in the spec; the renderer maps
  `i→İ` and `ı→I` correctly (Python's `.upper()` alone does not).

## 4. Colour and backgrounds

- Take the background from the brand, ideally one flat colour that also appears in the UI (Waze cyan, Spotify
  pink/green, Kalshi brown matched to its dark UI).
- Contrast: headline vs background ≥ 4.5:1 (the renderer warns below that).
- Gradients: allowed if they come from the brand and are subtle (ChatGPT's pastels, Suno's warm orange).
  The default purple→blue or pink→orange gradient is the most common "template" signal in the weak sets
  (`gradient-bg`: 8 weak vs 2 exemplary).
- Dark UI → dark or deep-colour background; light UI → light or saturated background. Don't put a white
  screen on a white background without a frame or shadow.
- Photos: real, matching the audience, not stock smiles at a phone.

## 5. Emphasis devices

Pick one per set. Spec syntax: wrap the word(s) in `*asterisks*` inside `headline`.

| Device | Spec `emphasis.style` | Example |
|---|---|---|
| Colour word | `color` | Gemini "Dive **deep** into any topic" in brand blue |
| Highlight box | `box` | Flo "Predict your [next period]" white box on lilac |
| Marker | `marker` | Threads yellow marker behind "conversation" |
| Italic / second font | `font` (with `emphasis.font`) | Kindle serif italic "Build a *habit*." |
| Bold weight | `font` (bold file) | WhatsApp "**Message privately** with end-to-end encryption" |

## 6. When the renderer isn't enough: the HTML route

For hand-drawn annotations, custom shapes, panoramas or brand motifs, build the shot as an HTML page at the
exact pixel size and screenshot it with a headless browser (Playwright or Chrome) if the environment has one:

```html
<body style="margin:0;width:1206px;height:2622px;background:#0b6;font-family:'Your Brand',sans-serif">
  <h1 style="margin:180px 96px 0;font-size:112px;line-height:1.08;color:#fff">Kaldığın bölüm<br>hep hazır</h1>
  <img src="screen.png" style="position:absolute;left:131px;top:620px;width:944px;border-radius:72px">
</body>
```
`page.set_viewport_size({"width":1206,"height":2622})` then `page.screenshot(path="01.png")`, then run
`check_set.py` on the result like any other set. Keep the same system rules as above.
