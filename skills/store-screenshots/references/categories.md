# Category playbooks

What each App Store category's chart apps actually do, what the exemplary ones do differently, the clichés
that make a set interchangeable, and where the room to stand out is. Built from the library (top 4 free apps
per category in the TR and US stores + 2 US challengers, collected 2026-11-04). Quality labels are a
reviewer's judgement, not conversion data - use these as starting points and check the live chart with
`search_library.py --category <slug> --summary` and `fetch_listing.py --search`.

Each entry ends with three **directions** for `concepts.py`: safe (fits the category) · bold · unexpected.
`concepts.py` uses the same picks when you pass `--category`.

## Contents
Books · Business · Developer Tools · Education · Entertainment · Finance · Food & Drink · Games ·
Graphics & Design · Health & Fitness · Lifestyle · Magazines & Newspapers · Medical · Music · Navigation ·
News · Photo & Video · Productivity · Reference · Shopping · Social Networking · Sports · Travel · Utilities ·
Weather · Kids and others

How to use: read your category and one neighbour (a news app reads Magazines too; a habit tracker reads
Productivity and Health). Take the **norm** as what the search results will look like around you, steal from
the **best**, ban the **clichés**, and pick the angle (`angle.md`) from **stand out**.

---

## Books (`books`)
- **Norm:** device frames on cover collages; benefit or content first shot; lots of photo grounds.
- **Best:** Storytel (one brand colour per shot, 2–5 word headlines, features as chips), Audible (parallel
  rhythm "Audiobooks you'll love. Podcasts you'll binge."), Libby (one maroon ground, one bold word),
  Kindle (small coloured overline + serif headline with one italic word).
- **Clichés:** glossy AI fantasy art, pink/purple gradients, "A universe of stories", caps hooks like
  "1M+ NOVELS". Short-fiction apps all look the same.
- **Stand out:** the reader's ritual (bedtime chapter, commute listening), a real cover wall that is
  clearly *your* catalogue, the reading stat only you track. Bookish serif type earns trust.
- **Directions:** `editorial` · `cinematic` · `crafted`

## Business (`business`)
- **Norm:** device frames on blue gradients; brand-first or benefit; social proof.
- **Best:** Indeed - a quantified promise first ("Get hired 30% faster", with footnote) and UI cards that
  break out of the frame.
- **Clichés:** "Your AI-powered collaboration platform", sparkle icons, pastel 3D blobs with tilted phones,
  government-portal long headlines ending in "!", logo instead of a caption.
- **Stand out:** one job and one person ("Approve invoices from the train"), a number you can footnote, the
  exact document or screen your user lives in. Most of the chart is weak - plain competence wins.
- **Directions:** `native` · `poster` · `editorial`

