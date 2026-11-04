# Store Screenshots Skill for Claude, ChatGPT & AI agents

A skill that turns Claude, ChatGPT or any agent that supports **Agent Skills** (`SKILL.md`) into an app-marketing
designer for **App Store and Google Play screenshots**: from the app's promise to headline copy, layout and
pixel-exact PNGs - built from the app's real screens, with copy that passes the "swap test" and doesn't read
as AI-generated.

![Seenfy App Store screenshots made with this skill, Turkish](docs/images/seenfy-tr.jpg)

- **Process & craft** - brief, category research, story order, the first three shots, headline patterns,
  banned/tired phrases (EN + TR), layouts, type, colour, emphasis devices, localisation, critique scorecard,
  and up-to-date store specs (checked 2026-11-04).
- **A reference library of 1,718 real screenshots** - the top 4 free iPhone apps in 25 App Store categories
  (Turkish and US stores) plus 2 well-rated small/mid-size "challengers" per category. Every app is labelled
  (layout, techniques, first-shot type, quality, AI smell, why); every screenshot has headline text (355
  human-verified), position, language and colour data. Searchable from the command line; refreshed monthly.
- **Niche, not generic** - a step that finds the app's *angle* (the exact person, the enemy, the ritual,
  the insider word, the proof only it has), a playbook per category (what the chart does, what the best
  sets do differently, the clichés to avoid, where the room is), and **seven design directions** -
  editorial, poster, playful, cinematic, crafted, native, utility - each a full visual system driven by the
  app's brand colours. A concept sheet shows the first three shots in three directions before anything is
  rendered, so the look is a choice, not a template.
- **Scripts** (Python 3 + Pillow) - read a live store listing, check and clean raw screens (status bar, debug
  UI), place crops on a grid, render a whole set from one JSON spec at exact store sizes (every locale at once,
  iPhone and Android frames, Google Play feature graphic, bundled OFL fonts, emphasis words, zoom cards,
  callouts, posters, Turkish-safe capitals), check it against store and copy rules with a search-result
  preview, and peer-test it next to exemplary sets.

## Real example: Seenfy

[Seenfy](https://apps.apple.com/tr/app/id6764370964) is a Turkish film & TV discovery and tracking app. The set
above was made end to end with the skill:

1. **Intake** - `fetch_listing.py` read the live App Store listing (description, release notes, category,
   current screenshots) and found closer competitors with `--search "film dizi takip"` (Raf, Kare,
   Letterboxd, Bingers, Muvy).
2. **Critique** - the existing set scored **13/20**: strong Turkish voice ("Filmi izledin. Şimdi konuş."), but
   AI-rendered cinema rooms, tilted phones, UI too small to read, two shots on the same screen.
3. **Angle** - three candidates (the film-diary keeper, "the end of *ne izlesek?*", "not what's popular");
   the enemy angle won because the screens prove it: the "%88 Sana Uygun" match score.
4. **Storyboard** - one promise per shot, taken from the listing's own proof points (personal picks, mood
   collections, continue watching, one-tap tracking, spoiler-free comments), then a request for exactly the
   raw screens each shot needs.
5. **Direction** - `concepts.py` rendered shots 1–3 in four directions (below); *cinematic* fits a dark,
   poster-rich film app, and one hand-drawn circle on "S2E5" is the human touch.
6. **Render & check** - 6 raw iPhone screens → `prepare_screens.py` (low-res warning, debug button covered)
   → `render_set.py` with one spec for both languages, App Store and Google Play sizes and a Play feature
   graphic → `check_set.py` for store and copy rules, `peer_test.py` next to exemplary sets.

**Concept sheet** - same copy and screens, four directions (cinematic · editorial · poster · crafted):

![Seenfy concept sheet: the first three shots in four design directions](docs/images/seenfy-concepts.jpg)

**Turkish (App Store TR)**

| # | Headline | Proof on screen |
|---|---|---|
| 1 | Popüler olanı değil, *seveceğini* izle | "%88 Sana Uygun" match score, pulled out |
| 2 | Bu akşam *plot twist* mi istiyorsun? | Mood collections |
| 3 | Kaldığın bölüm *hep hazır* | Continue watching, S2E5 circled by hand |
| 4 | İzle, beğen, *işaretle* | Watchlist / like / watched buttons |
| 5 | Ne izlesem diye *düşünme* | Discover |
| 6 | *Spoiler* yok. Söz. | Poster: spoiler comments stay hidden |

**English** - rewritten, not translated:

![Seenfy screenshots, English captions](docs/images/seenfy-en.jpg)

*Not what's popular. What you'll love. · In the mood for a plot twist? · Your next episode, always ready ·
Watch, like, check it off · Stop wondering what to watch · No spoilers. Promise.*

