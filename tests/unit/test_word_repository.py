import json
import pytest
from hangman.services.word_repository import WordRepository

# -----------------------------
# Fixtures
# -----------------------------

@pytest.fixture
def make_json_file(tmp_path):
    def _make(data, filename="words.json"):
        file_path = tmp_path / filename
        file_path.write_text(json.dumps(data), encoding="utf-8")
        return file_path
    return _make

@pytest.fixture
def valid_dict_word_file(make_json_file):
    return make_json_file({
        "easy": ["cat", "dog"],
        "medium": ["python", "hangman"],
        "hard": ["architecture"]
    })

@pytest.fixture
def valid_list_word_file(make_json_file):
    return make_json_file(["apple", "banana", "cherry"])

@pytest.fixture
def invalid_json_file(tmp_path):
    file_path = tmp_path / "words.json"
    file_path.write_text("{ invalid json }", encoding="utf-8")

    return file_path

@pytest.fixture
def nonexistent_file(tmp_path):
    return tmp_path / "missing.json"

@pytest.fixture
def invalid_root_integer(make_json_file):
    return make_json_file(123)

@pytest.fixture
def invalid_root_string(make_json_file):
    return make_json_file("hello world")

@pytest.fixture
def dict_with_multiple_difficulties(make_json_file):
    return make_json_file({
        "easy": ["cat"],
        "medium": ["dog"],
    })

@pytest.fixture
def equivalent_dict_and_list(make_json_file):
    data_list = ["apple", "banana", "cherry"]
    data_dict = {"medium": data_list}

    return (
        make_json_file(data_list, filename="list.json"),
        make_json_file(data_dict, filename="dict.json"),
    )

@pytest.fixture
def large_mixed_list(make_json_file):
    data = ["validword"] * 50 + ["!", "", 123, None] * 50
    return make_json_file(data)

@pytest.fixture
def list_with_overlong_word(make_json_file):
    return make_json_file([
        "a" * 121,
        "validword"
    ])

@pytest.fixture
def dict_with_unknown_difficulty(make_json_file):
    return make_json_file({
        "easy": ["cat"],
        "impossible": ["dragon"]
    })

@pytest.fixture
def dict_with_mixed_entries(make_json_file):
    return make_json_file({
        "easy": ["cat", 123, "", "a", "dog!", "bird"],
        "medium": ["python", None, "ok"],
    })

@pytest.fixture
def dict_with_non_string_keys(make_json_file):
    return make_json_file({
        "easy": ["cat"],
        123: ["dog"],
    })

@pytest.fixture
def dict_with_non_list_values(make_json_file):
    return make_json_file({
        "easy": "cat",
        "medium": ["python"]
    })

@pytest.fixture
def dict_with_mixed_case_keys(make_json_file):
    return make_json_file({
        "Easy": ["cat"],
        "MeDiUm": ["python"],
        "HARD": ["architecture"]
    })

@pytest.fixture
def dict_with_only_invalid_entries(make_json_file):
    return make_json_file({
        "easy": ["!", "", 123]
    })

@pytest.fixture
def list_with_mixed_entries(make_json_file):
    return make_json_file([
        "apple",
        "banana",
        "",
        "a",
        "dog!",
        123,
        "cherry"
    ])

@pytest.fixture
def list_with_only_invalid_entries(make_json_file):
    return make_json_file([
        "", "!", 123, None, "a"
    ])


@pytest.fixture
def list_with_duplicates_and_variants(make_json_file):
    return make_json_file([
        "apple",
        "Apple",
        "  apple  ",
        "ápple"
    ])

@pytest.fixture
def empty_repo(tmp_path):
    file_path = tmp_path / "empty.json"
    file_path.write_text("[]", encoding="utf-8")
    return WordRepository(file_path)


# -----------------------------
# Initialization Tests
# -----------------------------

def test_init_with_valid_dict(valid_dict_word_file):
    repo = WordRepository(valid_dict_word_file)

    assert repo.file_path.exists()
    assert repo.used_words == set()
    assert set(repo.normalized_words_by_diff.keys()) == {"EASY", "MEDIUM", "HARD"}

def test_init_with_list_format(valid_list_word_file):
    repo = WordRepository(valid_list_word_file)

    assert repo.file_path.exists()
    assert repo.used_words == set()