## Developer Tools (`developer-tools`)
- **Norm:** flat or gradient grounds; feature first; many sets with no captions at all.
- **Best:** Working Copy - mint brand colour, plain 3–4 word headlines naming exact jobs ("Fix merge
  conflicts", "Commit graph with search") over real code.
- **Clichés:** spec-label caps ("DEVICE and SENSOR Information"), "intelligent", bare screenshots, an
  un-localised UI in the local store.
- **Stand out:** insider words (commit, diff, SSH, logs), mono type, a grid; show the gnarly real thing
  (a conflict, a stack trace) solved. Developers read precision as respect.
- **Directions:** `utility` · `native` · `poster`

## Education (`education`)
- **Norm:** gradients and photos; social proof; two-tone headlines; lots of paragraph copy.
- **Best:** Duolingo - real lesson UI full-bleed, the caption in a chunky coloured pill at the bottom, in the
  brand font, lowercase and verb-led, one colour per shot.
- **Clichés:** noun-phrase slogans ("All-in-one study buddy", "Pro-level explanation"), feature lists on every
  shot, government school portals with no captions.
- **Stand out:** the learner's exact moment (the night before the exam, the first conversation abroad), a
  visible streak/progress, the subject's own vocabulary. Playful but legible.
- **Directions:** `playful` · `native` · `crafted`

## Entertainment (`entertainment`)
- **Norm:** dark (65% of shots), content showcases, generic claims. Short-drama apps dominate the chart and are
  nearly identical (4 of 9 flagged for AI/template smell).
- **Best:** TickPick - copy with rhythm and a point ("Every event. No hidden fees. Ever.", "Track. Freeze.
  Save.", "See it. Pick it. Done.").
- **Clichés:** "Premium immersive drama", "Massive variety", "Expect the unexpected", italic Title-Case
  slogans, laurel numbers, dark-red glossy posters, the app name as every headline.
- **Stand out:** an enemy (fees, the algorithm, spoilers), the fan's insider words, a mood instead of a
  catalogue. Cinematic grounds sampled from real artwork beat a generic dark gradient.
- **Directions:** `cinematic` · `poster` · `editorial`

## Finance (`finance`)
- **Norm:** flat or gradient brand grounds; stat numbers; footnoted claims; company-centric openers in
  Turkish banking ("Uygulamamız yenilendi!").
- **Best:** Kalshi (warm brown matched to the UI, all-verb condensed headlines), Cash App (green/black/beige
  rotation, concrete numbers "Invest with as little as $1", one card per shot), PayPal (deep blue, specific
  footnoted promises).
- **Clichés:** floating 3D coins and piggy banks, "We renewed the app!", exclamation marks, raw banking
  screens, "secure and easy".
- **Stand out:** one concrete number per shot (fee, rate, minutes to open an account), the user's money
  moment (payday, splitting rent), a footnote that makes the claim checkable. Never a balance you can't show.
- **Directions:** `native` · `poster` · `editorial`

## Food & Drink (`food-drink`)
- **Norm:** flat brand colour, appetite photos, wordplay, captions alternating top/bottom. No weak sets in the
  chart - the bar is high.
- **Best:** Trendyol Go ("İndirim mmmmm" with a burger, then one-word Turkish headlines), McDonald's (bold
  payoff, a human aside in brackets), DoorDash (condensed caps on brand red, products bursting from the
  frame, a sentence finished on the last shot), CAVA (headline split above and below the phone, hand-drawn
  arrows).
- **Clichés:** "Delicious food delivered", stock plates, a generic burger.
- **Stand out:** the local dish, the exact craving moment (late-night, rainy day), a real price or a
  minutes-to-door number. Appetite + humour; let products break the frame.
- **Directions:** `poster` · `playful` · `crafted`

## Games (`games`)
- **Norm:** full-bleed gameplay (7 of 9), caption bands, exclamations.
- **Best:** Gardenscapes - one-verb headlines on a constant red banner ("Collect!", "Fill orders!",
  "Renovate!") and a before/after shot.
- **Clichés:** single words ("RELAXING", "SIMPLE FUN"), eight near-identical boards, "Level 15…50".
- **Stand out:** progression in one glance (before/after), the one mechanic nobody else has, a character
  moment. Device frames are rare here - full-bleed with a strong band reads as the game itself.
- **Directions:** `playful` · `poster` · `cinematic`

## Graphics & Design (`graphics-design`)
- **Norm:** content-first device frames; 29% dark; no exemplary chart set.
- **Best (solid):** Sketchbook ("A complete artist's toolkit"), Pixelcut ("Easily create professional images").
- **Clichés:** spec-sheet headlines ("Multi-reference fusion", "HDR native 4K"), AI imagery, stock couples in
  collages, "500+ templates".
- **Stand out:** the user's own result (one before/after per shot), the craft vocabulary (layers, brushes,
  kerning), an annotated detail. The work is the hero - frame it like a gallery.
- **Directions:** `cinematic` · `editorial` · `poster`

## Health & Fitness (`health-fitness`)
- **Norm:** consistent brand colour; benefit first (8 of 10); social proof; dark UIs.
- **Best:** TaraGör (spoken Turkish lines with a coloured second half, "Ne yediğini artık bil."), Flo (one
  lilac ground, the key phrase in a white box, UI cropped to the proving card), LADDER (neon-yellow opener,
  black shots with heavy caps and real coaches - looks like a sports brand).
- **Clichés:** five type sizes per shot, "WHEREVER YOU ARE…!", "Your go-to app for all things wellness",
  foreign-market copy in the local store.
- **Stand out:** a specific body or goal ("Get stronger, with a plan."), real coaches or real data, the
  question your user asks ("Ürün neyi saklıyor?"). Calm for health, loud for training.
- **Directions:** `native` · `poster` · `crafted`

## Lifestyle (`lifestyle`)
- **Norm:** gradients (38%), people photos, social proof.
- **Best:** Pinterest (seasonal set - "Embrace spooky season" - moody real photography, 3-word headlines),
  Tinder (witty serif headlines with one italic word, "You wanted a sign, here's twelve").
- **Clichés:** rainbow gradients, floating objects, "X is here for you!", English copy in a Turkish store.
- **Stand out:** humour and a point of view, the season or the occasion, real people. Serif wit reads
  grown-up; stickers read community.
- **Directions:** `editorial` · `playful` · `crafted`

