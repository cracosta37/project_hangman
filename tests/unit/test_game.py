import pytest
from hangman.model.game import Game

class DummyConstants:
    MAX_HEALTH = 3
    HANGMAN = ["H", "A", "N", "G", "M", "A", "N"]

@pytest.fixture
def constants():
    return DummyConstants()

@pytest.fixture
def game(constants):
    return Game(constants)

@pytest.fixture
def game_with_players(game):
    game.create_players(["Alice", "Bob"])
    return game

@pytest.fixture
def prepared_game(game_with_players):
    game_with_players.set_word("HELLO")
    return game_with_players

def test_game_initializes_remaining_letters(game):
    assert len(game.remaining_letters) == 26
    assert "A" in game.remaining_letters
    assert "Z" in game.remaining_letters

def test_extended_alphabet_when_normalization_disabled(constants):
    game = Game(constants, normalize_input=False)

    assert "Ñ" in game.remaining_letters
    assert "Á" in game.remaining_letters

def test_set_word_rejects_none(game):
    result = game.set_word(None)

    assert result["ok"] is False

def test_set_word_rejects_empty_string(game):
    result = game.set_word("   ")

    assert result["ok"] is False

def test_set_word_requires_at_least_two_letters(game):
    result = game.set_word("A")

    assert result["ok"] is False

def test_set_word_rejects_invalid_characters(game):
    result = game.set_word("HELLO!")

    assert result["ok"] is False

def test_set_word_initializes_masked_word(game):
    result = game.set_word("HELLO")

    assert result["ok"] is True
    assert game.unknown_word == ["_", "_", "_", "_", "_"]

def test_set_word_detects_phrase(game):
    game.set_word("HELLO WORLD")

    assert game.is_phrase is True
    assert game.remaining_spaces == 10

def test_create_players_requires_nonempty_list(game):
    result = game.create_players([])

    assert result["ok"] is False

def test_create_players_rejects_empty_names(game):
    result = game.create_players(["Alice", ""])

    assert result["ok"] is False

def test_create_players_requires_unique_names(game):
    result = game.create_players(["Alice", "alice"])

    assert result["ok"] is False

def test_create_players_success(game):
    result = game.create_players(["Alice", "Bob"])

    assert result["ok"] is True
    assert len(game.players) == 2
    assert game.remaining_players == 2
    assert game.players[0].name == "Alice"
    assert game.players[1].name == "Bob"

def test_guess_letter_invalid_player_index(prepared_game):
    result = prepared_game.guess_letter(5, "A")

    assert result["ok"] is False
    assert result["repeat"] is False

def test_guess_letter_invalid_input(prepared_game):
    result = prepared_game.guess_letter(0, "1")

    assert result["ok"] is False
    assert result["repeat"] is True

def test_guess_letter_detects_repeated_letter(prepared_game):
    prepared_game.guess_letter(0, "H")

    result = prepared_game.guess_letter(0, "H")

    assert result["ok"] is False
    assert result["repeat"] is True

def test_guess_letter_correct_guess(prepared_game):
    result = prepared_game.guess_letter(0, "H")

    assert result["ok"] is True
    assert result["correct"] is True
    assert result["positions"] == [0]
    assert prepared_game.unknown_word[0] == "H"

def test_guess_letter_incorrect_guess(prepared_game):
    player = prepared_game.players[0]
    initial_health = player.health

    result = prepared_game.guess_letter(0, "Z")

    assert result["ok"] is True
    assert result["correct"] is False
    assert result["positions"] == []
    assert player.health == initial_health - 1

def test_guess_letter_eliminates_player(prepared_game):
    player = prepared_game.players[0]
    player.health = 1

    result = prepared_game.guess_letter(0, "Z")

    assert result["eliminated"] is True
    assert prepared_game.remaining_players == 1

def test_guess_letter_wins_game(prepared_game):
    prepared_game.guess_letter(0, "H")
    prepared_game.guess_letter(0, "E")
    prepared_game.guess_letter(0, "L")

    result = prepared_game.guess_letter(0, "O")

    assert result["game_won"] is True
    assert result["winner"] == 0