def test_init_missing_file_raises_error(nonexistent_file):
    with pytest.raises(FileNotFoundError):
        WordRepository(nonexistent_file)

def test_init_invalid_json_raises_error(invalid_json_file):
    with pytest.raises(ValueError):
        WordRepository(invalid_json_file)


#-----------------------------
# Loading and Validation Tests
#-----------------------------

def test_load_dict_structure(valid_dict_word_file):
    repo = WordRepository(valid_dict_word_file)

    assert repo.normalized_words_by_diff["EASY"] == {"CAT", "DOG"}
    assert repo.normalized_words_by_diff["MEDIUM"] == {"PYTHON", "HANGMAN"}
    assert repo.normalized_words_by_diff["HARD"] == {"ARCHITECTURE"}

def test_load_list_structure(valid_list_word_file):
    repo = WordRepository(valid_list_word_file)

    assert repo.normalized_words_by_diff["MEDIUM"] == {
        "APPLE", "BANANA", "CHERRY"
    }

    assert repo.normalized_words_by_diff["EASY"] == set()
    assert repo.normalized_words_by_diff["HARD"] == set()

def test_load_invalid_root_integer(invalid_root_integer):
    with pytest.raises(TypeError):
        WordRepository(invalid_root_integer)

def test_load_invalid_root_string(invalid_root_string):
    with pytest.raises(TypeError):
        WordRepository(invalid_root_string)

def test_list_and_dict_loading_are_equivalent(equivalent_dict_and_list):
    list_file, dict_file = equivalent_dict_and_list

    repo_list = WordRepository(list_file)
    repo_dict = WordRepository(dict_file)

    assert repo_list.normalized_words_by_diff["MEDIUM"] == \
           repo_dict.normalized_words_by_diff["MEDIUM"]

def test_add_if_valid_respects_target_difficulty(dict_with_multiple_difficulties):
    repo = WordRepository(dict_with_multiple_difficulties)

    assert repo.normalized_words_by_diff["EASY"] == {"CAT"}
    assert repo.normalized_words_by_diff["MEDIUM"] == {"DOG"}
    assert repo.normalized_words_by_diff["HARD"] == set()

def test_large_input_filters_correctly(large_mixed_list):
    repo = WordRepository(large_mixed_list)

    assert repo.normalized_words_by_diff["MEDIUM"] == {"VALIDWORD"}

def test_load_from_list_rejects_overlong_words(list_with_overlong_word):
    repo = WordRepository(list_with_overlong_word)

    assert repo.normalized_words_by_diff["MEDIUM"] == {"VALIDWORD"}

def test_unknown_difficulty_keys_are_ignored(dict_with_unknown_difficulty):
    repo = WordRepository(dict_with_unknown_difficulty)

    assert repo.normalized_words_by_diff["EASY"] == {"CAT"}
    assert repo.normalized_words_by_diff["MEDIUM"] == set()
    assert repo.normalized_words_by_diff["HARD"] == set()

def test_invalid_entries_are_filtered_across_difficulties(dict_with_mixed_entries):
    repo = WordRepository(dict_with_mixed_entries)

    assert repo.normalized_words_by_diff["EASY"] == {"CAT", "BIRD"}
    assert repo.normalized_words_by_diff["MEDIUM"] == {"PYTHON", "OK"}

def test_load_from_dict_ignores_non_string_keys(dict_with_non_string_keys):
    repo = WordRepository(dict_with_non_string_keys)

    assert repo.normalized_words_by_diff["EASY"] == {"CAT"}

def test_load_from_dict_ignores_non_list_values(dict_with_non_list_values):
    repo = WordRepository(dict_with_non_list_values)

    assert repo.normalized_words_by_diff["EASY"] == set()
    assert repo.normalized_words_by_diff["MEDIUM"] == {"PYTHON"}

def test_load_from_dict_normalizes_keys(dict_with_mixed_case_keys):
    repo = WordRepository(dict_with_mixed_case_keys)

    assert repo.normalized_words_by_diff["EASY"] == {"CAT"}
    assert repo.normalized_words_by_diff["MEDIUM"] == {"PYTHON"}
    assert repo.normalized_words_by_diff["HARD"] == {"ARCHITECTURE"}