## Magazines & Newspapers (`magazines-newspapers`)
- **Norm:** device frames on flat paper or the masthead colour; serif type; verb-led; specific pains.
- **Best:** NYTimes (bold overline "Follow Today / Listen Today" above a serif headline - one section per
  shot), Ground News (concrete jobs on paper-beige), The Pour Over (point-of-view copy, a quote shot), The
  Economist (its red and serif, sentences that sound like the paper).
- **Clichés:** channel grids with no captions, "Fearless journalism" without proof.
- **Stand out:** the editorial voice itself, the section structure as the set structure, the reading
  moment (5-minute morning brief). Strong category - match the masthead, don't decorate.
- **Directions:** `editorial` · `native` · `poster`

## Medical (`medical`)
- **Norm:** flat or flat-top; two-tier copy; cards breaking out; no exemplary set in the chart.
- **Best (solid):** pregnancy trackers ("Track baby's growth"), "The #1 pregnancy & baby app".
- **Clichés:** the splash screen and a login form as shots 1–3, tiny two-line captions on pale mint, the logo
  on every shot, long Turkish sentences.
- **Stand out:** the patient's question in their words, one task per shot (book, results, reminder), calm
  confident type. An empty category: a clean, warm, legible set wins by default.
- **Directions:** `native` · `crafted` · `editorial`

