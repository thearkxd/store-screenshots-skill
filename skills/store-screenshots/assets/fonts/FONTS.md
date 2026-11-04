# Bundled fonts

Subset to Latin, Latin-1, Latin Extended-A (Turkish İ ı Ş ş Ğ ğ…), common punctuation, € and ₺ so the
skill stays small. All are licensed under the SIL Open Font License 1.1 (`OFL.txt`); bundling them with
software is permitted.

| File | Family | Copyright |
|---|---|---|
| `InterDisplay-SemiBold.otf`, `InterDisplay-Bold.otf`, `InterDisplay-Medium.otf`, `InterDisplay-SemiBoldItalic.otf`, `Inter-Regular.otf`, `Inter-Medium.otf` | Inter / Inter Display | Copyright (c) 2016 The Inter Project Authors (https://github.com/rsms/inter) |
| `Lora-Variable.ttf`, `Lora-Italic-Variable.ttf` | Lora (variable weight 400–700) | Copyright 2011 The Lora Project Authors (https://github.com/cyrealtype/Lora-Cyrillic) |

Aliases accepted by `render_set.py` (`"font": "<alias>"`):

| Alias | File |
|---|---|
| `sans` (default headline) | InterDisplay-SemiBold |
| `sans-bold` | InterDisplay-Bold |
| `sans-medium` | InterDisplay-Medium |
| `sans-italic` | InterDisplay-SemiBoldItalic |
| `text` (default sub-line) | Inter-Regular |
| `text-medium` | Inter-Medium |
| `serif` | Lora, weight 600 |
| `serif-italic` | Lora Italic, weight 500 |

These are neutral, well-made defaults. If the app has a brand font, use that instead (`"font": "path/to/Brand.ttf"`).
