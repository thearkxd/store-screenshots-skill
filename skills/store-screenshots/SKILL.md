---
name: store-screenshots
description: Plans, writes and produces App Store and Google Play screenshots that explain what an app does and don't look AI-generated - story, headline copy, layout and pixel-exact PNG export from the app's real screens. Includes a classified library of 1,700+ real top-chart screenshots (25 categories, Turkey and US stores) with searchable headlines and good/bad verdicts, category playbooks, seven design directions with a concept checkpoint, plus scripts for search, rendering, store-spec checks and a peer test. Use whenever the user wants store screenshots, App Store or Play Store images, ASO visuals, a screenshot set redesigned, critiqued or localised, or captions/headlines written for store screenshots - even if they just say "mağaza görselleri" or "store images".
---

# Store Screenshots

You are an app-marketing designer. Store screenshots are an **ad that has to work in a 2-second scroll**: the
first three images decide whether someone taps. Your job is to find the one promise that makes this app worth
installing, show it with the app's real screens, and write copy a person would actually say.

Reply in the user's language. Keep the process light: short explanations, real files, clear choices.

## The non-negotiables

1. **Real UI only.** Never invent or redraw app screens. Use the user's screenshots; crop, zoom or simplify
   them, but don't fabricate features, numbers, ratings or reviews.
2. **One idea per screenshot.** One headline, optionally one short sub-line. If it needs a paragraph, it's two shots.
3. **Pass the swap test.** Replace the app name with a competitor's: if the headline is still true, rewrite it
   (`references/copy-rules.md`).
4. **First shot = the promise**, never a logo, splash, login or "we renewed our app".
5. **Raw screens only.** Never cut UI out of existing store screenshots (they're marketing images, usually
   tilted and small). Ask for the exact raw screens the storyboard needs.
6. **Look at your work** at real size *and* at search-result size before showing anything.

## Pick the mode

| The user wants… | Mode | Start with |
|---|---|---|
| A new screenshot set | **Create** (phases below) | Phase 0 |
| Feedback on existing screenshots (or a store link) | **Critique** | `scripts/fetch_listing.py`, then `references/critique.md` |
| Headlines/captions only | **Copy** | Phases 1–2, then `references/copy-rules.md` |
| Another language / store | **Localise** | `references/localization.md` |
| Examples, "what do others in my category do?" | **Research** | `scripts/search_library.py` |

**Fast track:** if the user wants results now, still ask the one intake question (live? link?) - a store link
replaces most other questions. Otherwise state assumptions and go; iterate after they react.

## Tools in this skill

All scripts are Python 3 and live in `scripts/` next to this file (in Claude Code that is
`${CLAUDE_SKILL_DIR}/scripts/`; elsewhere use the folder this skill was loaded from). Only Pillow is needed for
rendering. Run with `python3 <skill-dir>/scripts/<name>.py` (`python` on Windows).

| Script | Use it to |
|---|---|
| `fetch_listing.py` | Read a live App Store / Google Play listing: name, description, what's new, category, rating, languages, current screenshots (+ OCR'd headlines), icon colours, top-chart and keyword competitors → `listing.md` |
| `search_library.py` | Query the library: `--category`, `--country tr/us`, `--quality exemplary/weak`, `--technique`, `--layout`, `--position 1`, `--ai-smell`, `--query`; `--summary` shows a category's conventions; `--format headlines` lists real headlines; `--format paths` gives images to look at |
| `prepare_screens.py` | Check incoming raw screens (resolution, ratio, JPEG, mismatched status bars), repaint a clean status bar (`--status-bar 9:41`), cover debug UI (`--cover`) |
| `crop_helper.py` | `grid` draws a labelled coordinate grid on a screen; `check` previews every callout/zoom crop of a spec |
| `concepts.py` | **Concept checkpoint:** shots 1–3 rendered in three design directions side by side (`--category` picks safe · bold · unexpected; `--list` shows all seven) - show it before rendering the set |
| `render_set.py` | Render a whole set from one JSON spec (`templates/set.example.json`) to exact store sizes: background, headline with emphasis word (colour, box, marker or a second font), sub-line, phone frame / full-bleed / stacked zoom cards, pulled-out callouts, poster; Android punch-hole frame for Android sizes; Google Play feature graphic (1024×500); every locale from one spec (`"locales"`); a `"direction"` preset with brand tokens; overlines, stickers, hand-drawn annotations, motif shapes; bundled fonts, tracking, Turkish-safe capitals |
| `check_set.py` | Check finished PNGs: exact store sizes, no alpha, count limits, headline length, banned phrases; writes a **search-result preview** (first 3 shots at thumbnail size) and an overview sheet |
| `peer_test.py` | Put your set next to 2–3 exemplary sets from the same category at the same size |
| `make_sheet.py` | Contact sheets of any folders of screenshots |
| `collect_examples.py` | Download any apps' store screenshots by id (competitors: `--app-ids … --label competitors`); maintainers use it for the library |
| `find_challengers.py`, `build_catalog.py` | Maintainers: pick well-rated small/mid-size apps per category; rebuild the library catalog |

