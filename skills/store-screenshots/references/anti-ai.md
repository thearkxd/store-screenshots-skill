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
| **Default gradients** | Purple→blue, pink→orange, rainbow mesh, with no link to the app | DOA, Trendyol, Gauth, O-KAM | Flat brand colour, a gradient sampled from the UI, or the app's own gradient (§ When an effect is right) |
| **3D props and glow** | Chrome hearts, floating gems, neon glow, sparkles | Trendyol, Oley, Music Creator, Hepsiburada | Remove; let a real UI element be the hero. Glow that is the app's own light (a neon UI, a lit accent) is a material, not a prop |
| **Generated imagery** | Glossy fantasy portraits, painterly backdrops | GoodNovel, Nurlu, Shots | Real photography, or no imagery |
| **Floating tilted devices** | Phones at 15–30° in empty space, in every shot, for no reason, no shadow, each lit differently | Microsoft Teams, Trumore, Dreame | Straight device, bigger; a callout for energy. If depth is the message (a stack, a scene, two devices talking), a `device3d` at a moderate angle, with the set's one light and lens and a shadow, in at most two shots, with `3d` in the campaign's materials |
| **Stock emotion** | Models laughing at phones, 3D emoji stickers | Reverse Audio: Sing Fun | Show the app's result instead |
| **Machine-translated copy** | "AI intelligent service", "Share Amazing Sound With Friend" | O-KAM, Reverse Audio | Write natively per language |
| **Typos left in** | "Onginals", "Mutilingual" | DramaBox, Kling AI | Proofread every headline at full size |
| **"AI-powered" as the claim** | "Your AI-Powered Collaboration Platform" | Zoom, Gauth | Say what the AI does for the user, concretely |
| **The template look** | Headline on top, phone in the middle, a card beside it - in every shot, for every app | most of the "solid" sets | A concept from the app's DNA; vary placement, scale and crop per shot (`design-process.md` §5) |
| **Decoration without a reason** | Blobs, rings, confetti, random lines, a glow behind the phone | DOA, Oley | Every shape needs a motive from the app (its progress bar, its card radius) - or delete it |
| **Fake UI** | A redrawn badge, button or chart that isn't cropped from the app | - | Crop the real element from a screen; never draw UI (`design-process.md` §1) |

## When an effect is right

The rows above are defaults, not bans. Each of these looks AI-made when it is **the same on every app**. The
same effect is design when it comes from **this** app:

| Effect | A source that makes it right | Still wrong |
|---|---|---|
| Gradient | The app's UI uses it (Instagram's gradient, a fintech's card), or the concept needs a light (dawn for a sleep app) | Purple→blue because "tech" |
| Glow / coloured light | The app's accent is lit (a neon music UI, a night-mode app), or the light carries the message (the one new episode) | A halo behind every phone |
| Glass | The app's own panels are frosted (iOS materials, Liquid Glass), so glass is how its UI already looks | Glass cards in a flat Material app |
| Tilt / 3D phone | Depth is part of the message (a stack of cards, a camera app in a scene, a multi-device set) | Every shot turned 20° "for energy" |
| Texture / grain | The brand is print, film or paper (a journal, a recipe app, a photo app) | Grain to hide a flat design |
| Illustration | The app itself uses illustration (onboarding, empty states, mascot) | Stock blobs and confetti |

How the skill holds this line:
1. **The DNA lists the materials** the app's own screens are made of (`dna.py`: `"materials"`, shown on the
   board, with what is *not* in the app).
2. **The campaign lists the materials** the set uses, each with its reason: `"dna: the tab bar is frosted"`,
   `"concept: the accent is the only light"`, `"brand guide: …"`.
3. **The renderer warns about any effect without a source**: glass, glow, a gradient, grain, a tilted screen, a
   3D device or an illustration that neither the campaign's materials nor the layer's `"motive"` explains. It
   also warns when an effect sits on every shot without coming from the DNA.

A brand guide that asks for an effect is a source too. Follow it and say so in the campaign.

## The skill's own habits

Any designer has habits, and so does this skill. Each one below is right for some shot. When it appears on
every shot of every set, the skill's output becomes recognisable, which is just a template seen from further
away. The renderer counts them across a set (`habit_warnings`). With `--history` it also compares a set to
the ones made earlier for other apps.

| Habit | Where it's right | Warned when |
|---|---|---|
| A near-black ground with one accent | A dark app, or a concept about night or focus | The app's UI is light and every shot is dark |
| The lifted card with a deep shadow | The one shot whose message is that element | A lift in most shots |
| A hand-drawn circle or arrow | The one detail a shot is about | Marks in most shots |
| The phone cropped at the bottom edge | A long screen where the top is the proof | Every shot of a 4+ set |
| Headline top-left, screen below-right at 92 % | Any single shot | Three shots with the same composition (set check) |
| The bundled example's numbers | Never: the examples show the file format | A shot that repeats an example's placements number for number |
| Glass, glow or 3D on every shot | When the app is made of it (a `dna:` reason) | On every shot of a 4+ set without one |

Before you reach for one, ask whether this message needs it, or whether the last set had it.

## What human-made sets have instead

From the exemplary sets:
- **A voice.** Copy that sounds like one person with an opinion: HIRKA, The Pour Over, Tinder, McDonald's.
- **Specifics.** Numbers with footnotes, real places, real content in the UI (Indeed, Cash App, Ground News).
- **Restraint.** One colour system, one type family, one emphasis device (Waze, Flo, Spotify, Threads).
- **A motif that couldn't belong to anyone else.** HIRKA's rope, Moovit's transit lines, Bible's red loops,
  Instagram's hand-drawn circles.
- **Lived-in screens.** Plausible names, local data, results rather than empty states.

## Final checklist (run before showing anything)

- [ ] The promise (shot 1) fails the swap test for every competitor; every headline passes the say-it and
      proof tests; none uses a banned phrase (`copy-rules.md` §1, §4).
- [ ] Shots 1–3 explain the app at search-result size (`_search-preview.jpg`).
- [ ] One campaign system across the set (ground family, type family, emphasis device, motif) - and no two
      neighbours with the same composition.
- [ ] Every decorative layer has a motive from the app's DNA or the concept; every effect (gradient, glow,
      glass, tilt, 3D, texture, illustration) is in the campaign's materials with its reason.
- [ ] No sparkles, emoji stickers, stock smiles, chrome props; no tilted phones or glow without a source.
- [ ] None of the skill's own habits on every shot (§ The skill's own habits).
- [ ] Every screen is real UI from the app (cropped/zoomed is fine), with realistic data in the right language.
- [ ] Captions and UI are in the same language as the store listing.
- [ ] No unverified claims. On Google Play, no ranking, award, price or promo text, which Google recommends
      leaving out (an exception is the user's informed choice).
- [ ] Proofread at 100 %: typos, widows, hyphenation, Turkish İ/ı.
- [ ] Next to 2–3 exemplary peers (`peer_test.py`), the set looks equally resolved.
