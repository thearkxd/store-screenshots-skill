# Bundled fonts

Subset to Latin, Latin-1, Latin Extended-A (Turkish İ ı Ş ş Ğ ğ…), common punctuation, € and ₺ so the
skill stays small. All are licensed under the SIL Open Font License 1.1 (`OFL.txt`); bundling them with
software is permitted. The subsets are Modified Versions under the OFL: the original copyright notices are
kept in each file, and Lora, which has a Reserved Font Name, is renamed **Store Serif**.

| File | Family | Copyright |
|---|---|---|
| `InterDisplay-SemiBold.otf`, `InterDisplay-Bold.otf`, `InterDisplay-Medium.otf`, `InterDisplay-SemiBoldItalic.otf`, `Inter-Regular.otf`, `Inter-Medium.otf` | Inter / Inter Display | Copyright (c) 2016 The Inter Project Authors (https://github.com/rsms/inter) |
| `StoreSerif-Variable.ttf`, `StoreSerif-Italic-Variable.ttf` | Store Serif - a renamed subset of Lora (variable weight 400–700) | Copyright 2011 The Lora Project Authors (https://github.com/cyrealtype/Lora-Cyrillic), with Reserved Font Name "Lora" |
| `InstrumentSerif_400Regular.ttf`, `InstrumentSerif_400Regular_Italic.ttf` | Instrument Serif | Copyright 2022 The Instrument Serif Project Authors (https://github.com/Instrument/instrument-serif) |
| `Fraunces_600SemiBold.ttf`, `Fraunces_900Black.ttf`, `Fraunces_400Regular_Italic.ttf` | Fraunces | Copyright 2020 The Fraunces Project Authors (https://github.com/undercasetype/Fraunces) |
| `Anton_400Regular.ttf` | Anton | Copyright 2020 The Anton Project Authors (https://github.com/googlefonts/AntonFont) |
| `Baloo2_800ExtraBold.ttf`, `Baloo2_700Bold.ttf` | Baloo 2 | Copyright 2019 The Baloo 2 Project Authors (https://github.com/EkType/Baloo2) |
| `SpaceGrotesk_700Bold.ttf`, `SpaceGrotesk_500Medium.ttf` | Space Grotesk | Copyright 2020 The Space Grotesk Project Authors (https://github.com/floriankarsten/space-grotesk) |
| `BricolageGrotesque_800ExtraBold.ttf`, `BricolageGrotesque_500Medium.ttf` | Bricolage Grotesque | Copyright 2022 The Bricolage Grotesque Project Authors (https://github.com/ateliertriay/bricolage) |
| `Caveat_700Bold.ttf` | Caveat | Copyright 2014 The Caveat Project Authors (https://github.com/googlefonts/caveat) |
| `JetBrainsMono_700Bold.ttf` | JetBrains Mono | Copyright 2020 The JetBrains Mono Project Authors (https://github.com/JetBrains/JetBrainsMono) |

Aliases accepted by `render_set.py` (`"font": "<alias>"`):

| Alias | File | Used by |
|---|---|---|
| `sans` (default headline) | InterDisplay-SemiBold | native |
| `sans-bold` | InterDisplay-Bold | poster overlines, concept sheet labels |
| `sans-medium` | InterDisplay-Medium | cinematic headline; most overlines |
| `sans-italic` | InterDisplay-SemiBoldItalic | |
| `text` (default sub-line) | Inter-Regular | every direction's sub-line |
| `text-medium` | Inter-Medium | |
| `serif`, `serif-bold`, `serif-italic` | Store Serif 600 / 700 / Italic 500 | |
| `elegant`, `elegant-italic` | Instrument Serif / Italic | editorial; cinematic emphasis |
| `display`, `display-black`, `display-italic` | Fraunces 600 / 900 / Italic 400 | crafted |
| `condensed` | Anton | poster |
| `rounded`, `rounded-medium` | Baloo 2 800 / 700 | playful, stickers |
| `grotesk`, `grotesk-medium` | Space Grotesk 700 / 500 | utility |
| `bricolage`, `bricolage-medium` | Bricolage Grotesque 800 / 500 | a quirky alternative for playful or poster |
| `hand` | Caveat 700 | annotations |
| `mono` | JetBrains Mono 700 | utility overlines, numbers |

These are well-made defaults. If the app has a brand font, use that instead (`"font": "path/to/Brand.ttf"`);
`render_set.py` warns when a font lacks a character the copy needs.
