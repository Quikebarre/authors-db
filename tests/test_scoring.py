from authors_db.scoring import name_similarity, rank, score_candidate
from authors_db.wikidata import Candidate


def make(qid: str = "Q1", names: list[str] | None = None, **kw) -> Candidate:
    base = {
        "qid": qid,
        "label": "x",
        "description": "",
        "names": names or ["x"],
        "is_writer": False,
        "open_library_ids": [],
        "sitelinks": 0,
        "birth_year": None,
        "death_year": None,
    }
    return Candidate(**{**base, **kw})


def test_name_similarity_exact_key_returns_100():
    sim, best = name_similarity("mark twain", ["Mark Twain"])
    assert sim == 100
    assert best == "Mark Twain"


def test_name_similarity_uses_best_alias():
    sim, best = name_similarity("samuel clemens", ["Mark Twain", "Samuel Clemens"])
    assert sim == 100
    assert best == "Samuel Clemens"


def test_name_similarity_single_token_does_not_match_longer_name_fully():
    sim, _ = name_similarity("homer", ["Homer Simpson"])
    assert sim < 70


def test_name_similarity_token_subset_is_capped_below_exact():
    sim, _ = name_similarity("leopoldo alas clarin", ["Leopoldo Alas"])
    assert 80 < sim < 100


def test_score_candidate_writer_with_open_library_outranks_namesake():
    author = make("Q1", ["Homer"], is_writer=True, open_library_ids=["OL1A"])
    painter = make("Q2", ["Homer"], open_library_ids=["OL2A"])
    ranked = rank("homer", [painter, author])
    assert [s.candidate.qid for s in ranked] == ["Q1", "Q2"]


def test_score_candidate_sitelinks_only_break_ties():
    low = score_candidate("homer", make(names=["Homer"], sitelinks=0))
    high = score_candidate("homer", make(names=["Homer"], sitelinks=500))
    assert 0 < high.score - low.score <= 3


def test_score_candidate_reason_lists_evidence():
    scored = score_candidate(
        "homer", make(names=["Homer"], is_writer=True, open_library_ids=["OL1A"])
    )
    assert "writer+15" in scored.reason
    assert "openlibrary+15" in scored.reason
