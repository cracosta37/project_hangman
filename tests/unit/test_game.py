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