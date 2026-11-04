# Testing the skill in claude.ai and ChatGPT

CI checks that the scripts run and the example sets render. It can't check how the skill behaves inside the
products people use. Run this checklist after a release that changes `SKILL.md`, the references or the
scripts, and note the results in the release or an issue.

## 1. Install

| Where | How | Check |
|---|---|---|
| claude.ai / desktop | Settings → Skills (Capabilities) → upload `store-screenshots-lite.zip` | Upload accepted (zip < 20 MB, one top-level folder); skill listed and enabled; **code execution** on |
| ChatGPT | Skills → Create → Upload from your computer → `store-screenshots-lite.zip` | Upload accepted; skill appears under Skills; plan/workspace allows skills |
| Claude Code | `/plugin marketplace add thearkxd/store-screenshots-skill` → `/plugin install store-screenshots@store-screenshots-skill` | `/skills` lists `store-screenshots` |

Network for live listings (claude.ai): allow `itunes.apple.com`, `is1-ssl.mzstatic.com` (and for Google Play
`play.google.com`, `play-lh.googleusercontent.com`) under Settings → Capabilities. Test both with and without.

## 2. Prompts (fresh chat each)

Tick each expected behaviour. The prompts match `evals/evals.json`.

**A. Triggering and intake**
- [ ] "Uygulamam için mağaza görselleri hazırlar mısın?" → the skill loads (Claude reads `SKILL.md`) and the
      first reply asks whether the app is live and for the store link. No design work yet.
- [ ] "Can you make App Store screenshots for my app?" → same, in English.
- [ ] "Write me a tagline for my coffee shop" → the skill does **not** load (no false trigger).

**B. Live app**
- [ ] Send `https://apps.apple.com/tr/app/seenfy-ne-izlesem-film-dizi/id6764370964` → `fetch_listing.py`
      runs (or, if the network is blocked, it says so and falls back: web fetch, or asks you to paste the
      listing). Brief drafted from the description; current set scored with the 20-point scorecard; good lines
      kept; asks whether the set is for the current version or an update.
- [ ] Storyboard table, then a list of the exact raw screens per shot. It does **not** crop UI out of the
      store screenshots and does not render before screens arrive.

**C. Not live**
- [ ] "Henüz yayında olmayan bir bütçe uygulaması yapıyorum, adı Kumbara." → one short form, the name not
      re-asked.

**D. Render** (attach 4–6 raw screens)
- [ ] The brief has an `Angle:` line chosen from three candidates; the category playbook is used.
- [ ] Before the full set, `concepts.py` runs and the reply shows the concept sheet (three directions) and
      asks which one - unless you said "just deliver".
- [ ] `prepare_screens.py` runs and its report is summarised (resolution, status bars).
- [ ] Renders at 1206×2622 and 1080×1920; `check_set.py` runs; the reply shows the overview and search preview
      images, not just file paths.
- [ ] Android set uses the punch-hole frame; a feature graphic is offered or rendered for Google Play.
- [ ] Turkish capitals are right (İ/ı) if caps are used.

**E. Research**
- [ ] "What do the best weather apps put in their first screenshot?" → `search_library.py`, quotes only
      verified headlines, mentions that quality labels are judgement, not conversion data.

## 3. Environment checks

Ask the assistant to run these in the code tool and paste the output:
```bash
python3 -c "import PIL; print(PIL.__version__)"          # Pillow present?
python3 <skill-dir>/scripts/search_library.py --list-values | tail -1   # library found, images on disk
python3 <skill-dir>/scripts/render_set.py --presets      # fonts and presets
which tesseract || echo "no tesseract (only needed for OCR of current headlines)"
```
If Pillow is missing and can't be installed, rendering and checks won't work - the skill should say so and
fall back to copy, storyboard and an HTML route.

## 4. What to record

For each surface: date, skill version (release tag), pass/fail per box, and anything odd (skill not
triggering, wrong paths, timeouts, file not shown). File issues with the prompt and the transcript.
