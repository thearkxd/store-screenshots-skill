# Store Screenshots Skill for Claude, ChatGPT & AI agents

A skill that turns Claude, ChatGPT or any agent that supports **Agent Skills** (`SKILL.md`) into an app-marketing
designer for **App Store and Google Play screenshots**: from the app's promise to headline copy, layout and
pixel-exact PNGs - built from the app's real screens, with copy that passes the "swap test" and doesn't read
as AI-generated.

![Example set rendered by render_set.py from placeholder screens](docs/images/example-set.jpg)

- **Process & craft** - brief, category research, story order, the first three shots, headline patterns,
  banned/tired phrases (EN + TR), layouts, type, colour, emphasis devices, localisation, critique scorecard,
  and up-to-date store specs (checked 2026-11-04).
- **A reference library of 1,366 real screenshots** - the top 4 free iPhone apps in 25 App Store categories,
  Turkish and US stores. Every app is labelled (layout, techniques, first-shot type, quality, AI smell, why);
  every screenshot has headline text (243 human-verified), position, language and colour data. Searchable
  from the command line.
- **Scripts** (Python 3 + Pillow) - search the library, render a whole set from one JSON spec at exact store
  sizes (Turkish-safe capitals, emphasis words, zoom cards, pulled-out callouts, posters), check a set against
  store and copy rules with a search-result preview, and peer-test it next to exemplary sets.

## Full vs lite

| Package | Contents | Size | Use for |
|---|---|---|---|
| `store-screenshots.zip` | everything, all 1,267 library images | ~36 MB | Claude Code, Codex, Cursor, Gemini CLI, cloning the repo |
| `store-screenshots-lite.zip` | full text catalog + 549 images (every shot of the 42 exemplary apps, the first shot of every app, shots 1–3 of instructive bad ones) | ~16 MB (17 MB unpacked) | claude.ai and ChatGPT uploads |

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

Skills don't sync between products - install in each one you use.

## Use

Just ask, in any language:
- "Seenfy için App Store mağaza görselleri hazırla, ekran görüntüleri ekte."
- "Critique our Play Store screenshots and tell me the three biggest fixes."
- "What do the best finance apps put in their first screenshot?"
- "Bu İngilizce başlıkları Türkçe'ye uyarla."

Or run the tools yourself:
```bash
S=skills/store-screenshots/scripts
python3 $S/search_library.py --category weather --summary
python3 $S/search_library.py --quality exemplary --position 1 --verified --format headlines
python3 $S/render_set.py skills/store-screenshots/templates/set.example.json --out out/
python3 $S/check_set.py out/ios --store ios --lang tr
python3 $S/peer_test.py out/ios --category entertainment -o peer.jpg
```

## What's inside

```
skills/store-screenshots/
  SKILL.md                    workflow, non-negotiables, red flags, tool map
  references/                 copy-rules · storytelling · layouts · anti-ai · localization · store-specs ·
                              critique · library-guide
  scripts/                    search_library · render_set · check_set · peer_test · make_sheet ·
                              collect_examples · build_catalog
  templates/                  set.example.json + placeholder screens
  assets/library/             catalog.json · classifications.json · stats.json · img/
evals/evals.json              test prompts with expected behaviour
tools/package_skill.py        builds the full and lite zips
```

## Library at a glance

- 25 categories × 4 apps × 2 stores, collected 2026-11-04 from the public App Store charts.
- 42 apps rated exemplary, 79 solid, 52 weak; 22 flagged for AI/template smell.
- Strongest signals in the data: verb-led headlines (11 exemplary / 0 weak apps), one emphasised word (11/1),
  pulled-out UI cards (4/0) - versus generic claims (0/16), no captions (0/15), tilted floating phones (0/12).
- Quality labels are a reviewer's judgement (made with Claude), not conversion data. See
  `references/library-guide.md` for method, limits and biases.

Refresh or extend the library with `collect_examples.py` + `build_catalog.py` (needs access to
`itunes.apple.com` and `is1-ssl.mzstatic.com`, Pillow and tesseract with `eng` + `tur`).

## Releases (CI/CD)

`.github/workflows/release.yml` runs on every push: it installs Pillow, runs `tools/smoke_test.py` (every script,
an example render, store and copy checks) and builds both zips with `tools/package_skill.py` - which fails the
build if the lite package grows past 20 MB. Pushes to `main` then publish a GitHub release with both zips.

- Version: `major.minor` comes from `.claude-plugin/plugin.json`, the patch number is the workflow run
  (`v1.0.7`, `v1.0.8`, …). Bump `version` there for a new minor/major line.
- Other branches and pull requests: the zips are attached to the workflow run as artifacts (14 days).
- Put `[skip release]` in a commit message to build without publishing.

## License

Code, reference texts and classification data: MIT. **The screenshots in the library belong to their
publishers** and are included for study only - see [NOTICE.md](NOTICE.md).

---

### Türkçe özet

App Store ve Google Play mağaza görselleri için bir skill: uygulamanın vaadini bulur, gerçek ekranlardan yola
çıkar, "değiştirme testinden" geçen ve yapay zekâ kokmayan başlıklar yazar, görselleri mağaza ölçülerinde
PNG olarak üretir ve kontrol eder. İçinde Türkiye ve ABD App Store'larında 25 kategoriden en popüler
uygulamaların 1.366 mağaza görseli var; her uygulama iyi/kötü ve nedeniyle etiketli. claude.ai ve ChatGPT
için 20 MB altındaki **lite** paketi, Claude Code ve diğer ajanlar için **tam** paketi kullanın.
