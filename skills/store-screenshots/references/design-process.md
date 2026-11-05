# The design process: from the app's DNA to a campaign

This skill designs each set for one app. It doesn't pick a template and fill it. The steps:
1. Measure the app's look from its real screens: its **visual DNA**.
2. Write concepts that could only belong to this app.
3. Compose every screenshot from its message.
4. Hold the set together with a campaign system, not a layout.

`scene-format.md` is the file format. The seven presets of `render_set.py` (`directions.md`) are reference
and fallback (§10).

## Contents
1. The truth rules
2. Evidence: the only pixels you may show
3. Visual DNA
4. Concepts: three ideas, not three colour schemes
5. The campaign system: what stays, what changes
6. Composition briefs: one per shot
7. Writing the scenes
8. Look, fix, look again
9. Sizes and stores
10. When to use the presets instead
11. The Seenfy pilot, as an example

---

## 1. The truth rules

Originality never costs the truth. Breaking a truth rule isn't a design choice.

**Allowed with the app's real UI:**
- scale it (proportionally);
- crop it;
- round its corners (a mask);
- add a shadow;
- rotate it a little;
- place it on any ground;
- lift a region forward, larger, over its own place;
- point at it with a hand mark;
- put several crops of one screen side by side;
- turn the whole screen in 3D on a device body (`device3d`), within the angle limits. That is a rigid object
  photographed at an angle, not a distortion: the renderer maps it with the camera's exact perspective.

**Never:**
- stretch it (a screen takes `w` or `h`, never both);
- recolour it, filter it or fade it;
- paint text or shapes over it;
- redraw a UI component - a button, a badge, a card, a chart;
- show a screen the evidence doesn't have;
- change its numbers.

**A UI look-alike is cropped from a screen, or it isn't there at all.** If the headline talks about a badge,
the badge is a crop of the real badge. A marketing sticker must not look like a button the app doesn't have.

**Claims:** every headline names its proof (`"proof"`: which screen and region shows it). Every number on the
canvas must be readable on the screens the shot shows. That includes a giant number, not only the headline.

**Data:** the screens must look lived-in and consistent (`intake.md` §5). The renderer can't fix thin data,
and you must not fake it.

## 2. Evidence: the only pixels you may show

```bash
python3 scripts/evidence.py build screens/ --assets icon.png -o evidence.json   # ids, sizes, SHA-256, OCR words
python3 scripts/evidence.py show evidence.json home -o home.grid.png             # grid + OCR boxes, to read crops
python3 scripts/evidence.py name evidence.json home continue-card 0.04,0.21,0.78,0.44
```

- Raw screens only, at the device's native resolution (`intake.md` §5). A crop drawn at more than 1.8× its
  pixels looks soft, and the renderer warns.
- **Name every region you'll crop:** the name documents the crop. It also reads the text of the region up close
  (small UI text like a badge or a chip is often missed on the whole screen), so a claim like "%88" can be
  checked.
- **Cut components, not slices.**
  - A crop's edges go through gaps between components, or along the screen's own edge.
  - Anything you lift, or show as a card, is named with `--snap`. It is then cut exactly to its own edges and
    keeps its own corner radius.
  - A lift with a margin around the card shows two edges. A lifted row with no background of its own shows
    none. Either reads as a rendering bug, and the renderer warns about both.
- Assets are brand images that aren't UI: icon, logo, a product photo. They can't stand in for UI.

## 3. Visual DNA

```bash
python3 scripts/dna.py measure evidence.json --app "Seenfy" -o dna.json          # + --site https://… if there is one
python3 scripts/dna.py fonts evidence.json home --region 0.05,0.08,0.6,0.12 --text "İzlemeye Devam Et" -o font-match.jpg
python3 scripts/dna.py board dna.json -o dna-board.jpg
```

**`measure`** finds what a script can find:
- the UI palette, from flat pixels only, so posters and photos don't count;
- each colour's role (surface, ink, accent, semantic) and how many screens it appears on;
- dark or light UI;
- the type scale from the words on screen;
- with `--site`, the fonts and colours the website's CSS declares. If the shell can't reach the site, read it
  with your web-fetch tool and fill `website` by hand.

**Then complete `dna.json` by looking at every screen.** This is designing, not data entry:
- **fonts** (`display`, `text`). Priority: the user's font files, then the website's font, then the closest open
  (OFL) match on the font-match sheet. Tell the user which one you used and why.
- **palette**: the roles you'll actually use, with the app's hex values.
- **shape**: corner radius, elevation (flat or shadowed), density, icon style.
- **signatures** - 2-4 elements only this app has, each with its evidence and crop. Seenfy: the indigo "%88 Sana
  Uygun" pill, the continue-watching card with "S2E5", the mood collections. Signatures are what concepts are
  made of.
