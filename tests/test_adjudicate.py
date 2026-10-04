import json

from authors_db.adjudicate import CandidateEvidence, adjudicate_one, format_candidates


class FakeClient:
    model = "fake-model"
    digest = "sha256:fake"

    def __init__(self, answer: str) -> None:
        self._answer = answer
        self.messages: list[dict[str, str]] = []

    def chat(self, messages: list[dict[str, str]]) -> str:
        self.messages = messages
        return self._answer


def evidence(qid: str, label: str) -> CandidateEvidence:
    return CandidateEvidence(
        qid, label, label, "French novelist", "1802-07-24", None, True, True, 100
    )


CANDIDATES = [evidence("Q1", "Alexandre Dumas"), evidence("Q2", "Alexandre Dumas fils")]


def test_adjudicate_one_with_valid_letter_returns_the_candidate_qid():
    client = FakeClient(json.dumps({"choice": "B", "reason": "The son is meant."}))
    result = adjudicate_one(client, 1, "Alexandre Dumas", CANDIDATES)
    assert (result.chosen_qid, result.is_valid_output) == ("Q2", True)


def test_adjudicate_one_with_none_returns_no_choice_but_valid_output():
    client = FakeClient(json.dumps({"choice": "none", "reason": "Not sure."}))
    result = adjudicate_one(client, 1, "Alexandre Dumas", CANDIDATES)
    assert (result.chosen_qid, result.is_valid_output) == (None, True)


def test_adjudicate_one_with_invalid_json_returns_no_choice_and_invalid_output():
    result = adjudicate_one(FakeClient("not json"), 1, "Alexandre Dumas", CANDIDATES)
    assert (result.chosen_qid, result.is_valid_output) == (None, False)


def test_adjudicate_one_with_letter_outside_the_list_is_invalid():
    client = FakeClient(json.dumps({"choice": "D", "reason": "x"}))
    result = adjudicate_one(client, 1, "Alexandre Dumas", CANDIDATES)
    assert (result.chosen_qid, result.is_valid_output) == (None, False)


def test_format_candidates_lists_letters_and_facts():
    text = format_candidates(CANDIDATES)
    assert text.startswith("A. Alexandre Dumas")
    assert "B. Alexandre Dumas fils" in text
    assert "born 1802" in text


def test_adjudicate_one_sends_the_seed_name_in_the_user_message():
    client = FakeClient(json.dumps({"choice": "A", "reason": "x"}))
    adjudicate_one(client, 1, "Alexandre Dumas", CANDIDATES)
    assert "Seed name: Alexandre Dumas" in client.messages[-1]["content"]
