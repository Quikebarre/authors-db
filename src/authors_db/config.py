"""Thresholds and paths. This is the single place for these values."""

from pathlib import Path

MIN_MATCH_SCORE = 80.0  # A top score below this value gives the status `not_found`.
MIN_MARGIN = 10.0  # A margin below this value gives the status `ambiguous`.

SEED_PATH = Path("data/input/authors_seed.csv")
CACHE_DIR = Path("data/cache")
OUTPUT_DIR = Path("data/output")
DB_PATH = OUTPUT_DIR / "authors.duckdb"
