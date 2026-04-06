import pytest
from unittest.mock import patch, Mock

from hangman.controller.game_controller import GameController


# ==========================================================
# FIXTURES: CORE FACTORIES
# ==========================================================

@pytest.fixture
def view_factory():
    def _factory():
        view = Mock()

        view.prompt.return_value = ""
        view.prompt_hidden.return_value = ""
        view.display.return_value = None
        view.clear.return_value = None
        view.pause.return_value = None
        view.show_title.return_value = None
        view.show_health.return_value = None
        view.show_word.return_value = None
        view.get_choice.return_value = "1"

        return view
    return _factory


@pytest.fixture
def game_factory():
    def _factory():
        game = Mock()

        game.set_word.return_value = {"ok": True}
        game.create_players.return_value = {"ok": True}
        game.reset_for_new_round.return_value = {"ok": True}

        game.is_game_over.return_value = True
        game.remaining_players = 1
        game.n_players = 1
        game.remaining_spaces = 1

        player = Mock()
        player.name = "Alice"
        player.is_alive.return_value = True

        game.get_player.return_value = player
        game.get_visible_word.return_value = "_ _ _"
        game.word_label.return_value = "word"

        return game
    return _factory


@pytest.fixture
def word_repo_factory():
    def _factory():
        repo = Mock()
        repo.get_by_difficulty.return_value = "TEST"
        return repo
    return _factory


@pytest.fixture
def controller_factory(view_factory, game_factory, word_repo_factory):
    def _factory():
        view = view_factory()
        controller = GameController(view=view, constants_module=Mock())

        controller.game = game_factory()
        controller.word_repo = word_repo_factory()

        return controller, view
    return _factory


# ==========================================================
# CONFIGURATION METHODS
# ==========================================================

@pytest.mark.parametrize(
    "inputs, expected",
    [
        (["Y"], True),              # Accept normalization
        (["N"], False),             # Decline normalization
        (["invalid", "Y"], True),   # Invalid input followed by valid acceptance
    ],
)
def test_choose_normalization(controller_factory, inputs, expected):
    controller, view = controller_factory()
    view.prompt.side_effect = inputs

    result = controller.choose_normalization()

    assert result is expected


@pytest.mark.parametrize(
    "inputs, expected",
    [
        (["1"], "1"),       # Valid choice
        (["2"], "2"),       # Valid choice
        (["x", "2"], "2"),  # Invalid input followed by valid choice
    ],
)
def test_choose_word_source(controller_factory, inputs, expected):
    controller, view = controller_factory()
    view.prompt.side_effect = inputs

    result = controller.choose_word_source()

    assert result == expected


@pytest.mark.parametrize(
    "inputs, expected",
    [
        (["easy"], "EASY"),                 # Valid choice in lowercase
        (["HARD"], "HARD"),                 # Valid choice in uppercase
        (["wrong", "medium"], "MEDIUM"),    # Invalid input followed by valid choice
    ],
)
def test_choose_difficulty(controller_factory, inputs, expected):
    controller, view = controller_factory()
    view.prompt.side_effect = inputs

    result = controller.choose_difficulty()

    assert result == expected


@pytest.mark.parametrize(
    "inputs, expected",
    [
        (["Y"], True),              # Accept reset session
        (["N"], False),             # Decline reset session
        (["invalid", "N"], False),  # Invalid input followed by valid decline
    ],
)
def test_choose_reset_session(controller_factory, inputs, expected):
    controller, view = controller_factory()
    view.prompt.side_effect = inputs

    result = controller.choose_reset_session()

    assert result is expected


# ==========================================================
# ERROR DETECTION
# ==========================================================

def test_is_exhaustion_error_detects_correct_message(controller_factory):
    controller, _ = controller_factory()

    error = ValueError("No unused words remaining in repository")

    assert controller._is_exhaustion_error(error) is True


def test_is_exhaustion_error_rejects_other_errors(controller_factory):
    controller, _ = controller_factory()

    error = ValueError("Some other error")

    assert controller._is_exhaustion_error(error) is False


# ==========================================================
# SETUP GAME (CONFIGURATION FLOW)
# ==========================================================

def test_setup_game_retries_invalid_player_count(controller_factory):
    controller, view = controller_factory()

    mock_game = Mock()
    mock_game.set_word.return_value = {"ok": True}
    mock_game.create_players.return_value = {"ok": True}

    with patch("hangman.controller.game_controller.Game", return_value=mock_game):
        view.prompt.side_effect = [
            "Y",   # normalization
            "1",   # word source
            "0",   # invalid players
            "2",   # valid players
            "Alice",
            "Bob",
        ]

        view.prompt_hidden.return_value = "word"

        controller.setup_game()

    mock_game.create_players.assert_called_with(["Alice", "Bob"])


# ==========================================================
# GAME LOOP (MAIN CONTROL FLOW)
# ==========================================================

def test_run_game_loop_exits_when_game_over(controller_factory):
    controller, view = controller_factory()

    controller.game.is_game_over.return_value = True

    controller.run_game_loop()

    view.pause.assert_called()


