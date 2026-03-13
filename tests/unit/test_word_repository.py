import json
import pytest
from hangman.services.word_repository import WordRepository

# -----------------------------
# Fixtures
# -----------------------------

@pytest.fixture
def valid_dict_word_file(tmp_path):
    data = {
        "easy": ["cat", "dog"],
        "medium": ["python", "hangman"],
        "hard": ["architecture"]
    }

    file_path = tmp_path / "words.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")

    return file_path

@pytest.fixture
def valid_list_word_file(tmp_path):
    data = ["apple", "banana", "cherry"]

    file_path = tmp_path / "words.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")

    return file_path

@pytest.fixture
def invalid_json_file(tmp_path):
    file_path = tmp_path / "words.json"
    file_path.write_text("{ invalid json }", encoding="utf-8")

    return file_path

@pytest.fixture
def nonexistent_file(tmp_path):
    return tmp_path / "missing.json"


# -----------------------------
# Initialization Tests
# -----------------------------

def test_init_with_valid_dict(valid_dict_word_file):
    repo = WordRepository(valid_dict_word_file)

    assert repo.file_path.exists()
    assert repo.used_words == set()

    assert set(repo.normalized_words_by_diff.keys()) == {"EASY", "MEDIUM", "HARD"}

    assert "CAT" in repo.normalized_words_by_diff["EASY"]
    assert "DOG" in repo.normalized_words_by_diff["EASY"]
    assert "PYTHON" in repo.normalized_words_by_diff["MEDIUM"]

def test_init_with_list_format(valid_list_word_file):
    repo = WordRepository(valid_list_word_file)

    assert repo.normalized_words_by_diff["MEDIUM"]
    assert "APPLE" in repo.normalized_words_by_diff["MEDIUM"]
    assert "BANANA" in repo.normalized_words_by_diff["MEDIUM"]

def test_init_missing_file_raises_error(nonexistent_file):
    with pytest.raises(FileNotFoundError):
        WordRepository(nonexistent_file)

def test_init_invalid_json_raises_error(invalid_json_file):
    with pytest.raises(ValueError):
        WordRepository(invalid_json_file)
