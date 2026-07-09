"""Free, rule-based mood/theme tagging (no AI API calls).

Maps each title's genre(s) and a keyword scan over the Arabic synopsis to
tags from the controlled vocabulary in ../mood-tags-vocabulary.md. Deterministic
and free, at the cost of missing nuance an LLM reading the actual story would
catch. Writes results into each record's `mood_tags.ai_suggested` so the
downstream human-review step works the same as with the AI-based tagger
(see tag_moods.py, which does the same job via the Claude Batch API for when
an API budget is available).

Usage:
    python rule_tag_moods.py --in ../scraper/output/sample.json --out output/sample.tagged.json
"""

import argparse
import json
import re

# Approximate Arabic letter block, used to build word-boundary patterns.
# Python's \b doesn't work for Arabic: the definite article "ال" attaches
# directly to the following word with no space, so there's no \w/\W
# transition at the point a bare \b keyword needs one.
_ARABIC_LETTERS = "ء-ي"

GENRE_TAGS = {
    "comedy": ["feel-good", "slapstick comedy"],
    "drama": ["family drama", "moral dilemma"],
    "crime": ["crime & heist"],
    "action": ["underdog"],
    "thriller": ["mystery & suspense"],
    "mystery": ["mystery & suspense"],
    "horror": ["supernatural & horror"],
    "romance": ["forbidden love"],
    "family": ["family saga"],
    "history": ["historical epic"],
    "war": ["war & conflict"],
    "biography": ["historical epic"],
    "documentary": ["social commentary"],
    "musical": ["musical & celebration"],
    "fantasy": ["folklore & legend"],
    "adventure": ["underdog"],
}

# Arabic substrings -> tag. Best-effort keyword scan over the synopsis;
# intentionally simple (no stemming/NLP) since this is the free-tier tagger.
KEYWORD_TAGS = {
    "انتقام": "revenge",
    "خيانة": "marriage & betrayal",
    "فقر": "poverty & survival",
    "سجن": "prison & captivity",
    "حرب": "war & conflict",
    "فساد": "corruption",
    "هجرة": "immigration & displacement",
    "الطبقية": "class conflict",
    "حنين": "nostalgia",
    "أمل": "hope & resilience",
    "أشباح": "supernatural & horror",
    "جن": "supernatural & horror",
    "زواج": "marriage & betrayal",
    "صداقة": "friendship & loyalty",
}


def tag_record(record):
    tags = []

    genres = (record.get("genres") or []) + (record.get("tmdb_genres") or [])
    for genre in genres:
        for tag in GENRE_TAGS.get(genre.lower(), []):
            if tag not in tags:
                tags.append(tag)

    synopsis = record.get("synopsis_ar") or ""
    for keyword, tag in KEYWORD_TAGS.items():
        # Word-boundary match (allowing an attached "ال" prefix), not a plain
        # substring — "جن" (jinn) is a substring of "السجن" (the prison) and
        # would otherwise false-match.
        pattern = rf"(?<![{_ARABIC_LETTERS}])(?:ال)?{re.escape(keyword)}(?![{_ARABIC_LETTERS}])"
        if re.search(pattern, synopsis) and tag not in tags:
            tags.append(tag)

    return tags[:5]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="infile", required=True, help="Input scraped JSON")
    parser.add_argument("--out", dest="outfile", required=True, help="Output tagged JSON")
    args = parser.parse_args()

    with open(args.infile, encoding="utf-8") as f:
        records = json.load(f)

    tagged = 0
    for record in records:
        tags = tag_record(record)
        record.setdefault("mood_tags", {"ai_suggested": [], "approved": []})
        record["mood_tags"]["ai_suggested"] = tags
        if tags:
            tagged += 1

    with open(args.outfile, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"Tagged {tagged}/{len(records)} records (at least 1 tag). Wrote {args.outfile}")


if __name__ == "__main__":
    main()
