# Status — Arabic Movie & Show Map

Last updated: 2026-07-09

## Current stage
Scraper built and validated on a small sample. Next: AI tagging + review flow.

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
- [ ] AI tagging + human review flow — test on the small sample
- [ ] Similarity engine — validate weighting on the small sample
- [ ] Frontend graph prototype — wire to small sample dataset
- [ ] Scale scraper to full 500–2000+ titles
- [ ] Deploy

## Open items to decide later
- Mood/theme tag vocabulary — draft exists ([mood-tags-vocabulary.md](mood-tags-vocabulary.md)), needs review/edit.
- Final similarity weights (start: genre 35%, mood tags 45%, era 20%).
- Whether friends other than Mohamed get a way to submit/edit titles, or it stays
  single-maintainer.
