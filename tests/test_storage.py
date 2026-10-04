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
    (cache / "abc.json").write_text(json.dumps(record), encoding="utf-8")
    storage.build_raw_responses(con, RUN, "raw_wikidata_responses", cache)
    url, params, ok = con.execute(
        "SELECT url, params, response->>'$.ok' FROM raw_wikidata_responses"
    ).fetchone()
    assert (url, params, ok) == ("https://x/api", '{"a": 1, "b": 2}', "true")


def test_build_raw_responses_with_missing_cache_creates_empty_table(con, tmp_path):
    storage.build_raw_responses(con, RUN, "raw_openlibrary_responses", tmp_path / "nope")
    assert con.execute("SELECT COUNT(*) FROM raw_openlibrary_responses").fetchone() == (0,)
