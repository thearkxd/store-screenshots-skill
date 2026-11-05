# Scene format (version-2 sets, `compose.py`)

A version-2 set describes every screenshot as a **scene**: a canvas and an ordered list of layers you place
freely. There is no built-in layout. The process that decides what goes in a scene is in
`design-process.md`; this file is the reference for writing one. A complete worked set is
`templates/scene.example.json` (the fictional Dizilog, concept "Tek Turuncu"). It shows the format, not a
look to reuse.

```bash
python3 scripts/compose.py render set.json --out out/                  # every locale × size: PNG + SVG + _render.json
python3 scripts/compose.py render set.json --out out/ --shots detail    # re-render one shot (numbering and report kept)
python3 scripts/compose.py xray set.json --shot promise -o x.png        # boxes, roles, margins, seam, thumbnail inset
python3 scripts/compose.py concepts a.json b.json c.json --board dna-board.jpg -o concepts.jpg
python3 scripts/compose.py render set.json --out out/ --history         # opt-in: compare with earlier sets, then log it
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
 "dna": "dna.json",                                      // optional: materials, UI mode and references to check against
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
 "materials": {"flat": "dna: flat dark cards", "photo": "dna: posters are the content"},
 "type": {
  "headline": {"font": "display", "size": 0.088, "min_size": 0.066, "line_height": 1.1, "tracking": -0.018,
               "color": "$ink", "max_lines": 3, "emphasis": {"style": "color", "color": "$accent"}},
  "datum":    {"font": "display", "size": 0.42, "line_height": 0.92, "tracking": -0.05, "color": "$accent"},
  "sub":      {"font": "text", "size": 0.036, "line_height": 1.35, "color": "$muted"},
  "callout":  {"font": "display", "size": 0.034, "color": "$ground"}}}
```

- **tokens** - every colour the set uses, named by role, taken from the DNA. Write `"$name"` anywhere a colour
  goes. The validator flags colours that aren't tokens (white and black are always allowed).
- **fonts** - paths (relative to the file that holds the campaign) or bundled aliases (`assets/fonts/FONTS.md`).
  Text layers use these names; the validator flags any other font.
- **materials** - what the set is made of, each with where it comes from. The names are flat, elevated, glass,
  glow, gradient, texture, paper, 3d, tilt, illustration and photo. The reason starts with its source:
  `"dna: …"` (the app shows it; with `"dna"` linked, the DNA must list it too), `"concept: …"` or
  `"brand guide: …"`. An effect in a shot needs its material here or a `"motive"` on the layer, or it is
  warned. The renderer finds:
  - glass: `glass` on a rect;
  - glow: `glow` on a layer, or a background `light`;
  - gradient: a gradient fill;
  - texture: grain;
  - tilt: a rotated screen;
  - 3d: a device3d layer;
  - illustration: an `svg` layer;
  - photo: a photo background.
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
 "alt": "Seenfy keşfet ekranı: %88 Sana Uygun rozetiyle önerilen bir film",       // ≤ 140 characters (Google Play)
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
- `role`: `headline`, `sub`, `display` (big type that isn't the headline), `footnote` (a small disclosure such as
  "Örnek veriler", at the bottom margin), `callout` (a label pointing at the UI, below), `label`, `proof`,
  `decor`, `brand`, `annotation`, `context` (a 3D device that sets the scene, §5);
- `motive` - required for `decor`: where the shape comes from;
- placement (§1), `rotate`, `opacity`.

