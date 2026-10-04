"""Read author data and main works from the Open Library API."""

import re
from dataclasses import dataclass

from authors_db.http import CachedClient

BASE = "https://openlibrary.org"
MAIN_WORKS = 3
NOT_COMPARABLE_RE = re.compile(r"\bBC\b|\bB\.C\.|\bc\.|\bca\.|circa|\?|\bcentury\b", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(\d{3,4})\b")


def parse_year(text: str | None) -> int | None:
    """Return the year of an Open Library date text, or None if the text is not comparable.

    A text with "BC", "c.", "circa", "?" or "century" is not comparable.
    """
    if not text or NOT_COMPARABLE_RE.search(text):
        return None
    match = YEAR_RE.search(text)
    return int(match.group(1)) if match else None


@dataclass(frozen=True)
class OlAuthor:
    """An Open Library author record."""

    ol_id: str
    name: str | None
    birth_text: str | None
    death_text: str | None
    wikidata_qid: str | None
    retrieved_at: str | None
    found: bool = True

    @property
    def birth_year(self) -> int | None:
        return parse_year(self.birth_text)

    @property
    def death_year(self) -> int | None:
        return parse_year(self.death_text)


@dataclass(frozen=True)
class OlWork:
    work_key: str
    title: str
    first_publish_year: int | None
    edition_count: int | None


@dataclass(frozen=True)
class OlWorks:
    """The work count of an author and the main works, sorted by number of editions."""

    work_count: int
    works: list[OlWork]
    retrieved_at: str | None


def parse_author(ol_id: str, record: dict[str, object]) -> OlAuthor:
    """Convert a cache record of `/authors/<id>.json` to an `OlAuthor`."""
    response = record["response"]
    retrieved_at = str(record["retrieved_at"])
    if not isinstance(response, dict) or response.get("_http_status") == 404:
        return OlAuthor(ol_id, None, None, None, None, retrieved_at, found=False)
    remote_ids = response.get("remote_ids") or {}
    return OlAuthor(
        ol_id=ol_id,
        name=response.get("name"),
        birth_text=response.get("birth_date"),
        death_text=response.get("death_date"),
        wikidata_qid=remote_ids.get("wikidata") if isinstance(remote_ids, dict) else None,
        retrieved_at=retrieved_at,
    )


class OpenLibrarySource:
    """Two requests for each author: the record, and the search for the main works."""

    def __init__(self, client: CachedClient) -> None:
        self._client = client

    def author(self, ol_id: str) -> OlAuthor:
        """Read the author record. Follow one redirect to the merged record."""
        record = self._client.get_record(f"{BASE}/authors/{ol_id}.json", {})
        response = record["response"]
        if isinstance(response, dict) and response.get("type", {}).get("key") == "/type/redirect":
            target = str(response["location"]).rsplit("/", 1)[-1]
            record = self._client.get_record(f"{BASE}/authors/{target}.json", {})
        return parse_author(ol_id, record)

    def works(self, ol_id: str) -> OlWorks:
        """Read the work count and the main works, sorted by number of editions."""
        params = {
            "author_key": ol_id,
            "sort": "editions",
            "limit": MAIN_WORKS,
            "fields": "key,title,first_publish_year,edition_count",
        }
        record = self._client.get_record(f"{BASE}/search.json", params)
        response = record["response"]
        works = [
            OlWork(
                d["key"], d.get("title", ""), d.get("first_publish_year"), d.get("edition_count")
            )
            for d in response.get("docs", [])
        ]
        return OlWorks(int(response.get("numFound", 0)), works, str(record["retrieved_at"]))


def backlink_status(author: OlAuthor | None, qid: str) -> str:
    """Compare the Wikidata ID in the Open Library record with the QID of the match.

    The result is `match`, `mismatch`, `absent` (no Wikidata ID in Open Library),
    `ol_not_found`, or `no_ol_id`.
    """
    if author is None:
        return "no_ol_id"
    if not author.found:
        return "ol_not_found"
    if author.wikidata_qid is None:
        return "absent"
    return "match" if author.wikidata_qid == qid else "mismatch"


def select_author(candidates: list[OlAuthor], qid: str) -> OlAuthor | None:
    """Choose the record that links back to the QID. Else choose the first record found."""
    found = [a for a in candidates if a.found]
    for author in found:
        if author.wikidata_qid == qid:
            return author
    return found[0] if found else (candidates[0] if candidates else None)
