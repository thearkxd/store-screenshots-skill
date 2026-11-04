# Scene format (version-2 sets, `compose.py`)

A version-2 set describes every screenshot as a **scene**: a canvas and an ordered list of layers you place
freely. There is no built-in layout. The process that decides what goes in a scene is in
`design-process.md`; this file is the reference for writing one. A complete worked set is
`templates/scene.example.json` (Seenfy, concept "Ekrandaki Sayı").

```bash
python3 scripts/compose.py render set.json --out out/                  # every locale × size: PNG + SVG + _render.json
python3 scripts/compose.py render set.json --out out/ --shots detail    # re-render one shot (numbering and report kept)
python3 scripts/compose.py xray set.json --shot promise -o x.png        # boxes, roles, margins, seam, thumbnail inset
python3 scripts/compose.py concepts a.json b.json c.json --board dna-board.jpg -o concepts.jpg
```

Drawn with resvg (`pip install resvg-py`) when it's installed, otherwise with Pillow (`--backend pillow`);
`svg` layers need resvg. Every shot is also written as `NN.svg`, which opens in Figma or Illustrator with live
text (fonts referenced by family name) and the screens embedded.

## Contents
1. Units and placement
2. The set file
3. The campaign
4. Shots and backgrounds
5. Layers
6. Sizes, stores and locales
7. What the renderer refuses, what it warns about

---

## 1. Units and placement

- **1u = the canvas height ÷ 2.174** - the full width of an iPhone canvas. Every canvas is 2.174u tall; its
  width depends on the device: iPhone 1u, Android 1.22u, iPhone Duo outer 1.49u, a span pair 2u. So type
  sizes and gaps given in u keep their proportion to the height on every device.
- Any x or width can also be **`"N%"` of the canvas width**, any y or height `"N%"` of its height. Use `%`
  for things that should fill the width on every device (`"w": "88%"`), u for things tied to the type.
- Horizontal anchor: `x` (left edge) · `cx` (centre) · `right` (distance of the right edge from the canvas's
  right edge). Vertical: `y` · `cy` · `bottom`. No anchor = centred.
- **Relative placement:** `"below": "head"`, `"above"`, `"right_of"`, `"left_of"` an earlier layer's `id`,
  with `"gap"` in u (default 0.03). A sub-line placed `below` its headline follows it however the headline wraps.
- In a span pair (`"span": 2`) the canvas is two slots wide: slot 1 is x 0-1u, slot 2 x 1-2u (iPhone). `cx: "50%"`
  is the seam.
- `rotate` (degrees, clockwise) and `opacity` work on every layer except that screens can't be faded.

## 2. The set file

