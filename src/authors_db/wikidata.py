"""Search for candidates in Wikidata and parse the entities."""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from authors_db.http import CachedClient

API = "https://www.wikidata.org/w/api.php"
HUMAN = "Q5"
PSEUDONYM = "Q61002"
# Ocupaciones consideradas "escritor" (P106): writer, poet, novelist, playwright, essayist,
# philosopher, historian, journalist, translator, screenwriter...
WRITER_OCCUPATIONS = frozenset(
    {
        "Q36180",
        "Q49757",
        "Q6625963",
        "Q482980",
        "Q4853732",
        "Q214917",
        "Q1930187",
        "Q4263842",
        "Q11774202",
        "Q4964182",
        "Q201788",
        "Q333634",
        "Q28389",
        "Q1209498",
    }
)
# Propiedades que enlazan un ítem-seudónimo con la persona: P1535 (used by), P460 (same as).
PSEUDONYM_TARGET_PROPS = ("P1535", "P460")
# Propiedades que aportan nombres alternativos: P742 (pseudónimo), P1477 (nombre de nacimiento).
EXTRA_NAME_PROPS = ("P742", "P1477", "P1559")
SEARCH_LIMIT = 10
FETCH_BATCH = 40
# Wikidata often keeps the correct name only in "mul" or in another language.
LANGUAGES = "en|es|fr|de|it|pt|ca|mul"


@dataclass
class Candidate:
    """A human from Wikidata with the evidence that the score needs."""

    qid: str
    label: str
    description: str
    names: list[str]
    is_writer: bool
    open_library_ids: list[str]
    sitelinks: int
    birth_year: int | None
    death_year: int | None
    birth_date: str | None = None  # Only with day precision.
    death_date: str | None = None
    nationality_qids: list[str] = field(default_factory=list)
    language_qids: list[str] = field(default_factory=list)
    found_via: list[str] = field(default_factory=list)
    via_pseudonym: str | None = None
    retrieved_at: str | None = None

    @property
    def open_library_id(self) -> str | None:
        """The first Open Library ID. The pipeline can choose another one later."""
        return self.open_library_ids[0] if self.open_library_ids else None


