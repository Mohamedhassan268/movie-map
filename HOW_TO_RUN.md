# How to Run — Arabic Movie & Show Map

**The live app is TMDB-powered** (see "Frontend" below): search any movie/show,
the map shows TMDB's similar titles. It queries TMDB live through a serverless
proxy, so there's no pre-built dataset to generate for it.

The **Elcinema → tagging → similarity** sections below are the original
Arabic-first offline pipeline. It is **shelved** — kept in the repo, not wired
to the live app. Skip to "Frontend" for the running product.

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

## TMDB Discover scraper (bulk Egyptian catalog, preferred over Elcinema scrape for volume)

```
cd scraper
python -m pip install -r requirements.txt
python tmdb_discover.py --from-year 1930 --to-year 2026 --out output/egypt_movies.json
```

- Requires the same free TMDB API key as below: `export TMDB_API_KEY=...` (bash) /
  `$env:TMDB_API_KEY = '...'` (PowerShell).
- Pulls every movie TMDB has tagged with `with_origin_country=EG` from
  `/discover/movie`, iterating year by year (avoids TMDB's ~500-page/10k-result
  cap per query) and fetching both Arabic and English localizations per title.
- Output already has `tmdb_id`, `tmdb_genres`, `tmdb_overview_en`,
  `tmdb_original_language` populated — **skip the `tmdb_enrich.py` step** for
  this output, it's redundant. `cast`/`director`/`tmdb_keywords` are left
  `null` (not returned by discover; unused by the tagger/similarity steps).
- Feed the output straight into AI tagging below.

## TMDB enrichment (optional, supplements an Elcinema scrape)

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

Two options — currently using the free rule-based tagger; the Claude-based
one is built and ready if/when an API budget is available.

### Rule-based (free, in use now)

```
cd ai_tagging
python rule_tag_moods.py --in ../scraper/output/sample.tmdb.json --out output/sample.tagged.json
```

- No API key, no cost. Maps each title's genre(s) (Elcinema + TMDB) and a
  keyword scan over the Arabic synopsis to tags from the controlled
  vocabulary in [mood-tags-vocabulary.md](mood-tags-vocabulary.md).
- Arabic keyword matching uses a custom word-boundary pattern (plain `\b`
  doesn't work — Arabic's attached definite article "ال" means there's no
  `\w`/`\W` transition where a bare `\b` needs one; substring matching alone
  false-positives, e.g. "جن" inside "السجن" (prison) wrongly matching a
  "supernatural & horror" keyword).
- Deterministic and free, but misses nuance an LLM reading the actual
  synopsis would catch. Validated on both samples: 15/19 and 16/20 titles
  got at least one tag.

### Claude Batch API (higher quality, small cost — not currently used)

```
cd ai_tagging
python -m pip install -r requirements.txt
python tag_moods.py --in ../scraper/output/sample.tmdb.json --out output/sample.tagged.json
```

- Requires an Anthropic API key (separate from a claude.ai subscription) —
  get one at console.anthropic.com/settings/keys with a small credit balance,
  then set `export ANTHROPIC_API_KEY=...` (bash) /
  `$env:ANTHROPIC_API_KEY = '...'` (PowerShell).
- Uses the Message Batches API (async, 50% cheaper than live calls) with
  `claude-haiku-4-5`. Cost for ~2000 titles: roughly $1-2.
- Same input/output shape as the rule-based tagger — writes
  `mood_tags.ai_suggested`; `approved` stays empty until human review.

## Similarity engine

```
cd similarity
python compute_similarity.py --in ../ai_tagging/output/sample.tagged.json ../ai_tagging/output/1995_sample.tagged.json --out ../docs/data.json --top-n 8
```

- No API key, no cost — pure computation over the tagged records.
- Weighted score per the spec's starting weights (genre overlap 35%, mood-tag
  overlap 45%, era proximity 20%, all Jaccard-based) between every pair of
  titles; keeps each title's top `--top-n` neighbors.
- `--in` takes one or more tagged JSON files and merges them (dedup by `id`).
- Output feeds `docs/index.html` directly — the frontend never recomputes
  similarity at request time.

## Frontend (TMDB-live, deploys on Vercel)

The live app. `index.html` (repo root) is a single-file D3 force-directed
graph that searches TMDB and shows each title's TMDB "similar/recommended"
neighbors. It talks to TMDB through `api/tmdb.js`, a serverless proxy that
injects the TMDB key server-side (so the key is never in the page).

### Files
- `index.html` + `vendor/d3.v7.min.js` — the static frontend (D3 vendored
  locally, no CDN).
- `api/tmdb.js` — Vercel serverless function. Whitelists TMDB endpoints
  (search/genres/details/recommendations/similar) and reads the credential
  from an env var: `TMDB_READ_TOKEN` (v4 read token, preferred) or
  `TMDB_API_KEY` (v3 key).

### Deploy on Vercel (one-time)
1. Go to vercel.com, sign in with GitHub, "Add New → Project", import
   `Mohamedhassan268/movie-map`.
2. Framework preset: **Other** (it's a static site + an API function; no
   build step). Leave build/output settings default.
3. Under **Environment Variables**, add `TMDB_READ_TOKEN` = your TMDB v4 API
   Read Access Token (or `TMDB_API_KEY` = the v3 key). This is the secret —
   it lives only in Vercel, never in the repo. Optionally add `ALLOWED_ORIGIN`
   = your deployed site URL (e.g. `https://movie-map.vercel.app`) to lock the
   `/api/tmdb` proxy to your own site so strangers can't burn your TMDB quota;
   leave it unset to allow all origins.
4. Deploy. Vercel serves `index.html` at `/` and the function at
   `/api/tmdb`. Pushes to `master` auto-redeploy.

### Local dev
`vercel dev` (after `npm i -g vercel` and `vercel link`) runs the static site
+ the function together with the env var loaded, at http://localhost:3000.
Keep secrets in `.env.local` (gitignored — see `.env.example` for the list of
vars); `vercel env pull .env.local` fetches them from the project. Never put a
key in a tracked file.

### Behaviour
- Landing: title, tagline, Arabic/English origin filter, one search box —
  nothing else (no pre-populated list). The filter scopes search to TMDB
  `original_language` `ar` vs `en`.
- Type ≥2 chars → live TMDB results dropdown (poster + native-language title +
  year + movie/series badge). Pick one → the map renders that title centered
  with its TMDB neighbors.
- Click a neighbor → re-center on it (live fetch, cached per title). "Back"
  steps to the previous center; "New search" returns to the landing page.
- Each title shows in its own origin language (Arabic-origin → Arabic name,
  foreign → English name), read from TMDB `original_language`.

> The old GitHub Pages demo (`docs/`, the pre-pivot 39-title static version)
> still exists in the repo for reference but is superseded by this app.

## Frontend (dev server)
_TBD once the frontend project is scaffolded._

## Deploy
_TBD once hosting is set up._
