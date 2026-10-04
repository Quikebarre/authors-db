"""DuckDB storage in layers: raw tables, stg tables, and final tables. Each step is idempotent."""

import csv
import gzip
import json
from pathlib import Path

import duckdb
import pandas as pd

from authors_db.normalize import normalize

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
