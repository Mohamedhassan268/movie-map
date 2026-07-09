"""Non-destructive TMDB enrichment for already-scraped Elcinema records.

Looks each title up on TMDB (movie and TV search) by title + year, and adds
`tmdb_id`, `tmdb_genres`, `tmdb_keywords`, `tmdb_overview_en` when a confident
match is found. Never touches existing Elcinema-sourced fields.

Requires a free TMDB API key: https://www.themoviedb.org/settings/api
Set it as the TMDB_API_KEY environment variable before running.

Usage:
    python tmdb_enrich.py --in output/sample.json --out output/sample.tmdb.json
"""

import argparse
import json
import os
import re
import sys
import time

import requests
import truststore

truststore.inject_into_ssl()

# Windows consoles default to cp1252, which can't print Arabic titles.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

TMDB_BASE = "https://api.themoviedb.org/3"
DELAY_SECONDS = 0.3


def normalize_title(title):
    return re.sub(r"[^a-z0-9]+", "", title.lower()) if title else ""


def search_tmdb(session, api_key, media_type, query, year):
    params = {"api_key": api_key, "query": query}
    if year:
        params["year" if media_type == "movie" else "first_air_date_year"] = year
    resp = session.get(f"{TMDB_BASE}/search/{media_type}", params=params, timeout=20)
    resp.raise_for_status()
    time.sleep(DELAY_SECONDS)
    return resp.json().get("results", [])


def find_match(session, api_key, record):
    media_type = "tv" if record.get("type") == "series" else "movie"
    query = record.get("title_en") or record.get("title_ar")
    if not query:
        return None, media_type

    results = search_tmdb(session, api_key, media_type, query, record.get("year"))
    if not results:
        return None, media_type

    target_title = normalize_title(query)
    target_year = record.get("year")
    for r in results:
        result_title = r.get("title") or r.get("name") or ""
        result_date = r.get("release_date") or r.get("first_air_date") or ""
        result_year = int(result_date[:4]) if result_date[:4].isdigit() else None
        if normalize_title(result_title) == target_title and (
            not target_year or not result_year or result_year == target_year
        ):
            return r, media_type

    # No confident (title+year) match; don't guess.
    return None, media_type


def fetch_details(session, api_key, media_type, tmdb_id):
    resp = session.get(
        f"{TMDB_BASE}/{media_type}/{tmdb_id}",
        params={"api_key": api_key, "append_to_response": "keywords"},
        timeout=20,
    )
    resp.raise_for_status()
    time.sleep(DELAY_SECONDS)
    return resp.json()


def enrich_record(session, api_key, record):
    match, media_type = find_match(session, api_key, record)
    if not match:
        record.setdefault("tmdb_id", None)
        record.setdefault("tmdb_genres", None)
        record.setdefault("tmdb_keywords", None)
        record.setdefault("tmdb_overview_en", None)
        return record

    details = fetch_details(session, api_key, media_type, match["id"])
    keywords_key = "keywords" if media_type == "movie" else "results"
    keywords = [
        k["name"] for k in details.get("keywords", {}).get(keywords_key, [])
    ]

    record["tmdb_id"] = details.get("id")
    record["tmdb_genres"] = [g["name"] for g in details.get("genres", [])] or None
    record["tmdb_keywords"] = keywords or None
    record["tmdb_overview_en"] = details.get("overview") or None
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="infile", required=True, help="Input Elcinema JSON")
    parser.add_argument("--out", dest="outfile", required=True, help="Output enriched JSON")
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

    with open(args.infile, encoding="utf-8") as f:
        records = json.load(f)

    session = requests.Session()
    matched = 0
    for i, record in enumerate(records, 1):
        title = record.get("title_en") or record.get("title_ar")
        print(f"[{i}/{len(records)}] {title} ...")
        enrich_record(session, api_key, record)
        if record.get("tmdb_id"):
            matched += 1

    with open(args.outfile, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"Matched {matched}/{len(records)} titles on TMDB. Wrote {args.outfile}")


if __name__ == "__main__":
    main()
