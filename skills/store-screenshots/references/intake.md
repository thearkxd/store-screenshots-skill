# Intake: start from the store listing, or from the user

The first thing to settle is **whether the app is already live**. A live listing answers most brief questions
by itself (name, subtitle, description, category, languages, what's new, current screenshots, rating), so the
user doesn't have to type them and you don't have to guess.

## Contents
1. The opening question
2. Live app: fetch, read, critique
3. When the store can't be reached
4. Not live yet: the short form
5. Both paths: the brief, then the screen request
6. Message templates (TR / EN)

---

## 1. The opening question

Skip whatever the user already told you. Otherwise ask, in one message:

> Is the app already on the App Store / Google Play? If yes, send the store link(s). If not, I'll ask a few
> quick questions instead.

If it's live, also ask: **"Are these screenshots for the current version, or for an update with new
features?"** New features won't be in the listing yet; get them from the user.

## 2. Live app: fetch, read, critique

```bash
python3 scripts/fetch_listing.py <app-store-url> [<play-url>] --search "<2-3 category keywords>" --out listing/
```
- Writes `listing/<store>-<country>-<app>/listing.md` (facts + OCR'd current headlines + icon colours +
  competitors), `listing.json`, `screenshots/`, `icon.png` and `current.jpg`.
- `--search` lists apps matching the keywords (e.g. `"film dizi takip"`, `"budget tracker"`). These are
  usually closer competitors than the category top chart, which is often dominated by giants.
- To look at competitors' screenshots, collect them and make a sheet:
  `python3 scripts/collect_examples.py --countries tr --app-ids <id> <id> --label competitors --out raw/`
  then `python3 scripts/make_sheet.py --rows raw/tr/competitors/* -o competitors.jpg`.

Then:
1. **Read `listing.md` and open `current.jpg`.** OCR'd headlines are rough (heavy caps fonts often lose
   letters). Read the real ones off the image.
2. **Draft the brief** (§5) from the description and release notes: the promise, the audience, and the
   proof points (usually the description's section headings), plus the tone the listing already uses.
3. **Critique the current set** with `references/critique.md` and give the score and the top three fixes.
   Keep what works. A good existing line ("Filmi izledin. Şimdi konuş.") should survive the redesign.
4. Confirm the brief with the user in one short message. Ask about upcoming features at the same time.

**Never cut UI out of the current store screenshots.** They are marketing images: tilted, small, often
generated backgrounds. They're study material for the critique, not material for the new set.

## 3. When the store can't be reached

`fetch_listing.py` exits with code 2 and prints `NETWORK BLOCKED` when the environment can't reach the store
(claude.ai needs `itunes.apple.com` and `is1-ssl.mzstatic.com` on the allowed domains; API skill containers
have no network at all). Fall back in this order:
1. A web-fetch / browsing tool, if the environment has one: open the listing page and read the name,
   subtitle, description, what's new, category and rating; look at the screenshots there.
2. Otherwise ask the user to **paste the listing text** (name, subtitle, description, what's new) and
   attach the current screenshots if they want a critique.
3. Google Play pages are parsed best-effort (no official API); if fields come back empty, use 1 or 2.

## 4. Not live yet: the short form

Ask at most these, in one message (skip what you already know):
1. **Name** and, if decided, the subtitle / short description.
2. **What it does, in one sentence**, and **for whom**.
3. **The 2–3 things it does better** than what people use today (name the alternatives if you can).
4. **Brand:** colours, font, logo/icon. Point to a website, landing page or Figma if there is one.
5. **Stores and languages** (App Store, Google Play; Turkish, English…).

Screenshots of the app can come now or after the storyboard (§5). If the user has a website, landing page or
pitch deck, read it: it's usually a better source for the promise than a form.

## 5. Both paths: the brief, then the screen request

**Brief (5 lines, confirm with the user):**
```
Promise:      <what it does for whom, in the user's words>
Audience:     <who, in what moment>
Proof points: <3–6, ordered by what the user cares about>
Tone:         <e.g. warm, witty, calm, expert - taken from the listing or the user>
Constraints:  <stores, languages, claims to avoid, brand rules, what must stay from the current set>
```

**Then storyboard** (`storytelling.md`, `copy-rules.md`). Once the storyboard is agreed, **ask for exactly the
raw screens it needs**, one line per shot, with how to capture them:

```
For the new set I need these raw screenshots (PNG, straight from the device or simulator):
1. <screen> - showing <state/data>, e.g. "Discover, with the 'Picked for you' row filled"
2. …
Capture tips: dark/light mode as in the design · app language = store language · realistic, filled data
(no empty states, no real personal data) · same clean status bar on every screen · no debug UI (test
buttons, dev banners) · full-resolution PNG, not a shared/compressed copy · iPhone 1179×2556 or 1206×2622.
Simulator: `xcrun simctl status_bar booted override --time 9:41 --batteryState charged --batteryLevel 100`,
then `xcrun simctl io booted screenshot shot.png`. Android: `adb exec-out screencap -p > shot.png`.
```

When screens arrive, run `python3 scripts/prepare_screens.py screens/ --out prepared/` - it reports resolution,
aspect ratio, JPEG sources and mismatched status bars, and with `--status-bar 9:41` / `--cover FILE:x0,y0,x1,y1`
fixes the last two. Then open each one and check: resolution (a 738-px-wide share is usable but soft; ask for
the original if time allows), stray debug UI (cover it with the surrounding background colour - that's
simplifying, not inventing), mismatched status bars, personal data. Measure crop boxes for callouts and zoom
cards on the actual files (`crop_helper.py grid`) and preview them before rendering (`crop_helper.py check`). Callouts default to the element's own
position (`dx`/`dy` nudge it); check that an enlarged callout fully covers the original and doesn't hide a
section heading.

Render only when real screens are in hand. If the user can't provide one, change that shot (another
screen, a zoom card of a screen you have, or the one allowed poster shot), not the rule.

## 6. Message templates

**TR - açılış**
> Uygulama App Store ya da Google Play'de yayında mı? Yayındaysa mağaza linklerini gönder; sayfayı inceleyip
> mevcut görselleri de değerlendireyim. Yayında değilse birkaç kısa soru soracağım.

**TR - yayında, onay**
> Mağaza sayfasından çıkardığım brief: … Mevcut set: 13/20 - en büyük üç sorun: … Bu görseller mevcut sürüm
> için mi, yoksa yeni özellikleri olan bir güncelleme için mi?

**EN - opening**
> Is the app already live on the App Store or Google Play? If so, send the store link(s) and I'll review the
> listing and the current screenshots. If not, I'll ask a few quick questions instead.
