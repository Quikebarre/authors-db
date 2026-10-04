"""Optional adjudication of the `ambiguous` rows with a local language model.

The model only chooses between the candidates, or answers "none". It never creates a field.
"""

import gzip
import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal, Protocol

import httpx
from pydantic import BaseModel, ValidationError

from authors_db import config
from authors_db.prompts import PROMPT_VERSION, SYSTEM_PROMPT, USER_PROMPT

LETTERS = "ABCDEFGH"


class SlmAnswer(BaseModel):
    """The JSON answer that the model must give."""

    choice: Literal["A", "B", "C", "D", "none"]
    reason: str


@dataclass(frozen=True)
class CandidateEvidence:
    """The facts about one candidate that the model receives."""

    qid: str
    label: str
    matched_name: str
    description: str
    birth: str | None
    death: str | None
    is_writer: bool
    has_open_library_id: bool
    sitelinks: int


@dataclass(frozen=True)
class Adjudication:
    """The result for one seed name. `chosen_qid` is None if the model did not choose."""

    row_number: int
    seed_name: str
    model: str
    model_digest: str
    prompt_version: str
    candidates: list[CandidateEvidence]
    choice: str | None
    chosen_qid: str | None
    reason: str | None
    is_valid_output: bool
    raw_response: str
    reverse_qid: str | None = None
    order_consistent: bool = True


class ChatClient(Protocol):
    """A client that sends messages to a language model and returns the text."""

    model: str
    digest: str

    def chat(self, messages: list[dict[str, str]]) -> str: ...


class OfflineModelCacheMissError(RuntimeError):
    """Raised when the offline mode is on and the cache has no answer for the request."""


class ModelVersionError(RuntimeError):
    """Raised when the installed model does not have the pinned digest."""


class OllamaClient:
    """Chat client for a local Ollama server. Each answer is saved in a gzip cache."""

    def __init__(self, cache_dir: Path, offline: bool = False, timeout_s: float = 600.0) -> None:
        self.model = config.OLLAMA_MODEL
        self._cache_dir = cache_dir
        self._offline = offline
        self._http = httpx.Client(base_url=config.OLLAMA_URL, timeout=timeout_s)
        self.digest = config.OLLAMA_MODEL_DIGEST
        installed = self._read_digest()
        if installed != "unavailable" and installed != self.digest:
            raise ModelVersionError(f"Pinned {self.digest}, installed {installed}")
        cache_dir.mkdir(parents=True, exist_ok=True)

    def _read_digest(self) -> str:
        """Return the digest of the model. The digest fixes the model version."""
        try:
            tags = self._http.get("/api/tags").json()
        except httpx.TransportError:
            return "unavailable"
        for entry in tags.get("models", []):
            if entry.get("name") == self.model:
                return str(entry.get("digest", "unknown"))
        return "not-installed"

    def _request_body(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": SlmAnswer.model_json_schema(),
            "options": {"temperature": 0, "seed": 0, "num_ctx": 4096},
        }

    def chat(self, messages: list[dict[str, str]]) -> str:
        body = self._request_body(messages)
        key_source = json.dumps([self.digest, PROMPT_VERSION, body], sort_keys=True)
        path = self._cache_dir / f"{hashlib.sha256(key_source.encode()).hexdigest()[:24]}.json.gz"
        if path.exists():
            return str(json.loads(gzip.decompress(path.read_bytes()))["content"])
        if self._offline:
            raise OfflineModelCacheMissError(messages[-1]["content"][:80])
        response = self._http.post("/api/chat", json=body)
        response.raise_for_status()
        content = str(response.json()["message"]["content"])
        record = {
            "model": self.model,
            "digest": self.digest,
            "prompt_version": PROMPT_VERSION,
            "request": body,
            "content": content,
        }
        path.write_bytes(gzip.compress(json.dumps(record, ensure_ascii=False).encode("utf-8")))
        return content


def _year(date: str | None) -> str:
    return date[:4].lstrip("0") or "?" if date else "?"


def format_candidates(candidates: list[CandidateEvidence]) -> str:
    """Return the text block that lists the candidates with their facts."""
    lines = []
    for letter, c in zip(LETTERS, candidates, strict=False):
        lines.append(
            f"{letter}. {c.label} (matched name: {c.matched_name}); "
            f"description: {c.description or 'none'}; born {_year(c.birth)}, "
            f"died {_year(c.death)}; has a writer occupation: {'yes' if c.is_writer else 'no'}; "
            f"has an Open Library page: {'yes' if c.has_open_library_id else 'no'}; "
            f"Wikipedia language editions: {c.sitelinks}"
        )
    return "\n".join(lines)


def adjudicate_one(
    client: ChatClient, row_number: int, seed_name: str, candidates: list[CandidateEvidence]
) -> Adjudication:
    """Ask the model to choose. A wrong or invalid answer gives no choice."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": USER_PROMPT.format(
                seed_name=seed_name, candidates=format_candidates(candidates)
            ),
        },
    ]
    raw = client.chat(messages)
    choice: str | None = None
    chosen_qid: str | None = None
    reason: str | None = None
    valid = False
    try:
        answer = SlmAnswer.model_validate_json(raw)
        valid = True
        choice, reason = answer.choice, answer.reason
        index = LETTERS.find(answer.choice) if answer.choice != "none" else -1
        if 0 <= index < len(candidates):
            chosen_qid = candidates[index].qid
        elif answer.choice != "none":
            valid = False  # The letter does not match any candidate.
    except ValidationError:
        pass
    return Adjudication(
        row_number,
        seed_name,
        client.model,
        client.digest,
        PROMPT_VERSION,
        candidates,
        choice,
        chosen_qid,
        reason,
        valid,
        raw,
    )


def adjudicate_consistent(
    client: ChatClient, row_number: int, seed_name: str, candidates: list[CandidateEvidence]
) -> Adjudication:
    """Ask twice, with the candidates in reverse order the second time.

    The choice counts only if both answers give the same candidate. This removes the
    effect of the position of a candidate in the list.
    """
    forward = adjudicate_one(client, row_number, seed_name, candidates)
    backward = adjudicate_one(client, row_number, seed_name, candidates[::-1])
    consistent = forward.chosen_qid is not None and forward.chosen_qid == backward.chosen_qid
    if consistent or forward.chosen_qid is None and backward.chosen_qid is None:
        return replace(forward, reverse_qid=backward.chosen_qid, order_consistent=True)
    return replace(
        forward,
        chosen_qid=None,
        reverse_qid=backward.chosen_qid,
        order_consistent=False,
        reason=f"The answer depends on the order of the candidates. {forward.reason}",
    )
