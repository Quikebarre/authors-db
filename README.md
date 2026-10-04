# authors-db

This project builds a database of book authors from public data.

## Purpose

The input is a CSV file with 500 seed names. The pipeline finds each author in Wikidata. Later, it will add the works from Open Library. The result is a DuckDB database. The database keeps the evidence for each decision.

## Status

| Step | State |
|---|---|
| Normalization of seed names | Done. |
| Search for candidates in Wikidata, and score for each candidate | Done. |
| Match status, with the model and the dominance rule for `ambiguous` rows | Done. |
| Layers `raw_*`, `stg_*`, and the final table `authors` | Done. |
| Export of `authors` to CSV and Parquet | Done. |
| Open Library, `author_works`, and `field_provenance` | Done. |
| Sample of 20 matches for a human review | Done. The human column is empty. |
| Command `make all` | Done. |

## Requirements

- Python 3.11 or later.
- [uv](https://docs.astral.sh/uv/) as the package manager.
- Network access to the Wikidata API for the first run.
- [Ollama](https://ollama.com/) for the option `--adjudicate`. A GPU with 6 GB of memory is enough.

## Installation

1. Install `uv`.
2. Clone the repository.
3. Run `uv sync`.
4. For the option `--adjudicate`, run `ollama pull qwen2.5:7b-instruct-q4_K_M`.

## Run the pipeline

Warning: Do not use fewer than 0.4 seconds between two requests. Wikidata returned HTTP 429 at 0.2 seconds with 8 threads. The client in `src/authors_db/http.py` already uses the safe value.

1. Run the pipeline: `uv run python -m authors_db run`.
2. To test with a few rows, add `--limit 20`.
3. To use only the cache, add `--offline`. The command then makes no request to Wikidata.
4. To resolve `ambiguous` rows with the model, add `--adjudicate`.
5. Read the result in `data/output/`. Each final table has a CSV file and a Parquet file. The database is `authors.duckdb`.
6. To run the full pipeline from the cache with the model, run `make all`.

Note: The first full run makes more than 2,700 requests and takes more than 20 minutes. The client saves each response in `data/cache/`. The repository contains this cache, so `--offline --adjudicate` gives the same result without a network.

## Other commands

1. Run the tests: `uv run pytest`.
2. Write the sample for the human review: `uv run python scripts/make_review_sample.py`.
3. Check the code style: `uv run ruff check .`
4. Show the scores for one name: `uv run python scripts/explore_scoring.py "Mark Twain"`.
5. Check the documents: `uv run python scripts/check_ste.py`.

## Storage layers

The DuckDB database has one prefix for each layer. Each table has the column `run_id`. Each step uses `CREATE OR REPLACE`, so the user can run a step again.

| Layer | Tables |
|---|---|
| Raw | `raw_seed`, `raw_wikidata_responses`, `raw_openlibrary_responses` |
| Staging | `stg_seed_normalized`, `stg_wikidata_candidates`, `stg_candidate_scores`, `stg_slm_adjudications`, `stg_match_decisions`, `stg_wikidata_labels`, `stg_openlibrary_authors`, `stg_openlibrary_works` |
| Final | `authors`, `author_works`, `field_provenance` |
| Metadata | `pipeline_runs` |

The export contains only the final tables. The `stg_` tables stay in the `.duckdb` file for audit.

## Columns of `authors`

| Column | Meaning |
|---|---|
| `seed_name` | The seed name, as it is in the input file. |
| `is_author` | `false` for a seed name that is not an author, such as `Anonymous`. |
| `invalid_reason` | The reason when `is_author` is `false`. |
| `match_status` | The match status. |
| `qid` | The Wikidata ID. It is empty if the status is not `matched`. |
| `canonical_name` | The `mul` label of the item in Wikidata. |
| `birth_year`, `death_year` | The years from Wikidata, as integers. A year before the common era is negative. |
| `birth_date`, `death_date` | The date from Wikidata. It is set only with day precision. |
| `nationality`, `languages` | The labels of properties P27 and P1412 in Wikidata. |
| `open_library_id` | The selected Open Library record. |
| `open_library_backlink` | `match`, `mismatch`, `absent`, `ol_not_found`, or `no_ol_id`. |
| `open_library_work_count` | The number of works in Open Library. |
| `resolved_by` | `rule`, `slm`, or `dominance_rule`. |
| `confidence` | The score divided by 100. A row resolved by `slm` or `dominance_rule` has a factor of 0.8. It is empty when `qid` is empty. |
| `duplicate_of` | The first seed name that has the same `qid`. |

## Glossary

The documents use one term for each concept.

| Term | Meaning |
|---|---|
| seed name | A value of `author_name` in `authors_seed.csv`. We never change it. |
| candidate | A human in Wikidata that can be the author of a seed name. |
| score | A number from 0 to 100 for one candidate. A higher number means a better match. |
| margin | The score of the best candidate minus the score of the second candidate. |
| match status | One of `matched`, `ambiguous`, `not_found`, or `invalid`. |
| model | The local language model that chooses between candidates. |
| pseudonym | A name that an author uses in place of the real name. |
| back-link | The Wikidata ID that an Open Library record names for the same author. |
| cache | The files in `data/cache/` that hold the raw responses of the APIs and of the model. |

## Note on the style of the text

The text follows the rules of ASD-STE100 Simplified Technical English for technical text. We did not validate the vocabulary against the official dictionary. We did not use a certified tool. The script `scripts/check_ste.py` checks only the sentence length, the `-ing` words, the contractions, the phrasal verbs, and the paragraph length. The text is not certified as ASD-STE100.

## Documents

- `docs/DECISIONS.md` gives the technical decisions.
- `docs/QUALITY.md` gives the quality figures, the limits, and the doubtful cases.
- `ai-usage/` is a literal record of the use of AI. It does not follow these rules.
