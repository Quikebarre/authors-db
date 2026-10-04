"""Exploración para calibrar el scoring: busca nombres representativos en Wikidata.

Uso: uv run python scripts/explore_wikidata.py [--offline]
"""

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from rapidfuzz import fuzz

from authors_db.http import CachedClient
from authors_db.normalize import match_key, normalize

API = "https://www.wikidata.org/w/api.php"
WRITER_QIDS = {"Q36180", "Q49757", "Q6625963", "Q482980", "Q4853732", "Q214917", "Q1930187"}
NAMES = [
    "Gabriel García Márquez",
    "J. K. Rowling",
    "Robert Galbraith",
    "Mark Twain",
    "Samuel Clemens",
    "Homer",
    "Colette",
    "Adonis",
    "Rumi",
    "Plato",
    "Voltaire",
    "Stephen Hawking",
    "Daniel Kahneman",
    "Yuval Noah Harari",
    "Dostoevsky",
    "Ngũgĩ wa Thiong'o",
    "Natsume Soseki",
    "bell hooks",
    "Leopoldo Alas Clarín",
    "Inca Garcilaso de la Vega",
    "Anonymous",
]


def search(client: CachedClient, name: str) -> list[dict]:
    params = {
        "action": "wbsearchentities",
        "search": name,
        "language": "en",
        "type": "item",
        "limit": 7,
        "format": "json",
    }
    return client.get_json(API, params).get("search", [])


def entities(client: CachedClient, qids: list[str]) -> dict[str, dict]:
    if not qids:
        return {}
    params = {
        "action": "wbgetentities",
        "ids": "|".join(qids),
        "format": "json",
        "props": "labels|aliases|descriptions|claims|sitelinks",
        "languages": "en",
    }
    return client.get_json(API, params).get("entities", {})


def claim_ids(entity: dict, prop: str) -> list[str]:
    out = []
    for c in entity.get("claims", {}).get(prop, []):
        val = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(val, dict) and "id" in val:
            out.append(val["id"])
    return out


def claim_time(entity: dict, prop: str) -> str:
    for c in entity.get("claims", {}).get(prop, []):
        val = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(val, dict) and "time" in val:
            return val["time"][:11].lstrip("+")
    return ""


def explore(client: CachedClient, name: str) -> list[str]:
    norm = normalize(name)
    if not norm.is_valid:
        return [f"== {name!r}: INVALID ({norm.invalid_reason})"]
    hits = search(client, norm.clean_name)
    ents = entities(client, [h["id"] for h in hits])
    lines = [f"== {name!r}  key={norm.match_key!r}  candidatos={len(hits)}"]
    for h in hits:
        e = ents.get(h["id"], {})
        label = e.get("labels", {}).get("en", {}).get("value", h.get("label", ""))
        aliases = [a["value"] for a in e.get("aliases", {}).get("en", [])]
        sim = max(fuzz.ratio(norm.match_key, match_key(t)) for t in [label, *aliases])
        occ = set(claim_ids(e, "P106"))
        writer = "W" if occ & WRITER_QIDS else "-"
        human = "H" if "Q5" in claim_ids(e, "P31") else "-"
        ol = "OL" if e.get("claims", {}).get("P648") else "--"
        lines.append(
            f"  {h['id']:<10} sim={sim:5.1f} {human}{writer} {ol} "
            f"sl={len(e.get('sitelinks', {})):<3} {claim_time(e, 'P569'):<11}"
            f"{label[:28]:<28} | {h.get('description', '')[:55]}"
        )
    return lines


def main() -> None:
    client = CachedClient(Path("data/cache/wikidata"), offline="--offline" in sys.argv)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for lines in pool.map(lambda n: explore(client, n), NAMES):
            print("\n".join(lines))


if __name__ == "__main__":
    main()
