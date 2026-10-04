"""Run the pipeline from the seed file to the final tables and the export."""

import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from authors_db import config, storage
from authors_db.http import CachedClient
from authors_db.normalize import normalize
from authors_db.scoring import ScoredCandidate, rank
from authors_db.wikidata import WikidataSource

FINAL_TABLES = ("authors",)
THREADS = 4


def code_version() -> str:
    """Return the short git commit of the code, or 'unknown' outside a git repository."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return out.stdout.strip()


def score_seed_names(
    names: list[str], source: WikidataSource
) -> dict[int, tuple[str, list[ScoredCandidate]]]:
    """Search and score the candidates of each valid seed name. The work runs in threads."""
    valid = []
    for row_number, name in enumerate(names, 1):
        normalized = normalize(name)
        if normalized.is_valid:
            valid.append((row_number, name, normalized))

    def work(item: tuple[int, str, object]) -> tuple[int, tuple[str, list[ScoredCandidate]]]:
        row_number, name, normalized = item
        ranked = rank(normalized.match_key, source.candidates(normalized.clean_name))
        return row_number, (name, ranked)

    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        return dict(pool.map(work, valid))


def export_final_tables(con: duckdb.DuckDBPyConnection, output_dir: Path) -> None:
    """Write the final tables to CSV and Parquet. The staging tables stay in the database."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for table in FINAL_TABLES:
        con.execute(f"COPY {table} TO '{output_dir / table}.csv' (HEADER, DELIMITER ',')")  # noqa: S608
        con.execute(f"COPY {table} TO '{output_dir / table}.parquet' (FORMAT PARQUET)")  # noqa: S608


def run(limit: int | None = None, offline: bool = False) -> str:
    """Run all steps. Return the run id."""
    started = datetime.now(UTC)
    run_id = started.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(config.DB_PATH))

    names = storage.load_seed(config.SEED_PATH)[:limit]
    storage.build_raw_seed(con, run_id, config.SEED_PATH, limit)
    storage.build_stg_seed_normalized(con, run_id)

    client = CachedClient(config.CACHE_DIR / "wikidata", offline=offline, min_interval_s=0.4)
    scored = score_seed_names(names, WikidataSource(client))
    storage.build_raw_responses(
        con, run_id, "raw_wikidata_responses", config.CACHE_DIR / "wikidata"
    )
    storage.build_raw_responses(
        con, run_id, "raw_openlibrary_responses", config.CACHE_DIR / "openlibrary"
    )
    storage.build_stg_candidates_and_scores(con, run_id, scored)
    storage.build_stg_match_decisions(con, run_id, config.MIN_MATCH_SCORE, config.MIN_MARGIN)
    storage.build_authors(con, run_id)
    export_final_tables(con, config.OUTPUT_DIR)
    storage.record_pipeline_run(
        con,
        run_id,
        started,
        code_version(),
        {
            "limit": limit,
            "offline": offline,
            "min_score": config.MIN_MATCH_SCORE,
            "min_margin": config.MIN_MARGIN,
        },
    )
    con.close()
    return run_id
