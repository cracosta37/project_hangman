import json
import pytest
from unittest.mock import patch
from hangman.services.word_repository import WordRepository


# -----------------------------
# Core Fixtures (Factories)
# -----------------------------

@pytest.fixture
def make_json_file(tmp_path):
    def _make(data, filename="words.json"):
        file_path = tmp_path / filename
        file_path.write_text(json.dumps(data), encoding="utf-8")
        return file_path
    return _make


@pytest.fixture
def make_repo(make_json_file):
    def _make(data):
        return WordRepository(make_json_file(data))
    return _make


# -----------------------------
# Semantic Fixtures
# -----------------------------

@pytest.fixture
def repo_with_words(make_repo):
    return make_repo({
        "easy": ["cat", "dog"],
        "medium": ["python"],
        "hard": ["architecture"]
    })


@pytest.fixture
def repo_single_word(make_repo):
    return make_repo({
        "easy": ["cat"]
    })


@pytest.fixture
def empty_repo(tmp_path):
    file_path = tmp_path / "empty.json"
    file_path.write_text("[]", encoding="utf-8")
    return WordRepository(file_path)


# -----------------------------
# Initialization Tests
# -----------------------------

def test_init_with_valid_dict(make_repo):
    repo = make_repo({
        "easy": ["cat"],
        "medium": ["python"],
        "hard": ["architecture"]
    })

    assert repo.used_words == set()
    assert set(repo.normalized_words_by_diff.keys()) == {"EASY", "MEDIUM", "HARD"}


def test_init_with_list_format(make_repo):
    repo = make_repo(["apple", "banana"])

    assert repo.used_words == set()


def test_init_missing_file_raises_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        WordRepository(tmp_path / "missing.json")


def test_init_invalid_json_raises_error(tmp_path):
    file_path = tmp_path / "words.json"
    file_path.write_text("{ invalid json }", encoding="utf-8")

    with pytest.raises(ValueError):
        WordRepository(file_path)


@pytest.mark.parametrize("invalid_root", [123, "hello"])
def test_invalid_root_types(make_repo, invalid_root):
    with pytest.raises(TypeError):
        make_repo(invalid_root)


# -----------------------------
# Loading Tests
# -----------------------------

def test_load_dict_structure(make_repo):
    repo = make_repo({
        "easy": ["cat", "dog"],
        "medium": ["python"],
        "hard": ["architecture"]
    })

    assert repo.normalized_words_by_diff["EASY"] == {"CAT", "DOG"}
    assert repo.normalized_words_by_diff["MEDIUM"] == {"PYTHON"}
    assert repo.normalized_words_by_diff["HARD"] == {"ARCHITECTURE"}


def test_load_list_structure(make_repo):
    repo = make_repo(["apple", "banana"])

    assert repo.normalized_words_by_diff["MEDIUM"] == {"APPLE", "BANANA"}
    assert repo.normalized_words_by_diff["EASY"] == set()
    assert repo.normalized_words_by_diff["HARD"] == set()


@pytest.mark.parametrize("data,expected", [
    (["apple", "", "banana", "!"], {"APPLE", "BANANA"}),
    (["!", "", None], set()),
])
def test_load_from_list_filtering(make_repo, data, expected):
    repo = make_repo(data)
    assert repo.normalized_words_by_diff["MEDIUM"] == expected


def test_load_from_list_deduplication(make_repo):
    repo = make_repo(["apple", "Apple", "ápple", " apple "])
    assert repo.normalized_words_by_diff["MEDIUM"] == {"APPLE"}


def test_load_from_list_rejects_overlong(make_repo):
    repo = make_repo(["a" * 121, "valid"])
    assert repo.normalized_words_by_diff["MEDIUM"] == {"VALID"}


def test_dict_and_list_equivalence(make_json_file):
    list_file = make_json_file(["apple", "banana"])
    dict_file = make_json_file({"medium": ["apple", "banana"]})

    repo_list = WordRepository(list_file)
    repo_dict = WordRepository(dict_file)

    assert repo_list.normalized_words_by_diff["MEDIUM"] == \
           repo_dict.normalized_words_by_diff["MEDIUM"]


