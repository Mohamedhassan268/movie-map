# CLAUDE.md — Arabic Movie & Show Map

DIY recommendation-map website for Arabic movies/TV shows. Pick a title, see it as a
center node on an interactive graph surrounded by similar titles (genre, era, mood/theme).

- Full spec / locked-in decisions: [arabic-movie-map-project-spec.md](arabic-movie-map-project-spec.md)
- Current progress / next steps: [STATUS.md](STATUS.md)
- Commands to run each pipeline stage: [HOW_TO_RUN.md](HOW_TO_RUN.md)
- Controlled mood/theme tag vocabulary (draft): [mood-tags-vocabulary.md](mood-tags-vocabulary.md)

## Layout
- `scraper/` — Elcinema scraper (`scrape.py`), outputs to `scraper/output/*.json`.
  See [HOW_TO_RUN.md](HOW_TO_RUN.md) for usage.
