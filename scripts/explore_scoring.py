"""Muestra el ranking de candidatos para nombres de la semilla (calibración de umbrales).

Uso: uv run python scripts/explore_scoring.py [--offline] [nombre ...]
"""

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from authors_db.http import CachedClient
from authors_db.normalize import normalize
from authors_db.scoring import rank
from authors_db.wikidata import WikidataSource

DEFAULT = [
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
    "Stendhal",
    "Stephen Hawking",
    "Fyodor Dostoevsky",
    "Ngũgĩ wa Thiong'o",
    "Natsume Soseki",
    "bell hooks",
    "Leopoldo Alas Clarín",
    "Inca Garcilaso de la Vega",
    "Pepetela",
    "Azorín",
    "Hafez",
    "Dr. Seuss",
    "Theodor Seuss Geisel",
    "George Eliot",
    "Mary Ann Evans",
    "Romain Gary",
    "Émile Ajar",
    "Karen Blixen",
    "Isak Dinesen",
]


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    client = CachedClient(Path("data/cache/wikidata"), offline="--offline" in sys.argv)
    source = WikidataSource(client)

    def run(name: str) -> str:
        norm = normalize(name)
        ranked = rank(norm.match_key, source.candidates(norm.clean_name))[:4]
        lines = [f"== {name}"]
        for s in ranked:
            c = s.candidate
            lines.append(
                f"  {s.score:5.1f} {c.qid:<10} {c.label[:26]:<26} {c.birth or '':<10} "
                f"{c.description[:38]:<38} | {s.reason}"
            )
        return "\n".join(lines)

    with ThreadPoolExecutor(max_workers=4) as pool:
        for out in pool.map(run, args or DEFAULT):
            print(out)


if __name__ == "__main__":
    main()