@pytest.mark.parametrize("data,expected_easy,expected_medium", [
    (
        {"easy": ["cat", 123, "", "bird"], "medium": ["python", None]},
        {"CAT", "BIRD"},
        {"PYTHON"},
    ),
])
def test_dict_filtering(make_repo, data, expected_easy, expected_medium):
    repo = make_repo(data)

    assert repo.normalized_words_by_diff["EASY"] == expected_easy
    assert repo.normalized_words_by_diff["MEDIUM"] == expected_medium


# -----------------------------
# Validation Tests
# -----------------------------

@pytest.mark.parametrize("value,expected", [
    ("cat", "CAT"),
    ("  dog  ", "DOG"),
    ("hello   world", "HELLO WORLD"),
    ("café", "CAFE"),
    ("well-being", "WELL-BEING"),
])
def test_validate_normalize_valid_cases(empty_repo, value, expected):
    assert empty_repo._validate_normalize(value) == expected


@pytest.mark.parametrize("value", [
    123, None, [], {},
    "", "   ",
    "dog!", "hello123",
    "a", "-", " - ",
])
def test_validate_normalize_invalid_cases(empty_repo, value):
    assert empty_repo._validate_normalize(value) is None


def test_validate_normalize_length_bounds(empty_repo):
    assert empty_repo._validate_normalize("a" * 121) is None
    assert empty_repo._validate_normalize("a" * 120) == "A" * 120


# -----------------------------
# Normalization Tests
# -----------------------------

@pytest.mark.parametrize("input_text,expected", [
    ("hello", "HELLO"),
    ("  hello   world  ", "HELLO WORLD"),
    ("café", "CAFE"),
    ("Árbol Niño", "ARBOL NINO"),
    ("hello\tworld\npython", "HELLO WORLD PYTHON"),
    ("well-being", "WELL-BEING"),
    ("e\u0301", "E"),
    ("\u0301\u0301", ""),
])
def test_normalize_for_internal(input_text, expected):
    assert WordRepository._normalize_for_internal(input_text) == expected


def test_normalize_for_internal_idempotent():
    text = "HELLO WORLD"
    assert WordRepository._normalize_for_internal(text) == text


# -----------------------------
# Public API Tests
# -----------------------------

def test_get_by_difficulty_returns_valid(repo_with_words):
    assert repo_with_words.get_by_difficulty("easy") in {"CAT", "DOG"}


def test_get_by_difficulty_normalizes_input(repo_with_words):
    assert repo_with_words.get_by_difficulty("  Easy ") in {"CAT", "DOG"}


def test_get_by_difficulty_marks_used(repo_with_words):
    word = repo_with_words.get_by_difficulty("easy")
    assert word in repo_with_words.used_words


def test_get_by_difficulty_no_repeats(repo_with_words):
    results = {
        repo_with_words.get_by_difficulty("easy"),
        repo_with_words.get_by_difficulty("easy")
    }
    assert results == {"CAT", "DOG"}


def test_get_by_difficulty_exhaustion(repo_single_word):
    repo_single_word.get_by_difficulty("easy")

    with pytest.raises(ValueError):
        repo_single_word.get_by_difficulty("easy")


@pytest.mark.parametrize("value", [123, None, [], {}])
def test_get_by_difficulty_requires_string(repo_with_words, value):
    with pytest.raises(TypeError):
        repo_with_words.get_by_difficulty(value)


def test_get_by_difficulty_invalid_key(repo_with_words):
    with pytest.raises(ValueError):
        repo_with_words.get_by_difficulty("invalid")


def test_get_by_difficulty_empty_bucket(make_repo):
    repo = make_repo({"easy": ["cat"]})

    with pytest.raises(ValueError):
        repo.get_by_difficulty("medium")


def test_get_by_difficulty_isolation(repo_with_words):
    easy_word = repo_with_words.get_by_difficulty("easy")
    medium_word = repo_with_words.get_by_difficulty("medium")

    assert easy_word in {"CAT", "DOG"}
    assert medium_word == "PYTHON"


def test_get_by_difficulty_single_deterministic(repo_single_word):
    assert repo_single_word.get_by_difficulty("easy") == "CAT"


def test_get_by_difficulty_mocked_random(repo_with_words):
    with patch("random.choice", return_value="CAT"):
        assert repo_with_words.get_by_difficulty("easy") == "CAT"