- **voice**: how the app talks (sen or siz, slang, the insider words).
- **output**: what the app makes or shows - posters, carousels, plans, charts.
- **avoid**: the category clichés (`categories.md`), the competitors' looks, and anything the brand isn't.

Render the board and show it with the concepts (§4). If you're unsure about the DNA - no brand material, a
font you can't identify - show the board first and confirm it.

## 4. Concepts: three ideas, not three colour schemes

A concept is **an idea about how this app shows itself**, made from its DNA. It is not a ground colour, and it
is not a layout. Write three that differ in their idea. Change the idea, not the colours: if two concepts would
read the same in greyscale, they're one concept.

Ways in:
- **A signature becomes the system.** The app's own element carries every headline. Seenfy "Sana Uygun": the
  indigo pill of the app sets every emphasis word, and the proving element lifts out of the screen.
- **The app's data becomes the image.** A real number or name from the screens, set poster-size. Seenfy
  "Ekrandaki Sayı": %88, Plot twist, S2E5, 8.5, each opening one shot.
- **Turn the app's material inside out.** A dark app on a light page, a dense app given a lot of space, a
  playful app set in a serious type. Seenfy "Açık Sayfa": the dark screens as objects on the app's own ink colour.
- **The ritual or moment.** When and how people use it: morning, a commute, the end of a match. Only if the
  screens show that moment.
- **The output as the hero.** What the app makes - a carousel, a plan, a photo - big. Span pairs suit wide
  outputs.
- **The angle's word.** The insider word from `angle.md`, set as the typographic idea.