def test_run_game_loop_handles_winner(controller_factory):
    controller, view = controller_factory()

    controller.game.is_game_over.side_effect = [False, True]
    controller.game.remaining_players = 1

    controller.handle_letter_guess = Mock(return_value={
        "game_won": True,
        "winner": 0,
    })

    view.prompt.return_value = "1"

    controller.run_game_loop()

    view.display.assert_any_call("Congratulations, Alice! You won!\n")


# ==========================================================
# LETTER HANDLER
# ==========================================================

def test_handle_letter_guess_correct(controller_factory):
    controller, view = controller_factory()

    controller.game.guess_letter.return_value = {
        "ok": True,
        "correct": True,
        "times": 2,
    }

    view.prompt.return_value = "a"

    result = controller.handle_letter_guess(0)

    assert result["correct"] is True
    view.display.assert_called()


def test_handle_letter_guess_incorrect_not_eliminated(controller_factory):
    controller, view = controller_factory()

    controller.game.guess_letter.return_value = {
        "ok": True,
        "correct": False,
        "eliminated": False,
    }

    view.prompt.return_value = "z"

    result = controller.handle_letter_guess(0)

    assert result["correct"] is False

    view.display.assert_any_call("Sorry, the letter 'Z' is not in the word.\n")

    for call in view.display.call_args_list:
        assert "has been eliminated" not in call.args[0]

    view.pause.assert_called()


def test_handle_letter_guess_incorrect_and_eliminated(controller_factory):
    controller, view = controller_factory()

    controller.game.guess_letter.return_value = {
        "ok": True,
        "correct": False,
        "eliminated": True,
    }

    view.prompt.return_value = "z"

    result = controller.handle_letter_guess(0)

    assert result["correct"] is False
    view.display.assert_any_call("Alice has been eliminated.\n")


def test_handle_letter_guess_repeat_retry(controller_factory):
    controller, view = controller_factory()

    controller.game.guess_letter.side_effect = [
        {"repeat": True, "error": "Repeated"},
        {"ok": True, "correct": True, "times": 1},
    ]

    view.prompt.side_effect = ["a", "b"]

    result = controller.handle_letter_guess(0)

    assert result["correct"] is True


def test_handle_letter_guess_non_recoverable_error(controller_factory):
    controller, view = controller_factory()

    controller.game.guess_letter.return_value = {
        "ok": False,
        "repeat": False,
        "error": "Invalid",
    }

    view.prompt.return_value = "!"

    result = controller.handle_letter_guess(0)

    assert result["ok"] is False
    view.pause.assert_called()


# ==========================================================
# WORD HANDLER
# ==========================================================

def test_handle_word_guess_correct(controller_factory):
    controller, view = controller_factory()

    controller.game.guess_word.return_value = {
        "ok": True,
        "correct": True,
    }

    view.prompt.return_value = "test"

    result = controller.handle_word_guess(0)

    assert result["correct"] is True


def test_handle_word_guess_incorrect_not_eliminated(controller_factory):
    controller, view = controller_factory()

    controller.game.guess_word.return_value = {
        "ok": True,
        "correct": False,
        "eliminated": False,
    }

    view.prompt.return_value = "wrong"

    result = controller.handle_word_guess(0)

    assert result["correct"] is False

    view.display.assert_any_call("Sorry, 'WRONG' is not the correct word.\n")

    for call in view.display.call_args_list:
        assert "has been eliminated" not in call.args[0]

    view.pause.assert_called()


def test_handle_word_guess_incorrect_and_eliminated(controller_factory):
    controller, view = controller_factory()

    controller.game.guess_word.return_value = {
        "ok": True,
        "correct": False,
        "eliminated": True,
    }

    view.prompt.return_value = "wrong"

    result = controller.handle_word_guess(0)

    assert result["correct"] is False
    view.display.assert_any_call("Alice has been eliminated.\n")


def test_handle_word_guess_repeat_retry(controller_factory):
    controller, view = controller_factory()

    controller.game.guess_word.side_effect = [
        {"repeat": True, "error": "Repeated"},
        {"ok": True, "correct": True},
    ]

    view.prompt.side_effect = ["repeated_guess", "valid_guess"]

    result = controller.handle_word_guess(0)

    assert result["correct"] is True


def test_handle_word_guess_non_recoverable_error(controller_factory):
    controller, view = controller_factory()

    controller.game.guess_word.return_value = {
        "ok": False,
        "repeat": False,
        "error": "Invalid",
    }

    view.prompt.return_value = "invalid!"

    result = controller.handle_word_guess(0)

    assert result["ok"] is False
    view.pause.assert_called()


# ==========================================================
# START METHOD (ENTRY POINT AND HIGH-LEVEL CONTROL FLOW)
# ==========================================================

def test_start_exits_when_user_declines_new_game(controller_factory):
    controller, view = controller_factory()

    controller.setup_game = Mock()
    controller.run_game_loop = Mock()
    controller.exit_game = Mock()

    view.prompt.side_effect = ["N"]

    controller.start()

    controller.exit_game.assert_called_once()


def test_start_resets_word_session(controller_factory):
    controller, view = controller_factory()

    controller.setup_game = Mock()
    controller.run_game_loop = Mock()

    view.prompt.side_effect = [
        "Y",    # continue
        "Y",    # reset session
        "1",    # word source
        "word", # new word
        "N",    # exit next loop
    ]

    controller.start()

    controller.word_repo.reset_session.assert_called()