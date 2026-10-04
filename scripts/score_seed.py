"""Puntúa TODA la semilla y vuelca top-2 por nombre a un TSV (calibración de umbrales).

Uso: uv run python scripts/score_seed.py <salida.tsv> [--offline]
"""

import csv
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from authors_db.http import CachedClient
from authors_db.normalize import normalize
from authors_db.scoring import rank
from authors_db.wikidata import WikidataSource

SEED = Path("data/input/authors_seed.csv")


def main() -> None:
    out_path = Path(sys.argv[1])
    client = CachedClient(Path("data/cache/wikidata"), offline="--offline" in sys.argv)
    source = WikidataSource(client)
    with SEED.open(encoding="utf-8") as fh:
        names = [r["author_name"] for r in csv.DictReader(fh)]

    def run(name: str) -> list[str]:
        norm = normalize(name)
        if not norm.is_valid:
            return [name, "", "", "", "", "", "", "0", "invalid"]
        ranked = rank(norm.match_key, source.candidates(norm.clean_name))
        top = ranked[:2] + [None] * (2 - len(ranked[:2]))
        row = [name]
        for s in top:
            row += [s.candidate.qid, s.candidate.label, f"{s.score:.1f}"] if s else ["", "", ""]
        row += [str(len(ranked)), top[0].reason if top[0] else "no_candidates"]
        return row

    with ThreadPoolExecutor(max_workers=4) as pool, out_path.open("w", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["seed", "qid1", "label1", "score1", "qid2", "label2", "score2", "n", "reason1"])
        for i, row in enumerate(pool.map(run, names), 1):
            w.writerow(row)
            if i % 50 == 0:
                print(f"{i}/{len(names)}", flush=True)


if __name__ == "__main__":
    main()
