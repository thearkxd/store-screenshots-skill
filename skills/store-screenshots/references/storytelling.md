# Storytelling: ordering a screenshot set

## Contents
1. What people actually see
2. The first three shots
3. Set structures that work
4. Choosing which screens to show
5. Shot roles cheat sheet

---

## 1. What people actually see

- **App Store search results** show the first screenshots of a listing next to the icon (portrait sets show
  up to three side by side). For most people, shots 1–3 *are* your listing. Shots 4–10 are for people who
  already tapped and are deciding.
- **Google Play** shows the first screenshots in the listing carousel (and in some promotional surfaces,
  which require ≥ 4 screenshots at ≥ 1080 px). The feature graphic (1024×500) appears above on some surfaces.
- So: shots 1–3 must work **alone, small and in order**. Run `check_set.py` and look at
  `_search-preview.jpg` every time.

## 2. The first three shots

**Shot 1 - the promise.** What this app does for whom, in the user's words, over the screen that proves it.
In the library, apps rated exemplary mostly open with a benefit (27 of 42); weak sets often open with a logo,
splash or bare UI (26 of 52 weak apps open with `brand` or `ui-only`).
- Good: "Ne yediğini artık bil." over a live barcode scan (TaraGör) · "Get hired 30% faster with the app*"
  (Indeed) · "Make any song you can imagine" (Suno)
- Allowed alternatives: a strong **hook** ("Embrace spooky season" - Pinterest's seasonal set) or a **proof
  opener** when the proof is the reason to install ("Trusted by 300M women", an Apple award) - but the
  promise must then be shot 2.
- Never: splash, login, onboarding, logo-only, "the app is renewed".

**Shot 2 - the main reason it's better.** The one capability competitors don't have or do worse.

**Shot 3 - the second reason, or the proof.** A number, a before/after, a real result.

After shot 3, cover the remaining proof points in order of importance, then secondary features, then
trust (privacy, support, platforms). Close with something that works as a last impression (a summary line,
the widget, a sentence that completes the set).

## 3. Set structures that work

| Structure | How | Library examples | Good for |
|---|---|---|---|
| **One job per shot** | Each shot = one thing the user does, verb-led | Gemini, ChatGPT, Waze | Tools with several clear uses |
| **The journey** | Shots follow one session in order | Uber (destination → ride → price → pickup → safety → rating, with a progress line) | Flows: rides, orders, bookings |
| **Series system** | Same caption grammar every shot | NYT ("Follow Today / Listen Today / Play Today"), Kindle (overline + serif line) | Many features under one brand idea |
| **Sentence across shots** | Headline continues from one shot to the next | DoorDash, Vinted, Planet Fitness | Bold brands; risky if shot 1 doesn't stand alone |
| **Persona story** | Every screen uses the same believable user/business | WhatsApp Business (one cake shop); Muse (concrete household tasks: a field-trip form, a stroller under budget) | B2B, productivity, anything abstract |
| **Proof stack** | Promise, then numbers, then testimonials | Capital One Shopping, Bible (a quote shot), The Pour Over | Money, trust-sensitive categories |

Mix at most two structures. The series system plus one poster shot (Uber's "GO ANY-WHERE") is a strong
default for most apps.

## 4. Choosing which screens to show

- Start from the proof points, then find the screen that proves each one. If no screen proves it, either
  design a real state that does (seed the app with good demo data) or drop the claim.
- **Seed realistic data.** Real names, plausible numbers, local content (a Turkish city in a Turkish listing,
  TL prices, Turkish UI). The library's strongest sets look lived-in: Claude's prompts are localised per
  market; WhatsApp's chats are ordinary and warm.
- Hide anything that dates or confuses: debug banners, empty states, lorem ipsum, 2019 dates, an old status
  bar, someone's real personal data.
- Prefer the state *after* the user did something (a result, a filled list) over the empty start screen.
- Use **zoom/crop** when the proof is one card on a busy screen (Flo's "Period in 3 days", Capital One's 720
  credit score, ParkMobile's timer).

## 5. Shot roles cheat sheet

| Role | Headline style | Layout that usually fits |
|---|---|---|
| Promise | Spoken sentence or number | Device frame, big type |
| Differentiator | Verb-led job or named pain | Device frame or zoom card |
| Proof | Number, before/after, testimonial | Zoom card, callout pulled out |
| Breadth | "Also: …" or category words | Full-bleed UI or grid of real cards |
| Trust | Privacy/safety, concrete | Device frame, calm |
| Poster (max 1) | 2–4 giant words | Type-led, no device |
| Closer | Sentence that completes the set, or platforms (widget, watch) | Device frame or photo |