| type | keys |
|---|---|
| `text` | `text` (with `*emphasis*` and `\n`), `style`, `w` (default 86 %), optional `h`, any type-style key (§3) |
| `screen` | `evidence` (screen id), `crop` `[x0, y0, x1, y1]` fractions or a region name, **`w` or `h` - never both**, `radius`, `frame`, `shadow`, `glow`, `lift` |
| `device3d` | a whole screen on a phone body turned in space: `evidence`, `w` or `h` (the body as if it faced you), placement on its silhouette, `rotate3d` `{"yaw", "pitch", "roll"}`, `model`, `body`, `camera`, `shadow` - see below |
| `image` | `asset` (a registered brand image: icon, logo, photo), same sizing as `screen`; `opacity` allowed |
| `rect` / `ellipse` | `w`, `h`, `radius` (rect), `fill` (colour or gradient), `stroke`, `stroke_width`, `shadow`, `glow`, `glass` (rect) |
| `path` | `d` in u (M L H V C S Q T Z, absolute and relative; no arcs), offset `x`/`y`, `fill`, `stroke`, `stroke_width`, `cap` |
| `svg` | `markup` (SVG elements) or `file`, drawn in u at offset `x`/`y`; `$tokens` allowed; no `<text>`/`<image>` |
| `group` | `layers`, and `rotate`/`opacity` for all of them together |
| `mark` | hand-drawn: `kind` circle / underline / arrow; `on` a screen id + `region` (fractions of that screen), or `box` in u; arrow `from` [x, y] and `to`; `color`, `width`, `pad`, `curve` |

Screen options:
- `frame`: `{"style": "phone", "border": 0.02, "color": "#0E0E10"}` (with the island) · `"android"` (punch hole) ·
  `"plain"` (a keyline, no island: `{"style": "plain", "border": 0.005, "color": "$edge", "island": false}`).
  No frame on Google Play.
- `shadow`: `soft`, `deep`, `tight` or `{"blur", "dy", "dx", "opacity", "color"}` (u).
- `glow`: `{"color": "$accent", "blur": 0.08, "opacity": 0.45, "spread": 0}` (u) - a coloured halo with no
  offset. It also works on rects and ellipses. It is the `glow` material.
- `lift`: `{"from": "main", "scale": 1.15, "dx": 0, "dy": 0}`. The same region, cut from the same screen, drawn
  over its own place in the `from` layer and enlarged: the element the headline talks about comes forward. The
  lifted piece must cover its place, or the UI shows twice (warned).
- Name crops once: `evidence.py name evidence.json home continue-card 0.04,0.21,0.78,0.44`. Then
  `"crop": "continue-card"`; the name also reads the region's text up close for the claim check.
- **Anything you lift or show as a card: name it with `--snap`.** Draw the box a little larger than the
  component. `--snap` tightens it to the component's own edges and records its corner radius. A layer with
  that crop then keeps the component's radius at its new size, unless you give `"radius"`. A lift cut wider
  than its component shows two edges; a lift of a row with no background of its own has no edge at all.
  Both read as broken UI, and both are warned.
- **Crops end in gaps:** put a crop's edges between components, or at the screen's own edge, never through a
  card, a row or a word.

### 3D devices (`device3d`)

```json
{"type": "device3d", "id": "phone", "evidence": "home", "w": 0.8, "cx": "50%", "y": 0.62,
 "rotate3d": {"yaw": -18, "pitch": 6, "roll": 0}, "model": "island", "body": {"color": "titanium"}}
```

**How it draws:**
- The screen is mapped onto the front of the body with the exact perspective a camera gives a flat object (a
  homography). Every pixel of the UI is there, in its own proportions.
- The body is drawn in the same camera and lit by one light: glass, rounded slab, metal band, keys, island or
  punch hole.

**Settings:**
- **`rotate3d`** (degrees):
  - `yaw` > 0 turns the face to the viewer's right, `pitch` > 0 tilts it up, `roll` > 0 turns it clockwise;
  - limits: yaw ±40, pitch ±30, roll ±25.
- **`"role": "context"`**: a device that sets the scene and proves nothing, such as a phone on the table behind
  the proof, or a second phone half out of frame.
  - Its limits are wider: yaw ±60, pitch ±45, roll ±35.
  - It gets no far-side warning.
  - Its screen doesn't count as proof or as content.
  - A shot whose only devices are context devices is warned.
- **`model`:**
  - `island` (iPhone-like, the default);
  - `punch` (Android, the default on android sizes);
  - `slab` (no cutout, no keys; the default for iPad/Duo).
