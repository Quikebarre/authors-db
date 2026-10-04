import pytest

from authors_db.normalize import clean_name, match_key, normalize


def test_clean_name_with_surrounding_whitespace_trims_and_collapses():
    assert clean_name("  Isabel   Allende ") == "Isabel Allende"


def test_clean_name_with_decomposed_unicode_returns_nfc():
    decomposed = "García"
    assert clean_name(decomposed) == "García"


def test_clean_name_with_surname_first_returns_natural_order():
    assert clean_name("Borges, Jorge Luis") == "Jorge Luis Borges"


def test_clean_name_with_generational_suffix_is_not_inverted():
    assert clean_name("Martin Luther King, Jr.") == "Martin Luther King, Jr."


def test_clean_name_without_comma_is_unchanged():
    assert clean_name("Gabriel García Márquez") == "Gabriel García Márquez"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Gabriel García Márquez", "gabriel garcia marquez"),
        ("Ngũgĩ wa Thiong'o", "ngugi wa thiongo"),
        ("Kenzaburō Ōe", "kenzaburo oe"),
        ("Nguyễn Du", "nguyen du"),
        ("bell hooks", "bell hooks"),
        ("J. K. Rowling", "j k rowling"),
        ("Fiódor Dostoyevski", "fiodor dostoyevski"),
    ],
)
def test_match_key_strips_accents_case_and_punctuation(raw: str, expected: str):
    assert match_key(raw) == expected


def test_match_key_is_equal_for_accent_and_case_variants():
    assert match_key("Natsume Sōseki") == match_key("natsume soseki")


def test_normalize_keeps_original_seed_name():
    result = normalize("  bell hooks ")
    assert result.seed_name == "  bell hooks "
    assert result.clean_name == "bell hooks"
    assert result.is_valid


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        ("Anonymous", "not_an_author"),
        ("Various Authors", "not_an_author"),
        ("", "empty"),
        ("   ", "empty"),
        (None, "empty"),
    ],
)
def test_normalize_with_non_author_marks_invalid(raw: str | None, reason: str):
    result = normalize(raw)
    assert not result.is_valid
    assert result.invalid_reason == reason
