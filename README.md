# authors-db

This project builds a database of book authors from public data.

## Purpose

The input is a CSV file with 500 seed names. The pipeline finds each author in Wikidata. Later, it will add the works from Open Library. The result is a DuckDB database. The database keeps the evidence for each decision.

## Status

| Step | State |
|---|---|
| Normalization of seed names | Done. 19 tests. |
| Search for candidates in Wikidata | Done. |
| Score for each candidate | Done. The thresholds are not fixed. |
| Storage layers `raw_*` and `stg_seed_normalized` | Done. 4 tests. |
| Match status, Open Library, final tables, export | Not built. |
| Command `make all` | Not built. |

## Requirements

- Python 3.11 or later.
- [uv](https://docs.astral.sh/uv/) as the package manager.
- Network access to the Wikidata API for the first run.

## Installation

1. Install `uv`.
2. Clone the repository.
3. Run `uv sync`.

## Commands

Warning: Do not use fewer than 0.4 seconds between two requests. Wikidata returned HTTP 429 at 0.2 seconds with 8 threads. The client in `src/authors_db/http.py` already uses the safe values.

1. Run the tests: `uv run pytest`.
2. Check the code style: `uv run ruff check .`
3. Show the scores for one name: `uv run python scripts/explore_scoring.py "Mark Twain"`.
4. Score the full seed file: `uv run python scripts/score_seed.py scores.tsv`.
5. Check the documents: `uv run python scripts/check_ste.py`.

Note: The first run of step 4 takes more than 5 minutes. The client saves each response in `data/cache/`. Later runs read the cache.

## Storage layers

The DuckDB database has one prefix for each layer. Each table has the column `run_id`. Each step uses `CREATE OR REPLACE`, so the user can run a step again.

| Layer | Prefix | Content |
|---|---|---|
| Raw | `raw_` | The data as it arrives. No change. |
| Staging | `stg_` | Parsed, normalized, and scored data. |
| Final | none | The tables `authors`, `author_works`, and `field_provenance`. |

## Glossary

The documents use one term for each concept.

| Term | Meaning |
|---|---|
| seed name | A value of `author_name` in `authors_seed.csv`. We never change it. |
| candidate | A human in Wikidata that can be the author of a seed name. |
| score | A number from 0 to 100 for one candidate. A higher number means a better match. |
| margin | The score of the best candidate minus the score of the second candidate. |
| match status | One of `matched`, `ambiguous`, or `not_found`. |
| pseudonym | A name that an author uses in place of the real name. |
| cache | The JSON files in `data/cache/` that hold the raw API responses. |

## Note on the style of the text

The text follows the rules of ASD-STE100 Simplified Technical English for technical text. We did not validate the vocabulary against the official dictionary. We did not use a certified tool. The script `scripts/check_ste.py` checks only the sentence length, the `-ing` words, the contractions, the phrasal verbs, and the paragraph length. The text is not certified as ASD-STE100.

## Documents

- `docs/DECISIONS.md` gives the technical decisions.
- `docs/QUALITY.md` gives the quality figures, the limits, and the doubtful cases.
- `ai-usage/` is a literal record of the use of AI. It does not follow these rules.
