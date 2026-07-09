"""Offline similarity engine (spec §4.5).

Merges all tagged sample files, computes a weighted pairwise similarity score
per title (genre overlap 35%, mood-tag overlap 45%, era proximity 20% - the
spec's starting weights, not yet tuned), and keeps each title's top-N nearest
neighbors. Output feeds the frontend graph directly - it never recomputes
similarity at request time.

Usage:
    python compute_similarity.py --in ../ai_tagging/output/sample.tagged.json ../ai_tagging/output/1995_sample.tagged.json --out ../docs/data.json --top-n 8
"""

import argparse
import json

GENRE_WEIGHT = 0.35
MOOD_WEIGHT = 0.45
ERA_WEIGHT = 0.20


def jaccard(a, b):
    a, b = set(x.lower() for x in a), set(x.lower() for x in b)
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def era_proximity(decade_a, decade_b):
    if not decade_a or not decade_b:
        return 0.0
    diff = abs(int(decade_a[:-1]) - int(decade_b[:-1])) // 10
    return 1.0 / (1 + diff)


def genres_of(record):
    return (record.get("genres") or []) + (record.get("tmdb_genres") or [])


def similarity(a, b):
    g = jaccard(genres_of(a), genres_of(b))
    m = jaccard(a.get("mood_tags", {}).get("ai_suggested") or [],
                b.get("mood_tags", {}).get("ai_suggested") or [])
    e = era_proximity(a.get("decade"), b.get("decade"))
    return GENRE_WEIGHT * g + MOOD_WEIGHT * m + ERA_WEIGHT * e


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="infiles", nargs="+", required=True)
    parser.add_argument("--out", dest="outfile", required=True)
    parser.add_argument("--top-n", type=int, default=8)
    args = parser.parse_args()

    records = []
    seen_ids = set()
    for path in args.infiles:
        with open(path, encoding="utf-8") as f:
            for r in json.load(f):
                if r["id"] not in seen_ids:
                    seen_ids.add(r["id"])
                    records.append(r)

    for a in records:
        scored = []
        for b in records:
            if a["id"] == b["id"]:
                continue
            scored.append((similarity(a, b), b["id"]))
        scored.sort(key=lambda x: x[0], reverse=True)
        a["neighbors"] = [
            {"id": bid, "score": round(score, 4)}
            for score, bid in scored[: args.top_n]
            if score > 0
        ]

    with open(args.outfile, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    avg_neighbors = sum(len(r["neighbors"]) for r in records) / len(records)
    print(f"Computed similarity for {len(records)} titles, "
          f"avg {avg_neighbors:.1f} neighbors/title. Wrote {args.outfile}")


if __name__ == "__main__":
    main()
