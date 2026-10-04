"""Búsqueda de candidatos en Wikidata y parseo de entidades."""

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


@dataclass
class Candidate:
    """Candidato humano de Wikidata con la evidencia necesaria para puntuarlo."""

    qid: str
    label: str
    description: str
    names: list[str]
    is_writer: bool
    open_library_id: str | None
    sitelinks: int
    birth: str | None
    death: str | None
    found_via: list[str] = field(default_factory=list)
    via_pseudonym: str | None = None


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


def _time_value(entity: dict[str, Any], prop: str) -> str | None:
    for claim in entity.get("claims", {}).get(prop, []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(value, dict) and "time" in value:
            return str(value["time"]).lstrip("+")[:10]
    return None


def _labels(entity: dict[str, Any]) -> tuple[str, str, list[str]]:
    labels = entity.get("labels", {})
    label = (labels.get("en") or next(iter(labels.values()), {})).get("value", "")
    desc = entity.get("descriptions", {}).get("en", {}).get("value", "")
    names = [v["value"] for v in labels.values()]
    for alias_list in entity.get("aliases", {}).values():
        names.extend(a["value"] for a in alias_list)
    for prop in EXTRA_NAME_PROPS:
        names.extend(_string_values(entity, prop))
    return label, desc, list(dict.fromkeys(names))


def parse_candidate(entity: dict[str, Any]) -> Candidate | None:
    """Convierte una entidad en Candidate; None si no es una persona."""
    if HUMAN not in _item_ids(entity, "P31"):
        return None
    label, desc, names = _labels(entity)
    ol = _string_values(entity, "P648")
    return Candidate(
        qid=entity["id"],
        label=label,
        description=desc,
        names=names,
        is_writer=bool(WRITER_OCCUPATIONS & set(_item_ids(entity, "P106"))),
        open_library_id=ol[0] if ol else None,
        sitelinks=len(entity.get("sitelinks", {})),
        birth=_time_value(entity, "P569"),
        death=_time_value(entity, "P570"),
    )


def pseudonym_targets(entity: dict[str, Any]) -> list[str]:
    """QIDs de las personas tras un ítem-seudónimo (vacío si no es un seudónimo)."""
    if PSEUDONYM not in _item_ids(entity, "P31"):
        return []
    for prop in PSEUDONYM_TARGET_PROPS:
        targets = _item_ids(entity, prop)
        if targets:
            return targets
    return []


class WikidataSource:
    """Obtiene candidatos para un nombre combinando dos búsquedas."""

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
                "languages": "en|es",
                "props": "labels|aliases|descriptions|claims|sitelinks",
            }
            out.update(self._client.get_json(API, params).get("entities", {}))
        return out

    def candidates(self, name: str) -> list[Candidate]:
        """Candidatos humanos; los ítems-seudónimo se traducen a la persona."""
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
