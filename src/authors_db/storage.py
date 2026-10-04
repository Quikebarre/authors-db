"""DuckDB storage in layers: raw tables, stg tables, and final tables. Each step is idempotent."""

import csv
import gzip
import json
from pathlib import Path

import duckdb
import pandas as pd

from authors_db.normalize import normalize
from authors_db.scoring import ScoredCandidate

RESPONSE_COLUMNS = ["run_id", "cache_key", "url", "params", "retrieved_at", "response"]


def load_seed(path: Path) -> list[str]:
    with path.open(encoding="utf-8", newline="") as fh:
        return [row["author_name"] for row in csv.DictReader(fh)]


def build_raw_seed(con: duckdb.DuckDBPyConnection, run_id: str, seed_path: Path) -> None:
    """Create `raw_seed`. The table has the CSV rows without changes and a row number."""
    names = load_seed(seed_path)
    df = pd.DataFrame(
        {"run_id": run_id, "row_number": range(1, len(names) + 1), "author_name": names}
    )
    con.register("_raw_seed_df", df)
    con.execute("CREATE OR REPLACE TABLE raw_seed AS SELECT * FROM _raw_seed_df")
    con.unregister("_raw_seed_df")


def build_raw_responses(
    con: duckdb.DuckDBPyConnection, run_id: str, table: str, cache_dir: Path
) -> None:
    """Create a table of raw responses. Load the JSON, URL, parameters, and time from the cache."""
    rows = []
    for path in sorted(cache_dir.glob("*.json.gz")) if cache_dir.exists() else []:
        record = json.loads(gzip.decompress(path.read_bytes()))
        rows.append(
            (
                run_id,
                path.name.removesuffix(".json.gz"),
                record["url"],
                json.dumps(record["params"], ensure_ascii=False, sort_keys=True),
                record["retrieved_at"],
                json.dumps(record["response"], ensure_ascii=False),
            )
        )
    df = pd.DataFrame(rows, columns=RESPONSE_COLUMNS).astype(
        {
            "run_id": "string",
            "cache_key": "string",
            "url": "string",
            "params": "string",
            "retrieved_at": "string",
            "response": "string",
        }
    )
    con.register("_raw_resp_df", df)
    con.execute(
        f"CREATE OR REPLACE TABLE {table} AS "  # noqa: S608 - nombre de tabla interno
        "SELECT run_id, cache_key, url, params, CAST(retrieved_at AS TIMESTAMPTZ) AS retrieved_at, "
        "CAST(response AS JSON) AS response FROM _raw_resp_df"
    )
    con.unregister("_raw_resp_df")


def build_stg_seed_normalized(con: duckdb.DuckDBPyConnection, run_id: str) -> None:
    """Create `stg_seed_normalized`. Python normalizes names. SQL marks exact duplicates."""
    rows = []
    for row_number, seed_name in con.execute(
        "SELECT row_number, author_name FROM raw_seed ORDER BY row_number"
    ).fetchall():
        n = normalize(seed_name)
        rows.append(
            (
                run_id,
                row_number,
                seed_name,
                n.clean_name,
                n.match_key,
                not n.is_valid,
                n.invalid_reason,
            )
        )
    df = pd.DataFrame(
        rows,
        columns=[
            "run_id",
            "row_number",
            "seed_name",
            "display_name",
            "match_key",
            "is_invalid",
            "invalid_reason",
        ],
    )
    con.register("_norm_df", df)
    con.execute("""
        CREATE OR REPLACE TABLE stg_seed_normalized AS
        SELECT *,
               CASE WHEN NOT is_invalid AND row_number > MIN(row_number) OVER w
                    THEN FIRST_VALUE(seed_name) OVER w END AS exact_dup_of
        FROM _norm_df
        WINDOW w AS (PARTITION BY match_key ORDER BY row_number
                     ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)
        ORDER BY row_number
    """)
    con.unregister("_norm_df")


def _register_and_create(con: duckdb.DuckDBPyConnection, table: str, df: pd.DataFrame) -> None:
    con.register("_stage_df", df)
    con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM _stage_df")  # noqa: S608
    con.unregister("_stage_df")


