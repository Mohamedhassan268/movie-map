# CLAUDE.md — Arabic Movie & Show Map

DIY recommendation-map website for Arabic movies/TV shows. Pick a title, see it as a
center node on an interactive graph surrounded by similar titles (genre, era, mood/theme).

- Full spec / locked-in decisions: [arabic-movie-map-project-spec.md](arabic-movie-map-project-spec.md)
- Current progress / next steps: [STATUS.md](STATUS.md)
- Commands to run each pipeline stage: [HOW_TO_RUN.md](HOW_TO_RUN.md)
- Controlled mood/theme tag vocabulary: [mood-tags-vocabulary.md](mood-tags-vocabulary.md)
- GitHub: [github.com/Mohamedhassan268/movie-map](https://github.com/Mohamedhassan268/movie-map)
- Live app: TMDB-powered, deploys on Vercel (URL set once Mohamed connects the repo).
  Old GitHub Pages demo (pre-pivot, 39 titles): [mohamedhassan268.github.io/movie-map](https://mohamedhassan268.github.io/movie-map/)

## Layout
**Live app (TMDB-powered):**
- `index.html` + `vendor/d3.v7.min.js` — the frontend: search TMDB, graph of
  TMDB "similar" titles. Deploys on Vercel.
- `api/tmdb.js` — Vercel serverless proxy hiding the TMDB key (env var).

**Shelved offline pipeline (Arabic-first, not wired to the live app):**
- `scraper/` — Elcinema scraper (`scrape.py`) + TMDB enrichment (`tmdb_enrich.py`).
- `ai_tagging/` — mood/theme tagging (`rule_tag_moods.py`, `tag_moods.py`).
- `similarity/` — `compute_similarity.py` (weighted neighbors → `docs/data.json`).
- `docs/` — the pre-pivot GitHub Pages static demo (39 titles), superseded.

See [HOW_TO_RUN.md](HOW_TO_RUN.md) for exact commands.
