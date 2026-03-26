import pytest
from hangman.model.game import Game


# -----------------------------
# FIXTURES
# -----------------------------

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


# -----------------------------
# INITIALIZATION TESTS
# -----------------------------

def test_game_initializes_remaining_letters(game):
    assert len(game.remaining_letters) == 26
    assert "A" in game.remaining_letters
    assert "Z" in game.remaining_letters

def test_extended_alphabet_when_normalization_disabled(constants):
    game = Game(constants, normalize_input=False)

    assert "Ñ" in game.remaining_letters
    assert "Á" in game.remaining_letters


# -----------------------------
# NORMALIZATION TESTS
# -----------------------------

@pytest.mark.parametrize(
    "input_text, expected",
    [
        (None, ""),                                 # None input
        ("hello", "HELLO"),                         # Basic lowercase
        ("canción", "CANCION"),                     # Accented characters
        ("áéíóú", "AEIOU"),                         # Multiple accents
        ("hola-mundo feliz", "HOLA-MUNDO FELIZ"),   # Phrase with hyphen and space
        (" Árbol-azúl ", " ARBOL-AZUL "),           # Leading/trailing whitespace
    ],
)
def test_normalization(game, input_text, expected):
    assert game._normalize(input_text) == expected

def test_normalize_disabled_keeps_accents(constants):
    game = Game(constants, normalize_input=False)

    result = game._normalize("canción")

    assert result == "CANCIÓN"


# -----------------------------
# WORD SETTING TESTS
# -----------------------------

@pytest.mark.parametrize(
    "word",
    [None, "   ", "A", "HELLO!"], # Invalid inputs: None, empty, single letter, invalid character
)
def test_set_word_invalid_inputs(game, word):
    result = game.set_word(word)

    assert result["ok"] is False

def test_set_word_initializes_masked_word(game):
    result = game.set_word("HELLO")

    assert result["ok"] is True
    assert game.unknown_word == ["_", "_", "_", "_", "_"]

def test_set_word_detects_phrase(game):
    game.set_word("HELLO WORLD")

    assert game.is_phrase is True
    assert game.remaining_spaces == 10


# -----------------------------
# RESET FOR NEW ROUND TESTS
# -----------------------------

def test_reset_for_new_round_success(prepared_game):
    prepared_game.players[0].health = 1
    prepared_game.remaining_letters.remove("A")
    prepared_game.remaining_players = 1

    # verify preconditions
    assert prepared_game.players[0].health == 1
    assert "A" not in prepared_game.remaining_letters
    assert prepared_game.remaining_players == 1

    result = prepared_game.reset_for_new_round("WORLD")

    assert result["ok"] is True
    assert prepared_game.word == "WORLD"

    assert prepared_game.players[0].health == prepared_game.players[0].max_health
    assert "A" in prepared_game.remaining_letters
    assert prepared_game.remaining_players == prepared_game.n_players

def test_reset_for_new_round_preserves_players(prepared_game):
    original_players = prepared_game.players

    prepared_game.reset_for_new_round("WORLD")

    assert prepared_game.players is original_players
    assert len(prepared_game.players) == 2

def test_reset_for_new_round_initializes_unknown_word(prepared_game):
    # verify initial state
    assert prepared_game.remaining_spaces == 5

    result = prepared_game.reset_for_new_round("PYTHON")

    assert result["ok"] is True
    assert prepared_game.unknown_word == ["_", "_", "_", "_", "_", "_"]
    assert prepared_game.remaining_spaces == 6

def test_reset_for_new_round_invalid_word(prepared_game):
    result = prepared_game.reset_for_new_round("A")

    assert result["ok"] is False

def test_reset_for_new_round_restores_remaining_letters(prepared_game):
    prepared_game.guess_letter(0, "H")
    prepared_game.guess_letter(0, "E")

    prepared_game.reset_for_new_round("WORLD")

    assert len(prepared_game.remaining_letters) == 26
    assert "H" in prepared_game.remaining_letters
    assert "E" in prepared_game.remaining_letters