def test_load_from_dict_empty_valid_result(dict_with_only_invalid_entries):
    repo = WordRepository(dict_with_only_invalid_entries)

    assert repo.normalized_words_by_diff["EASY"] == set()

def test_load_from_list_filters_invalid_entries(list_with_mixed_entries):
    repo = WordRepository(list_with_mixed_entries)

    assert repo.normalized_words_by_diff["MEDIUM"] == {
        "APPLE", "BANANA", "CHERRY"
    }

def test_load_from_list_only_invalid_entries_results_empty(list_with_only_invalid_entries):
    repo = WordRepository(list_with_only_invalid_entries)

    assert repo.normalized_words_by_diff["MEDIUM"] == set()

def test_load_from_list_deduplicates_and_normalizes(list_with_duplicates_and_variants):
    repo = WordRepository(list_with_duplicates_and_variants)

    assert repo.normalized_words_by_diff["MEDIUM"] == {"APPLE"}

def test_load_from_list_does_not_affect_other_difficulties(valid_list_word_file):
    repo = WordRepository(valid_list_word_file)

    assert repo.normalized_words_by_diff["EASY"] == set()
    assert repo.normalized_words_by_diff["HARD"] == set()

def test_validate_normalize_valid_word(empty_repo):
    result = empty_repo._validate_normalize("cat")

    assert result == "CAT"

def test_validate_normalize_strips_and_uppercases(empty_repo):
    result = empty_repo._validate_normalize("  dog  ")

    assert result == "DOG"

def test_validate_normalize_collapses_spaces(empty_repo):
    result = empty_repo._validate_normalize("hello   world")

    assert result == "HELLO WORLD"

def test_validate_normalize_removes_diacritics(empty_repo):
    result = empty_repo._validate_normalize("café")

    assert result == "CAFE"

def test_validate_normalize_allows_hyphens(empty_repo):
    result = empty_repo._validate_normalize("well-being")

    assert result == "WELL-BEING"

@pytest.mark.parametrize("value", [123, None, ["list"], {"key": "value"}])
def test_validate_normalize_rejects_non_string(empty_repo, value):
    assert empty_repo._validate_normalize(value) is None

@pytest.mark.parametrize("value", ["", "   ", "\n", "\t"])
def test_validate_normalize_rejects_empty_strings(empty_repo, value):
    assert empty_repo._validate_normalize(value) is None

@pytest.mark.parametrize("value", [
    "dog!",
    "hello123",
    "test@case",
    "name#",
])
def test_validate_normalize_rejects_invalid_characters(empty_repo, value):
    assert empty_repo._validate_normalize(value) is None

@pytest.mark.parametrize("value", [
    "a",
    "-",
    " - ",
])
def test_validate_normalize_requires_minimum_alpha(empty_repo, value):
    assert empty_repo._validate_normalize(value) is None

def test_validate_normalize_rejects_overlong_strings(empty_repo):
    value = "a" * 121

    assert empty_repo._validate_normalize(value) is None

def test_validate_normalize_accepts_max_length(empty_repo):
    value = "a" * 120

    result = empty_repo._validate_normalize(value)

    assert result == "A" * 120


# -------------------------
# Normalization Tests
#--------------------------

@pytest.mark.parametrize("input_text,expected", [
    ("hello", "HELLO"),                             # Uppercases
    ("  hello   world  ", "HELLO WORLD"),           # Collapses and strips spaces
    ("café", "CAFE"),                               # Removes diacritics
    ("Árbol Niño", "ARBOL NINO"),                   # Handles complex unicode
    ("hello\tworld\npython", "HELLO WORLD PYTHON"), # Handles tabs and newlines
    ("well-being", "WELL-BEING"),                   # Preserves hyphens
    ("e\u0301", "E"),                               # Removes combining marks
    ("\u0301\u0301", "")                            # Only combining marks
])
def test_normalize_for_internal_parametrized(input_text, expected):
    result = WordRepository._normalize_for_internal(input_text)

    assert result == expected

def test_normalize_for_internal_is_idempotent():
    text = "HELLO WORLD"

    result = WordRepository._normalize_for_internal(text)

    assert result == text