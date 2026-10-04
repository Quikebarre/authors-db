"""Scoring explícito y explicable de candidatos. Funciones puras."""

from dataclasses import dataclass

from rapidfuzz import fuzz

from authors_db.normalize import match_key
from authors_db.wikidata import Candidate

W_NAME = 0.65
W_WRITER = 15.0
W_OPEN_LIBRARY = 15.0
SITELINKS_MAX_BONUS = 3.0  # solo desempate
TOKEN_SET_CAP = 90.0


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: Candidate
    score: float
    name_similarity: float
    best_name: str
    reason: str


def name_similarity(key: str, names: list[str]) -> tuple[float, str]:
    """Mejor similitud (0-100) entre la clave y cualquier etiqueta/alias.

    token_set_ratio solo cuenta si la clave tiene >=2 tokens y se limita a 90, para que
    'homer' no iguale a 'homer simpson' pero 'leopoldo alas clarin' sí acerque 'leopoldo alas'.
    """
    best, best_name = 0.0, ""
    multi = len(key.split()) >= 2
    for name in names:
        other = match_key(name)
        if not other:
            continue
        sim = fuzz.ratio(key, other)
        if multi and len(other.split()) >= 2:
            sim = max(sim, min(fuzz.token_set_ratio(key, other), TOKEN_SET_CAP))
        if sim > best:
            best, best_name = sim, name
    return best, best_name


def score_candidate(key: str, cand: Candidate) -> ScoredCandidate:
    sim, best_name = name_similarity(key, cand.names)
    parts = [f"name={sim:.0f} ('{best_name}')"]
    score = W_NAME * sim
    if cand.is_writer:
        score += W_WRITER
        parts.append("writer+15")
    if cand.open_library_id:
        score += W_OPEN_LIBRARY
        parts.append("openlibrary+15")
    bonus = min(cand.sitelinks / 100, 1.0) * SITELINKS_MAX_BONUS
    score += bonus
    parts.append(f"sitelinks+{bonus:.1f}")
    if cand.via_pseudonym:
        parts.append(f"via pseudonym {cand.via_pseudonym}")
    return ScoredCandidate(cand, round(score, 1), sim, best_name, "; ".join(parts))


def rank(key: str, candidates: list[Candidate]) -> list[ScoredCandidate]:
    return sorted((score_candidate(key, c) for c in candidates), key=lambda s: -s.score)
