import pytest

from authors_db.openlibrary import (
    OlAuthor,
    backlink_status,
    parse_author,
    parse_year,
    select_author,
)


@pytest.mark.parametrize(
    ("text", "year"),
    [
        ("1893", 1893),
        ("31 July 1965", 1965),
        ("May 5, 1818", 1818),
        ("427 BC", None),
        ("c. 1207", None),
        ("1207?", None),
        ("5th century", None),
        (None, None),
        ("", None),
    ],
)
def test_parse_year_returns_year_only_for_comparable_dates(text, year):
    assert parse_year(text) == year


def author(ol_id="OL1A", qid=None, found=True, birth="1900"):
    return OlAuthor(ol_id, "Name", birth, None, qid, "2026-10-04T00:00:00+00:00", found)


def test_backlink_status_covers_all_cases():
    assert backlink_status(author(qid="Q1"), "Q1") == "match"
    assert backlink_status(author(qid="Q2"), "Q1") == "mismatch"
    assert backlink_status(author(qid=None), "Q1") == "absent"
    assert backlink_status(author(found=False), "Q1") == "ol_not_found"
    assert backlink_status(None, "Q1") == "no_ol_id"


def test_select_author_prefers_the_record_that_links_back_to_the_qid():
    records = [author("OL1A", qid="Q9"), author("OL2A", qid="Q1"), author("OL3A")]
    assert select_author(records, "Q1").ol_id == "OL2A"


def test_select_author_without_backlink_returns_first_found_record():
    records = [author("OL1A", found=False), author("OL2A"), author("OL3A")]
    assert select_author(records, "Q1").ol_id == "OL2A"


def test_parse_author_with_404_returns_not_found_record():
    record = {"response": {"_http_status": 404}, "retrieved_at": "2026-10-04T00:00:00+00:00"}
    assert not parse_author("OL9A", record).found


def test_parse_author_reads_wikidata_remote_id_and_dates():
    record = {
        "response": {"name": "X", "birth_date": "1893", "remote_ids": {"wikidata": "Q117018"}},
        "retrieved_at": "2026-10-04T00:00:00+00:00",
    }
    parsed = parse_author("OL256110A", record)
    assert (parsed.wikidata_qid, parsed.birth_year) == ("Q117018", 1893)
