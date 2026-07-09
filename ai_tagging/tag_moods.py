"""Batch mood/theme tagging for scraped titles.

Reads a scraped (optionally TMDB-enriched) JSON file, submits one Batch API
request per title asking Claude to pick mood/theme tags strictly from the
controlled vocabulary in ../mood-tags-vocabulary.md, and writes the results
into each record's `mood_tags.ai_suggested`.

Uses the Anthropic Message Batches API (50% cheaper than live calls, suited to
this one-time offline enrichment step). Requires ANTHROPIC_API_KEY.

Usage:
    python tag_moods.py --in ../scraper/output/sample.json --out output/sample.tagged.json
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

MODEL = "claude-haiku-4-5"
VOCAB_PATH = Path(__file__).parent.parent / "mood-tags-vocabulary.md"


def load_vocabulary():
    text = VOCAB_PATH.read_text(encoding="utf-8")
    sections = text.split("## ")
    tags = []
    for section in sections:
        if section.startswith("Open questions"):
            continue
        for line in section.splitlines():
            m = re.match(r"^- (.+)$", line.strip())
            if m:
                tags.append(m.group(1).strip())
    return tags


def build_request(record, vocabulary):
    title = record.get("title_en") or record.get("title_ar")
    synopsis = record.get("synopsis_ar") or record.get("tmdb_overview_en") or ""
    genres = record.get("genres") or record.get("tmdb_genres") or []

    prompt = (
        f"Title: {title}\n"
        f"Genres: {', '.join(genres) if genres else '(none)'}\n"
        f"Synopsis: {synopsis if synopsis else '(none available)'}\n\n"
        "Pick 2-5 mood/theme tags that best describe this title, choosing "
        "ONLY from the controlled vocabulary list. Do not invent new tags."
    )

    schema = {
        "type": "object",
        "properties": {
            "tags": {
                "type": "array",
                "items": {"type": "string", "enum": vocabulary},
                "minItems": 1,
                "maxItems": 5,
            }
        },
        "required": ["tags"],
        "additionalProperties": False,
    }

    return Request(
        custom_id=record["id"],
        params=MessageCreateParamsNonStreaming(
            model=MODEL,
            max_tokens=300,
            output_config={"format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": prompt}],
        ),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="infile", required=True, help="Input scraped JSON")
    parser.add_argument("--out", dest="outfile", required=True, help="Output tagged JSON")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ANTHROPIC_API_KEY is not set. Get a key at "
            "https://console.anthropic.com/settings/keys and set it as an "
            "environment variable, e.g.:\n"
            "  export ANTHROPIC_API_KEY=your_key_here   (bash)\n"
            "  $env:ANTHROPIC_API_KEY = 'your_key_here'  (PowerShell)",
            file=sys.stderr,
        )
        sys.exit(1)

    vocabulary = load_vocabulary()
    print(f"Loaded {len(vocabulary)} tags from {VOCAB_PATH.name}")

    with open(args.infile, encoding="utf-8") as f:
        records = json.load(f)

    client = anthropic.Anthropic()
    requests = [build_request(r, vocabulary) for r in records]

    print(f"Submitting batch of {len(requests)} requests using {MODEL} ...")
    batch = client.messages.batches.create(requests=requests)
    print(f"Batch ID: {batch.id}")

    while True:
        batch = client.messages.batches.retrieve(batch.id)
        if batch.processing_status == "ended":
            break
        print(f"  status: {batch.processing_status} ({batch.request_counts})")
        time.sleep(15)

    print(f"Batch complete. Succeeded: {batch.request_counts.succeeded}, "
          f"errored: {batch.request_counts.errored}")

    tags_by_id = {}
    for result in client.messages.batches.results(batch.id):
        if result.result.type == "succeeded":
            msg = result.result.message
            text = next((b.text for b in msg.content if b.type == "text"), None)
            if text:
                tags_by_id[result.custom_id] = json.loads(text).get("tags", [])
        else:
            print(f"  [{result.custom_id}] {result.result.type}")

    for record in records:
        suggested = tags_by_id.get(record["id"], [])
        record.setdefault("mood_tags", {"ai_suggested": [], "approved": []})
        record["mood_tags"]["ai_suggested"] = suggested

    with open(args.outfile, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(records)} tagged records to {args.outfile}")


if __name__ == "__main__":
    main()
