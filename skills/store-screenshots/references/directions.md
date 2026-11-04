# Design directions (presets: the fast path and fallback)

> **New sets are designed, not picked:** the default route is `design-process.md` - the app's DNA, three
> app-specific concepts, free scenes rendered by `compose.py`. Use these presets when the user wants a quick
> conventional set, the brand already has a screenshot system to match, or scenes can't be rendered - and say
> so. They also work as a reference: each preset is one coherent campaign system (ground, type, emphasis,
> device, motif), worth studying when you write your own.

A **direction** is a complete visual system - ground, type pairing, emphasis device, device treatment,
motif and a per-shot colour rotation - stored as a preset in `assets/directions/<name>.json`. It replaces
"one template for every app": the same copy and screens look like a different, deliberate brand in each
direction. The brand's colours flow in through tokens, so every direction is still *this* app's.

## Contents
1. The seven directions
2. Choosing: angle → category → brand → concepts
3. The concept checkpoint (`concepts.py`)
4. Using a direction in a spec
5. Brand tokens
6. Overriding and extending
7. Extra spec features (overline, stickers, annotations, shapes, device)
8. Span pairs (one picture across two slots)

---

## 1. The seven directions

| Direction | Looks like | Type | Fits | Avoid for |
|---|---|---|---|---|
| `editorial` | A magazine page: paper + grain, large serif headline with one italic word, small-caps overline | Instrument Serif + Inter | news, books, reference, finance, lifestyle, curated entertainment | kids, casual games, loud offers |
| `poster` | Huge condensed caps on a brand-colour flood, phone pushed to one side, colour rotation | Anton | food, shopping, travel, sports, finance, deals | calm/clinical products; headlines over 5 words |
| `playful` | Tinted ground with dots, rounded type, highlight-box emphasis, flat phone with an offset shadow, stickers | Baloo 2 | social, games, education, music, lifestyle | finance, health, anything where trust beats charm |
| `cinematic` | The app's own imagery blurred and darkened into the ground, grain, a soft brand light, serif-italic emphasis | Inter Display + Instrument Serif italic | entertainment, music, photo/video, books, games | plain white UIs with no imagery |
| `crafted` | Warm paper, a continuous wave motif that runs across the whole set, soft serif display type | Fraunces | weather, lifestyle, food, travel, navigation, local services | tech-forward or data-heavy products |
| `native` | Clean light gradient, big straight phone, Apple-like sans; nothing between the user and the UI | Inter Display | productivity, utilities, business, health, education | plain or very busy UIs (it hides nothing) |
| `utility` | Dark ground with a faint grid, grotesk headlines, mono numbered overline ("01 — SYNC") | Space Grotesk + JetBrains Mono | developer tools, utilities, finance/data, weather, sports stats | emotional consumer products, kids, food |

`python3 scripts/concepts.py --list` prints each direction's summary, fits and library references.

## 2. Choosing

1. **Angle first** (`angle.md` §3): curated → editorial/cinematic, energy/deals → poster, community →
   playful, immersion → cinematic, care/ritual → crafted, competence → native, precision → utility.
2. **Category** (`categories.md`): what the neighbours look like. Being the only calm set among loud ones (or
   the reverse) is a real advantage in search results - as long as it still fits the angle.
3. **Brand:** a direction must carry the brand's colours and, if there is one, its font. If the brand is a
   pale pastel, `poster` needs `secondary`/`ink` to do the heavy lifting; if the UI is dark, `cinematic` and
   `utility` sit naturally next to it.
4. **Show three** - safe · bold · unexpected - and let the user choose (next section). Never pick silently.

## 3. The concept checkpoint

Before rendering the whole set, render shots 1–3 in three directions on one sheet:

```bash
python3 scripts/concepts.py set.json -o concepts.jpg                       # picks from the spec's "category"
python3 scripts/concepts.py set.json --directions cinematic poster editorial --shots 1 2 3 -o concepts.jpg
python3 scripts/concepts.py set.json --locale en -o concepts-en.jpg
```

