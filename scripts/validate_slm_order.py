"""Check the position bias of the model: ask again with the candidates in reverse order.

Usage: uv run python scripts/validate_slm_order.py
The script reads the `ambiguous` rows from the database. It prints the rows where the answer
changes with the order of the candidates.
"""

import duckdb

from authors_db import config, storage
from authors_db.adjudicate import OllamaClient, adjudicate_one


def main() -> None:
    con = duckdb.connect(str(config.DB_PATH), read_only=True)
    evidence = storage.read_ambiguous_evidence(
        con, config.MAX_CANDIDATES_FOR_ADJUDICATION, config.MIN_MARGIN
    )
    original = dict(
        con.execute(
            "SELECT row_number, chosen_qid FROM stg_match_decisions WHERE rule_status = 'ambiguous'"
        ).fetchall()
    )
    client = OllamaClient(config.CACHE_DIR / "ollama")
    same = 0
    for row_number, (seed_name, candidates) in evidence.items():
        reverse = adjudicate_one(client, row_number, seed_name, candidates[::-1])
        if reverse.chosen_qid == original.get(row_number):
            same += 1
        else:
            print(
                f"CHANGED {seed_name}: first={original.get(row_number)} "
                f"reverse={reverse.chosen_qid} ({reverse.reason})"
            )
    print(f"Same answer in both orders: {same} of {len(evidence)}")


if __name__ == "__main__":
    main()
