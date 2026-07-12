# Status — Arabic Movie & Show Map

Last updated: 2026-07-12

## Current stage
**Live on Vercel**, hybrid catalog + live-TMDB search, with a similarity-aware
map and a mobile-specific layout. Deployed at
[movie-map-steel.vercel.app](https://movie-map-steel.vercel.app/).

### The catalog
- `scraper/tmdb_discover.py` pulls Egyptian films year-by-year from TMDB's
  `/discover/movie` (origin country EG), fetching both Arabic and English
  localizations per title — no per-title API calls needed, since discover
  results already carry genres, overview, poster, backdrop, and rating in
  bulk. `scraper/serper_gapfill.py` supplements it with a Serper-driven
  Wikipedia sweep for titles TMDB's origin-country filter misses.
- Pipeline: discover → gap-fill → `ai_tagging/rule_tag_moods.py` (mood tags)
  → `similarity/compute_similarity.py` (genre 35% / mood 45% / era 20%
  weighted neighbors) → `docs/data.json`.
- Current catalog: **4,555 titles** (1930–2026), each enriched with
  `backdrop_path` + `vote_average` so the frontend needs zero extra fetches
  to show a catalog title's backdrop/rating.

### The live app (`index.html`, root)
- **Hybrid search**: queries the curated catalog first (instant, badged
  "catalog"), merges in live TMDB results not already covered. Catalog
  neighbors carry the real precomputed similarity score; TMDB-only
  neighbors get a client-side estimate (genre overlap + era proximity) so
  color/tooltip work everywhere.
- **Similarity-colored graph**: nodes colored on a d3 Viridis scale by
  similarity to the centered title (toggle back to genre coloring), with a
  legend, a "why similar" breakdown (shared genres/mood/era) on hover, and a
  min-similarity threshold slider.
- **Genre/mood/decade "Vibes" filter chips**, a "Surprise me" random-title
  button, shareable `?movie=type:id` deep links, and a per-movie TMDB
  backdrop wallpaper (previews on node hover too).
- **Language toggle** (English/العربية, top-right in map view only): switches
  the plot summary and Vibes chip labels between `tmdb_overview_en` and
  `synopsis_ar` (with fallback). Movie titles are never translated — they
  always show in their original language via `nativeTitle()`. Separate from
  the Arabic/English *origin* filter, which controls what search returns.
- **Mobile layout** (`@media max-width:640px`, desktop untouched): the
  scattered corner-pinned controls (color toggle, similarity slider, Vibes,
  language, legend) collapse behind a single "⚙ Controls" menu; the detail
  panel becomes a bottom sheet that peeks (title/rating only, map stays
  visible) and expands on tap for the full summary. Verified against a real
  render (headless Edge + DevTools Protocol at a 390px viewport), which
  caught and fixed a real bug: two buttons lost their dark styling when
  reparented out of `#toolbar` because their only styling came from an
  ancestor-dependent CSS selector.
- Whole-page scroll on the landing/search view (was previously trapped
  inside a fixed-height, separately-scrolling results dropdown — a mobile
  usability bug).

### Security
- `api/tmdb.js` (Vercel serverless proxy): whitelists TMDB endpoints,
  injects the credential from an env var (`TMDB_READ_TOKEN`/`TMDB_API_KEY`)
  server-side, GET-only, optional `ALLOWED_ORIGIN` lock against quota abuse.
- All untrusted text (titles, keywords, chips — TMDB is community-editable)
  is HTML-escaped via `esc()` before hitting `innerHTML`, closing a real
  DOM-XSS path found during a security pass.
- `vercel.json` sets CSP + `X-Content-Type-Options`/`X-Frame-Options`/
  `Referrer-Policy`/`Permissions-Policy`.
- `.gitignore` blocks `.env*`/`.vercel/` and the large regenerable pipeline
  build artifacts; only `docs/data.json` (the dataset the apps consume) is
  committed.
- **Outstanding (needs Mohamed):** rotate the TMDB + Serper API keys (both
  were pasted in chat during development); set `ALLOWED_ORIGIN` in Vercel.

### `/docs/` — catalog graph demo
Same `docs/data.json`, served at `/docs/` on the same Vercel deploy (separate
from the main app). Search-to-select landing, click-to-recenter graph,
capped "Overview" mode (250 nodes) so the full 4,555-title graph doesn't
freeze the browser.

## Build order checklist
(from [arabic-movie-map-project-spec.md](arabic-movie-map-project-spec.md) §5)

- [x] Scraper — now TMDB Discover-based, 4,555 Egyptian titles (not the
      original small Elcinema sample)
- [x] Data schema + storage — `docs/data.json`, enriched with backdrop/rating
- [x] AI tagging (rule-based, free) — ~86% of catalog titles get ≥1 mood tag
- [ ] Human review flow — mood tags are all machine-suggested, never
      human-reviewed (`mood_tags.approved` stays empty)
- [x] Similarity engine — weighted genre/mood/era score, live in the catalog
- [x] Frontend graph — hybrid catalog+TMDB search, similarity coloring,
      mobile layout, deployed on Vercel
- [x] Deploy to Vercel — live at movie-map-steel.vercel.app
- [ ] Rotate exposed API keys (TMDB, Serper) — see Security above

## Open items to decide later
- Whether to enrich `docs/data.json` further offline (cast/director data,
  so catalog *neighbors* — not just the center — could show ratings without
  any live fetch).
- Accessibility pass (keyboard-focusable graph nodes, ARIA labels, RTL
  layout for Arabic text) and CSP hardening (`script-src` still allows
  `unsafe-inline` because the app's JS is inline — externalizing it would
  let CSP actually block injected scripts).
- Whether friends other than Mohamed get a way to submit/edit titles, or it
  stays single-maintainer.

---

## Prior stage (shelved): Elcinema-first offline pipeline
Before the TMDB Discover pivot, the offline pipeline scraped Elcinema
directly (Arabic-first, ~39 titles) and was validated end-to-end: scraper,
TMDB enrichment merge, rule-based mood tagging (including a fixed Arabic
word-boundary bug — naive substring matching false-positived "جن" inside
"السجن"), and the similarity engine. That pipeline (`scraper/scrape.py`,
`scraper/tmdb_enrich.py`) still exists in the repo for reference but is
superseded by `tmdb_discover.py` for actually growing the catalog — TMDB
Discover returns far more Egyptian titles per API call than scraping
Elcinema page-by-page. The old 39-title dataset is preserved at
`docs/data.old39.json`.
