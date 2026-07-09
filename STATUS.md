# Status — Arabic Movie & Show Map

Last updated: 2026-07-09

## Current stage
Full pipeline (scraper → TMDB enrichment → mood tagging → similarity engine
→ interactive graph frontend) validated end-to-end on the 39-title sample
and live on GitHub Pages. Next: human review flow, then data schema lock and
scaling up the scraper.

- **Similarity engine** (`similarity/compute_similarity.py`): weighted score
  per spec (genre 35% / mood tags 45% / era 20%), keeps each title's top-8
  neighbors. Validated the ranking makes sense (same-genre/same-era titles
  cluster; cross-era pairs score low).
- **Frontend test page** (`docs/index.html`, D3 force-directed graph, live at
  [mohamedhassan268.github.io/movie-map](https://mohamedhassan268.github.io/movie-map/)):
  landing screen with an Arabic/English origin filter + search-to-select
  (no full map dumped on load — matches the spec's "pick a title" flow),
  click a node to re-center on it, "Show all" / "New search" to reset.
  Titles display in their own origin language automatically (Arabic
  productions in Arabic script, foreign titles like Braveheart in English)
  via a new `tmdb_original_language` field, rather than one global toggle —
  per Mohamed's feedback that mixed-language display is the right behavior
  for the target audience. D3 is vendored locally (no CDN dependency).
  Verified with a headless-browser (Playwright) test: landing/filter/search/
  select/reset all work, correct native-language labels, zero console
  errors — see screenshots taken during that session.

- Mood/theme vocabulary approved by Mohamed:
  [mood-tags-vocabulary.md](mood-tags-vocabulary.md) (37 tags).
- **TMDB enrichment** (`scraper/tmdb_enrich.py`): non-destructive merge,
  matches by title+year. 0/19 matches on the 2026 sample (too recent/
  unreleased to be in TMDB yet — expected), 3/20 on the 1995 sample — all 3
  matches were Hollywood films (Braveheart, Strange Days, The Immortals)
  that screened in Egyptian cinemas that year, not native Arabic productions.
  Confirms TMDB helps for foreign titles shown locally but doesn't cover
  genuinely Arabic content — Elcinema remains the primary source.
- **Mood tagging** — went with the free rule-based tagger
  (`ai_tagging/rule_tag_moods.py`) instead of the Claude Batch API, since an
  Anthropic API key (separate billing from a claude.ai subscription) wasn't
  set up. Maps genre + an Arabic keyword scan over the synopsis to vocabulary
  tags. Caught and fixed a real bug during validation: naive substring
  matching false-positived "جن" (jinn) inside "السجن" (the prison) into a
  spurious "supernatural & horror" tag — fixed with a custom word-boundary
  regex that accounts for Arabic's attached "ال" (the) prefix, which plain
  `\b` doesn't handle. Validated result: 15/19 and 16/20 titles tagged.
  `ai_tagging/tag_moods.py` (Claude Batch API, `claude-haiku-4-5`, ~$1-2 for
  2000 titles) is built and ready to swap in if a budget becomes available —
  same input/output shape as the rule-based tagger.
- Project now under git, pushed to
  [github.com/Mohamedhassan268/movie-map](https://github.com/Mohamedhassan268/movie-map)
  (public — needed a repo URL for the TMDB API key application).

- `scraper/scrape.py` pulls listing + detail pages from Elcinema (English +
  Arabic versions) and writes JSON records matching the spec's schema.
- Confirmed against `elcinema.com/robots.txt` — generic user-agents are
  allowed (`Allow: /`), no crawl-delay restriction for non-bingbot UAs. Kept
  the spec's 1.5s delay between requests as a courtesy anyway.
- Ran against the Egypt country listing (`--country eg --limit 20`): 19/20
  titles scraped successfully (1 genuine 404 from the listing). Retries added
  for transient connection drops (see `HOW_TO_RUN.md`).
- Known gaps in scraped data (expected — many sampled titles are unreleased
  2026 titles with incomplete listings): missing `synopsis_ar` (5/19),
  missing `genres` (4/19), missing `title_en` (5/19). Cast is capped at the
  first ~6 names shown on the detail page (full cast lives at a separate
  `/work/ID/cast` page, not yet scraped).
- Sample output: `scraper/output/sample.json` (not reviewed/published data —
  per the schema, nothing here is "approved" yet).
- Generalized `--country` to `--listing` (any `/en/index/work/<path>/` index,
  e.g. `release_year/1995`) and pulled a second sample for era/genre variety:
  `scraper/output/1995_sample.json`, 20/20 titles scraped, spanning Drama,
  Crime, Action, History, War, Comedy, Family, Fantasy, Musical.
- Drafted a starter controlled vocabulary for mood/theme tags:
  [mood-tags-vocabulary.md](mood-tags-vocabulary.md) — **not yet approved**,
  needs your review before the AI tagging script locks it in.

## Build order checklist
(from [arabic-movie-map-project-spec.md](arabic-movie-map-project-spec.md) §5)

- [x] Scraper — pull clean data for a small sample (~20 titles) from Elcinema
- [ ] Data schema + storage — lock JSON shape
- [x] AI tagging (rule-based, free) — validated on both samples
- [ ] Human review flow — not yet built
- [x] Similarity engine — validated on the small sample
- [x] Frontend graph prototype — wired to small sample dataset, live on GitHub Pages
- [ ] Scale scraper to full 500–2000+ titles
- [ ] Deploy (proper — current GitHub Pages is a test deployment, not final hosting)

## Open items to decide later
- Mood/theme tag vocabulary — draft exists ([mood-tags-vocabulary.md](mood-tags-vocabulary.md)), needs review/edit.
- Final similarity weights (start: genre 35%, mood tags 45%, era 20%).
- Whether friends other than Mohamed get a way to submit/edit titles, or it stays
  single-maintainer.
