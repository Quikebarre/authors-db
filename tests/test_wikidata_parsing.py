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
