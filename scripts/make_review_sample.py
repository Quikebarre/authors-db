"""Write a reproducible sample of matches for a human review.

Usage: uv run python scripts/make_review_sample.py
The sample has two strata. The first has 10 rows that the rule matched, chosen with a fixed hash.
The second has the 10 rows that the model resolved with the lowest margin.
The column `correct_human` stays empty for the reviewer.
The columns `agent_verdict` and `agent_note` come from `ai-usage/04-agent-verdicts.csv`.
The columns `correct_human` and `note_human` come from `data/input/human_verdicts.csv`.
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
HUMAN_VERDICTS = Path("data/input/human_verdicts.csv")
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


def read_verdicts(path: Path) -> dict[str, dict[str, str]]:
    """Read a CSV of verdicts. The key is the seed name. Return an empty dict if no file exists."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as fh:
        return {r["seed_name"]: r for r in csv.DictReader(fh)}


def main() -> None:
    con = duckdb.connect(str(config.DB_PATH), read_only=True)
    rows = []
    for stratum, condition, limit, order in (
        ("rule", "a.resolved_by = 'rule'", RULE_ROWS, f"hash(a.seed_name || '{SEED}')"),
        ("model", "a.resolved_by = 'slm'", HARD_ROWS, "d.margin, a.seed_name"),
    ):
        sql = QUERY.format(stratum=stratum, condition=condition, limit=limit, order=order)
        rows += con.execute(sql).fetchall()
    agent = read_verdicts(AGENT_VERDICTS)
    human = read_verdicts(HUMAN_VERDICTS)
    index = {
        name: COLUMNS.index(name)
        for name in ("agent_verdict", "agent_note", "correct_human", "note_human")
    }
    for position, row in enumerate(rows):
        values = list(row)
        for source, names in (
            (agent, ("agent_verdict", "agent_note")),
            (human, ("correct_human", "note_human")),
        ):
            if verdict := source.get(row[1]):
                for name in names:
                    values[index[name]] = verdict[name]
        rows[position] = tuple(values)
    with OUTPUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUTPUT}")


if __name__ == "__main__":
    main()