**Google Play** - same spec, Android frame, plus the required 1024×500 feature graphic:

![Seenfy Google Play feature graphic](docs/images/seenfy-feature-graphic.jpg)

![Seenfy Google Play screenshots with the Android frame](docs/images/seenfy-android.jpg)

> The English set reuses the Turkish UI to show the copy side by side. For a real US listing, capture the
> screens with the app in English - caption language should always match the UI (`references/localization.md`).

Reproduce everything (TR + EN, iOS + Android + feature graphic) from one spec:
`python3 skills/store-screenshots/scripts/render_set.py examples/seenfy/set.json --out out/` → `out/tr/…`,
`out/en/…`. The spec and screens are in `examples/seenfy/`.

<details><summary>The skill's own demo set (fictional app, from <code>templates/set.example.json</code>)</summary>

![Example set rendered by render_set.py from the demo screens of a fictional app](docs/images/example-set.jpg)

</details>

## Full vs lite

| Package | Contents | Size | Use for |
|---|---|---|---|
| `store-screenshots.zip` | everything, all 1,619 library images | ~46 MB | Claude Code, Codex, Cursor, Gemini CLI, cloning the repo |
| `store-screenshots-lite.zip` | full text catalog + 661 images at 420 px (every shot of the exemplary apps, the first shot of every app, shots 1–3 of instructive bad ones) | ~16 MB (18 MB unpacked) | claude.ai and ChatGPT uploads |

Both work the same way; the scripts only offer images that are on disk. Build them with
`python3 tools/package_skill.py` (writes `dist/`).

## Install

**Claude Code - plugin marketplace**
```
/plugin marketplace add thearkxd/store-screenshots-skill
/plugin install store-screenshots@store-screenshots-skill
```
**Claude Code - manual**
```bash
git clone https://github.com/thearkxd/store-screenshots-skill.git
cp -r store-screenshots-skill/skills/store-screenshots ~/.claude/skills/store-screenshots
```
**claude.ai / Claude desktop** - download `store-screenshots-lite.zip` from Releases and upload it in the Skills
section of your settings (custom skills need code execution enabled).

**ChatGPT** - Skills → Create → Upload from your computer, and pick `store-screenshots-lite.zip`. (Skills
availability depends on your ChatGPT plan and workspace settings.)

**Codex CLI, Gemini CLI, Cursor and others** - copy `skills/store-screenshots` into your agent's skills folder
(for example `~/.codex/skills/`, `~/.gemini/skills/` or `~/.agents/skills/`).

Skills don't sync between products - install in each one you use. After installing, run the checklist in
[`docs/testing.md`](docs/testing.md) once to make sure the skill triggers and the scripts run there.

## Use

