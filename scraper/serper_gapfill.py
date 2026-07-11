"""Gap-fill Egyptian films that TMDB's /discover with_origin_country=EG missed.

Uses Serper (Google search API) to find Wikipedia "List of Egyptian films"
pages, extracts candidate titles from the tables on those pages, then looks
each one up on TMDB (reusing tmdb_enrich.py's search+match logic). Matches
not already present in the tmdb_discover.py output are enriched into the same
record schema and appended.

This is a secondary, best-effort pass -- Wikipedia's list pages are not
uniformly one-page-per-year (some cover a whole decade) and title matching is
looser (no year constraint), so expect lower precision than the discover
scraper.

Requires:
  SERPER_API_KEY  -- https://serper.dev (free tier available)
  TMDB_API_KEY    -- https://www.themoviedb.org/settings/api

Usage:
    python serper_gapfill.py --egypt-file output/egypt_movies.json \
        --from-year 1930 --to-year 2026 --out output/egypt_movies.gapfilled.json
"""

import argparse
import json
import os
import sys
import time
from datetime import date

import requests
import truststore
from bs4 import BeautifulSoup

from tmdb_discover import decade_of
from tmdb_enrich import find_match, normalize_title

truststore.inject_into_ssl()

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

SERPER_URL = "https://google.serper.dev/search"
TMDB_BASE = "https://api.themoviedb.org/3"
DELAY_SECONDS = 0.3
WIKIPEDIA_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def serper_search(session, api_key, query):
    resp = session.post(
        SERPER_URL,
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json={"q": query},
        timeout=20,
    )
    resp.raise_for_status()
    time.sleep(DELAY_SECONDS)
    return resp.json()


def find_wikipedia_list_url(session, api_key, year):
    data = serper_search(session, api_key, f"List of Egyptian films of {year} wikipedia")
    target = f"wikipedia.org/wiki/list_of_egyptian_films_of_{year}".lower()
    for result in data.get("organic", []):
        link = result.get("link", "")
        # Match the per-year page exactly (not "..._of_the_1930s" decade index
        # pages, which list links to per-year pages but have no film table).
        if link.lower().rstrip("/").endswith(target):
            return link
    return None


def extract_titles_from_wikipedia(session, url):
    resp = session.get(url, headers={"User-Agent": WIKIPEDIA_USER_AGENT}, timeout=20)
    resp.raise_for_status()
    time.sleep(DELAY_SECONDS)
    soup = BeautifulSoup(resp.text, "html.parser")

    titles = []
    for table in soup.select("table.wikitable"):
        header_cells = [th.get_text(strip=True).lower() for th in table.select("tr th")]
        title_col = next(
            (i for i, h in enumerate(header_cells) if "title" in h), 0
        )
        for row in table.select("tr"):
            cells = row.find_all("td")
            if len(cells) <= title_col:
                continue
            cell = cells[title_col]
            # Prefer the bold transliterated title over a wikilink (title
            # cells are usually "<i><b>Title</b></i> (English translation)"
            # with no link) or the raw cell text, which would include that
            # parenthetical translation and break TMDB title matching.
            bold = cell.find("b")
            link = cell.find("a")
            if bold:
                text = bold.get_text(strip=True)
            elif link:
                text = link.get_text(strip=True)
            else:
                text = cell.get_text(strip=True)
            if text:
                titles.append(text)
    return titles


def fetch_movie_details(session, api_key, tmdb_id, language):
    resp = session.get(
        f"{TMDB_BASE}/movie/{tmdb_id}",
        params={"api_key": api_key, "language": language},
        timeout=20,
    )
    resp.raise_for_status()
    time.sleep(DELAY_SECONDS)
    return resp.json()


def build_gapfill_record(tmdb_id, ar_details, en_details):
    release_date = en_details.get("release_date") or ar_details.get("release_date") or ""
    year = int(release_date[:4]) if release_date[:4].isdigit() else None
    genres = [g["name"] for g in en_details.get("genres", [])] or None
    poster_path = en_details.get("poster_path") or ar_details.get("poster_path")
    poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None

    return {
        "id": str(tmdb_id),
        "title_ar": ar_details.get("title") or None,
        "title_en": en_details.get("title") or en_details.get("original_title") or None,
        "type": "movie",
        "year": year,
        "decade": decade_of(year),
        "genres": genres,
        "cast": None,
        "director": None,
        "synopsis_ar": ar_details.get("overview") or None,
        "poster_url": poster_url,
        "elcinema_url": f"https://www.themoviedb.org/movie/{tmdb_id}",
        "mood_tags": {"ai_suggested": [], "approved": []},
        "scraped_at": date.today().isoformat(),
        "reviewed": False,
        "tmdb_id": tmdb_id,
        "tmdb_genres": genres,
        "tmdb_keywords": None,
        "tmdb_overview_en": en_details.get("overview") or None,
        "tmdb_original_language": en_details.get("original_language")
        or ar_details.get("original_language")
        or None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--egypt-file", required=True, help="Existing tmdb_discover.py output")
    parser.add_argument("--from-year", type=int, required=True)
    parser.add_argument("--to-year", type=int, required=True)
    parser.add_argument("--out", required=True, help="Output JSON path (existing + gap-filled)")
    args = parser.parse_args()

    serper_key = os.environ.get("SERPER_API_KEY")
    tmdb_key = os.environ.get("TMDB_API_KEY")
    if not serper_key or not tmdb_key:
        print(
            "Both SERPER_API_KEY and TMDB_API_KEY must be set as environment "
            "variables.",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(args.egypt_file, encoding="utf-8") as f:
        existing_records = json.load(f)
    existing_ids = {r["tmdb_id"] for r in existing_records if r.get("tmdb_id")}
    existing_titles = {
        normalize_title(r["title_en"]) for r in existing_records if r.get("title_en")
    } | {normalize_title(r["title_ar"]) for r in existing_records if r.get("title_ar")}

    session = requests.Session()

    seen_wiki_urls = set()
    candidate_titles = set()
    for year in range(args.from_year, args.to_year + 1):
        print(f"Searching Wikipedia list for {year} ...")
        url = find_wikipedia_list_url(session, serper_key, year)
        if not url or url in seen_wiki_urls:
            continue
        seen_wiki_urls.add(url)
        titles = extract_titles_from_wikipedia(session, url)
        print(f"  found {len(titles)} titles on {url}")
        for title in titles:
            if normalize_title(title) not in existing_titles:
                candidate_titles.add(title)

    print(f"{len(candidate_titles)} candidate titles not already in the catalog")

    new_records = []
    for i, title in enumerate(sorted(candidate_titles), 1):
        print(f"[{i}/{len(candidate_titles)}] matching '{title}' on TMDB ...")
        match, media_type = find_match(
            session, tmdb_key, {"title_en": title, "type": "movie"}
        )
        if not match or media_type != "movie":
            continue
        tmdb_id = match["id"]
        if tmdb_id in existing_ids:
            continue
        ar_details = fetch_movie_details(session, tmdb_key, tmdb_id, "ar")
        en_details = fetch_movie_details(session, tmdb_key, tmdb_id, "en-US")
        new_records.append(build_gapfill_record(tmdb_id, ar_details, en_details))
        existing_ids.add(tmdb_id)

    print(f"Matched {len(new_records)} new titles on TMDB")

    merged = existing_records + new_records
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(merged)} total records to {args.out}")


if __name__ == "__main__":
    main()