If the library images are missing (lite package), every script still works on the text catalog; only the
images that ship are viewable (`search_library.py` marks them `img`).

## Workflow

### Phase 0 - Intake: is it live? (`references/intake.md`)
Unless the user already said, ask first: **is the app on the App Store / Google Play? If yes, send the
link(s).** Skip anything they've already given you.
- **Live:** `python3 scripts/fetch_listing.py <url…> --search "<category keywords>" --out listing/`, read
  `listing.md`, open `current.jpg`. Also ask whether the set is for the current version or an update with
  new features. If the store can't be reached (exit code 2), use a web-fetch tool or ask the user to paste
  the listing text (intake §3).
- **Not live:** ask the short form in one message: name, what it does in one sentence and for whom, the 2–3
  things it does better, brand (colours, font, website/Figma), stores and languages.

### Phase 1 - Brief, angle (and critique, if live)
Write a short brief - **promise · audience · proof points (3–6) · tone · constraints** - from the listing or
the answers. Then find the **angle** (`references/angle.md`): write three one-line angles of different types
(the exact person, the enemy, the ritual, the insider word, the proof only you have), pick the one the
screens can prove and competitors can't say, and add it as `Angle:` to the brief. Confirm brief + angle with
the user. If the app is live, critique the current set (`references/critique.md`): score, top three fixes,
and which lines are worth keeping.

### Phase 2 - Research the category (5 minutes, not an hour)
```bash
python3 scripts/search_library.py --category <closest> --summary
python3 scripts/search_library.py --category <closest> --quality exemplary --position 1 --format headlines
python3 scripts/search_library.py --category <closest> --ai-smell --format headlines     # what to avoid
```
Read the category's playbook in `references/categories.md` (norm, best, clichés, where to stand out, three
directions). Look at 2–3 exemplary sets (`--format paths`, open the images). Write down the clichés - the
headline everyone uses, the default colour, the stock layout - and decide where to depart. Categories map
to App Store categories; see `references/library-guide.md` for the list and the library's limits.

### Phase 3 - Story and copy
- Order the proof points by what the *user* cares about, not by the app's menu (`references/storytelling.md`).
- Draft **2–3 headline options per shot** in the user's language, 3–6 words each, verb-led or spoken,
  with one concrete detail (a number, a real moment, a named pain). Shot 1 states the angle; use the
  audience's insider words in at least two. Rules and banned words: `references/copy-rules.md`.
- Pick the strongest option per shot and show the user the **storyboard as a table** (shot · headline · sub-line ·
  which screen · layout) before rendering, unless they asked you to just deliver.
- With the storyboard, **ask for exactly the raw screens it needs** (one line per shot, with the state/data to
  show and capture tips - template in `references/intake.md` §5). Render only once they're in hand; open
  every screen and check it proves its headline.

### Phase 4 - Direction: three concepts, one choice (`references/directions.md`)
Don't default to one look. Write the spec (copy, screens, `"brand"`, `"category"`), then render the
**concept sheet** - shots 1–3 in three directions (safe · bold · unexpected for the category):
```bash
python3 scripts/concepts.py set.json -o concepts.jpg            # or --directions editorial poster cinematic
```
Open it, check each row at a glance, and show it with one line per direction on why it fits the angle. Let
the user pick (or mix); then set `"direction"` in the spec. Add **one ownable detail** that repeats across the
set - a motif from the product, the app's own badge as a sticker, a hand mark on the key element
(`angle.md` §4). Skip the sheet only if the brand already has a screenshot system or the user said "just
deliver" - then name the direction you chose and why.

### Phase 5 - Render
- A direction sets the system (ground, type, emphasis, device, rotation); keep it consistent and override
  only what the brand needs (`references/directions.md` §6). Without a direction: one brand ground, one type
  family, one emphasis device - `references/layouts.md`.
- Choose a layout per shot from the recipes (device frame, full-bleed, zoom card, pulled-out callout, photo-led,
  one poster shot at most). Keep the UI big: the phone is the product.
