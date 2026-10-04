"""DuckDB storage in layers: raw tables, stg tables, and final tables. Each step is idempotent."""

import csv
import gzip
import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

from authors_db.adjudicate import Adjudication, CandidateEvidence
from authors_db.normalize import normalize
from authors_db.scoring import ScoredCandidate

RESPONSE_COLUMNS = ["run_id", "cache_key", "url", "params", "retrieved_at", "response"]


def load_seed(path: Path) -> list[str]:
    with path.open(encoding="utf-8", newline="") as fh:
        return [row["author_name"] for row in csv.DictReader(fh)]


def build_raw_seed(
    con: duckdb.DuckDBPyConnection, run_id: str, seed_path: Path, limit: int | None = None
) -> None:
    """Create `raw_seed`. The table has the CSV rows without changes and a row number."""
    names = load_seed(seed_path)[:limit]
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
        ).astype({"row_number": "int64", "sitelinks": "int64"}),
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
        ).astype(
            {
                "row_number": "int64",
                "qid": "string",
                "best_name": "string",
                "reason": "string",
                "rank": "int64",
                "score": "float64",
                "name_similarity": "float64",
                "sitelinks": "int64",
            }
        ),
    )


def build_stg_slm_adjudications(
    con: duckdb.DuckDBPyConnection, run_id: str, results: list[Adjudication]
) -> None:
    """Create `stg_slm_adjudications`. The table is empty if the run has no adjudication."""
    rows = [
        (
            run_id,
            a.row_number,
            a.seed_name,
            a.model,
            a.model_digest,
            a.prompt_version,
            json.dumps([c.__dict__ for c in a.candidates], ensure_ascii=False),
            a.choice,
            a.chosen_qid,
            a.reason,
            a.is_valid_output,
            a.raw_response,
            a.reverse_qid,
            a.order_consistent,
        )
        for a in results
    ]
    _register_and_create(
        con,
        "stg_slm_adjudications",
        pd.DataFrame(
            rows,
            columns=[
                "run_id",
                "row_number",
                "seed_name",
                "model",
                "model_digest",
                "prompt_version",
                "candidates",
                "choice",
                "chosen_qid",
                "reason",
                "is_valid_output",
                "raw_response",
                "reverse_qid",
                "order_consistent",
            ],
        ).astype(
            {
                "row_number": "int64",
                "chosen_qid": "string",
                "reason": "string",
                "choice": "string",
                "is_valid_output": "bool",
                "reverse_qid": "string",
                "order_consistent": "bool",
            }
        ),
    )


def read_ambiguous_evidence(
    con: duckdb.DuckDBPyConnection, max_candidates: int, margin: float
) -> dict[int, tuple[str, list[CandidateEvidence]]]:
    """Read the `ambiguous` rows with the evidence of the candidates that cause the doubt."""
    rows = con.execute(f"""
        SELECT s.row_number, s.seed_name, c.qid, c.label, s.best_name, c.description, c.birth,
               c.death, c.is_writer, c.open_library_id IS NOT NULL, c.sitelinks
        FROM stg_match_decisions d
        JOIN stg_candidate_scores s ON s.row_number = d.row_number
        JOIN stg_wikidata_candidates c ON c.row_number = s.row_number AND c.qid = s.qid
        WHERE d.rule_status = 'ambiguous' AND s.rank <= {max_candidates}
              AND s.score >= d.best_score - {margin}
        ORDER BY s.row_number, s.rank
    """).fetchall()  # noqa: S608 - the values are constants from `config`
    out: dict[int, tuple[str, list[CandidateEvidence]]] = {}
    for row_number, seed_name, *fields in rows:
        out.setdefault(row_number, (seed_name, []))[1].append(CandidateEvidence(*fields))
    return out


