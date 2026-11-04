# Localisation (Turkish ↔ English and beyond)

## The most common mistake: the wrong language

About one in eight top apps in the Turkish store in this library shows English captions, or a UI in another
language, on its Turkish listing (`--technique locale-mismatch`): Yemeksepeti, Migros, Trendyol, Martı,
Starbucks Türkiye, DOA, Turkcell, fatsecret (Australian copy), GitHub (Spanish UI). Google Play explicitly asks
for separate screenshots per language when they contain text, and the same expectation is sensible on the
App Store.

**Rule:** caption language = store language = UI language in the screen. If the app has no Turkish UI yet,
write Turkish captions and say in the brief that the UI is English.

## Rewrite, don't translate

Write the headline again from the brief in the target language. A translated headline is usually longer,
flatter and keeps English rhythm.

| English source | Literal (bad) | Rewritten (good) |
|---|---|---|
| Never lose track of where you left off | Kaldığın yeri asla kaybetme | Kaldığın bölüm hep hazır |
| Know what you eat | Ne yediğini bil | Ne yediğini artık bil. (TaraGör) |
| Cardigan or coat? One glance. | Hırka mı, mont mu? Bir bakış. | Hırka mı, mont mu? Tek bakış yeter. |

## Turkish specifics

- **Capitals:** `i → İ`, `ı → I`. Python's `.upper()` and CSS `text-transform: uppercase` without
  `lang="tr"` produce "TAKIP"/"TAKiP"-style errors. In `render_set.py` set `"lang": "tr"` - it handles this.
- **Long words.** Turkish is agglutinative: fewer words, longer words ("gidebileceğinizi"). Plan for one word
  fewer per line than in English, check line breaks, and never hyphenate a headline.
- **Sen / siz.** Consumer apps in the library's best Turkish copy use **sen** (TaraGör, Trendyol Go, Bookios,
  HIRKA's Turkish UI). Government, banking and health apps often use **siz**. Pick one and keep it.
- **Imperatives work:** "Riskleri anında gör.", "Haberi Hızlı Oku", "İlanları Kaçırma". Avoid stacking
  "-ebilirsiniz" constructions; they turn headlines into instructions (Pegasus, e-Devlet, Otobüsüm Nerede).
- **Punctuation:** a period at the end of a short Turkish headline reads confident; "!" on every shot reads
  like a banner ad (Halkbank, Ziraat, A101).
- **Local proof:** TL amounts, Turkish cities and real Turkish content in the UI.

## Checklist per locale

- [ ] Headlines rewritten natively; banned phrases checked for that language (`copy-rules.md` §4).
- [ ] UI screenshots captured in that language with local demo data.
- [ ] Line breaks checked at full size; no hyphenation; Turkish capitals correct.
- [ ] Claims valid in that market (prices, availability, legal footnotes).
- [ ] `check_set.py --lang tr|en` run on the exported set.
