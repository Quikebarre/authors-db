"""Functions that normalize author names. The functions have no input or output side effects."""

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
    """Result of the normalization of a seed name. The original seed name is always kept."""

    seed_name: str
    clean_name: str
    match_key: str
    is_valid: bool
    invalid_reason: str | None = None


def clean_name(raw: str) -> str:
    """Trim the name, apply Unicode NFC, and change 'Last, First' to 'First Last'."""
    text = _SPACES_RE.sub(" ", unicodedata.normalize("NFC", raw)).strip()
    if text.count(",") == 1:
        last, first = (part.strip() for part in text.split(","))
        # "Martin Luther King, Jr." es sufijo, no inversión.
        if last and first and first.lower().rstrip(".") not in _SUFFIXES:
            return f"{first} {last}"
    return text


def match_key(name: str) -> str:
    """Return a comparison key in lowercase ASCII with no punctuation and single spaces."""
    ascii_name = unidecode(unicodedata.normalize("NFC", name)).lower()
    return _SPACES_RE.sub(" ", _PUNCT_RE.sub("", ascii_name)).strip()


def normalize(raw: str | None) -> NormalizedName:
    """Normalize a seed name. Mark the name as invalid if it is not an author."""
    seed = raw or ""
    cleaned = clean_name(seed)
    key = match_key(cleaned)
    if not key:
        return NormalizedName(seed, cleaned, key, False, "empty")
    if key in NOT_AN_AUTHOR:
        return NormalizedName(seed, cleaned, key, False, "not_an_author")
    return NormalizedName(seed, cleaned, key, True)
