# Arabic Movie & Show Map — Project Spec

A DIY recommendation-map website for Arabic movies and TV shows, built by Mohamed and friends.

## 1. What it does

You (or a friend) pick a movie/show you like. The site shows it as a center node on an
interactive graph, surrounded by other Arabic titles that are similar — based on genre,
era, and mood/theme. Click any connected title to re-center the map on it and keep exploring.
A searchable list/grid view is available as a fallback for quick lookups or filtering.

## 2. Decisions locked in

| Question | Decision |
|---|---|
| Data source | Scrape Elcinema (Arabic movie/show database) |
| Scale | Broad set, 500–2000+ titles, grown over time |
| Update cadence | Periodic re-scrapes / additions, not a one-time snapshot |
| Similarity factors | Genre & tags, release era/decade, mood/theme |
| Mood/theme tags | AI-suggested (Claude reads the synopsis) → human reviewed & edited |
| Visualization | Interactive node-graph (main view) + list/grid (fallback) |
| Hosting | Shared web app with a link (Vercel-style) |
| Language | Bilingual — Arabic/English toggle |

## 3. Data schema (per title)

```json
{
  "id": "unique-slug-or-elcinema-id",
  "title_ar": "اسم الفيلم",
  "title_en": "Transliterated/English title",
  "type": "movie | series",
  "year": 2019,
  "decade": "2010s",
  "genres": ["drama", "comedy"],
  "cast": ["Actor 1", "Actor 2"],
  "director": "Director name",
  "synopsis_ar": "...",
  "poster_url": "...",
  "elcinema_url": "...",
  "mood_tags": {
    "ai_suggested": ["family drama", "redemption"],
    "approved": ["family drama"]
  },
  "scraped_at": "2026-07-09",
  "reviewed": true
}
```

Keep `ai_suggested` and `approved` separate so nothing goes live unreviewed, and so you can
re-run the AI tagger later without losing prior human edits.

## 4. Pipeline stages

1. **Scraper** (Python, e.g. `requests` + `BeautifulSoup`, or `Scrapy` at this scale)
   - Check `robots.txt` first; only scrape allowed paths.
   - Rate-limit requests (e.g. 1–2 seconds between pages) — this is a shared courtesy for
     small sites and also reduces the chance of getting IP-blocked.
   - Save raw output as JSON/SQLite, keyed by a stable ID (Elcinema's own ID if available).

2. **AI tagging** (Claude API, batch mode)
   - Feed each synopsis + genre + cast to Claude, ask for a short list of candidate mood/theme
     tags from a controlled vocabulary you define (keeps tags consistent instead of infinite
     one-off phrases).
   - Store as `ai_suggested`, not directly published.

3. **Human review**
   - A lightweight review screen (could be as simple as a spreadsheet or a tiny local tool)
     where you and friends approve/edit tags per title before they count toward similarity.

4. **Published dataset**
   - The reviewed, "clean" JSON that the live site actually reads. This is what gets
     committed/deployed — the live site itself doesn't scrape or call the AI at request time.

5. **Similarity engine** (offline, re-run whenever the dataset changes)
   - Compute a weighted similarity score between every pair of titles:
     - genre overlap (Jaccard or weighted overlap)
     - era/decade proximity
     - mood/theme tag overlap
   - Example starting weights (tune later): genre 35%, mood tags 45%, era 20%.
   - For each title, keep only its top ~10–15 nearest neighbors — this is what the graph
     actually renders, not the full pairwise matrix.

6. **Frontend**
   - Graph view: center node = selected title, neighbor nodes = precomputed similar titles,
     click to re-center. Library suggestion: D3.js force-directed graph or Cytoscape.js.
   - List/grid view: searchable, filterable by genre/era/tag, for quick lookup.
   - Bilingual: simple language toggle switching `title_ar`/`title_en` and UI strings.

7. **Hosting**
   - Static frontend + the published JSON dataset, deployed on Vercel (or similar).
   - No live backend needed for browsing — the site just reads the pre-built dataset.
   - When you add new titles later, you re-run steps 1–5 locally and redeploy.

## 5. Suggested build order

1. Scraper → confirm you can reliably pull clean data for a small sample (~20 titles) first.
2. Data schema + storage → lock the JSON shape before scaling up scraping.
3. AI tagging + review flow → test on the same small sample.
4. Similarity engine → validate the weighting "feels right" on the small sample.
5. Frontend graph prototype → wire it to the small sample dataset.
6. Scale the scraper up to the full 500–2000+ titles.
7. Deploy.

Building and validating on a small sample first avoids re-doing work across 2000 titles if
something in the schema or weighting needs to change.

## 6. Open items to decide later

- Exact controlled vocabulary for mood/theme tags (a fixed list keeps things consistent).
- Final similarity weights (start with the example above, tune after seeing real results).
- Whether friends other than you get a way to submit/edit titles, or it stays single-maintainer.
