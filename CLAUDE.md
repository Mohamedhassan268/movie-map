# CLAUDE.md — Arabic Movie & Show Map

DIY recommendation-map website for Arabic movies/TV shows. Pick a title, see it as a
center node on an interactive graph surrounded by similar titles (genre, era, mood/theme).

- Full spec / locked-in decisions: [arabic-movie-map-project-spec.md](arabic-movie-map-project-spec.md)
- Current progress / next steps: [STATUS.md](STATUS.md)
- Commands to run each pipeline stage: [HOW_TO_RUN.md](HOW_TO_RUN.md)
- Controlled mood/theme tag vocabulary: [mood-tags-vocabulary.md](mood-tags-vocabulary.md)
- GitHub: [github.com/Mohamedhassan268/movie-map](https://github.com/Mohamedhassan268/movie-map)
- Live test frontend: [mohamedhassan268.github.io/movie-map](https://mohamedhassan268.github.io/movie-map/)

## Layout
- `scraper/` — Elcinema scraper (`scrape.py`) + TMDB enrichment
  (`tmdb_enrich.py`), outputs to `scraper/output/*.json`.
- `ai_tagging/` — mood/theme tagging: `rule_tag_moods.py` (free, in use) and
  `tag_moods.py` (Claude Batch API, ready but not in use — needs an
  Anthropic API key/budget).
- `similarity/` — `compute_similarity.py`, weighted pairwise similarity +
  top-N neighbors per title, outputs to `docs/data.json`.
- `docs/` — GitHub Pages test frontend (`index.html`, D3 force-directed
  graph, D3 vendored locally in `vendor/`). Served from `/docs` on `master`.
- See [HOW_TO_RUN.md](HOW_TO_RUN.md) for exact commands.
