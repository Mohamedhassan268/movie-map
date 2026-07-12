"""Offline similarity engine (spec §4.5).

Merges all tagged sample files, computes a weighted pairwise similarity score
per title (semantic plot/theme 50%, genre overlap 25%, mood-tag overlap 15%,
era proximity 10% - semantic dominates now that embed_catalog.py supplies a
real plot-understanding signal instead of relying on genre/keyword overlap
alone), and keeps each title's top-N nearest neighbors. Output feeds the
frontend graph directly - it never recomputes similarity at request time.

Usage:
    python compute_similarity.py --in ../ai_tagging/output/sample.tagged.json ../ai_tagging/output/1995_sample.tagged.json --out ../docs/data.json --top-n 8 --embeddings .embeddings_cache.json

Requires numpy (see requirements.txt) to vectorize the semantic similarity
matrix - at ~4,500 titles a pure-Python cosine loop over every pair would be
too slow (~20M pairs x 256-dim dot products).
"""

import argparse
import json

import numpy as np

SEMANTIC_WEIGHT = 0.50
GENRE_WEIGHT = 0.25
MOOD_WEIGHT = 0.15
ERA_WEIGHT = 0.10

# Weights renormalized over whichever signals are actually available for a
# given pair, so a title missing an embedding still gets a sensible score
# from genre/mood/era instead of being silently penalized.
WEIGHTS = {
    "semantic": SEMANTIC_WEIGHT,
    "genre": GENRE_WEIGHT,
    "mood": MOOD_WEIGHT,
    "era": ERA_WEIGHT,
}


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


def semantic_matrix(records, embeddings):
    """Cosine similarity between every pair of titles with an embedding,
    computed as one normalized matrix multiply instead of a Python loop."""
    ids = [str(r["id"]) for r in records]
    dim = len(next(iter(embeddings.values())))
    mat = np.zeros((len(ids), dim), dtype=np.float32)
    has_vec = np.zeros(len(ids), dtype=bool)
    for i, rid in enumerate(ids):
        vec = embeddings.get(rid)
        if vec:
            mat[i] = vec
            has_vec[i] = True
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normalized = mat / norms
    sim = normalized @ normalized.T
    return sim, has_vec


def similarity(a, b, i, j, sim_matrix, has_vec):
    values = {
        "genre": jaccard(genres_of(a), genres_of(b)),
        "mood": jaccard(a.get("mood_tags", {}).get("ai_suggested") or [],
                         b.get("mood_tags", {}).get("ai_suggested") or []),
        "era": era_proximity(a.get("decade"), b.get("decade")),
    }
    if has_vec[i] and has_vec[j]:
        values["semantic"] = float(sim_matrix[i, j])

    used_weight = sum(WEIGHTS[k] for k in values)
    return sum(WEIGHTS[k] * v for k, v in values.items()) / used_weight


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="infiles", nargs="+", required=True)
    parser.add_argument("--out", dest="outfile", required=True)
    parser.add_argument("--top-n", type=int, default=8)
    parser.add_argument("--embeddings", dest="embeddingsfile", default=None,
                         help="Path to embed_catalog.py's cache file (id -> vector). "
                              "Omit to fall back to genre/mood/era only.")
    args = parser.parse_args()

    records = []
    seen_ids = set()
    for path in args.infiles:
        with open(path, encoding="utf-8") as f:
            for r in json.load(f):
                if r["id"] not in seen_ids:
                    seen_ids.add(r["id"])
                    records.append(r)

    embeddings = {}
    if args.embeddingsfile:
        with open(args.embeddingsfile, encoding="utf-8") as f:
            embeddings = json.load(f)

    if embeddings:
        sim_matrix, has_vec = semantic_matrix(records, embeddings)
    else:
        sim_matrix, has_vec = None, [False] * len(records)

    for i, a in enumerate(records):
        scored = []
        for j, b in enumerate(records):
            if a["id"] == b["id"]:
                continue
            scored.append((similarity(a, b, i, j, sim_matrix, has_vec), b["id"]))
        scored.sort(key=lambda x: x[0], reverse=True)
        a["neighbors"] = [
            {"id": bid, "score": round(score, 4)}
            for score, bid in scored[: args.top_n]
            if score > 0
        ]

    with open(args.outfile, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    avg_neighbors = sum(len(r["neighbors"]) for r in records) / len(records)
    with_embeddings = sum(1 for r in records if str(r["id"]) in embeddings)
    print(f"Computed similarity for {len(records)} titles "
          f"({with_embeddings} with semantic embeddings), "
          f"avg {avg_neighbors:.1f} neighbors/title. Wrote {args.outfile}")


if __name__ == "__main__":
    main()
