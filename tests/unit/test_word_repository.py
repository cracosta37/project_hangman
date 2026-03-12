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

