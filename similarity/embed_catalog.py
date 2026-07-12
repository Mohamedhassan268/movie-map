"""Offline text embeddings for the catalog's plot/theme similarity signal.

For each title, embeds its synopsis (Arabic preferred, English overview as
fallback) with Google's free-tier Gemini embedding API. Vectors are cached to
disk keyed by title id, so reruns after a catalog update only embed
new/changed titles. compute_similarity.py reads this cache to add a semantic
similarity term alongside genre/mood/era.

Usage:
    export GEMINI_API_KEY=...
    python embed_catalog.py --in ../docs/data.json --cache .embeddings_cache.json

Safe to interrupt/rerun: the cache is written to disk after every batch (not
just at the end), and rate-limit (429) errors are retried with backoff
instead of killing the run.
"""

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import truststore

# On Windows machines with antivirus TLS inspection (e.g. Avast), trust the
# OS certificate store instead of failing SSL verification - see
# scraper/scrape.py, which hits the same issue.
truststore.inject_into_ssl()

# gemini-embedding-001 is the stable model available on the free tier (a
# ListModels check found text-embedding-004 isn't accessible to this key).
# It also has no synchronous batch method - only embedContent - so titles
# are embedded one call each, run concurrently.
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"
BATCH_SIZE = 40
CONCURRENCY = 3
OUTPUT_DIMENSIONALITY = 256
MAX_RETRIES = 6


def text_of(record):
    return record.get("synopsis_ar") or record.get("tmdb_overview_en") or ""


def embed_one(api_key, text):
    body = json.dumps({
        "content": {"parts": [{"text": text[:2000]}]},
        "outputDimensionality": OUTPUT_DIMENSIONALITY,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{GEMINI_URL}?key={api_key}",
        data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )
    delay = 5
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.load(resp)
            return data["embedding"]["values"]
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < MAX_RETRIES - 1:
                print(f"  rate limited, retrying in {delay}s...")
                time.sleep(delay)
                delay = min(delay * 2, 60)
                continue
            raise


def embed_batch(api_key, texts):
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        return list(pool.map(lambda t: embed_one(api_key, t), texts))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="infile", required=True)
    parser.add_argument("--cache", dest="cachefile", default=".embeddings_cache.json")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("Set GEMINI_API_KEY first.")

    with open(args.infile, encoding="utf-8") as f:
        records = json.load(f)

    cache = {}
    if os.path.exists(args.cachefile):
        with open(args.cachefile, encoding="utf-8") as f:
            cache = json.load(f)

    todo = [
        (str(r["id"]), text_of(r))
        for r in records
        if text_of(r) and str(r["id"]) not in cache
    ]

    embedded = 0
    for i in range(0, len(todo), BATCH_SIZE):
        chunk = todo[i:i + BATCH_SIZE]
        vectors = embed_batch(api_key, [t for _, t in chunk])
        for (title_id, _), vec in zip(chunk, vectors):
            cache[title_id] = vec
        embedded += len(chunk)
        with open(args.cachefile, "w", encoding="utf-8") as f:
            json.dump(cache, f)
        print(f"Embedded {embedded}/{len(todo)}... (saved)")
        time.sleep(2)  # stay well under the free-tier rate limit

    print(f"Cache now has {len(cache)} vectors ({embedded} newly embedded). "
          f"Wrote {args.cachefile}")


if __name__ == "__main__":
    main()
