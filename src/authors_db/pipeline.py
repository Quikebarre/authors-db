"""Run the pipeline from the seed file to the final tables and the export."""

import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from authors_db import config, storage
from authors_db.adjudicate import Adjudication, OllamaClient, adjudicate_consistent
from authors_db.http import CachedClient
from authors_db.normalize import normalize
from authors_db.openlibrary import (
    OlAuthor,
    OlWorks,
    OpenLibrarySource,
    backlink_status,
    select_author,
)
from authors_db.scoring import ScoredCandidate, rank
from authors_db.wikidata import Candidate, WikidataSource

FINAL_TABLES = ("authors", "author_works", "field_provenance")
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
    """Write the final tables to CSV and Parquet. The `stg_` tables stay in the database."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for table in FINAL_TABLES:
        con.execute(f"COPY {table} TO '{output_dir / table}.csv' (HEADER, DELIMITER ',')")  # noqa: S608
        con.execute(f"COPY {table} TO '{output_dir / table}.parquet' (FORMAT PARQUET)")  # noqa: S608


def adjudicate_ambiguous(con: duckdb.DuckDBPyConnection) -> list[Adjudication]:
    """Ask the model about each `ambiguous` row. The answers are cached.

    The model runs on this computer, so the offline mode of the HTTP client does not apply.
    """
    evidence = storage.read_ambiguous_evidence(
        con, config.MAX_CANDIDATES_FOR_ADJUDICATION, config.MIN_MARGIN
    )
    client = OllamaClient(config.CACHE_DIR / "ollama", offline=False)
    return [
        adjudicate_consistent(client, row_number, seed_name, candidates)
        for row_number, (seed_name, candidates) in evidence.items()
    ]


AuthorRow = tuple[str, OlAuthor | None, str, bool, int | None]


def enrich_open_library(
    source: OpenLibrarySource, candidates: dict[str, Candidate]
) -> tuple[list[AuthorRow], list[tuple[str, str, OlWorks]]]:
    """Read the Open Library records and the main works for each matched QID.

    The record that links back to the QID is the selected record. A QID with no Open Library ID
    gets one row with the status `no_ol_id`.
    """

    def work(item: tuple[str, Candidate]) -> tuple[list[AuthorRow], list[tuple[str, str, OlWorks]]]:
        qid, cand = item
        if not cand.open_library_ids:
            return [(qid, None, backlink_status(None, qid), True, None)], []
        records = [source.author(ol_id) for ol_id in cand.open_library_ids]
        selected = select_author(records, qid)
        works = source.works(selected.ol_id) if selected and selected.found else None
        rows: list[AuthorRow] = [
            (
                qid,
                rec,
                backlink_status(rec, qid),
                rec is selected,
                works.work_count if rec is selected and works else None,
            )
            for rec in records
        ]
        return rows, ([(qid, selected.ol_id, works)] if selected and works else [])

    author_rows: list[AuthorRow] = []
    work_rows: list[tuple[str, str, OlWorks]] = []
    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        for rows, works in pool.map(work, sorted(candidates.items())):
            author_rows += rows
            work_rows += works
    return author_rows, work_rows


def run(limit: int | None = None, offline: bool = False, adjudicate: bool = False) -> str:
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
    storage.build_stg_candidates_and_scores(con, run_id, scored)
    decision_args = (
        config.MIN_MATCH_SCORE,
        config.MIN_MARGIN,
        config.DOMINANCE_RATIO,
        config.RESOLVED_CONFIDENCE_FACTOR,
    )
    storage.build_stg_slm_adjudications(con, run_id, [])
    storage.build_stg_match_decisions(con, run_id, *decision_args)
    if adjudicate:
        storage.build_stg_slm_adjudications(con, run_id, adjudicate_ambiguous(con))
        storage.build_stg_match_decisions(con, run_id, *decision_args)
    by_qid = {sc.candidate.qid: sc.candidate for _, ranked in scored.values() for sc in ranked}
    chosen_qids = con.execute(
        "SELECT DISTINCT chosen_qid FROM stg_match_decisions WHERE chosen_qid IS NOT NULL"
    ).fetchall()
    chosen = {qid: by_qid[qid] for (qid,) in chosen_qids}
    wikidata = WikidataSource(client)
    label_qids = {q for c in chosen.values() for q in (*c.nationality_qids, *c.language_qids)}
    storage.build_stg_wikidata_labels(con, run_id, wikidata.labels(label_qids))
    ol_client = CachedClient(config.CACHE_DIR / "openlibrary", offline=offline, min_interval_s=0.5)
    author_rows, work_rows = enrich_open_library(OpenLibrarySource(ol_client), chosen)
    storage.build_stg_openlibrary(con, run_id, author_rows, work_rows)
    storage.build_raw_responses(
        con, run_id, "raw_wikidata_responses", config.CACHE_DIR / "wikidata"
    )
    storage.build_raw_responses(
        con, run_id, "raw_openlibrary_responses", config.CACHE_DIR / "openlibrary"
    )
    storage.build_authors(con, run_id)
    storage.build_author_works(con, run_id)
    storage.build_field_provenance(con, run_id)
    export_final_tables(con, config.OUTPUT_DIR)
    storage.record_pipeline_run(
        con,
        run_id,
        started,
        code_version(),
        {
            "limit": limit,
            "offline": offline,
            "adjudicate": adjudicate,
            "model": config.OLLAMA_MODEL if adjudicate else None,
            "min_score": config.MIN_MATCH_SCORE,
            "min_margin": config.MIN_MARGIN,
            "dominance_ratio": config.DOMINANCE_RATIO,
        },
    )
    con.close()
    return run_id