The skill starts by asking whether the app is already live. **Live:** send the App Store / Google Play
link(s) - it reads the listing (description, what's new, category, rating, current screenshots, competitors),
drafts the brief, scores the current set, and then asks for exactly the raw screens the new storyboard needs.
**Not live:** it asks a short form instead (what it does, for whom, what it does better, brand).

Just ask, in any language:
- "Şu uygulama için yeni mağaza görselleri yap: https://apps.apple.com/tr/app/…/id6764370964"
- "Henüz yayında olmayan bir bütçe uygulaması için mağaza görselleri hazırla."
- "Critique our Play Store screenshots and tell me the three biggest fixes."
- "What do the best finance apps put in their first screenshot?"
- "Bu İngilizce başlıkları Türkçe'ye uyarla."

Or run the tools yourself:
```bash
S=skills/store-screenshots/scripts
python3 $S/search_library.py --category weather --summary
python3 $S/search_library.py --quality exemplary --position 1 --verified --format headlines
python3 $S/fetch_listing.py https://apps.apple.com/tr/app/id6764370964 --search "film dizi takip"
python3 $S/prepare_screens.py examples/seenfy/screens --out prepared --status-bar 9:41
python3 $S/crop_helper.py check examples/seenfy/set.json -o crops.jpg
python3 $S/concepts.py examples/seenfy/set.json -o concepts.jpg        # 3 directions for the category
python3 $S/concepts.py --list                                          # all seven directions
python3 $S/render_set.py examples/seenfy/set.json --out out/
python3 $S/check_set.py out/tr/ios --store ios --lang tr
python3 $S/check_set.py out/tr/android --store android --lang tr
python3 $S/peer_test.py out/tr/ios --category entertainment -o peer.jpg
```

## What's inside

```
skills/store-screenshots/
  SKILL.md                    workflow, non-negotiables, red flags, tool map
  references/                 intake · angle · categories · directions · copy-rules · storytelling · layouts ·
                              anti-ai · localization · store-specs · critique · library-guide
  scripts/                    fetch_listing · prepare_screens · crop_helper · search_library · concepts ·
                              render_set · design · check_set · peer_test · make_sheet · collect_examples ·
                              find_challengers · build_catalog
  templates/                  set.example.json + demo screens of a fictional app
  assets/directions/          the seven design directions (JSON presets with brand tokens)
  assets/fonts/               10 OFL families - Inter, Instrument Serif, Fraunces, Anton, Baloo 2, Space Grotesk,
                              Bricolage Grotesque, Caveat, JetBrains Mono, Store Serif (Lora) - subset to Latin + Turkish
  assets/library/             catalog.json · classifications.json · stats.json · img/
examples/seenfy/              a real set: one multi-locale spec (TR + EN) and the raw screens
evals/evals.json              test prompts with expected behaviour
docs/testing.md               manual checklist for claude.ai / ChatGPT / Claude Code
tools/package_skill.py        builds the full and lite zips
tools/smoke_test.py           what CI runs on every push
tools/library_diff.py         monthly refresh: new / dropped chart apps vs. the library
tools/demo_screens/build.py   rebuilds the demo screens (HTML/CSS → Playwright)
```

## Library at a glance

- 25 categories × 4 chart apps × 2 stores + 50 US challengers (rating ≥ 4.6, not a giant seller), collected
  2026-11-04 from the public App Store.
- Chart apps: 42 rated exemplary, 79 solid, 52 weak; 22 flagged for AI/template smell. Challengers: 9
  exemplary (Working Copy, TickPick, CAVA, Tunesimo, Structured, GetYourGuide, Viator, Weather & Radar,
  The Economist).
- Strongest signals in the data: verb-led headlines (11 exemplary / 0 weak apps), one emphasised word (11/1),
  pulled-out UI cards (4/0) - versus generic claims (0/16), no captions (0/15), tilted floating phones (0/12).
- Quality labels are a reviewer's judgement (made with Claude), not conversion data. See
  `references/library-guide.md` for method, limits and biases.

Refresh or extend the library with `collect_examples.py` + `build_catalog.py` (needs access to
`itunes.apple.com` and `is1-ssl.mzstatic.com`, Pillow and tesseract with `eng` + `tur`).
`.github/workflows/library-refresh.yml` does the collecting on the 3rd of every month and opens an issue with
the new apps to classify.

## Releases (CI/CD)

`.github/workflows/release.yml` runs on every push: it installs Pillow, runs `tools/smoke_test.py` (every script,
an example render, store and copy checks) and builds both zips with `tools/package_skill.py` - which fails the
build if the lite package grows past 20 MB. Pushes to `main` then publish a GitHub release with both zips.

- Version: `major.minor` comes from `.claude-plugin/plugin.json`, the patch number is the workflow run
  (`v1.0.7`, `v1.0.8`, …). Bump `version` there for a new minor/major line.
- Other branches and pull requests: the zips are attached to the workflow run as artifacts (14 days).
- Put `[skip release]` in a commit message to build without publishing.
- `network-test.yml` fetches a real App Store and Google Play listing weekly (and when `fetch_listing.py`
  changes), so parser breakage shows up without blocking releases.

## License

Code, reference texts and classification data: MIT. Bundled fonts: SIL OFL 1.1 (`assets/fonts/`). **The screenshots in the library belong to their
publishers** and are included for study only - see [NOTICE.md](NOTICE.md).

---

### Türkçe özet

App Store ve Google Play mağaza görselleri için bir skill: uygulamanın vaadini bulur, gerçek ekranlardan yola
çıkar, "değiştirme testinden" geçen ve yapay zekâ kokmayan başlıklar yazar, görselleri mağaza ölçülerinde
PNG olarak üretir ve kontrol eder. İçinde Türkiye ve ABD App Store'larında 25 kategoriden en popüler
uygulamaların 1.718 mağaza görseli var; her uygulama iyi/kötü ve nedeniyle etiketli. Her kategori için bir
oyun kitabı, uygulamanın niş "açısını" bulan bir adım ve yedi tasarım yönü (editoryal, poster, oyuncu,
sinematik, el yapımı, native, veri) var: render'dan önce ilk üç görsel üç farklı yönde yan yana gösterilir. claude.ai ve ChatGPT
için 20 MB altındaki **lite** paketi, Claude Code ve diğer ajanlar için **tam** paketi kullanın.

Gerçek örnek: yukarıdaki Seenfy seti skill ile baştan sona üretildi (mağaza sayfası okundu, eski set 13/20
aldı, storyboard çıkarıldı, 6 ham ekranla render edildi). Türkçe ve İngilizce spec'ler `examples/seenfy/`
klasöründe.