- **`body`**: `color` (`titanium`, `graphite`, `silver`, `black`, `white`, a hex or a `$token`), and optionally
  `radius`, `bezel`, `thickness` (fractions of the body width) and `sheen` (0-0.6, a reflection band across the
  glass bezel, placed by the light; the screen is drawn over it, so the UI is untouched).
- **`camera`**: `{"fov": 22, "light": [-0.45, -0.75, -0.5]}`.
  - Put it in the **campaign** (`"campaign": {"camera": …}`), so every device in the set shares one lens and
    one light.
  - `fov` 6-60: smaller is flatter, like a long lens.
  - `light` points from the device towards the light (x right, y down, z away from the viewer).
  - `rim`: `{"color": "$accent", "strength": 0.6, "dir": [0.85, -0.3, 0.45]}`, a second, coloured light from
    behind. It edges the band and the keys, never the glass or the screen. Coloured light is the `glow`
    material, so give it its reason. It belongs to the campaign's camera like the key light, so the set keeps
    one lighting.
- **`shadow`**: `"auto"` (the default) falls away from the light; a preset or `{…}` as for screens; `"none"`.

**Not on a device3d:**
- `crop` (use a flat screen);
- `rotate` (use `rotate3d`);
- `frame`, `radius`;
- filters or `opacity`.

You can't lift from a 3D device, but a `mark` `on` it follows its perspective.

**Glass.** Use it on a top-level rect:
`{"type": "rect", "w": 0.6, "h": 0.16, "radius": 0.04, "fill": null, "glass": {"blur": 0.03, "tint": "#FFFFFF",
"opacity": 0.12, "edge": "#FFFFFF", "edge_opacity": 0.28}}`.
- The panel blurs whatever is drawn below it in the shot, tints it, and gives it a hairline edge.
- Text goes in a layer above it.
- Keep it off screens: glass over the UI is painting over it, and is warned.

**Callouts.** A callout is a short label that points at one part of the UI ("Spoiler gizli", "3 hatırlatma").
The campaign needs a text style whose name starts with `callout`. Draw it as a text layer
`{"role": "callout", "style": "callout", …}` over a rect `{"role": "callout", "fill": "$accent", "radius": …}`.
- In the campaign's style, it reads as the campaign talking. So it is exempt from the "looks like app UI"
  check, which a callout in any other style still gets.
- It may reach over a screen's edge, but covers at most 8 % of the screen.
- At least 0.03u, at most four per shot. Add a `mark` arrow if it needs to point.

**SVG recipes.** Each one uses `$tokens`, is drawn in u, and needs a `"motive"` saying what in the app it comes
from:
```jsonc
// the app's own progress bar as a motif - motive: "the episode progress bar"
{"type": "svg", "role": "decor", "motive": "the episode progress bar", "x": 0.08, "y": 1.9,
 "markup": "<rect width='0.84' height='0.012' rx='0.006' fill='$edge'/><rect width='0.52' height='0.012' rx='0.006' fill='$accent'/>"}
// a spot illustration in the app's icon style: outline, the icons' stroke weight, round caps
{"type": "svg", "role": "illustration", "motive": "the calendar tab icon, drawn large", "x": 0.62, "y": 0.2,
 "markup": "<g fill='none' stroke='$accent' stroke-width='0.012' stroke-linecap='round' stroke-linejoin='round'><rect x='0' y='0.03' width='0.26' height='0.24' rx='0.04'/><path d='M0 0.1H0.26M0.07 0V0.06M0.19 0V0.06'/><circle cx='0.13' cy='0.18' r='0.025' fill='$accent'/></g>"}
// a pattern from the card radius: the app's cards, as a quiet ground texture
{"type": "svg", "role": "decor", "motive": "the poster cards' 0.04u radius", "opacity": 0.25, "x": 0, "y": 1.4,
 "markup": "<g fill='$card'><rect x='0.06' y='0' width='0.26' height='0.38' rx='0.04'/><rect x='0.37' y='0.06' width='0.26' height='0.38' rx='0.04'/><rect x='0.68' y='0.12' width='0.26' height='0.38' rx='0.04'/></g>"}
// confetti from the app's own shapes - only over a result the screen shows (a streak, a goal reached)
{"type": "svg", "role": "decor", "motive": "the app's check and dot shapes, for the finished goal", "x": 0.1, "y": 0.9,
 "markup": "<g fill='$accent'><circle cx='0.05' cy='0.04' r='0.012'/><circle cx='0.7' cy='0.1' r='0.009'/></g><path d='M0.3 0.02l0.02 0.02 0.04-0.04' stroke='$accent' stroke-width='0.008' fill='none' stroke-linecap='round'/>"}
```
- Draw with the app's own vocabulary: its stroke weight, its corner radius, its fills.
- An illustration the app doesn't use anywhere needs the concept as its reason (`"illustration"` in the
  campaign's materials).