def build_stg_match_decisions(
    con: duckdb.DuckDBPyConnection,
    run_id: str,
    min_score: float,
    min_margin: float,
    dominance_ratio: float = 3.0,
    resolved_factor: float = 0.8,
) -> None:
    """Create `stg_match_decisions` with SQL. The thresholds are constants from `config`.

    The rule gives a first status. For an `ambiguous` row, the adjudication of the model comes
    first. If the model gave no choice, the dominance rule decides. Else the row stays ambiguous.
    """
    con.execute(f"""
        CREATE OR REPLACE TABLE stg_match_decisions AS
        WITH top AS (SELECT * FROM stg_candidate_scores WHERE rank = 1),
             second AS (SELECT * FROM stg_candidate_scores WHERE rank = 2),
             rule AS (
                 SELECT n.row_number, n.seed_name, n.is_invalid, n.invalid_reason,
                        t.qid AS best_qid, t.score AS best_score,
                        s.qid AS second_qid, s.score AS second_score,
                        t.score - COALESCE(s.score, 0) AS margin,
                        CASE WHEN n.is_invalid THEN 'invalid'
                             WHEN t.qid IS NULL OR t.score < {min_score} THEN 'not_found'
                             WHEN t.score - COALESCE(s.score, 0) < {min_margin} THEN 'ambiguous'
                             ELSE 'matched' END AS rule_status
                 FROM stg_seed_normalized n
                 LEFT JOIN top t USING (row_number)
                 LEFT JOIN second s USING (row_number)
             ),
             pair AS (
                 SELECT row_number, qid, sitelinks, ROW_NUMBER() OVER (
                     PARTITION BY row_number ORDER BY name_similarity DESC, sitelinks DESC, qid
                 ) AS prank
                 FROM stg_candidate_scores WHERE rank <= 2
             ),
             dominant AS (
                 SELECT a.row_number, a.qid FROM pair a
                 JOIN pair b ON a.row_number = b.row_number AND a.prank = 1 AND b.prank = 2
                 WHERE a.sitelinks >= {dominance_ratio} * GREATEST(b.sitelinks, 1)
             ),
             choice AS (
                 SELECT r.*, m.chosen_qid AS slm_qid, m.reason AS slm_reason,
                        m.row_number IS NOT NULL AS slm_asked, d.qid AS dominant_qid,
                        CASE WHEN r.rule_status = 'matched' THEN 'rule'
                             WHEN r.rule_status = 'ambiguous' AND m.chosen_qid IS NOT NULL
                                 THEN 'slm'
                             WHEN r.rule_status = 'ambiguous' AND m.row_number IS NOT NULL
                                  AND d.qid IS NOT NULL THEN 'dominance_rule'
                             ELSE 'rule' END AS resolved_by,
                        CASE WHEN r.rule_status = 'matched' THEN r.best_qid
                             WHEN r.rule_status = 'ambiguous' AND m.chosen_qid IS NOT NULL
                                 THEN m.chosen_qid
                             WHEN r.rule_status = 'ambiguous' AND m.row_number IS NOT NULL
                                 THEN d.qid END AS chosen_qid
                 FROM rule r
                 LEFT JOIN stg_slm_adjudications m ON m.row_number = r.row_number
                 LEFT JOIN dominant d ON d.row_number = r.row_number
             )
        SELECT '{run_id}' AS run_id, c.row_number, c.seed_name, c.rule_status,
               CASE WHEN c.chosen_qid IS NOT NULL THEN 'matched' ELSE c.rule_status END
                   AS match_status,
               c.chosen_qid, sc.score AS chosen_score,
               c.best_qid, c.best_score, c.second_qid, c.second_score, c.margin,
               CASE WHEN c.is_invalid THEN 'invalid seed name: ' || c.invalid_reason
                    WHEN c.best_qid IS NULL THEN 'no candidate found'
                    WHEN c.best_score < {min_score}
                        THEN 'top score ' || c.best_score || ' is below ' || {min_score}
                    WHEN c.margin < {min_margin}
                        THEN 'top score ' || c.best_score || ' but margin ' || ROUND(c.margin, 1)
                             || ' is below ' || {min_margin}
                             || CASE c.resolved_by
                                WHEN 'slm' THEN '; the model chose ' || c.chosen_qid || ': '
                                                || c.slm_reason
                                WHEN 'dominance_rule'
                                    THEN '; the model gave no choice; the dominance rule chose '
                                         || c.chosen_qid
                                ELSE '' END
                    ELSE 'top score ' || c.best_score || ' and margin ' || ROUND(c.margin, 1)
                         || ' meet the thresholds' END AS match_reason,
               c.resolved_by,
               CASE WHEN c.is_invalid THEN NULL
                    WHEN c.chosen_qid IS NULL THEN ROUND(c.best_score / 100, 3)
                    WHEN c.resolved_by = 'rule' THEN ROUND(sc.score / 100, 3)
                    ELSE ROUND(sc.score / 100 * {resolved_factor}, 3) END AS confidence
        FROM choice c
        LEFT JOIN stg_candidate_scores sc
               ON sc.row_number = c.row_number AND sc.qid = c.chosen_qid
        ORDER BY c.row_number
    """)  # noqa: S608 - the values are constants from `config`


def build_authors(con: duckdb.DuckDBPyConnection, run_id: str) -> None:
    """Create `authors` with SQL: one row for each seed name, with `duplicate_of`."""
    con.execute(f"""
        CREATE OR REPLACE TABLE authors AS
        WITH base AS (
            SELECT d.row_number, d.seed_name, n.display_name, NOT n.is_invalid AS is_author,
                   n.invalid_reason, n.exact_dup_of, d.match_status, d.confidence,
                   d.match_reason, d.resolved_by,
                   d.chosen_qid AS qid
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


def record_pipeline_run(
    con: duckdb.DuckDBPyConnection,
    run_id: str,
    started_at: datetime,
    code_version: str,
    parameters: dict[str, object],
) -> None:
    """Append a row to `pipeline_runs` with the parameters and the row count of each table."""
    tables = [
        r[0]
        for r in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name <> 'pipeline_runs' "
            "ORDER BY table_name"
        ).fetchall()
    ]
    counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}  # noqa: S608
    con.execute("""CREATE TABLE IF NOT EXISTS pipeline_runs (
        run_id VARCHAR, started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ, code_version VARCHAR,
        parameters JSON, row_counts JSON)""")
    con.execute(
        "INSERT INTO pipeline_runs VALUES (?, ?, ?, ?, ?, ?)",
        [
            run_id,
            started_at,
            datetime.now(UTC),
            code_version,
            json.dumps(parameters),
            json.dumps(counts),
        ],
    )
