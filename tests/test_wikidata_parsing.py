from authors_db.wikidata import parse_candidate, pseudonym_targets


def item(qid: str) -> dict:
    return {"mainsnak": {"datavalue": {"value": {"id": qid}}}}


def string(value: str) -> dict:
    return {"mainsnak": {"datavalue": {"value": value}}}


def test_parse_candidate_non_human_returns_none():
    entity = {"id": "Q959983", "claims": {"P31": [item("Q3863")]}}
    assert parse_candidate(entity) is None


def test_parse_candidate_extracts_evidence_and_extra_names():
    entity = {
        "id": "Q7245",
        "labels": {"en": {"value": "Mark Twain"}},
        "aliases": {"en": [{"value": "Twain"}]},
        "claims": {
            "P31": [item("Q5")],
            "P106": [item("Q36180")],
            "P648": [string("OL18319A")],
            "P1477": [string("Samuel Langhorne Clemens")],
        },
        "sitelinks": {"enwiki": {}, "eswiki": {}},
    }
    cand = parse_candidate(entity)
    assert cand is not None
    assert cand.is_writer
    assert cand.open_library_id == "OL18319A"
    assert cand.sitelinks == 2
    assert {"Mark Twain", "Twain", "Samuel Langhorne Clemens"} <= set(cand.names)


def test_pseudonym_targets_follows_used_by_property():
    entity = {"id": "Q110929251", "claims": {"P31": [item("Q61002")], "P1535": [item("Q34660")]}}
    assert pseudonym_targets(entity) == ["Q34660"]


def test_pseudonym_targets_for_regular_item_is_empty():
    entity = {"id": "Q34660", "claims": {"P31": [item("Q5")], "P1535": [item("Q1")]}}
    assert pseudonym_targets(entity) == []


def test_parse_candidate_prefers_mul_label_over_wrong_english_label():
    entity = {
        "id": "Q117018",
        "labels": {"en": {"value": "Vicente Hohoneo"}, "mul": {"value": "Vicente Huidobro"}},
        "claims": {"P31": [item("Q5")]},
    }
    cand = parse_candidate(entity)
    assert cand is not None
    assert cand.label == "Vicente Huidobro"
    assert "Vicente Hohoneo" in cand.names


def time_claim(time: str, precision: int) -> dict:
    return {"mainsnak": {"datavalue": {"value": {"time": time, "precision": precision}}}}


def test_parse_candidate_keeps_negative_year_and_no_date_for_year_precision():
    entity = {
        "id": "Q6691",
        "claims": {"P31": [item("Q5")], "P569": [time_claim("-0900-00-00T00:00:00Z", 9)]},
    }
    cand = parse_candidate(entity)
    assert (cand.birth_year, cand.birth_date) == (-900, None)


def test_parse_candidate_gives_full_date_for_day_precision():
    entity = {
        "id": "Q1",
        "claims": {"P31": [item("Q5")], "P569": [time_claim("+1893-01-10T00:00:00Z", 11)]},
    }
    cand = parse_candidate(entity)
    assert (cand.birth_year, cand.birth_date) == (1893, "1893-01-10")


def test_parse_candidate_reads_all_open_library_ids_and_nationality():
    entity = {
        "id": "Q1",
        "claims": {
            "P31": [item("Q5")],
            "P648": [string("OL1A"), string("OL2A")],
            "P27": [item("Q298")],
            "P1412": [item("Q1321")],
        },
    }
    cand = parse_candidate(entity)
    assert cand.open_library_ids == ["OL1A", "OL2A"]
    assert (cand.nationality_qids, cand.language_qids) == (["Q298"], ["Q1321"])


def ranked_time_claim(time: str, rank: str) -> dict:
    return {**time_claim(time, 11), "rank": rank}


def test_parse_candidate_uses_the_preferred_claim_and_ignores_deprecated_claims():
    entity = {
        "id": "Q153670",
        "claims": {
            "P31": [item("Q5")],
            "P569": [
                ranked_time_claim("+1900-01-01T00:00:00Z", "deprecated"),
                ranked_time_claim("+1918-07-31T00:00:00Z", "normal"),
                ranked_time_claim("+1919-07-31T00:00:00Z", "preferred"),
            ],
        },
    }
    assert parse_candidate(entity).birth_year == 1919