def test_reset_for_new_round_restores_remaining_players(prepared_game):
    prepared_game.remaining_players = 1

    prepared_game.reset_for_new_round("WORLD")

    assert prepared_game.remaining_players == prepared_game.n_players


# -----------------------------
# PLAYER MANAGEMENT TESTS
# -----------------------------

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


# -----------------------------
# LETTER GUESSING TESTS
# -----------------------------

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


# -----------------------------
# WORD GUESSING TESTS
# -----------------------------

def test_guess_word_invalid_player_index(prepared_game):
    result = prepared_game.guess_word(5, "HELLO")

    assert result["ok"] is False
    assert result["repeat"] is False

def test_guess_word_rejects_eliminated_player(prepared_game):
    player = prepared_game.players[0]
    player.health = 0

    result = prepared_game.guess_word(0, "HELLO")

    assert result["ok"] is False
    assert result["repeat"] is False

def test_guess_word_invalid_guess_input(prepared_game):
    result = prepared_game.guess_word(0, None)

    assert result["ok"] is False
    assert result["repeat"] is True

def test_guess_word_rejects_invalid_characters(prepared_game):
    result = prepared_game.guess_word(0, "HELLO!")

    assert result["ok"] is False
    assert result["repeat"] is True

def test_guess_word_incorrect_guess(prepared_game):
    player = prepared_game.players[0]
    initial_health = player.health

    result = prepared_game.guess_word(0, "WORLD")

    assert result["ok"] is True
    assert result["correct"] is False
    assert player.health == initial_health - 1

def test_guess_word_eliminates_player(prepared_game):
    player = prepared_game.players[0]
    player.health = 1

    result = prepared_game.guess_word(0, "WORLD")

    assert result["eliminated"] is True
    assert prepared_game.remaining_players == 1

def test_guess_word_correct_guess(prepared_game):
    result = prepared_game.guess_word(0, "HELLO")

    assert result["ok"] is True
    assert result["correct"] is True
    assert result["game_won"] is True
    assert result["winner"] == 0
    assert prepared_game.remaining_spaces == 0
    assert prepared_game.unknown_word == list("HELLO")


# -----------------------------
# GAME STATE & UTILITY TESTS
# -----------------------------

def test_word_label_returns_word(game):
    game.set_word("HELLO")

    assert game.word_label() == "word"

def test_word_label_returns_phrase(game):
    game.set_word("HELLO WORLD")

    assert game.word_label() == "phrase"

def test_is_game_over_false_when_game_active(prepared_game):
    assert prepared_game.is_game_over() is False

def test_is_game_over_when_no_players_remaining(prepared_game):
    prepared_game.remaining_players = 0

    assert prepared_game.is_game_over() is True

def test_is_game_over_when_word_completed(prepared_game):
    prepared_game.remaining_spaces = 0

    assert prepared_game.is_game_over() is True

def test_get_visible_word_returns_current_mask(prepared_game):
    visible = prepared_game.get_visible_word()

    assert visible == ["_", "_", "_", "_", "_"]

def test_get_visible_word_returns_copy(prepared_game):
    visible = prepared_game.get_visible_word()

    visible[0] = "X"

    assert prepared_game.unknown_word[0] == "_"

def test_get_player_returns_player(prepared_game):
    player = prepared_game.get_player(0)

    assert player.name == "Alice"

def test_get_player_invalid_index(prepared_game):
    player = prepared_game.get_player(5)

    assert player is None

def test_get_player_negative_index(prepared_game):
    player = prepared_game.get_player(-1)

    assert player is None

def test_get_remaining_letters_initial(game):
    letters = game.get_remaining_letters()

    assert "A" in letters
    assert "Z" in letters
    assert len(letters) == 26

def test_get_remaining_letters_returns_copy(game):
    letters = game.get_remaining_letters()

    letters.remove("A")

    assert "A" in game.remaining_letters