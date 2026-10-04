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


def scored_candidate(
    qid: str, score: float, label: str = "L", sitelinks: int = 1, sim: float = 100.0
):
    from authors_db.scoring import ScoredCandidate
    from authors_db.wikidata import Candidate

    cand = Candidate(
        qid=qid,
        label=label,
        description="",
        names=[label],
        is_writer=True,
        open_library_ids=["OL1A"],
        sitelinks=sitelinks,
        birth_year=1900,
        death_year=None,
    )
    return ScoredCandidate(cand, score, sim, label, "reason")


def build_chain(con, tmp_path, names, scored):
    storage.build_raw_seed(con, RUN, write_seed(tmp_path, names))
    storage.build_stg_seed_normalized(con, RUN)
    storage.build_stg_candidates_and_scores(con, RUN, scored)
    storage.build_stg_slm_adjudications(con, RUN, [])
    storage.build_stg_match_decisions(con, RUN, min_score=80.0, min_margin=10.0)
    storage.build_stg_wikidata_labels(con, RUN, {})
    storage.build_stg_openlibrary(con, RUN, [], [])
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


def adjudication(chosen_qid: str | None, row_number: int = 1):
    from authors_db.adjudicate import Adjudication

    return Adjudication(
        row_number,
        "Close",
        "m",
        "d",
        "v1",
        [],
        "A" if chosen_qid else "none",
        chosen_qid,
        "because",
        True,
        "{}",
    )


def rebuild_with(con, adjudications):
    storage.build_stg_slm_adjudications(con, RUN, adjudications)
    storage.build_stg_match_decisions(con, RUN, 80.0, 10.0, dominance_ratio=3.0)
    storage.build_authors(con, RUN)


def ambiguous_pair(sitelinks_top: int, sitelinks_second: int, sim_second: float = 100.0):
    return {
        1: (
            "Close",
            [
                scored_candidate("Q2", 98, sitelinks=sitelinks_top),
                scored_candidate("Q8", 95, sitelinks=sitelinks_second, sim=sim_second),
            ],
        )
    }


def test_slm_choice_resolves_ambiguous_row_with_lower_confidence(con, tmp_path):
    build_chain(con, tmp_path, ["Close"], ambiguous_pair(1, 1))
    rebuild_with(con, [adjudication("Q8")])
    row = con.execute("SELECT match_status, qid, resolved_by, confidence FROM authors").fetchone()
    assert row == ("matched", "Q8", "slm", 0.76)


def test_dominance_rule_applies_only_after_the_model_gave_no_choice(con, tmp_path):
    build_chain(con, tmp_path, ["Close"], ambiguous_pair(90, 10))
    assert con.execute("SELECT match_status FROM authors").fetchone() == ("ambiguous",)
    rebuild_with(con, [adjudication(None)])
    row = con.execute("SELECT match_status, qid, resolved_by FROM authors").fetchone()
    assert row == ("matched", "Q2", "dominance_rule")


def test_dominance_rule_does_not_choose_a_candidate_with_lower_name_similarity(con, tmp_path):
    scored = {
        1: (
            "Close",
            [
                scored_candidate("Q2", 98, sitelinks=10, sim=100),
                scored_candidate("Q8", 95, sitelinks=90, sim=91),
            ],
        )
    }
    build_chain(con, tmp_path, ["Close"], scored)
    rebuild_with(con, [adjudication(None)])
    row = con.execute("SELECT match_status, qid, resolved_by FROM authors").fetchone()
    assert row == ("matched", "Q2", "dominance_rule") or row == ("ambiguous", None, "rule")
    assert row[1] != "Q8"


def test_row_stays_ambiguous_when_model_and_dominance_rule_give_no_choice(con, tmp_path):
    build_chain(con, tmp_path, ["Close"], ambiguous_pair(50, 40))
    rebuild_with(con, [adjudication(None)])
    assert con.execute("SELECT match_status, qid FROM authors").fetchone() == ("ambiguous", None)


def ol_author(ol_id="OL1A", birth="1900", death=None, wikidata="Q7"):
    from authors_db.openlibrary import OlAuthor

    return OlAuthor(ol_id, "Name", birth, death, wikidata, "2026-10-04T00:00:00+00:00")


def build_with_openlibrary(con, tmp_path, author, status="match"):
    scored = {1: ("Clear", [scored_candidate("Q7", 98, "Clear")])}
    build_chain(con, tmp_path, ["Clear"], scored)
    from authors_db.openlibrary import OlWork, OlWorks

    works = OlWorks(12, [OlWork("/works/OL1W", "Book A", 1950, 40)], "2026-10-04T00:00:00+00:00")
    storage.build_stg_openlibrary(
        con, RUN, [("Q7", author, status, True, 12)], [("Q7", "OL1A", works)]
    )
    storage.build_authors(con, RUN)
    storage.build_author_works(con, RUN)
    storage.build_field_provenance(con, RUN)


def test_authors_takes_open_library_fields_from_the_selected_record(con, tmp_path):
    build_with_openlibrary(con, tmp_path, ol_author())
    row = con.execute(
        "SELECT open_library_id, open_library_backlink, open_library_work_count FROM authors"
    ).fetchone()
    assert row == ("OL1A", "match", 12)


def test_author_works_has_one_row_for_each_main_work_keyed_by_qid(con, tmp_path):
    build_with_openlibrary(con, tmp_path, ol_author())
    assert con.execute("SELECT qid, title, rank FROM author_works").fetchall() == [
        ("Q7", "Book A", 1)
    ]


def conflicts(con, field):
    return con.execute(
        "SELECT source, conflict, note FROM field_provenance WHERE field = ? ORDER BY source",
        [field],
    ).fetchall()


def test_field_provenance_flags_conflict_when_years_differ(con, tmp_path):
    build_with_openlibrary(con, tmp_path, ol_author(birth="1905"))
    assert conflicts(con, "birth_year") == [("openlibrary", True, None), ("wikidata", True, None)]


def test_field_provenance_has_no_conflict_when_years_are_equal(con, tmp_path):
    build_with_openlibrary(con, tmp_path, ol_author(birth="12 May 1900"))
    assert conflicts(con, "birth_year") == [("openlibrary", False, None), ("wikidata", False, None)]


def test_field_provenance_marks_not_comparable_instead_of_conflict(con, tmp_path):
    build_with_openlibrary(con, tmp_path, ol_author(birth="c. 1900"))
    assert conflicts(con, "birth_year") == [
        ("openlibrary", None, "not_comparable"),
        ("wikidata", None, "not_comparable"),
    ]


def test_field_provenance_flags_backlink_mismatch(con, tmp_path):
    build_with_openlibrary(con, tmp_path, ol_author(wikidata="Q999"), status="mismatch")
    assert conflicts(con, "wikidata_qid") == [("openlibrary", True, None)]
