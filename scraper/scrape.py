"""Small-sample Elcinema scraper.

Scrapes a handful of titles from an Elcinema country listing page, then fetches
each title's English detail page (/en/work/ID/) and Arabic detail page
(/work/ID/) to build one JSON record per title, matching the schema in
../arabic-movie-map-project-spec.md.

Usage:
    python scrape.py --listing country/eg --limit 20 --out output/sample.json
    python scrape.py --listing release_year/1995 --limit 20 --out output/1995.json
"""

import argparse
import json
import re
import ssl
import time
from datetime import date

import requests
import truststore
from bs4 import BeautifulSoup

# Use the OS certificate store (not just the bundled certifi list) so this
# works on machines where local antivirus/TLS-inspection software (e.g. Avast)
# injects its own root CA into Windows' trust store.
truststore.inject_into_ssl()

BASE = "https://elcinema.com"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
DELAY_SECONDS = 1.5


def fetch(session, url, retries=3):
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
            resp.raise_for_status()
            time.sleep(DELAY_SECONDS)
            return resp.text
        except requests.exceptions.ConnectionError:
            if attempt == retries:
                raise
            time.sleep(DELAY_SECONDS * attempt)


def get_listing_ids(session, listing_path, limit):
    url = f"{BASE}/en/index/work/{listing_path}/"
    html = fetch(session, url)
    soup = BeautifulSoup(html, "html.parser")
    ids = []
    seen = set()
    for a in soup.select('a[href^="/en/work/"]'):
        m = re.match(r"^/en/work/(\d+)/$", a["href"])
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            ids.append(m.group(1))
        if len(ids) >= limit:
            break
    return ids


def decade_of(year):
    if not year:
        return None
    return f"{(year // 10) * 10}s"


def extract_synopsis(soup):
    """Synopsis paragraphs truncate with a '...read more' link followed by a
    hidden <span class="hide"> holding the rest of the text; strip the link
    and join the remaining text so we get the full synopsis."""
    p = soup.select_one("div.columns.small-12.medium-9.large-9 > p")
    if not p:
        return None
    read_more = p.select_one("#read-more")
    if read_more:
        read_more.decompose()
    text = re.sub(r"\s+", " ", p.get_text(separator=" ", strip=True))
    return text or None


def parse_detail(html, lang):
    """Parse a work detail page. `lang` is 'en' or 'ar', used to pick which
    fields this pass is responsible for (title/synopsis are language-specific;
    everything else is taken from the English pass)."""
    soup = BeautifulSoup(html, "html.parser")
    data = {}

    h1 = soup.select_one("div.panel.jumbo h1")
    if h1:
        spans = h1.select("span")
        if lang == "en":
            ltr = h1.select_one('span[dir="ltr"]')
            data["title_en"] = (ltr.get_text(strip=True) if ltr else None) or None
            year_span = spans[1].get_text(strip=True) if len(spans) > 1 else ""
            m = re.search(r"(\d{4})", year_span)
            data["year"] = int(m.group(1)) if m else None
        else:
            rtl = h1.select_one('span[dir="rtl"]')
            data["title_ar"] = (rtl.get_text(strip=True) if rtl else None) or None

    if lang == "en":
        cat_a = soup.select_one('ul.list-separator a[href*="/index/work/category/"]')
        data["type"] = "series" if cat_a and "series" in cat_a.get_text(strip=True).lower() else "movie"

        poster_img = soup.select_one("ul.button-group-vertical img")
        data["poster_url"] = poster_img["src"] if poster_img else None

        genres = [
            a.get_text(strip=True)
            for a in soup.select('ul#jump-here-genre a[href*="/index/work/genre/"]')
        ]
        data["genres"] = genres or None

        director_li = soup.find("li", string="Director:")
        if director_li:
            sibling = director_li.find_next_sibling("li")
            data["director"] = sibling.select_one("a").get_text(strip=True) if sibling and sibling.select_one("a") else None
        else:
            data["director"] = None

        cast_header = soup.find("li", string="Cast:")
        cast = []
        if cast_header:
            for li in cast_header.find_next_siblings("li"):
                a = li.select_one("a")
                if not a or "(more)" in li.get_text():
                    continue
                cast.append(a.get_text(strip=True))
        data["cast"] = cast or None

        data["synopsis_en"] = extract_synopsis(soup)
    else:
        data["synopsis_ar"] = extract_synopsis(soup)

    return data


def scrape_title(session, work_id):
    en_html = fetch(session, f"{BASE}/en/work/{work_id}/")
    en_data = parse_detail(en_html, "en")

    ar_html = fetch(session, f"{BASE}/work/{work_id}/")
    ar_data = parse_detail(ar_html, "ar")

    record = {
        "id": work_id,
        "title_ar": ar_data.get("title_ar"),
        "title_en": en_data.get("title_en"),
        "type": en_data.get("type"),
        "year": en_data.get("year"),
        "decade": decade_of(en_data.get("year")),
        "genres": en_data.get("genres"),
        "cast": en_data.get("cast"),
        "director": en_data.get("director"),
        "synopsis_ar": ar_data.get("synopsis_ar"),
        "poster_url": en_data.get("poster_url"),
        "elcinema_url": f"{BASE}/en/work/{work_id}/",
        "mood_tags": {"ai_suggested": [], "approved": []},
        "scraped_at": date.today().isoformat(),
        "reviewed": False,
    }
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--listing",
        default="country/eg",
        help="Elcinema index path under /en/index/work/, e.g. 'country/eg' or 'release_year/1995'",
    )
    parser.add_argument("--limit", type=int, default=20, help="Number of titles to scrape")
    parser.add_argument("--out", default="output/sample.json", help="Output JSON path")
    args = parser.parse_args()

    session = requests.Session()
    ids = get_listing_ids(session, args.listing, args.limit)
    print(f"Found {len(ids)} title IDs from listing '{args.listing}'")

    records = []
    for i, work_id in enumerate(ids, 1):
        print(f"[{i}/{len(ids)}] scraping work/{work_id} ...")
        try:
            records.append(scrape_title(session, work_id))
        except Exception as e:
            print(f"  failed: {e}")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(records)} records to {args.out}")


if __name__ == "__main__":
    main()