def build_stg_candidates_and_scores(
    con: duckdb.DuckDBPyConnection,
    run_id: str,
    scored: dict[int, tuple[str, list[ScoredCandidate]]],
) -> None:
    """Create `stg_wikidata_candidates` and `stg_candidate_scores`.

    The argument maps a row number to the seed name and the ranked candidates.
    """
    cand_rows, score_rows = [], []
    for row_number, (seed_name, ranked) in sorted(scored.items()):
        for rank_number, s in enumerate(ranked, 1):
            c = s.candidate
            cand_rows.append(
                (
                    run_id,
                    row_number,
                    seed_name,
                    c.qid,
                    c.label,
                    c.description,
                    c.names,
                    c.is_writer,
                    c.open_library_id,
                    c.sitelinks,
                    c.birth,
                    c.death,
                    c.found_via,
                    c.via_pseudonym,
                )
            )
            score_rows.append(
                (
                    run_id,
                    row_number,
                    seed_name,
                    c.qid,
                    rank_number,
                    s.score,
                    s.name_similarity,
                    s.best_name,
                    c.is_writer,
                    c.open_library_id is not None,
                    c.sitelinks,
                    s.reason,
                )
            )
    _register_and_create(
        con,
        "stg_wikidata_candidates",
        pd.DataFrame(
            cand_rows,
            columns=[
                "run_id",
                "row_number",
                "seed_name",
                "qid",
                "label",
                "description",
                "names",
                "is_writer",
                "open_library_id",
                "sitelinks",
                "birth",
                "death",
                "found_via",
                "via_pseudonym",
            ],
        ),
    )
    _register_and_create(
        con,
        "stg_candidate_scores",
        pd.DataFrame(
            score_rows,
            columns=[
                "run_id",
                "row_number",
                "seed_name",
                "qid",
                "rank",
                "score",
                "name_similarity",
                "best_name",
                "is_writer",
                "has_open_library_id",
                "sitelinks",
                "reason",
            ],
        ),
    )


def build_stg_match_decisions(
    con: duckdb.DuckDBPyConnection, run_id: str, min_score: float, min_margin: float
) -> None:
    """Create `stg_match_decisions` with SQL. The thresholds are constants from `config`."""
    con.execute(f"""
        CREATE OR REPLACE TABLE stg_match_decisions AS
        WITH top AS (SELECT * FROM stg_candidate_scores WHERE rank = 1),
             second AS (SELECT * FROM stg_candidate_scores WHERE rank = 2),
             joined AS (
                 SELECT n.row_number, n.seed_name, n.is_invalid, n.invalid_reason,
                        t.qid AS best_qid, t.score AS best_score,
                        s.qid AS second_qid, s.score AS second_score,
                        t.score - COALESCE(s.score, 0) AS margin
                 FROM stg_seed_normalized n
                 LEFT JOIN top t USING (row_number)
                 LEFT JOIN second s USING (row_number)
             )
        SELECT '{run_id}' AS run_id, row_number, seed_name,
               CASE WHEN is_invalid THEN 'invalid'
                    WHEN best_qid IS NULL OR best_score < {min_score} THEN 'not_found'
                    WHEN margin < {min_margin} THEN 'ambiguous'
                    ELSE 'matched' END AS match_status,
               best_qid, best_score, second_qid, second_score, margin,
               CASE WHEN is_invalid THEN 'invalid seed name: ' || invalid_reason
                    WHEN best_qid IS NULL THEN 'no candidate found'
                    WHEN best_score < {min_score}
                        THEN 'top score ' || best_score || ' is below ' || {min_score}
                    WHEN margin < {min_margin}
                        THEN 'top score ' || best_score || ' but margin ' || ROUND(margin, 1)
                             || ' is below ' || {min_margin}
                    ELSE 'top score ' || best_score || ' and margin ' || ROUND(margin, 1)
                         || ' meet the thresholds' END AS match_reason,
               'rule' AS resolved_by,
               CASE WHEN is_invalid THEN NULL ELSE ROUND(best_score / 100, 3) END AS confidence
        FROM joined ORDER BY row_number
    """)  # noqa: S608 - the values are constants from `config`


def build_authors(con: duckdb.DuckDBPyConnection, run_id: str) -> None:
    """Create `authors` with SQL: one row for each seed name, with `duplicate_of`."""
    con.execute(f"""
        CREATE OR REPLACE TABLE authors AS
        WITH base AS (
            SELECT d.row_number, d.seed_name, n.display_name, NOT n.is_invalid AS is_author,
                   n.invalid_reason, n.exact_dup_of, d.match_status, d.confidence,
                   d.match_reason, d.resolved_by,
                   CASE WHEN d.match_status = 'matched' THEN d.best_qid END AS qid
            FROM stg_match_decisions d JOIN stg_seed_normalized n USING (row_number)
        )
        SELECT '{run_id}' AS run_id, b.row_number, b.seed_name, b.display_name, b.is_author,
               b.invalid_reason, b.match_status, b.qid, c.label AS canonical_name,
               c.birth, c.death, c.open_library_id, b.confidence, b.match_reason, b.resolved_by,
               COALESCE(b.exact_dup_of,
                        CASE WHEN b.qid IS NOT NULL
                                  AND b.row_number > MIN(b.row_number) OVER (PARTITION BY b.qid)
                             THEN FIRST_VALUE(b.seed_name) OVER (
                                  PARTITION BY b.qid ORDER BY b.row_number) END
               ) AS duplicate_of
        FROM base b
        LEFT JOIN stg_wikidata_candidates c ON c.row_number = b.row_number AND c.qid = b.qid
        ORDER BY b.row_number
    """)  # noqa: S608 - the run id is generated by the pipeline
