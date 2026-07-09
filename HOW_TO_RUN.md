# How to Run — Arabic Movie & Show Map

This file is filled in incrementally as each pipeline stage
(see [arabic-movie-map-project-spec.md](arabic-movie-map-project-spec.md) §4) is built.

## Scraper

```
cd scraper
python -m pip install -r requirements.txt
python scrape.py --listing country/eg --limit 20 --out output/sample.json
```

- `--listing`: any Elcinema index path under `/en/index/work/` — e.g.
  `country/eg`, `country/lb`, `release_year/1995` — pick which slice of the
  catalog to pull from.
- `--limit`: how many titles to scrape.
- Output is one JSON record per title, matching the schema in the spec (mood
  tags left empty — that's the AI tagging stage).
- Note: on Windows machines with antivirus TLS inspection (e.g. Avast), the
  scraper uses the `truststore` package to trust the OS certificate store
  instead of failing SSL verification.

## TMDB enrichment (optional, supplements the scrape)

```
cd scraper
python tmdb_enrich.py --in output/sample.json --out output/sample.tmdb.json
```

- Requires a free TMDB API key: sign up at themoviedb.org, go to
  **Settings → API**, request a key (choose "Developer"), then set it:
  `export TMDB_API_KEY=...` (bash) / `$env:TMDB_API_KEY = '...'` (PowerShell).
- Looks each title up on TMDB by title + year; adds `tmdb_id`, `tmdb_genres`,
  `tmdb_keywords`, `tmdb_overview_en` when a confident match is found — never
  overwrites Elcinema-sourced fields. Titles with no TMDB match keep those
  fields as `null` (expected for older/niche Arabic TV content).

## AI tagging

```
cd ai_tagging
python -m pip install -r requirements.txt
python tag_moods.py --in ../scraper/output/sample.json --out output/sample.tagged.json
```

- Requires an Anthropic API key: get one at
  console.anthropic.com/settings/keys, then set
  `export ANTHROPIC_API_KEY=...` (bash) / `$env:ANTHROPIC_API_KEY = '...'`
  (PowerShell).
- Uses the Message Batches API (async, 50% cheaper than live calls) with
  `claude-haiku-4-5` — a bounded classification task (pick tags from the fixed
  vocabulary in [mood-tags-vocabulary.md](mood-tags-vocabulary.md)), well
  within Haiku's capability. Cost for ~2000 titles: roughly $1-2.
- Input can be the raw scraper output or the TMDB-enriched version (falls
  back to `tmdb_overview_en`/`tmdb_genres` if Elcinema's `synopsis_ar`/`genres`
  are missing).
- Writes picked tags into each record's `mood_tags.ai_suggested` — `approved`
  stays empty; that's the human review stage (not yet built).
- The script polls the batch every 15s until it completes (usually well under
  an hour for a sample this size).

## Similarity engine
_TBD once the similarity computation is written._

## Frontend (dev server)
_TBD once the frontend project is scaffolded._

## Deploy
_TBD once hosting is set up._
