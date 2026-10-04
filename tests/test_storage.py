import gzip
import json
from pathlib import Path

import duckdb
import pytest

from authors_db import storage

RUN = "run-test"


@pytest.fixture
def con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(":memory:")


def write_seed(tmp_path: Path, names: list[str]) -> Path:
    path = tmp_path / "seed.csv"
    path.write_text("author_name\n" + "\n".join(names) + "\n", encoding="utf-8")
    return path


def test_build_raw_seed_keeps_names_and_row_numbers(con, tmp_path):
    storage.build_raw_seed(con, RUN, write_seed(tmp_path, ["Isabel Allende", "bell hooks"]))
    rows = con.execute("SELECT row_number, author_name, run_id FROM raw_seed ORDER BY 1").fetchall()
    assert rows == [(1, "Isabel Allende", RUN), (2, "bell hooks", RUN)]


def test_build_stg_seed_normalized_flags_invalid_and_exact_duplicates(con, tmp_path):
    names = ["Kenzaburō Ōe", "Anonymous", "Kenzaburo Oe"]
    storage.build_raw_seed(con, RUN, write_seed(tmp_path, names))
    storage.build_stg_seed_normalized(con, RUN)
    rows = con.execute(
        "SELECT seed_name, match_key, is_invalid, invalid_reason, exact_dup_of "
        "FROM stg_seed_normalized ORDER BY row_number"
    ).fetchall()
    assert rows == [
        ("Kenzaburō Ōe", "kenzaburo oe", False, None, None),
        ("Anonymous", "anonymous", True, "not_an_author", None),
        ("Kenzaburo Oe", "kenzaburo oe", False, None, "Kenzaburō Ōe"),
    ]


def test_build_raw_responses_loads_cache_records(con, tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    record = {
        "url": "https://x/api",
        "params": {"b": 2, "a": 1},
        "retrieved_at": "2026-10-04T18:00:00+00:00",
        "response": {"ok": True},
    }
    (cache / "abc.json.gz").write_bytes(gzip.compress(json.dumps(record).encode()))
    storage.build_raw_responses(con, RUN, "raw_wikidata_responses", cache)
    url, params, ok = con.execute(
        "SELECT url, params, response->>'$.ok' FROM raw_wikidata_responses"
    ).fetchone()
    assert (url, params, ok) == ("https://x/api", '{"a": 1, "b": 2}', "true")


def test_build_raw_responses_with_missing_cache_creates_empty_table(con, tmp_path):
    storage.build_raw_responses(con, RUN, "raw_openlibrary_responses", tmp_path / "nope")
    assert con.execute("SELECT COUNT(*) FROM raw_openlibrary_responses").fetchone() == (0,)


def scored_candidate(qid: str, score: float, label: str = "L"):
    from authors_db.scoring import ScoredCandidate
    from authors_db.wikidata import Candidate

    cand = Candidate(
        qid=qid,
        label=label,
        description="",
        names=[label],
        is_writer=True,
        open_library_id="OL1A",
        sitelinks=1,
        birth="1900-01-01",
        death=None,
    )
    return ScoredCandidate(cand, score, 100.0, label, "reason")


def build_chain(con, tmp_path, names, scored):
    storage.build_raw_seed(con, RUN, write_seed(tmp_path, names))
    storage.build_stg_seed_normalized(con, RUN)
    storage.build_stg_candidates_and_scores(con, RUN, scored)
    storage.build_stg_match_decisions(con, RUN, min_score=80.0, min_margin=10.0)
    storage.build_authors(con, RUN)


def test_match_decisions_apply_score_and_margin_thresholds(con, tmp_path):
    names = ["Clear", "Close", "Weak", "Nobody", "Anonymous"]
    scored = {
        1: ("Clear", [scored_candidate("Q1", 98), scored_candidate("Q9", 70)]),
        2: ("Close", [scored_candidate("Q2", 98), scored_candidate("Q8", 95)]),
        3: ("Weak", [scored_candidate("Q3", 77)]),
        4: ("Nobody", []),
        5: ("Anonymous", []),
    }
    build_chain(con, tmp_path, names, scored)
    rows = con.execute(
        "SELECT seed_name, match_status FROM stg_match_decisions ORDER BY row_number"
    ).fetchall()
    assert rows == [
        ("Clear", "matched"),
        ("Close", "ambiguous"),
        ("Weak", "not_found"),
        ("Nobody", "not_found"),
        ("Anonymous", "invalid"),
    ]


def test_authors_keeps_invalid_rows_with_is_author_false(con, tmp_path):
    build_chain(con, tmp_path, ["Anonymous"], {1: ("Anonymous", [])})
    row = con.execute("SELECT is_author, invalid_reason, match_status, qid FROM authors").fetchone()
    assert row == (False, "not_an_author", "invalid", None)


def test_authors_marks_duplicate_of_for_seed_names_with_same_qid(con, tmp_path):
    scored = {
        1: ("Mark Twain", [scored_candidate("Q7245", 98, "Mark Twain")]),
        2: ("Samuel Clemens", [scored_candidate("Q7245", 91, "Mark Twain")]),
    }
    build_chain(con, tmp_path, ["Mark Twain", "Samuel Clemens"], scored)
    rows = con.execute("SELECT seed_name, duplicate_of FROM authors ORDER BY row_number").fetchall()
    assert rows == [("Mark Twain", None), ("Samuel Clemens", "Mark Twain")]


def test_authors_has_no_qid_for_ambiguous_rows(con, tmp_path):
    scored = {1: ("Close", [scored_candidate("Q2", 98), scored_candidate("Q8", 95)])}
    build_chain(con, tmp_path, ["Close"], scored)
    assert con.execute("SELECT match_status, qid FROM authors").fetchone() == ("ambiguous", None)
