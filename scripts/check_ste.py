"""Check Markdown files and Python docstrings against a subset of the STE writing rules.

Usage: uv run python scripts/check_ste.py [path ...]
The script does not check the vocabulary. It checks sentence length, "-ing" words,
contractions, phrasal verbs and paragraph length.
"""

import ast
import re
import sys
from pathlib import Path

MAX_PROCEDURE_WORDS = 20
MAX_DESCRIPTION_WORDS = 25
MAX_PARAGRAPH_SENTENCES = 6
ING_ALLOWED = frozenset(
    {
        "string",
        "during",
        "thing",
        "nothing",
        "something",
        "anything",
        "warning",
        "rowling",
        "embedding",
    }
)
PHRASAL_VERBS = (
    "set up",
    "carry out",
    "find out",
    "look up",
    "turn on",
    "turn off",
    "pick up",
    "write down",
    "fill in",
    "check out",
    "break down",
    "figure out",
    "come up",
)
CODE_RE = re.compile(r"`[^`]*`")
LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
CONTRACTION_RE = re.compile(r"\b\w+(n't|'re|'ll|'ve|'d|'m)\b", re.IGNORECASE)
NUMBERED_RE = re.compile(r"^\s*\d+\.\s+")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9`\"(])")
WORD_RE = re.compile(r"[A-Za-z0-9_'\-]+")
ING_RE = re.compile(r"\b[A-Za-z]{3,}ing\b")


def clean(text: str) -> str:
    """Replace code spans with one word and keep the text of links."""
    return CODE_RE.sub("CODE", LINK_RE.sub(r"\1", text)).replace("**", "").replace("*", "")


def check_sentences(text: str, limit: int, where: str) -> list[str]:
    problems = []
    for sentence in SENTENCE_SPLIT_RE.split(clean(text).strip()):
        words = WORD_RE.findall(sentence)
        if len(words) > limit:
            problems.append(f"{where}: {len(words)} words (max {limit}): {sentence[:70]}...")
        for word in ING_RE.findall(sentence):
            if word.lower() not in ING_ALLOWED:
                problems.append(f"{where}: '-ing' word '{word}'")
        if CONTRACTION_RE.search(sentence):
            problems.append(f"{where}: contraction in: {sentence[:60]}")
        lowered = sentence.lower()
        problems.extend(f"{where}: phrasal verb '{p}'" for p in PHRASAL_VERBS if p in lowered)
    return problems


def markdown_blocks(path: Path) -> list[tuple[int, str, bool]]:
    """Return (line number, text, is_numbered_item) for each paragraph or list item."""
    blocks: list[tuple[int, str, bool]] = []
    current: list[str] = []
    start = 0
    in_code = False

    def flush() -> None:
        if current:
            blocks.append((start, " ".join(current), False))
            current.clear()

    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            flush()
            in_code = not in_code
            continue
        if in_code or stripped.startswith(("#", "|", ">", "---")) or not stripped:
            flush()
            continue
        if NUMBERED_RE.match(line):
            flush()
            blocks.append((number, NUMBERED_RE.sub("", line), True))
        elif stripped.startswith(("- ", "* ")):
            flush()
            blocks.append((number, stripped[2:], False))
        else:
            if not current:
                start = number
            current.append(stripped)
    flush()
    return blocks


def check_markdown(path: Path) -> list[str]:
    problems = []
    for number, text, numbered in markdown_blocks(path):
        where = f"{path}:{number}"
        limit = MAX_PROCEDURE_WORDS if numbered else MAX_DESCRIPTION_WORDS
        problems += check_sentences(text, limit, where)
        count = len(SENTENCE_SPLIT_RE.split(clean(text).strip()))
        if count > MAX_PARAGRAPH_SENTENCES:
            problems.append(f"{where}: paragraph has {count} sentences (max 6)")
    return problems


def check_python(path: Path) -> list[str]:
    problems = []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            doc = ast.get_docstring(node)
            if doc and not getattr(node, "name", "_").startswith("_"):
                where = f"{path}:{getattr(node, 'lineno', 1)}"
                problems += check_sentences(" ".join(doc.split()), MAX_DESCRIPTION_WORDS, where)
    return problems


def main() -> int:
    targets = [Path(a) for a in sys.argv[1:]] or [Path("README.md"), Path("docs"), Path("src")]
    files = [f for t in targets for f in ([t] if t.is_file() else sorted(t.rglob("*")))]
    problems = []
    for f in files:
        if f.suffix == ".md":
            problems += check_markdown(f)
        elif f.suffix == ".py":
            problems += check_python(f)
    print("\n".join(problems) if problems else "No problems found.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
