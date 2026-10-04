"""Thresholds and paths. This is the single place for these values."""

from pathlib import Path

MIN_MATCH_SCORE = 80.0  # A top score below this value gives the status `not_found`.
MIN_MARGIN = 10.0  # A margin below this value gives the status `ambiguous`.

SEED_PATH = Path("data/input/authors_seed.csv")
CACHE_DIR = Path("data/cache")
OUTPUT_DIR = Path("data/output")
DB_PATH = OUTPUT_DIR / "authors.duckdb"

# Rules for the rows with the status `ambiguous`.
DOMINANCE_RATIO = 3.0  # The winner needs this many times the sitelinks of the other candidate.
RESOLVED_CONFIDENCE_FACTOR = 0.8  # A row resolved after the rule gets a lower confidence.
MAX_CANDIDATES_FOR_ADJUDICATION = 4

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:7b-instruct-q4_K_M"
