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
        123: ["dog"],  # JSON forces keys to strings
    })

@pytest.fixture
def dict_with_non_list_values(make_json_file):
    return make_json_file({
        "easy": "cat",  # invalid
        "medium": ["python"]
    })


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

def test_unknown_difficulty_keys_are_ignored(dict_with_unknown_difficulty):
    repo = WordRepository(dict_with_unknown_difficulty)

    assert repo.normalized_words_by_diff["EASY"] == {"CAT"}
    assert repo.normalized_words_by_diff["MEDIUM"] == set()
    assert repo.normalized_words_by_diff["HARD"] == set()

def test_invalid_entries_are_filtered_across_difficulties(dict_with_mixed_entries):
    repo = WordRepository(dict_with_mixed_entries)

    assert repo.normalized_words_by_diff["EASY"] == {"CAT", "BIRD"}
    assert repo.normalized_words_by_diff["MEDIUM"] == {"PYTHON", "OK"}