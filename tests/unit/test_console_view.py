import builtins
import os
import getpass
import pytest

from hangman.view.console_view import ConsoleView


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def view():
    """Default ConsoleView with clearing enabled."""
    return ConsoleView(use_clear=True)


@pytest.fixture
def view_no_clear():
    """ConsoleView with clearing disabled."""
    return ConsoleView(use_clear=False)


@pytest.fixture
def mock_player():
    """Factory-like semantic fixture for a mock player."""
    class Player:
        def __init__(self):
            self.health = 1
            self.hangman_states = ["state0", "state1", "state2"]

    return Player()


# ============================================================
# CLEAR METHOD
# ============================================================

@pytest.mark.parametrize("os_name,expected_cmd", [
    ("nt", "cls"),
    ("posix", "clear"),
])
def test_clear_executes_correct_command(view, monkeypatch, os_name, expected_cmd):
    calls = []

    def mock_system(cmd):
        calls.append(cmd)

    monkeypatch.setattr(os, "name", os_name)
    monkeypatch.setattr(os, "system", mock_system)

    view.clear()

    assert len(calls) == 1
    assert calls == [expected_cmd]


def test_clear_does_nothing_when_disabled(view_no_clear, monkeypatch):
    called = False

    def mock_system(cmd):
        nonlocal called
        called = True

    monkeypatch.setattr(os, "system", mock_system)

    view_no_clear.clear()

    assert called is False


# ============================================================
# DISPLAY & TITLE
# ============================================================

def test_display_prints_message(view, capsys):
    view.display("Hello")
    captured = capsys.readouterr()

    assert "Hello" in captured.out


def test_show_title_calls_clear_and_display(view, monkeypatch):
    clear_called = False
    display_called = False

    def mock_clear():
        nonlocal clear_called
        clear_called = True

    def mock_display(msg):
        nonlocal display_called
        display_called = True
        assert "*** HANGMAN ***" in msg

    monkeypatch.setattr(view, "clear", mock_clear)
    monkeypatch.setattr(view, "display", mock_display)

    view.show_title()

    assert clear_called
    assert display_called


# ============================================================
# PROMPT METHODS
# ============================================================

def test_prompt_returns_input(view, monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda msg: "user_input")

    result = view.prompt("Enter:")

    assert result == "user_input"


@pytest.mark.parametrize("exception", [KeyboardInterrupt, EOFError])
def test_prompt_handles_interrupt(view, monkeypatch, exception):
    def raise_exception(_):
        raise exception

    monkeypatch.setattr(builtins, "input", raise_exception)

    clear_called = False

    def mock_clear():
        nonlocal clear_called
        clear_called = True

    monkeypatch.setattr(view, "clear", mock_clear)

    with pytest.raises(SystemExit) as e:
        view.prompt("Enter:")

    assert e.value.code == 0
    assert clear_called


def test_prompt_hidden_returns_input(view, monkeypatch):
    monkeypatch.setattr(getpass, "getpass", lambda prompt: "secret")

    result = view.prompt_hidden("Password:")

    assert result == "secret"


@pytest.mark.parametrize("exception", [KeyboardInterrupt, EOFError])
def test_prompt_hidden_handles_interrupt(view, monkeypatch, exception):
    def raise_exception(prompt):
        raise exception

    monkeypatch.setattr(getpass, "getpass", raise_exception)

    clear_called = False

    def mock_clear():
        nonlocal clear_called
        clear_called = True

    monkeypatch.setattr(view, "clear", mock_clear)

    with pytest.raises(SystemExit) as e:
        view.prompt_hidden("Password:")

    assert e.value.code == 0
    assert clear_called


# ============================================================
# PAUSE
# ============================================================

def test_pause_waits_for_input(view, monkeypatch):
    called = False

    def mock_input(msg):
        nonlocal called
        called = True

    monkeypatch.setattr(builtins, "input", mock_input)

    view.pause()

    assert called


@pytest.mark.parametrize("exception", [KeyboardInterrupt, EOFError])
def test_pause_handles_interrupt(view, monkeypatch, exception):
    def raise_exception(_):
        raise exception

    monkeypatch.setattr(builtins, "input", raise_exception)

    clear_called = False

    def mock_clear():
        nonlocal clear_called
        clear_called = True

    monkeypatch.setattr(view, "clear", mock_clear)

    with pytest.raises(SystemExit) as e:
        view.pause()

    assert e.value.code == 0
    assert clear_called


# ============================================================
# WORD DISPLAY
# ============================================================

def test_show_word_formats_correctly(view, capsys):
    view.show_word(["H", "A", "N", "G"])

    captured = capsys.readouterr()

    assert "H A N G" in captured.out
    assert captured.out.startswith("    ")
    assert captured.out.endswith("\n\n")


def test_show_word_empty_list(view, capsys):
    view.show_word([])

    captured = capsys.readouterr()

    # Edge case: empty word still prints spacing and newline
    assert captured.out.strip() == ""


# ============================================================
# HEALTH DISPLAY
# ============================================================

def test_show_health_displays_correct_state(view, mock_player, capsys):
    view.show_health(mock_player)

    captured = capsys.readouterr()

    assert "state1" in captured.out


def test_show_health_prints_newline(view, mock_player, capsys):
    view.show_health(mock_player)

    captured = capsys.readouterr()

    # Ensures spacing consistency
    assert captured.out.endswith("\n\n")