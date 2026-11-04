# Why screenshots look AI-made (and the fix for each)

"AI smell" is rarely one thing. It's the sum of defaults: a generic promise, a default gradient, floating
3D props and copy no one would say. In the library, 22 of 173 apps were flagged `ai_smell` - and none of
them were rated exemplary. Pull them up to calibrate your eye:

```bash
python3 scripts/search_library.py --ai-smell --position 1 --format table
python3 scripts/search_library.py --ai-smell --format paths --limit 12      # then open the images
```

## The signals

| Signal | What it looks like | Library cases | Fix |
|---|---|---|---|
| **Interchangeable promise** | "Premium Immersive Drama Series", "All-In-One Study Buddy" | NetShort, DramaBox, PineDrama, Gauth | Swap test; name a moment, a number or a pain |
| **Title Case Slogans** | "Create Stunning AI Covers With Any Voice" | Music Creator, Kling AI, Nurlu | Sentence case, verb-led, one idea |
| **Spec-sheet headlines** | "Multi-Reference Fusion", "HDR Format Native 4K" | Kling AI | Translate the spec into what the user gets |
| **Default gradients** | Purple→blue, pink→orange, rainbow mesh | DOA, Trendyol, Gauth, O-KAM | Flat brand colour, or a gradient sampled from the UI |
| **3D props and glow** | Chrome hearts, floating gems, neon glow, sparkles | Trendyol, Oley, Music Creator, Hepsiburada | Remove; let a real UI element be the hero |
| **Generated imagery** | Glossy fantasy portraits, painterly backdrops | GoodNovel, Nurlu, Shots | Real photography, or no imagery |
| **Floating tilted devices** | Phones at 15–30° in empty space | Microsoft Teams, Trumore, Dreame | Straight device, bigger; a callout for energy |
| **Stock emotion** | Models laughing at phones, 3D emoji stickers | Reverse Audio: Sing Fun | Show the app's result instead |
| **Machine-translated copy** | "AI intelligent service", "Share Amazing Sound With Friend" | O-KAM, Reverse Audio | Write natively per language |
| **Typos left in** | "Onginals", "Mutilingual" | DramaBox, Kling AI | Proofread every headline at full size |
| **"AI-powered" as the claim** | "Your AI-Powered Collaboration Platform" | Zoom, Gauth | Say what the AI does for the user, concretely |
| **The template look** | Headline on top, phone in the middle, a card beside it - in every shot, for every app | most of the "solid" sets | A concept from the app's DNA; vary placement, scale and crop per shot (`design-process.md` §5) |
| **Decoration without a reason** | Blobs, rings, confetti, random lines, a glow behind the phone | DOA, Oley | Every shape needs a motive from the app (its progress bar, its card radius) - or delete it |
| **Fake UI** | A redrawn badge, button or chart that isn't cropped from the app | - | Crop the real element from a screen; never draw UI (`design-process.md` §1) |

## What human-made sets have instead

From the exemplary sets:
- **A voice.** Copy that sounds like one person with an opinion: HIRKA, The Pour Over, Tinder, McDonald's.
- **Specifics.** Numbers with footnotes, real places, real content in the UI (Indeed, Cash App, Ground News).
- **Restraint.** One colour system, one type family, one emphasis device (Waze, Flo, Spotify, Threads).
- **A motif that couldn't belong to anyone else.** HIRKA's rope, Moovit's transit lines, Bible's red loops,
  Instagram's hand-drawn circles.
- **Lived-in screens.** Plausible names, local data, results rather than empty states.

## Final checklist (run before showing anything)

- [ ] Every headline passes the swap and say-it tests; none uses a banned phrase (`copy-rules.md` §4).
- [ ] Shots 1–3 explain the app at search-result size (`_search-preview.jpg`).
- [ ] One campaign system across the set (ground family, type family, emphasis device, motif) - and no two
      neighbours with the same composition.
- [ ] Every decorative layer has a motive from the app's DNA or the concept.
- [ ] No tilted floating phones, 3D props, glow, sparkles, emoji stickers or stock smiles.
- [ ] Every screen is real UI from the app (cropped/zoomed is fine), with realistic data in the right language.
- [ ] Captions and UI are in the same language as the store listing.
- [ ] No unverified claims; no ranking/award/price/promo text on Google Play images.
- [ ] Proofread at 100 %: typos, widows, hyphenation, Turkish İ/ı.
- [ ] Next to 2–3 exemplary peers (`peer_test.py`), the set looks equally resolved.
