"""TMDB Discover-based Egyptian movie scraper.

Pulls Egyptian movies directly from TMDB's /discover/movie endpoint (origin
country EG), year by year, fetching both Arabic and English localizations so
each record already has the tmdb_* fields populated -- no separate
tmdb_enrich.py pass needed. Produces records in the same schema as
scrape.py so rule_tag_moods.py and compute_similarity.py work unchanged.

Requires a free TMDB API key: https://www.themoviedb.org/settings/api
Set it as the TMDB_API_KEY environment variable before running.

Usage:
    python tmdb_discover.py --from-year 1930 --to-year 2026 --out output/egypt_movies.json
"""

import argparse
import json
import os
import sys
import time
from datetime import date

import requests
import truststore

truststore.inject_into_ssl()

# Windows consoles default to cp1252, which can't print Arabic titles.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

TMDB_BASE = "https://api.themoviedb.org/3"
DELAY_SECONDS = 0.25


def decade_of(year):
    if not year:
        return None
    return f"{(year // 10) * 10}s"


def fetch_genre_map(session, api_key):
    resp = session.get(
        f"{TMDB_BASE}/genre/movie/list",
        params={"api_key": api_key, "language": "en"},
        timeout=20,
    )
    resp.raise_for_status()
    return {g["id"]: g["name"] for g in resp.json().get("genres", [])}


def discover_page(session, api_key, year, page, language):
    params = {
        "api_key": api_key,
        "with_origin_country": "EG",
        "primary_release_year": year,
        "include_adult": "false",
        "sort_by": "primary_release_date.asc",
        "page": page,
        "language": language,
    }
    resp = session.get(f"{TMDB_BASE}/discover/movie", params=params, timeout=20)
    resp.raise_for_status()
    time.sleep(DELAY_SECONDS)
    return resp.json()


def discover_year(session, api_key, year, language):
    """Fetch all pages of Egyptian movies for a given year in one language."""
    results = {}
    data = discover_page(session, api_key, year, 1, language)
    total_pages = data.get("total_pages", 1)
    for r in data.get("results", []):
        results[r["id"]] = r
    for page in range(2, total_pages + 1):
        data = discover_page(session, api_key, year, page, language)
        for r in data.get("results", []):
            results[r["id"]] = r
    return results


def build_record(tmdb_id, ar_result, en_result, genre_map):
    ar_result = ar_result or {}
    en_result = en_result or {}

    release_date = en_result.get("release_date") or ar_result.get("release_date") or ""
    year = int(release_date[:4]) if release_date[:4].isdigit() else None

    genre_ids = en_result.get("genre_ids") or ar_result.get("genre_ids") or []
    genres = [genre_map[g] for g in genre_ids if g in genre_map] or None

    poster_path = en_result.get("poster_path") or ar_result.get("poster_path")
    poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None
    backdrop_path = en_result.get("backdrop_path") or ar_result.get("backdrop_path")
    vote_average = en_result.get("vote_average") or ar_result.get("vote_average")

    return {
        "id": str(tmdb_id),
        "title_ar": ar_result.get("title") or None,
        "title_en": en_result.get("title") or en_result.get("original_title") or None,
        "type": "movie",
        "year": year,
        "decade": decade_of(year),
        "genres": genres,
        "cast": None,
        "director": None,
        "synopsis_ar": ar_result.get("overview") or None,
        "poster_url": poster_url,
        "backdrop_path": backdrop_path,
        "vote_average": vote_average or None,
        "elcinema_url": f"https://www.themoviedb.org/movie/{tmdb_id}",
        "mood_tags": {"ai_suggested": [], "approved": []},
        "scraped_at": date.today().isoformat(),
        "reviewed": False,
        "tmdb_id": tmdb_id,
        "tmdb_genres": genres,
        "tmdb_keywords": None,
        "tmdb_overview_en": en_result.get("overview") or None,
        "tmdb_original_language": en_result.get("original_language")
        or ar_result.get("original_language")
        or None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-year", type=int, required=True)
    parser.add_argument("--to-year", type=int, required=True)
    parser.add_argument("--out", default="output/egypt_movies.json", help="Output JSON path")
    args = parser.parse_args()

    api_key = os.environ.get("TMDB_API_KEY")
    if not api_key:
        print(
            "TMDB_API_KEY is not set. Get a free key at "
            "https://www.themoviedb.org/settings/api and set it as an "
            "environment variable, e.g.:\n"
            "  export TMDB_API_KEY=your_key_here   (bash)\n"
            "  $env:TMDB_API_KEY = 'your_key_here'  (PowerShell)",
            file=sys.stderr,
        )
        sys.exit(1)

    session = requests.Session()
    genre_map = fetch_genre_map(session, api_key)

    all_records = {}
    for year in range(args.from_year, args.to_year + 1):
        print(f"Year {year} ...")
        ar_results = discover_year(session, api_key, year, "ar")
        en_results = discover_year(session, api_key, year, "en-US")
        ids = set(ar_results) | set(en_results)
        for tmdb_id in ids:
            record = build_record(
                tmdb_id, ar_results.get(tmdb_id), en_results.get(tmdb_id), genre_map
            )
            all_records[tmdb_id] = record
        print(f"  {len(ids)} titles (running total: {len(all_records)})")

    records = list(all_records.values())
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(records)} records to {args.out}")


if __name__ == "__main__":
    main()