- Stock blobs, sparkles and generic confetti have no motive for any app.

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
- `<text>` or `<image>` inside an `svg` layer;
- a `device3d` turned past its limits, with a crop, a 2D `rotate`, a filter, or lifted from.
- `glass` on anything but a top-level rect.

**Warned** (printed, stored in `_render.json`, reprinted by `check_set.py`):

*Truth:*
- text or a shape covering more than 2 % of a screen;
- a small rounded box with text in it (it looks like app UI);
- no `proof`;
- a number that isn't in the text read from the screens the shot shows;
- a lifted piece that doesn't cover its place.

*Crops and lifts that look broken:*
- a crop edge that slices through words (OCR) or through a component - UI on both sides of the edge;
- a lifted piece cut wider than its component (a double edge);
- a lifted piece with no visible edge (its background runs into what is behind it).

*Legibility:*
- headline under 0.06u, sub-line under 0.03u, a footnote outside 0.02-0.03u;
- text within 0.03u of an edge;
- contrast under 3:1 for large text or 4.5:1 for small, measured on the rendered pixels;
- text or a hand mark across the seam of a span;
- a split screen that isn't centred on the seam.

*Resolution:*
- a screen enlarged more than 1.8× its pixels;
- a full screen from the wrong kind of device.

*Campaign:*
- decoration without a `motive`, or more than 5 decorative layers;
- an effect (glass, glow, gradient, grain, tilt, 3D, illustration) with no source in the campaign's
  `materials` or the layer's `motive`;
- a campaign material without a reason, or a `dna:` reason the DNA doesn't list;
- campaign colours taken from a reference (`dna.py reference`) rather than the app;
- a callout outside the campaign's callout style, under 0.03u, covering more than 8 % of a screen, or more than four in a shot;
- colours that aren't tokens;
- fonts outside the campaign;
- more than one headline font in the set.

*3D:*
- a device whose far side shrinks below 72 % of its near side, so the UI stops reading (not for `context`);
- a device without a shadow (it floats);
- a shot whose only devices are `context` devices (nothing proves the headline);
- devices in one set with different lenses or lights (rim light included);
- turned phones in more than two shots, or in most of the set.

*Set:*
- three or more shots with the same composition (headline and main visual in the same place and scale);
- none of the first three headlines uses a promise word;
- the same screen with the same crop in two shots;
- the same content in two shots through different screens (the same posts on the calendar and on the home
  screen), read from the screens' text;
- only one iPhone size;
- the skill's own habits on most shots (`anti-ai.md`):
  - a lift or a mark in most shots;
  - every shot's phone cropped at the bottom edge;
  - one effect on every shot without a `dna:` reason;
  - a light app shown only on dark grounds;
- a shot that repeats a bundled example's placements number for number;
- with `--history`: a set that shares most of its look with one made earlier for another app.

*Google Play* (labelled `[Play recommendation]`; `check_set.py` adds the requirements and promotion rules):
- a device frame, or a 3D device;
- captions over 20 % of the height.