## Music (`music`)
- **Norm:** photo and gradient grounds; 45% dark; feature first.
- **Best:** Spotify (pink-on-green brand frame, caps with one bold word), Suno (red-orange brand gradient,
  light condensed serif, the real prompt UI - "Make any song you can imagine"), Tunesimo (Gen-Z voice "FIND
  YOUR TUNE TWINS", stickers from its own UI).
- **Clichés:** stock models laughing at phones, 3D emoji, neon glow, "AI-powered premium recommendations".
- **Stand out:** the listener's identity (taste, friends, a scene), real artwork sampled into the ground,
  insider slang. Music sets can be loud - as long as the voice is real.
- **Directions:** `cinematic` · `playful` · `poster`

## Navigation (`navigation`)
- **Norm:** consistent brand colour; verb-led; real map UI; some unreadable paragraph captions.
- **Best:** Moovit (transit lines run through every shot as a motif; key moments pop out as tilted pills -
  "Your bus is arriving NOW"), Waze (flat cyan, bold headlines that each name a driving moment).
- **Clichés:** 4–6 line Turkish paragraphs, phones floating in white, small two-line sentences on blue.
- **Stand out:** the moment on the road (the bus is late, the parking hunt), the city's real names, a motif
  drawn from the map itself (`crafted` lines/waves).
- **Directions:** `crafted` · `native` · `poster`

## News (`news`)
- **Norm:** flat grounds; social proof; dark UIs; brand-first openers.
- **Best:** Reddit (a loud colour per shot, white sticker strips, real funny posts), NYTimes (overline +
  serif).
- **Clichés:** small line icons with two-line captions, brand name and laurels on the first two shots.
- **Stand out:** the reader's tribe and voice (Reddit) or the institution's authority (NYT) - pick one; the
  real content is the proof.
- **Directions:** `editorial` · `poster` · `playful`

## Photo & Video (`photo-video`)
- **Norm:** device frames on flat grounds; feature first (7 of 8); before/after; small captions.
- **Best:** Instagram - hand-drawn circles and arrows annotate the feature on each shot.
- **Clichés:** one-word headlines ("Create", "Watch"), thin sub-lines on white, AI-glossy editors.
- **Stand out:** the user's own footage as the ground, before/after, hand annotations pointing at the one
  control that matters (`"annotations"`).
- **Directions:** `cinematic` · `native` · `playful`

## Productivity (`productivity`)
- **Norm:** real UI with specific use cases (5 of 7); gradients sampled from the brand.
- **Best:** Gemini (concrete jobs with one word in brand blue), ChatGPT (two-line headlines, believable real
  prompts), Claude (warm dark photography, serif headlines, prompts localised per market), Structured (soft
  pink, lowercase two-weight headlines placed around the UI).
- **Clichés:** "One chatbot, endless possibilities", glossy dark gradients, cartoon AI portraits.
- **Stand out:** a specific job per shot in the user's words, real example content localised to the market,
  a gentle personal system (Structured) instead of a power tool.
- **Directions:** `native` · `editorial` · `crafted`

## Reference (`reference`)
- **Norm:** serif type; testimonials; small captions; old UIs; government apps with no captions.
- **Best:** Bible - red hand-drawn loops tie the shots together, serif with one italic word ("No Ads or
  Purchases"), short real testimonials.
- **Clichés:** painterly AI backdrops, serif Title-Case slogans, "Every moment a verse", raw state portals.
- **Stand out:** the daily ritual, what you refuse (ads, paywalls), a hand-drawn motif. Quiet confidence.
- **Directions:** `editorial` · `crafted` · `native`

## Shopping (`shopping`)
- **Norm:** flat brand grounds; offers and numbers; some 3D objects.
- **Best:** Vinted (one teal ground, serif with personality - "Don't wear it? Sell it!", a headline spanning a
  garment), Capital One Shopping (concrete money everywhere, real retailer logos), Depop (red ground
  alternating with real fashion photography, a money benefit first).
- **Clichés:** pink-orange gradients with floating 3D hearts, English caps in the Turkish store, "Shop
  everything".
- **Stand out:** the shopper's identity (second-hand, sneakerheads, deal hunters), one checkable money number,
  real products. Ranking/price claims are restricted on Google Play (`store-specs.md`).
- **Directions:** `poster` · `editorial` · `playful`

## Social Networking (`social-networking`)
- **Norm:** flat grounds (41%); real content; colour per shot; people photos.
- **Best:** Threads (black ground, three-word headlines with one phrase in a hand-placed yellow block), WhatsApp
  ("Simple. Reliable. Private." three-beat opener, bold keywords alternating green and off-white).
- **Clichés:** "Connect with friends", "Stay closer", stock friend groups.
- **Stand out:** the specific relationship (close friends, a city, a hobby), believable real posts, a
  highlight block or sticker in the brand's voice.
- **Directions:** `playful` · `poster` · `editorial`

## Sports (`sports`)
- **Norm:** 48% dark; offers first (5 of 10); condensed caps; glow and 3D objects; no exemplary chart set.
- **Best (solid):** 18Birdies ("Golf GPS range finder"); LADDER (Health & Fitness) shows how a sports brand
  should look.
- **Clichés:** glossy 3D balls, gems and glow on royal blue, stacked caps lists, small Title-Case captions.
- **Stand out:** the fan's or athlete's moment (match day, the last km), real stats in mono/condensed type,
  one hero number. Google Play bans price and promo claims in screenshots - check `store-specs.md`.
- **Directions:** `poster` · `utility` · `cinematic`

## Travel (`travel`)
- **Norm:** consistent brand colour (9 of 10); icon overlines; people photos; benefit first.
- **Best:** Uber (shots follow one ride in order with a progress line; a "GO ANYWHERE" poster), Lyft (real
  riders, two-beat lines "Be there soon. Really soon."), GetYourGuide (giant "Right place / Right time" poster
  pair), Viator (conversational copy running across shots, sticker circles).
- **Clichés:** green panoramas then plain white shots, exclamation sentences, eight look-alike shots.
- **Stand out:** the trip as a story (one journey across the set), the stress you remove (free cancellation,
  tickets on your phone), a destination's real name.
- **Directions:** `poster` · `native` · `crafted`

## Utilities (`utilities`)
- **Norm:** flat grounds; mascots; many sets with no captions or onboarding screens used as shots.
- **Best:** Chrome - the feature name in a blue pill with its icon inside the headline ("Search what you see
  with [Lens]").
- **Clichés:** "Fast, secure, private" without proof, "Get started" buttons in the shot, seven identical shots.
- **Stand out:** the one annoying task you kill, the UI element named in the copy, a before/after. Plain and
  precise; a grid or mono overline for power users.
- **Directions:** `native` · `utility` · `playful`

## Weather (`weather`)
- **Norm:** device frames; cards breaking out (4 of 10); small captions; seasonal campaigns.
- **Best:** HIRKA (a knitted-rope motif wraps every phone, cream/maroon, "Not degrees, a decision."),
  WeatherX ("Label: specifics" headlines - "Exact rain timing: start to finish"), The Weather Channel (seasonal
  photography, life context "fall weekends & game days"), Weather & Radar (short spoken headlines, hand-drawn
  arrows on the radar).
- **Clichés:** "Most accurate / hyper-local forecast on the planet", thin centred superlatives, raw radar.
- **Stand out:** a decision instead of a number (what to wear, when to leave), the season, a motif. Every
  weather app has the same data - the angle is what you do with it.
- **Directions:** `crafted` · `utility` · `cinematic`

## Kids and others
Not in the library. For **Kids**: apps in Apple's Kids category get extra review (guideline 1.3), so keep
ads and purchase prompts out of the shots; `playful` is the safe default, `crafted` the warmer option; speak
to the parent in the copy, show the child's world on screen. For anything else, read the two nearest categories.