It keeps the spec's copy, screens, crops, callouts, stickers and annotations and drops its look keys
(background, colours, fonts, emphasis, device…), so each row shows the direction's own system. Show the
sheet to the user with one line per row on *why* it fits the angle, and ask which one (or which mix - "A's
type with B's ground"). Then set `"direction"` in the spec and render everything. Skip the checkpoint only if
the user already has a brand system to follow, or asked you to just deliver - then say which direction you
used and why.

## 4. Using a direction in a spec

```json
{
  "direction": "editorial",
  "category": "entertainment",
  "brand": {"primary": "#5B5BF5", "secondary": "#FFB547", "ink": "#121212", "paper": "#F2EFE9"},
  "shots": [
    {"overline": "Picked for you", "headline": "Not what's popular. What you'll *love*.", "screen": "screens/01.png"},
    {"layout": "poster", "headline": "No *spoilers*. Promise."}
  ]
}
```

Merge order, lowest to highest: renderer defaults → direction `style` → the direction's per-shot
`rotation[i % n]` (or `poster_defaults` for posters; `last_defaults` for the last shot) → the spec's
`"style"` → the shot's own keys. So anything you write in the spec wins; you only write what you want to
change. `"rotation": false` at the top of the spec keeps one ground for every shot.

No `"brand"`? Use `"brand_from": ["screens/01.png", "icon.png"]` to guess primary/secondary/ink/paper from
the icon and screens - then check the guess, because a screenshot's dominant colour is often a photo, not
the brand.

## 5. Brand tokens

Directions refer to colours as tokens; you can use them in your own spec too (`"text_color": "$primary"`).

| Token | Default |
|---|---|
| `$primary`, `$secondary`, `$accent`, `$ink`, `$paper`, `$dark` | from `"brand"` (secondary/dark/accent derived if missing) |
| `$primary_tint` / `$primary_light` / `$primary_shade` | primary mixed with white 82 % / white 38 % / black 55 % |
| `$secondary_tint` | secondary with white 80 % |
| `$paper_shade`, `$ink_soft` | paper darkened 7 %; ink softened 35 % toward paper |
| `$on_primary` | paper or ink, whichever reads on primary |

Any token can be set explicitly in `"brand"` when the derived one is wrong.

## 6. Overriding and extending

- **Tweak one thing:** put it in `"style"` (whole set) or on a shot. `"style": {"font": "sans-bold"}` gives
  `poster` a sans; `"style": {"device": {"width": 0.86}}` makes the phone bigger.
- **One colour on every shot:** `"rotation": false`, or `"background"` in `"style"`; for one shot, set
  `"background"` on that shot.
- **Brand font:** `"style": {"font": "fonts/Brand-Bold.ttf", "emphasis": {"font": "fonts/Brand-Italic.ttf"}}`.
  The renderer warns when a font lacks a glyph the copy needs (ğ ş İ ı…).
- **New direction:** copy a JSON in `assets/directions/`, change `label`, `summary`, `fits`, `style`,
  `rotation`. Keys: `style` (any style key), `shot_defaults`, `rotation` (list, cycles per shot),
  `poster_defaults`, `last_defaults`. Colours may be tokens.

## 7. Extra spec features

All of these work with or without a direction. Coordinates are fractions of the canvas unless noted.

**Overline** - a small label above the headline that names the feature (NYT, Kindle):
`"overline": "Collections"` on a shot; style with `"overline_style": {"font", "size", "color", "tracking",
"case", "gap", "pill"}`; `"overline_prefix": "{n:02d} — "` numbers every shot; `"show_overline": false`
hides it.

**Stickers** - short rotated labels on a pill, for a UI fact or a voice aside:
`"stickers": [{"text": "%88 match", "x": 0.74, "y": 0.47, "rotate": -6, "bg": "$secondary", "color": "$ink"}]`.
One per shot at most; use the app's own words.

**Annotations** - hand-drawn marks (Instagram, Weather & Radar, Bible):
```json
"annotations": [
  {"type": "circle", "screen_box": [0.06, 0.52, 0.5, 0.6]},
  {"type": "arrow", "from": [0.84, 0.36], "screen_box": [0.06, 0.52, 0.5, 0.6], "text": "tap once", "text_at": [0.82, 0.33]}
]
```
Types: `circle`, `underline`, `arrow` (`from` + `to`, or `from` + a box), `note` (just `text`).
`screen_box` is a fraction of the *screen image* and follows the device (position, scale, rotation);
`box` is a fraction of the canvas. Default colour `#FF4D2E`, font `hand` (Caveat). Mark the one thing the
headline is about - never more than one mark per shot.

**Shapes** - drawn behind the device: `circle` (`x, y, r`, optional `stroke`), `arch`, `rect`, `band`
(rotated stripe), `grid`, `dots`, `wave` (continuous across the set: `y, amp, period, phase, width`,
optional `double`), `line` (`points` in set space - x = shot index + fraction - so one line can run through
every shot, smoothed). Use one motif per set, not a collage.

**Device** - `"device": {"style": "phone" | "android" | "flat" | "none", "width", "x" (centre, fraction),
"dy", "gap", "border_color", "shadow", "rotate"}`. `flat` is a solid border with `flat_border`,
`flat_radius`, `offset_shadow`, `offset_color` (the playful look). Keep `rotate` at 0 - tilted phones are a
weak-set signal (`anti-ai.md`); if you use it, ±3° on a single shot at most.

**Background** - `{"color"}`, `{"gradient": [top, bottom]}`, `{"image": "photo.jpg"}`, or
`{"sample": true, "box": [x0, y0, x1, y1], "blur", "darken": [top, bottom], "tint"}` (blurs a part of the
shot's own screen into the ground). Add `"grain": 0.03` for paper/film texture and
`"light": {"color", "x", "y", "r", "opacity"}` for one soft glow.

**Motifs that clear the caption** - `"clear_caption": 0.012` on a `wave` or `line` keeps its top below the
lowest caption in the whole set (the same shift on every shot, so it still lines up from shot to shot). The
crafted direction's ribbon uses it.

## 8. Span pairs

One spec entry, two slots. Rules and when to use one: `layouts.md` §2b. Inside a span every x runs **0..2**
(1 = the seam): `device.x`, sticker and annotation positions, shape x, `line` points (in set space, like every
line). y and sizes are as in one shot. The halves are ordinary shots: any caption keys, `screen`, `layout`
(device, zoom, full, poster), `callouts`, `stickers`, `annotations` - with half-local coordinates.

**Bridge** - one phone across the seam (top-level `screen`):
```json
{"span": 2, "screen": "screens/02-calendar.png",
 "headline": "Know the moment\n*it drops*",
 "halves": [{"overline": "Calendar"}, {"headline": "The calendar\n*fills itself*"}],
 "annotations": [{"type": "circle", "screen_box": [0.74, 0.33, 0.92, 0.36]}]}
```
The phone is centred on the seam by default (`device.x` 1.0, an even width so both halves get the same
pixels). Top-level `headline`/`sub`/`overline` belong to the left half. `callouts` and `annotations` with
`screen_box` follow the shared phone. Captions sit at the top in both halves (no posters or zooms beside a
bridge phone); the phone starts below the taller caption.

**Pair** - a shared ground behind two shots (no top-level `screen`):
```json
{"span": 2, "background": {"gradient": ["$paper", "$primary_tint"], "grain": 0.03},
 "shapes": [{"type": "line", "points": [[5.05, 0.9], [5.6, 0.84], [6.3, 0.9], [6.95, 0.86]], "color": "$primary"}],
 "halves": [{"headline": "Check off\n*every episode*", "screen": "screens/05-detail.png"},
            {"headline": "*No* spoilers.\nPromise.", "layout": "poster"}]}
```
A sampled ground (`cinematic`) samples the bridge screen, or the first half's screen.

Output: the span writes two consecutive files (`02.png`, `03.png`); `_render.json` marks both with
`"span": "02-03"`, and `concepts.py` shows both halves with the store gap. A direction treats a span as one
entry: one ground colour from the rotation, the next entry changes colour.

Errors (render stops): `"span"` other than 2, `"halves"` without a span or with more than two entries, a
shared `screen` plus a half's own `screen`, crops or callouts on a pair span (put them in the half), bottom
captions/posters/zooms beside a bridge phone. Warnings: the phone doesn't cross the seam (an explicit `device.x` too far off 1.0), a sticker/callout/annotation crosses the seam, a half without a headline, a span on 3-4, more
than one span (two in sets under 8), too many screenshots.
