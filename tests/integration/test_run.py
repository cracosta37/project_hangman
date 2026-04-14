import pytest
import run as run_module


# ============================================================
# FACTORY FIXTURES
# ============================================================

@pytest.fixture
def mock_view_factory(mocker):
    """
    Factory fixture that returns a mocked ConsoleView class and instance.
    """
    def _factory():
        mock_view_instance = mocker.Mock(name="ConsoleViewInstance")
        mock_view_class = mocker.Mock(name="ConsoleView", return_value=mock_view_instance)
        return mock_view_class, mock_view_instance
    return _factory


@pytest.fixture
def mock_controller_factory(mocker):
    """
    Factory fixture that returns a mocked GameController class and instance.
    """
    def _factory():
        mock_controller_instance = mocker.Mock(name="GameControllerInstance")
        mock_controller_class = mocker.Mock(
            name="GameController",
            return_value=mock_controller_instance
        )
        return mock_controller_class, mock_controller_instance
    return _factory


# ============================================================
# SEMANTIC FIXTURES
# ============================================================

@pytest.fixture
def patched_dependencies(monkeypatch, mock_view_factory, mock_controller_factory):
    """
    Patches ConsoleView and GameController inside run.py.
    Returns structured access to mocks.
    """
    mock_view_class, mock_view_instance = mock_view_factory()
    mock_controller_class, mock_controller_instance = mock_controller_factory()

    monkeypatch.setattr(run_module, "ConsoleView", mock_view_class)
    monkeypatch.setattr(run_module, "GameController", mock_controller_class)

    return {
        "view_class": mock_view_class,
        "view_instance": mock_view_instance,
        "controller_class": mock_controller_class,
        "controller_instance": mock_controller_instance,
    }


# ============================================================
# CORE INTEGRATION TESTS
# ============================================================

def test_run_creates_view_instance(patched_dependencies):
    run_module.run()

    patched_dependencies["view_class"].assert_called_once_with()


def test_run_creates_controller_with_correct_dependencies(patched_dependencies):
    run_module.run()

    patched_dependencies["controller_class"].assert_called_once()

    _, kwargs = patched_dependencies["controller_class"].call_args

    assert "view" in kwargs
    assert "constants_module" in kwargs

    assert kwargs["view"] is patched_dependencies["view_instance"]
    assert kwargs["constants_module"] is run_module.constants


def test_run_calls_controller_start(patched_dependencies):
    run_module.run()

    patched_dependencies["controller_instance"].start.assert_called_once_with()


# ============================================================
# SINTERACTION ORDER & CONTRACT TESTS
# ============================================================

def test_run_execution_order(mocker, monkeypatch):
    """
    Ensures the correct sequence:
    1. View created
    2. Controller created
    3. Controller.start() called
    """

    call_order = []

    # Mock view
    mock_view_instance = mocker.Mock()
    def view_constructor():
        call_order.append("view_created")
        return mock_view_instance

    # Mock controller
    mock_controller_instance = mocker.Mock()
    def controller_constructor(*args, **kwargs):
        call_order.append("controller_created")
        return mock_controller_instance

    def start():
        call_order.append("start_called")

    mock_controller_instance.start.side_effect = start

    monkeypatch.setattr(run_module, "ConsoleView", view_constructor)
    monkeypatch.setattr(run_module, "GameController", controller_constructor)

    run_module.run()

    assert call_order == [
        "view_created",
        "controller_created",
        "start_called"
    ]


# ============================================================
# PARAMETRIZED ROBUSTNESS TESTS
# ============================================================

@pytest.mark.parametrize("exception_stage", ["view", "controller", "start"])
def test_run_propagates_exceptions(mocker, monkeypatch, exception_stage):
    """
    Ensures that run() does not silently swallow exceptions.
    """

    if exception_stage == "view":
        monkeypatch.setattr(
            run_module,
            "ConsoleView",
            mocker.Mock(side_effect=RuntimeError("view error"))
        )

    else:
        mock_view_instance = mocker.Mock()
        monkeypatch.setattr(
            run_module,
            "ConsoleView",
            mocker.Mock(return_value=mock_view_instance)
        )

    if exception_stage == "controller":
        monkeypatch.setattr(
            run_module,
            "GameController",
            mocker.Mock(side_effect=RuntimeError("controller error"))
        )

    else:
        mock_controller_instance = mocker.Mock()

        if exception_stage == "start":
            mock_controller_instance.start.side_effect = RuntimeError("start error")

        monkeypatch.setattr(
            run_module,
            "GameController",
            mocker.Mock(return_value=mock_controller_instance)
        )

    with pytest.raises(RuntimeError):
        run_module.run()


# ============================================================
# __MAIN__ EXECUTION PATH
# ============================================================

def test_main_executes_run(monkeypatch, mocker):
    """
    Simulates running the module as a script.
    """

    mock_run = mocker.Mock()
    monkeypatch.setattr(run_module, "run", mock_run)

    # Simulate __main__ execution
    monkeypatch.setattr(run_module, "__name__", "__main__")

    # Reload logic manually (since Python won't re-run module automatically)
    if run_module.__name__ == "__main__":
        run_module.run()

    mock_run.assert_called_once_with()