def _item_ids(entity: dict[str, Any], prop: str) -> list[str]:
    out = []
    for claim in entity.get("claims", {}).get(prop, []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(value, dict) and "id" in value:
            out.append(value["id"])
    return out


def _string_values(entity: dict[str, Any], prop: str) -> list[str]:
    out = []
    for claim in entity.get("claims", {}).get(prop, []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(value, str):
            out.append(value)
        elif isinstance(value, dict) and "text" in value:
            out.append(value["text"])
    return out


TIME_RE = re.compile(r"^([+-])(\d+)-(\d\d)-(\d\d)T")
DAY_PRECISION = 11


def _time_parts(entity: dict[str, Any], prop: str) -> tuple[int | None, str | None]:
    """Return (year, date). The date is set only when Wikidata has day precision."""
    for claim in entity.get("claims", {}).get(prop, []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if not isinstance(value, dict) or "time" not in value:
            continue
        match = TIME_RE.match(str(value["time"]))
        if not match:
            continue
        sign, digits, month, day = match.groups()
        year = int(f"{sign}{digits}")
        if value.get("precision", 0) >= DAY_PRECISION and month != "00" and day != "00":
            return year, f"{sign if sign == '-' else ''}{digits.zfill(4)}-{month}-{day}"
        return year, None
    return None, None


def _labels(entity: dict[str, Any]) -> tuple[str, str, list[str]]:
    labels = entity.get("labels", {})
    # The "mul" label is the default name for all languages. Some "en" labels are wrong.
    preferred = labels.get("mul") or labels.get("en") or next(iter(labels.values()), {})
    label = preferred.get("value", "")
    desc = entity.get("descriptions", {}).get("en", {}).get("value", "")
    names = [v["value"] for v in labels.values()]
    for alias_list in entity.get("aliases", {}).values():
        names.extend(a["value"] for a in alias_list)
    for prop in EXTRA_NAME_PROPS:
        names.extend(_string_values(entity, prop))
    return label, desc, list(dict.fromkeys(names))


def parse_candidate(entity: dict[str, Any]) -> Candidate | None:
    """Convert an entity to a candidate. Return None if the entity is not a human."""
    if HUMAN not in _item_ids(entity, "P31"):
        return None
    label, desc, names = _labels(entity)
    birth_year, birth_date = _time_parts(entity, "P569")
    death_year, death_date = _time_parts(entity, "P570")
    return Candidate(
        qid=entity["id"],
        label=label,
        description=desc,
        names=names,
        is_writer=bool(WRITER_OCCUPATIONS & set(_item_ids(entity, "P106"))),
        open_library_ids=_string_values(entity, "P648"),
        sitelinks=len(entity.get("sitelinks", {})),
        birth_year=birth_year,
        death_year=death_year,
        birth_date=birth_date,
        death_date=death_date,
        nationality_qids=_item_ids(entity, "P27"),
        language_qids=_item_ids(entity, "P1412"),
        retrieved_at=entity.get("_retrieved_at"),
    )


def pseudonym_targets(entity: dict[str, Any]) -> list[str]:
    """Return the QIDs of the humans that use a pseudonym item. Return an empty list otherwise."""
    if PSEUDONYM not in _item_ids(entity, "P31"):
        return []
    for prop in PSEUDONYM_TARGET_PROPS:
        targets = _item_ids(entity, prop)
        if targets:
            return targets
    return []


class WikidataSource:
    """Get the candidates for a name. The class combines two searches."""

    def __init__(self, client: CachedClient) -> None:
        self._client = client

    def _entity_search(self, name: str) -> list[str]:
        params = {
            "action": "wbsearchentities",
            "search": name,
            "language": "en",
            "type": "item",
            "limit": SEARCH_LIMIT,
            "format": "json",
        }
        return [h["id"] for h in self._client.get_json(API, params).get("search", [])]

    def _human_fulltext_search(self, name: str) -> list[str]:
        params = {
            "action": "query",
            "list": "search",
            "format": "json",
            "srsearch": f"{name} haswbstatement:P31={HUMAN}",
            "srlimit": SEARCH_LIMIT,
        }
        return [r["title"] for r in self._client.get_json(API, params)["query"]["search"]]

    def _fetch(self, qids: Iterable[str]) -> dict[str, dict[str, Any]]:
        ids = sorted(set(qids))
        out: dict[str, dict[str, Any]] = {}
        for i in range(0, len(ids), FETCH_BATCH):
            params = {
                "action": "wbgetentities",
                "ids": "|".join(ids[i : i + FETCH_BATCH]),
                "format": "json",
                "languages": LANGUAGES,
                "props": "labels|aliases|descriptions|claims|sitelinks",
            }
            record = self._client.get_record(API, params)
            for qid, entity in record["response"].get("entities", {}).items():
                out[qid] = {**entity, "_retrieved_at": record["retrieved_at"]}
        return out

    def candidates(self, name: str) -> list[Candidate]:
        """Return the human candidates. Replace each pseudonym item with its human."""
        found_via: dict[str, list[str]] = {}
        for source, qids in (
            ("entity_search", self._entity_search(name)),
            ("human_fulltext", self._human_fulltext_search(name)),
        ):
            for qid in qids:
                found_via.setdefault(qid, []).append(source)
        entities = self._fetch(found_via)

        redirects: dict[str, list[str]] = {}
        for qid, entity in entities.items():
            if targets := pseudonym_targets(entity):
                redirects[qid] = targets
        extra = {t for ts in redirects.values() for t in ts} - set(entities)
        entities.update(self._fetch(extra))

        result: dict[str, Candidate] = {}
        for qid, entity in entities.items():
            if qid in redirects:
                continue
            if cand := parse_candidate(entity):
                cand.found_via = found_via.get(qid, [])
                result[qid] = cand
        for pseudo_qid, targets in redirects.items():
            for target in targets:
                cand = result.get(target)
                if (
                    cand is None
                    and (ent := entities.get(target))
                    and (cand := parse_candidate(ent))
                ):
                    result[target] = cand
                if cand is not None:
                    cand.via_pseudonym = pseudo_qid
                    cand.found_via = [*cand.found_via, f"pseudonym:{pseudo_qid}"]
                    cand.names = list(
                        dict.fromkeys([*cand.names, *_labels(entities[pseudo_qid])[2]])
                    )
        return list(result.values())

    def labels(self, qids: Iterable[str]) -> dict[str, tuple[str, str | None]]:
        """Return (label, retrieved_at) for each QID, for example a country or a language."""
        ids = sorted(set(qids))
        out: dict[str, tuple[str, str | None]] = {}
        for i in range(0, len(ids), FETCH_BATCH):
            params = {
                "action": "wbgetentities",
                "ids": "|".join(ids[i : i + FETCH_BATCH]),
                "format": "json",
                "languages": "en|mul",
                "props": "labels",
            }
            record = self._client.get_record(API, params)
            for qid, entity in record["response"].get("entities", {}).items():
                label = _labels(entity)[0]
                out[qid] = (label, record["retrieved_at"])
        return out
