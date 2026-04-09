import pytest
from typing import List
from hangman.view.view_interface import View


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def view_instance():
    """Provides a fresh instance of the View interface."""
    return View()


# ============================================================
# PARAMETRIZED CONTRACT TESTS (NotImplementedError)
# ============================================================

@pytest.mark.parametrize(
    "method_name, args",
    [
        ("display", ("Hello",)),
        ("show_title", ()),
        ("prompt", ("Enter something:",)),
        ("prompt_hidden", ("Enter secret:",)),
        ("pause", ()),
        ("pause", ("Custom pause message",)),
        ("clear", ()),
        ("show_word", (["a", "_", "c"],)),
        ("show_word", ([],)),  # edge case: empty list
        ("show_health", (object(),)),  # generic player object
    ],
)
def test_all_methods_raise_not_implemented(view_instance, method_name, args):
    """
    Ensure every interface method raises NotImplementedError.
    This enforces the abstract contract.
    """
    method = getattr(view_instance, method_name)

    with pytest.raises(NotImplementedError):
        method(*args)


# ============================================================
# METHOD SIGNATURE VALIDATION
# ============================================================

def test_display_requires_message(view_instance):
    """display() should require exactly one argument."""
    with pytest.raises(TypeError):
        view_instance.display()


def test_prompt_requires_message(view_instance):
    """prompt() should require exactly one argument."""
    with pytest.raises(TypeError):
        view_instance.prompt()


def test_prompt_hidden_requires_message(view_instance):
    """prompt_hidden() should require exactly one argument."""
    with pytest.raises(TypeError):
        view_instance.prompt_hidden()


def test_show_word_requires_list(view_instance):
    """show_word() should require one argument."""
    with pytest.raises(TypeError):
        view_instance.show_word()


def test_show_health_requires_player(view_instance):
    """show_health() should require one argument."""
    with pytest.raises(TypeError):
        view_instance.show_health()


# ============================================================
# DEFAULT ARGUMENT BEHAVIOR
# ============================================================

def test_pause_default_argument(view_instance):
    """
    pause() should accept zero arguments due to default value.
    Still raises NotImplementedError due to abstract interface.
    """
    with pytest.raises(NotImplementedError):
        view_instance.pause()


def test_pause_custom_argument(view_instance):
    """
    pause() should accept a custom message argument.
    """
    with pytest.raises(NotImplementedError):
        view_instance.pause("Wait...")


# ============================================================
# EDGE CASE INPUT VALIDATION
# ============================================================

@pytest.mark.parametrize(
    "message",
    ["", " ", "Test message"],
)
def test_display_edge_cases(view_instance, message):
    """display() should handle various string inputs (contract-level)."""
    with pytest.raises(NotImplementedError):
        view_instance.display(message)


@pytest.mark.parametrize(
    "word_state",
    [
        [],
        ["_"],
        ["a", "b", "c"],
    ],
)
def test_show_word_edge_cases(view_instance, word_state: List[str]):
    """show_word() should accept various list structures."""
    with pytest.raises(NotImplementedError):
        view_instance.show_word(word_state)


# ============================================================
# INTERFACE CONSISTENCY TESTS
# ============================================================

def test_all_methods_exist():
    """
    Ensure the View interface defines all expected methods.
    This protects against accidental interface regression.
    """
    expected_methods = {
        "display",
        "show_title",
        "prompt",
        "prompt_hidden",
        "pause",
        "clear",
        "show_word",
        "show_health",
    }

    actual_methods = {
        method for method in dir(View)
        if callable(getattr(View, method)) and not method.startswith("__")
    }

    assert expected_methods.issubset(actual_methods)