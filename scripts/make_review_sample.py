"""Write a reproducible sample of matches for a human review.

Usage: uv run python scripts/make_review_sample.py
The sample has two strata. The first has 10 rows that the rule matched, chosen with a fixed hash.
The second has the 10 rows that the model resolved with the lowest margin.
The column `correct_human` stays empty for the reviewer.
The columns `agent_verdict` and `agent_note` come from `ai-usage/04-agent-verdicts.csv`.
"""

import csv
from pathlib import Path

import duckdb

from authors_db import config

SEED = 42
RULE_ROWS = 10
HARD_ROWS = 10
OUTPUT = Path("data/output/review_sample.csv")
AGENT_VERDICTS = Path("ai-usage/04-agent-verdicts.csv")
COLUMNS = [
    "stratum",
    "seed_name",
    "qid",
    "wikidata_url",
    "canonical_name",
    "description",
    "birth_year",
    "death_year",
    "match_status",
    "resolved_by",
    "score",
    "margin",
    "open_library_id",
    "open_library_url",
    "open_library_backlink",
    "agent_verdict",
    "agent_note",
    "correct_human",
    "note_human",
]
QUERY = """
    SELECT '{stratum}' AS stratum, a.seed_name, a.qid, 'https://www.wikidata.org/wiki/' || a.qid,
           a.canonical_name, c.description, a.birth_year, a.death_year, a.match_status,
           a.resolved_by, d.chosen_score, ROUND(d.margin, 1), a.open_library_id,
           CASE WHEN a.open_library_id IS NOT NULL
                THEN 'https://openlibrary.org/authors/' || a.open_library_id END,
           a.open_library_backlink, '', '', '', ''
    FROM authors a
    JOIN stg_match_decisions d USING (row_number)
    JOIN stg_wikidata_candidates c ON c.row_number = a.row_number AND c.qid = a.qid
    WHERE a.match_status = 'matched' AND a.duplicate_of IS NULL AND {condition}
    ORDER BY {order}
    LIMIT {limit}
"""


def main() -> None:
    con = duckdb.connect(str(config.DB_PATH), read_only=True)
    rows = []
    for stratum, condition, limit, order in (
        ("rule", "a.resolved_by = 'rule'", RULE_ROWS, f"hash(a.seed_name || '{SEED}')"),
        ("model", "a.resolved_by = 'slm'", HARD_ROWS, "d.margin, a.seed_name"),
    ):
        sql = QUERY.format(stratum=stratum, condition=condition, limit=limit, order=order)
        rows += con.execute(sql).fetchall()
    verdicts = {}
    if AGENT_VERDICTS.exists():
        with AGENT_VERDICTS.open(encoding="utf-8", newline="") as fh:
            verdicts = {r["seed_name"]: r for r in csv.DictReader(fh)}
    agent_columns = (COLUMNS.index("agent_verdict"), COLUMNS.index("agent_note"))
    for index, row in enumerate(rows):
        verdict = verdicts.get(row[1])
        if verdict:
            row = list(row)
            row[agent_columns[0]], row[agent_columns[1]] = (
                verdict["agent_verdict"],
                verdict["agent_note"],
            )
            rows[index] = tuple(row)
    with OUTPUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUTPUT}")


if __name__ == "__main__":
    main()
