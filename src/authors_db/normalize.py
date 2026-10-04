"""Normalización de nombres de autor. Funciones puras, sin I/O."""

import re
import unicodedata
from dataclasses import dataclass

from unidecode import unidecode

NOT_AN_AUTHOR = frozenset({"anonymous", "various authors", "various", "unknown", "n/a"})
_SUFFIXES = frozenset({"jr", "sr", "ii", "iii", "iv"})
_PUNCT_RE = re.compile(r"[^a-z0-9 ]")
_SPACES_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class NormalizedName:
    """Resultado de normalizar un seed_name. El original se conserva siempre."""

    seed_name: str
    clean_name: str
    match_key: str
    is_valid: bool
    invalid_reason: str | None = None


def clean_name(raw: str) -> str:
    """Trim, Unicode NFC, espacios colapsados y 'Apellido, Nombre' -> 'Nombre Apellido'."""
    text = _SPACES_RE.sub(" ", unicodedata.normalize("NFC", raw)).strip()
    if text.count(",") == 1:
        last, first = (part.strip() for part in text.split(","))
        # "Martin Luther King, Jr." es sufijo, no inversión.
        if last and first and first.lower().rstrip(".") not in _SUFFIXES:
            return f"{first} {last}"
    return text


def match_key(name: str) -> str:
    """Clave de comparación: sin acentos, minúsculas, sin puntuación, espacios simples."""
    ascii_name = unidecode(unicodedata.normalize("NFC", name)).lower()
    return _SPACES_RE.sub(" ", _PUNCT_RE.sub("", ascii_name)).strip()


def normalize(raw: str | None) -> NormalizedName:
    """Normaliza un seed_name y lo marca como inválido si no es un autor."""
    seed = raw or ""
    cleaned = clean_name(seed)
    key = match_key(cleaned)
    if not key:
        return NormalizedName(seed, cleaned, key, False, "empty")
    if key in NOT_AN_AUTHOR:
        return NormalizedName(seed, cleaned, key, False, "not_an_author")
    return NormalizedName(seed, cleaned, key, True)