(`//` comments here are explanations - JSON files can't contain them.)

```jsonc
{"version": 2,
 "app": "Seenfy", "lang": "tr",                         // or "locales": ["tr", "en"]
 "evidence": "evidence.json",                            // evidence.py build - the only app pixels allowed
 "sizes": ["ios", "ios-large", "android"],               // presets: references/store-specs.md
 "promise_words": ["izle", "film", "dizi"],              // one must appear in the first three headlines
 "concept": {"name": "Ekrandaki Sayı", "idea": "..."},   // shown on the concept sheet
 "campaign": { ... } | "campaign.json",
 "shots": [ ... ],
 "feature_graphic": {"background": ..., "layers": [...]}}  // Google Play, 1024×500 (2.174u tall, 4.45u wide)
```

## 3. The campaign

The campaign is what holds the set together while every composition differs (`design-process.md` §5).

```json
"campaign": {
 "tokens": {"ground": "#121212", "ink": "#EAF6F6", "muted": "#A9ADB5", "accent": "#5460F0"},
 "fonts": {"display": "fonts/Poppins-SemiBold.ttf", "text": "fonts/Poppins-Regular.ttf"},
 "type": {
  "headline": {"font": "display", "size": 0.088, "min_size": 0.066, "line_height": 1.1, "tracking": -0.018,
               "color": "$ink", "max_lines": 3, "emphasis": {"style": "color", "color": "$accent"}},
  "datum":    {"font": "display", "size": 0.42, "line_height": 0.92, "tracking": -0.05, "color": "$accent"},
  "sub":      {"font": "text", "size": 0.036, "line_height": 1.35, "color": "$muted"}}}
```

- **tokens** - every colour the set uses, named by role, taken from the DNA. Write `"$name"` anywhere a colour
  goes. The validator flags colours that aren't tokens (white and black are always allowed).
- **fonts** - paths (relative to the file that holds the campaign) or bundled aliases (`assets/fonts/FONTS.md`).
  Text layers use these names; the validator flags any other font.
- **type** - named text styles. A text layer takes `"style": "headline"` and may override any key.
  - `size`, `min_size` (u): the text shrinks towards `min_size` until it fits its `w` (and `h`, if given).
  - `line_height`, `tracking` (fraction of the size), `align` left/center/right, `case` none/upper/lower
    (Turkish-safe), `max_lines`, `color`, `weight`.
  - **Line breaks you write are kept:** with a `\n` in the text, it shrinks before it breaks a line again
    (`"wrap": true` lets it re-wrap).
  - `emphasis` - how `*words*` are set:
    - `color` - another colour;
    - `font` - a second face (`font`, `scale`, `color`);
    - `box` - a filled box behind the words (`color`, `text_color`, `radius` as a fraction of the size; 0.5 is a
      pill, `pad`);
    - `marker` - a highlighter band;
    - `underline` or `scribble` - hand-drawn marks (`mark_color`, `mark_width`).

## 4. Shots and backgrounds

```jsonc
{"id": "promise",
 "message": "Picks you'll love, not the charts - the match score proves it",   // the composition brief's message
 "proof": [{"evidence": "sana-uygun", "region": "match-badge"}],              // what proves the headline
 "span": 1, "stores": ["ios"],                                                 // optional
 "background": {"fill": "$ground", "grain": 0.03},
 "layers": [ ... ]}
```

`background`:
- `{"fill": "$ground"}` - a colour; or `{"fill": {"linear": {"angle": 180, "stops": [[0, "$a"], [1, "$b"]]}}}`;
  or `{"fill": {"radial": {"cx": 0.5, "cy": 0.3, "r": 0.6, "stops": [...]}}}`. A gradient needs a reason from the
  DNA or the concept (`design-process.md` §7).
- `{"sample": {"evidence": "id", "crop": [x0, y0, x1, y1], "blur": 0.08, "darken": [0.6, 0.8], "tint": "$ground"}}` -
  the app's own colours, blurred into a ground.
- `{"image": {"asset": "photo"}}` - a registered brand photo.
- Optional: `"light": {"x": "50%", "y": "10%", "r": 0.7, "opacity": 0.25, "color": "$accent"}` (a list for
  several), and `"grain": 0.02-0.04`.

## 5. Layers

Common keys:
- `type`;
- `id` (to anchor, lift or mark later layers);
- `role`: `headline`, `sub`, `display` (big type that isn't the headline), `label`, `proof`, `decor`, `brand`,
  `annotation`;
- `motive` - required for `decor`: where the shape comes from;
- placement (§1), `rotate`, `opacity`.

| type | keys |
|---|---|
| `text` | `text` (with `*emphasis*` and `\n`), `style`, `w` (default 86 %), optional `h`, any type-style key (§3) |
| `screen` | `evidence` (screen id), `crop` `[x0, y0, x1, y1]` fractions or a region name, **`w` or `h` - never both**, `radius`, `frame`, `shadow`, `lift` |
| `image` | `asset` (a registered brand image: icon, logo, photo), same sizing as `screen`; `opacity` allowed |
| `rect` / `ellipse` | `w`, `h`, `radius` (rect), `fill` (colour or gradient), `stroke`, `stroke_width`, `shadow` |
| `path` | `d` in u (M L H V C S Q T Z, absolute and relative; no arcs), offset `x`/`y`, `fill`, `stroke`, `stroke_width`, `cap` |
| `svg` | `markup` (SVG elements) or `file`, drawn in u at offset `x`/`y`; `$tokens` allowed; no `<text>`/`<image>` |
| `group` | `layers`, and `rotate`/`opacity` for all of them together |
| `mark` | hand-drawn: `kind` circle / underline / arrow; `on` a screen id + `region` (fractions of that screen), or `box` in u; arrow `from` [x, y] and `to`; `color`, `width`, `pad`, `curve` |

Screen options:
- `frame`: `{"style": "phone", "border": 0.02, "color": "#0E0E10"}` (with the island) · `"android"` (punch hole) ·
  `"plain"` (a keyline, no island: `{"style": "plain", "border": 0.005, "color": "$edge", "island": false}`).
  No frame on Google Play.
- `shadow`: `soft`, `deep`, `tight` or `{"blur", "dy", "dx", "opacity", "color"}` (u).
- `lift`: `{"from": "main", "scale": 1.15, "dx": 0, "dy": 0}`. The same region, cut from the same screen, drawn
  over its own place in the `from` layer and enlarged: the element the headline talks about comes forward. The
  lifted piece must cover its place, or the UI shows twice (warned).
- Name crops once: `evidence.py name evidence.json home continue-card 0.04,0.21,0.78,0.44`. Then
  `"crop": "continue-card"`; the name also reads the region's text up close for the claim check.

## 6. Sizes, stores and locales

Any value can vary by size or locale, at any depth:
- `{"default": …, "android": …}` - keys: an exact preset, a device class (`iphone`, `android`, `duo`, `ipad`),
  a store (`ios`, `android`), then `default`;
- `{"tr": …, "en": …}` for a locale.

A layer that is `null` for a size is left out there: `{"default": {…sub-line…}, "android": null}`. A shot with
`"stores": ["ios"]` is App Store only.

What changes per device is usually small: `%` widths fill a wider Android canvas by themselves. **Google Play**
wants no device frame and taglines on at most 20 % of the height. The 20 % counts every word on the canvas,
including big type, so give big type a smaller `size` in the android variant. On iPhone Duo and iPad, use
screens captured on that device, given per size.

## 7. What the renderer refuses, what it warns about

**Refused** (the shot isn't drawn):
- a screen or asset that isn't in the evidence manifest;
- a screen file that changed since the manifest was built (SHA-256);
- `w` and `h` together on a screen (it would stretch);
- `filter`, `blur`, `tint`, `recolor`, `saturation`, `brightness` or `opacity` on a screen;
- `<text>` or `<image>` inside an `svg` layer.

**Warned** (printed, stored in `_render.json`, reprinted by `check_set.py`):

*Truth:*
- text or a shape covering more than 2 % of a screen;
- a small rounded box with text in it (it looks like app UI);
- no `proof`;
- a number that isn't in the text read from the screens the shot shows;
- a lifted piece that doesn't cover its place.

*Legibility:*
- headline under 0.06u, sub-line under 0.03u;
- text within 0.03u of an edge;
- contrast under 3:1 for large text or 4.5:1 for small, measured on the rendered pixels;
- text or a hand mark across the seam of a span;
- a split screen that isn't centred on the seam.

*Resolution:*
- a screen enlarged more than 1.8× its pixels;
- a full screen from the wrong kind of device.

*Campaign:*
- decoration without a `motive`, or more than 5 decorative layers;
- colours that aren't tokens;
- fonts outside the campaign;
- more than one headline font in the set.

*Set:*
- three or more shots with the same composition (headline and main visual in the same place and scale);
- none of the first three headlines uses a promise word;
- the same screen with the same crop in two shots;
- only one iPhone size.

*Google Play:*
- a device frame;
- captions over 20 % of the height.
