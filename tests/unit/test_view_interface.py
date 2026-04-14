import pytest
import inspect
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

def test_prompt_return_type_contract():
    """prompt() should declare a string return type."""
    assert View.prompt.__annotations__["return"] is str


def test_prompt_hidden_return_type_contract():
    """prompt_hidden() should declare a string return type."""
    assert View.prompt_hidden.__annotations__["return"] is str


def test_display_return_type_contract():
    """display() should declare a None return type."""
    assert View.display.__annotations__["return"] is None


def test_display_signature():
    """display() should accept exactly one argument besides self."""
    sig = inspect.signature(View.display)
    params = list(sig.parameters.values())

    assert len(params) == 2  # self + message
    assert params[1].name == "message"


def test_pause_signature():
    """pause() should have a default message argument."""
    sig = inspect.signature(View.pause)
    params = list(sig.parameters.values())

    assert len(params) == 2
    assert params[1].default == "Press Enter to continue..."


@pytest.mark.parametrize(
    "method_name",
    ["display", "prompt", "prompt_hidden", "show_word", "show_health"]
)
def test_methods_require_argument(view_instance, method_name):
    """Methods requiring arguments should raise TypeError when missing."""
    method = getattr(view_instance, method_name)

    with pytest.raises(TypeError):
        method()


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


@pytest.mark.parametrize("invalid_input", [None, 123, [], {}])
def test_display_invalid_types(view_instance, invalid_input):
    """display() should handle invalid input types at contract level."""
    with pytest.raises(NotImplementedError):
        view_instance.display(invalid_input)


@pytest.mark.parametrize("invalid_input", [None, "string", 123])
def test_show_word_invalid_types(view_instance, invalid_input):
    """show_word() should receive a list-like structure."""
    with pytest.raises(NotImplementedError):
        view_instance.show_word(invalid_input)


# ============================================================
# INTERFACE INSTANTIATION BEHAVIOR
# ============================================================

def test_view_is_instantiable():
    """The interface can currently be instantiated (non-ABC design)."""
    view = View()
    assert isinstance(view, View)


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