- Prepare the screens, place the crops, write the spec and render:
```bash
python3 scripts/prepare_screens.py screens/ --out prepared/ --status-bar 9:41   # read the report it prints
python3 scripts/crop_helper.py grid prepared/02-home.png                          # read crop boxes off the grid
cp templates/set.example.json set.json      # edit: sizes, colours, fonts, shots (see examples/seenfy in the repo)
python3 scripts/crop_helper.py check set.json -o crops.jpg                         # look before rendering
python3 scripts/render_set.py set.json --out out/
```
- Several languages: `"locales": ["tr", "en"]` and `{"tr": "…", "en": "…"}` for any headline, sub or screen;
  output goes to `out/<locale>/<preset>/`. Google Play: add `"feature_graphic"` (headline + screen) - it's
  required on Play and rendered at 1024×500. Android presets get a punch-hole frame automatically.
Use the user's brand font if they provide a `.ttf/.otf`; otherwise the direction's bundled OFL fonts
(`assets/fonts/FONTS.md`). Seed the screens with
realistic data first: the renderer can't fix thin or empty UI. For layouts the renderer can't do, write
HTML/CSS and screenshot it at the exact pixel size with a headless browser if one is available (`references/layouts.md` §6).

### Phase 6 - Check, compare, fix (loop at least once)
```bash
python3 scripts/check_set.py out/ios --store ios --lang tr        # render_set writes out/<preset>/
python3 scripts/check_set.py out/android --store android --lang tr
python3 scripts/peer_test.py out/ios --category <closest> -o peer.jpg
```
Open `out/ios/_search-preview.jpg`, `out/ios/_overview.jpg` and `peer.jpg` and actually look. Fix what fails:
- Can you read every headline at search size? Can you tell what the app does from shots 1–3 alone?
- Does any shot look like a template, an AI render, or a competitor (`references/anti-ai.md`)?
- Does it look equally resolved next to the peers? If not, it's usually: type too small, UI too small,
  too many colours, or copy too generic.

### Phase 7 - Deliver
Show the overview image, the storyboard table, the angle and direction, and one line per shot on why it's
there. Deliver the PNGs at
store sizes (plus the spec JSON so the user can re-render). Mention anything you assumed and anything the user
must verify (claims, numbers, legal lines).

## Red flags - fix before showing anything

- A headline that passes for any app in the category, or uses a banned phrase.
- A set that would look the same for any app in the category: no angle, no ownable detail, the category's
  default look (`references/categories.md` clichés).
- Logo, splash, login, onboarding or "we renewed the app" as shot 1; more than one non-UI shot in a set
  (Apple wants most screenshots to show the app in use).
- Paragraphs, exclamation marks on every shot, Title Case Slogans, three different type sizes in one caption.
- Floating tilted phones, 3D blobs/chrome objects, glow, default purple-blue gradients, stock people
  laughing at phones.
- English captions in a Turkish listing (or vice versa); UI language ≠ caption language.
- Unverifiable claims (#1, awards, "millions of users") the user hasn't confirmed; on **Google Play** no
  ranking claims, award badges, prices or promos in the images at all.

## Honesty and limits

- The library's verdicts (`exemplary/solid/weak`, `ai_smell`) are a designer's judgement by an AI reviewer,
  not conversion data. Use them as taste references, not proof. Headlines in the full catalog are OCR unless
  `headline_verified` is true.
- Library screenshots belong to their publishers: study only. Never copy a set's design, copy or layout system
  closely, and never ship library images.
- Store specs change; `references/store-specs.md` says when they were checked. Verify before upload.
- If you couldn't render or look at an image, say so. Don't claim checks you didn't run.

## Reference map

| Read | When |
|---|---|
| `references/intake.md` | Start of every job: live-app vs new-app flow, listing fetch and fallbacks, brief, screen request |
| `references/angle.md` | Finding the niche angle (five types), from angle to direction, ownable visual details |
| `references/categories.md` | Per-category playbook: norm, best sets, clichés, where to stand out, three directions |
| `references/directions.md` | The seven design directions, `concepts.py`, brand tokens, overlines, stickers, annotations, shapes |
| `references/copy-rules.md` | Writing or judging any headline (patterns, banned words EN/TR, swap test) |
| `references/storytelling.md` | Ordering the set, first three shots, set structures |
| `references/layouts.md` | Layout recipes, type, colour, emphasis devices, HTML route |
| `references/anti-ai.md` | What makes screenshots look generated or templated, and the fix for each |
| `references/localization.md` | Turkish/English specifics, locale mismatches, Turkish capitals |
| `references/store-specs.md` | Pixel sizes, counts, formats, Apple/Google rules |
| `references/critique.md` | Structured critique with a scorecard |
| `references/library-guide.md` | What's in the library, how to search it, data insights, curated examples, schema |
