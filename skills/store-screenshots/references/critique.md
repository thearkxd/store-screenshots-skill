# Critiquing a screenshot set

Use this when the user shares an existing set (theirs or a competitor's). Be direct and specific; quote the
headlines; point to the shot number.

## Process

1. Look at the set at full size, then build a contact sheet and a search-size view:
   `python3 scripts/make_sheet.py --rows <folder> -o sheet.jpg` and
   `python3 scripts/check_set.py <folder> --store ios` (writes `_search-preview.jpg`; size errors are expected
   if the files aren't exports).
2. Write down, without looking at the store text: *what does this app do, for whom?* using only shots 1–3.
   If you can't, that's finding #1.
3. Score the set (below), then compare it to 2–3 exemplary peers (`peer_test.py`).
4. Give **the three changes with the biggest effect first**, then the rest. Offer to rewrite the copy and
   re-render.

## Scorecard (0–2 each, 20 max)

| # | Criterion | 0 | 1 | 2 |
|---|---|---|---|---|
| 1 | **Promise in shot 1** | Logo/splash/UI only | Generic claim | Clear, specific benefit |
| 2 | **Shots 1–3 alone** explain the app | No | Partly | Yes |
| 3 | **Specificity** (swap test) | Most headlines generic | Mixed | All specific |
| 4 | **Voice** (say-it test) | Slogans/Title Case | Plain | Sounds like a person |
| 5 | **Glance legibility** at search size | Unreadable | Some | All readable |
| 6 | **One idea per shot** | Paragraphs/lists | Some crowding | Clean |
| 7 | **Proof** (screen proves headline) | Unrelated screens | Loose | Each screen proves it |
| 8 | **Visual system** (colour/type/emphasis) | Inconsistent | Mostly | One system |
| 9 | **No AI/template smell** (`anti-ai.md`) | Several signals | One or two | None |
| 10 | **Localisation & compliance** | Wrong language / store violations | Minor issues | Correct |

16–20 strong · 11–15 workable, fix the top three · ≤ 10 rebuild the story first.

## Output format

```markdown
**Score: 12/20** - <one-sentence verdict>

**Top 3 fixes**
1. Shot 1 - "<current headline>" → "<suggested>" - why
2. …
3. …

**Shot by shot**
| # | Now | Issue | Suggestion |
|---|---|---|---|

**What's already working** - 1–3 bullets
```