Each concept has:
- a **name** and a one- or two-sentence **idea** in the user's language;
- its **system**: ground, type (from the DNA's fonts, at most two weights), the emphasis device, the one ownable
  motif, the scale rule;
- its first three shots as scenes.

Put all three in version-2 set files that share the same copy and evidence, then render the checkpoint:

```bash
python3 scripts/compose.py concepts a.json b.json c.json --board dna-board.jpg -o concepts.jpg
```

Show it with one line per concept on why it fits the angle, and your pick. Mixing is allowed ("B's numbers on
C's light page") - make a new set file for the mix. Skip the checkpoint only if the user said "just deliver"
or the brand already has a screenshot system. Then name the concept you chose and why.

## 5. The campaign system: what stays, what changes

A professional campaign varies the composition and keeps the system.

**Stays the same in every shot (the invariants):**
- the ground family - one ground, or one family of grounds from the DNA;
- the type: one headline face, one text face, the size bands (headline, sub, big type);
- one emphasis device;
- one motif or ownable detail, used with restraint;
- the margins (about 0.08u from the edges) and the corner radius from the DNA;
- the role of colour: the accent means the same thing everywhere.

**Changes from shot to shot (the variables):**
- where the headline sits: top, bottom, beside, over open ground;
- what the biggest thing is: the phone, a crop, a number, the output;
- the scale: a full screen, a lifted element, a close crop;
- the crop and how it bleeds off the edges;
- the reading order;
- whether a device frame appears at all.

**The test:** cover the headlines. The shots should still look like one brand, and no two neighbours should
look like the same layout. `compose.py` flags three shots with the same composition.

## 6. Composition briefs: one per shot

Before writing a scene, write its brief, one line each. It goes in the shot as `"message"` and `"proof"`, and
the rest guides the layers:

- **message** - the one thing this shot says (from the storyboard);
- **proof** - the screen and region that shows it;
- **focal point** - what the eye hits first, and why that, not something else;
- **scale** - which element is biggest; the UI stays big enough to read at full size;
- **reading order** - for example: big number, then headline, then crop;
- **crop** - full screen or region, and what bleeds off the edge;
- **text position** - where the headline sits, never over the UI;
- **contrast with the neighbours** - how it differs from the shots before and after it.

Let the message decide the composition:
- a *feature* lifts its element out of the screen;
- a *result* shows the output big;
- a *list of options* lays out its real cards;
- a *number* gets set huge;
- a *flow* gets a span pair.

## 7. Writing the scenes

- Start from the brief and place layers in u. Use `%` widths when they should fill any device.
- Anchor text to text (`"below": "head"`), so wrapping never causes collisions.
- Use the text's own size bands. A headline is at least 0.06u, so it reads in search results.
- A disclosure ("Örnek veriler", "Temsili görüntüdür") goes in a `footnote` at the bottom margin (0.02-0.03u),
  never in the sub-line slot under the headline, where it weakens the claim. A footnote doesn't count towards
  Google Play's 20 % caption limit.
- One proof per shot, across screens too. The same posts on the calendar and on the home screen are one proof
  shown twice, even though the screens differ. One item carried through the set as a story (the same draft
  suggested, approved, then queued) is fine.
- **Every decoration needs a `motive`** naming where it comes from in the DNA or the concept ("the app's progress
  bar track"). Without a motive it's AI decoration - delete it. At most a few per shot.
- **Gradients** only when the app has them, or they come from the app's own colours (`"sample"`), never the
  default purple-to-blue.
- **3D devices** (`device3d`, `scene-format.md` §5) only where depth means something:
  - a phone in a hand-held or on-the-table moment;
  - two devices in conversation;
  - the shot that turns the product into an object.

  Rules:
  - Keep the angle moderate (yaw 10-25°), so the UI still reads.
  - Use one camera (lens and light) for the whole set, from the campaign.
  - Give every device a shadow that agrees with the light.
  - Use turned phones in at most two shots; the rest stay flat. A tilted phone in every shot is the template
    look this skill exists to avoid.
  - No 3D on Google Play (device imagery).
- **Free vector work** (a motif, a pattern, a drawn shape) goes in an `svg` layer, written in u. For something
  no layer can do - complex illustration - use the HTML route (`layouts.md` §6). The truth rules
  still apply: screens are `<img>` tags of the evidence files, never redrawn, and the result is checked with
  `check_set.py`.
- Don't center everything, and don't give every shot the same scale or the same phone in the middle. A layout
  that works for any app in the category is a template.

## 8. Look, fix, look again

```bash
python3 scripts/compose.py render set.json --out out/
python3 scripts/compose.py xray set.json --shot promise -o xray.png   # boxes, roles, margins, thumbnail inset
python3 scripts/check_set.py out/ios --store ios --lang tr           # reprints the scene warnings + store rules
python3 scripts/peer_test.py out/ios --category <closest> -o peer.jpg
```

Open every PNG at full size and the search preview at thumbnail size. Fix every warning or know why it's
wrong. Then judge what no check can:
- Is the focal point the brief's focal point?
- Does it read in two seconds?
- Is anything decorative competing with the product?
- Do shots 1-3 alone say what the app does?
- Does it look like this app's own marketing, or like an AI render of a category (`anti-ai.md`)?

Do at least one round of fixes. Usually the fix is: larger UI, less type, fewer colours, a stronger focal point.

## 9. Sizes and stores

- One set file renders every size. `%` widths and anchored text adapt by themselves; override per size where
  needed (`scene-format.md` §6).
- **Google Play:**
  - no device frame;
  - all words on the canvas within 20 % of its height, including big type - shrink it in the android variant
    or drop a sub-line there;
  - no prices, promos, calls to action or rankings;
  - a feature graphic, 1024×500.
- **iPhone Duo / iPad:** use screens captured on that device, given per size, and re-check every composition -
  the canvas is wider.

## 10. When to use the presets instead

`render_set.py` with a `"direction"` (`directions.md`) is the fast path. Use it when:
- the user wants a quick, conventional set;
- the brand already has a screenshot system to match;
- or you can't render scenes - no Pillow, or something breaks.

Say that you used a preset. The library and the directions are also references for scenes: look at how the
best sets in the category handle scale and crop. Never copy them.

## 11. The Seenfy pilot, as an example

The Seenfy screens in `examples/seenfy/` went through this process. The worked result is
`templates/scene.example.json` (concept B), and `examples/seenfy-v2/` in the repository has all three concepts.

**DNA:**
- dark UI (#121212) with an indigo accent (#5460F0) and ink #EAF6F6;
- Poppins (closest open match);
- flat cards with a large radius;
- signatures: the match pill, the continue card, the mood collections;
- a warm, spoken voice with film slang.

**Concepts:**
- **A "Sana Uygun"** - the pill as the emphasis device, lifts.
- **B "Ekrandaki Sayı"** - the app's own data, poster-size.
- **C "Açık Sayfa"** - a light page with a progress line that advances through the set.

**B was chosen:** its numbers are real, ownable, and nobody in the category leads with them.

**Its five shots share one system** - ground #121212, Poppins, indigo for data and emphasis - **and change their
composition:**
- %88 at the top, with the matched card below;
- the mood cards first, then "Plot twist", then the line;
- the headline, then the card, then S2E5 at the bottom right;
- 8.5 at the top right, with the poster screen and its facts row lifted;
- the full screen, with the mark-watched row lifted.
