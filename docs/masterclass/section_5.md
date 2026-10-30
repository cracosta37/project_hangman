# 5. Software Testing & Pytest Framework

## Topic 5.1 — Pytest Fixtures

### 1. What is a fixture?

A **fixture** is a function that prepares a *resource* for a test — an object, a file, a mock, a database row, a configured environment — and hands it to the test. You declare it with the `@pytest.fixture` decorator, and pytest **injects it into your test function by matching the test's parameter name to the fixture's function name**.

The simplest example in this codebase is in `tests/unit/test_console_view.py:13`:

```python
@pytest.fixture
def view():
    """Default ConsoleView with clearing enabled."""
    return ConsoleView(use_clear=True)
```

And a test "requests" it just by naming a parameter `view`:

```python
# tests/unit/test_console_view.py:77
def test_display_prints_message(view, capsys):
    view.display("Hello")
    captured = capsys.readouterr()
    assert "Hello" in captured.out
```

The test never writes `ConsoleView(use_clear=True)` itself. Pytest sees the parameter `view`, finds the fixture named `view`, calls it, and passes the result in. This is the core mechanic: **name-based dependency injection**.

Key properties of fixtures (all visible in this project):

- **Lazy**: a fixture is only set up if a test actually requests it.
- **Cached per test**: if a test (or a chain of fixtures) requests the same fixture multiple times, it's built only once.
- **Composable**: a fixture can depend on other fixtures (more on this below).
- **Scoped**: by default, fixtures are *function-scoped* — a fresh instance for every single test. This project uses that default everywhere, which is deliberate: it guarantees **test isolation** (no test can leak state into another).

> Note: this project has **no `conftest.py`**. Every fixture is defined at the top of its own test file, so each fixture is only visible to tests in that file. If you ever need a fixture shared across files, that's what `conftest.py` is for.

---

### 2. The two fixture patterns in this codebase

The study guide says fixtures are used for "structuring reusable test environments." Looking at the actual test files, the project consistently uses **two complementary patterns**.

#### Pattern A — Semantic (state-oriented) fixtures

A fixture that returns a **fully pre-configured object in a specific state**. The fixture's *name* describes the state, so the test reads like English.

From `tests/unit/test_player.py:32-46` — exactly the three the study guide cites:

```python
@pytest.fixture
def player(make_player):
    return make_player()

@pytest.fixture
def low_health_player(make_player):
    return make_player(max_health=1)

@pytest.fixture
def dead_player(make_player):
    player = make_player(max_health=1)
    player.lose_health()
    return player
```

Each one encodes a different *scenario*:

| Fixture | State produced |
|---|---|
| `player` | A healthy player "Alice" with 5 health |
| `low_health_player` | A player with exactly 1 health (one wrong guess away from death) |
| `dead_player` | A player whose health is 0 (created with 1 health, then `lose_health()` called) |

Now look how readable the tests become:

```python
# tests/unit/test_player.py:70
def test_health_starts_equal_to_max_health(player):
    assert player.health == player.max_health

# tests/unit/test_player.py:138
def test_is_alive_after_transition(low_health_player):
    low_health_player.lose_health()
    assert low_health_player.is_alive() is False
```

`test_is_alive_after_transition(low_health_player)` says everything: "a player on 1 health, after losing health, is not alive." Without the fixture, every test that needs a 1-health player would have to repeat `Player(name=..., max_health=1, hangman_states=...)` — and if the constructor signature ever changed, you'd have to fix it in a dozen places.

The same pattern appears in `tests/unit/test_word_repository.py:31-44`:

```python
@pytest.fixture
def repo_with_words(make_repo):
    return make_repo({
        "easy": ["cat", "dog"],
        "medium": ["python"],
        "hard": ["architecture"]
    })

@pytest.fixture
def repo_single_word(make_repo):
    return make_repo({"easy": ["cat"]})
```

`repo_single_word` exists specifically so `test_get_by_difficulty_exhaustion` (test_word_repository.py:240) can test the "word bank runs out" scenario without any inline setup.

#### Pattern B — Factory fixtures

A semantic fixture is rigid: it always produces the *same* state. But many tests need the **same kind of object with different configurations**. The solution is a **factory fixture**: a fixture that returns a *callable* which builds objects on demand.

The canonical example is `make_player` in `tests/unit/test_player.py:9-25`:

```python
@pytest.fixture
def make_player():
    def _make_player(
        name="Alice",
        max_health=5,
        hangman_states=None
    ):
        if hangman_states is None:
            hangman_states = ["state1", "state2", "state3"]

        return Player(
            name=name,
            max_health=max_health,
            hangman_states=hangman_states
        )

    return _make_player
```

Notice the double function: the outer function is the fixture (run once per test), and the inner `_make_player` is what the test calls, with whatever arguments it needs. The defaults give you a sensible player; any argument can be overridden.

Usage in the same file:

```python
# tests/unit/test_player.py:97
def test_lose_health_behavior(make_player, initial_health, expected_health, expected_return):
    player = make_player(max_health=initial_health)
    ...

# tests/unit/test_player.py:131
def test_is_alive(make_player, health, expected):
    player = make_player(max_health=max(health, 1))
    player.health = health
    ...
```

Each parametrized case builds a player with a *different* health value — impossible with a single static `player` fixture.

The project uses factories heavily for **mocks** in `tests/unit/test_game_controller.py`, where the factory pre-wires a `Mock` with the return values the controller expects:

```python
# tests/unit/test_game_controller.py:11-27
@pytest.fixture
def view_factory():
    def _factory():
        view = Mock()
        view.prompt.return_value = ""
        view.prompt_hidden.return_value = ""
        view.display.return_value = None
        ...
        return view
    return _factory
```

And in `tests/unit/test_word_repository.py:11-17`, the factory even creates **real files on disk** (using pytest's built-in `tmp_path` fixture — see §4):

```python
@pytest.fixture
def make_json_file(tmp_path):
    def _make(data, filename="words.json"):
        file_path = tmp_path / filename
        file_path.write_text(json.dumps(data), encoding="utf-8")
        return file_path
    return _make
```

**When to use which?** A good rule of thumb, which this codebase follows:

- **Semantic fixture** → the state is fixed and the name tells the story (`dead_player`, `repo_single_word`).
- **Factory fixture** → tests need to vary the configuration (`make_player`, `make_repo`, `view_factory`).

And the two combine: the semantic fixtures in `test_player.py` are *built on top of* the factory (`player` calls `make_player()`). That's the DRY part — the construction logic lives in exactly one place.

---

### 3. Fixture composition (dependency chains)

A fixture can declare other fixtures as its own parameters. Pytest resolves the whole chain automatically, bottom-up. This is the most powerful fixture feature, and `tests/unit/test_game.py:9-29` shows a clean four-level chain:

```python
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
```

Reading it as a ladder of increasing readiness:

```
constants            →  a fake constants module (stand-in for hangman/constants.py)
   ↓
game                 →  a Game built with those constants
   ↓
game_with_players    →  a Game that already has Alice and Bob
   ↓
prepared_game        →  a Game with players AND the word "HELLO" set
```

Each level reuses the one below it. A test that only needs a bare game asks for `game`; a test that needs a fully playable round asks for `prepared_game` and gets the entire chain for free:

```python
# tests/unit/test_game.py:217
def test_guess_letter_correct_guess(prepared_game):
    result = prepared_game.guess_letter(0, "H")
    assert result["ok"] is True
    assert result["correct"] is True
    assert result["positions"] == [0]
```

Without this chain, every one of those ~20 guessing tests would start with the same 3 lines of setup (`create_players`, `set_word`, ...). With it, the setup is written once, and each level of the ladder is itself reusable.

The deepest composition in the project is in `tests/unit/test_game_controller.py:65-75`, where one factory composes three others:

```python
@pytest.fixture
def controller_factory(view_factory, game_factory, word_repo_factory):
    def _factory():
        view = view_factory()
        controller = GameController(view=view, constants_module=Mock())

        controller.game = game_factory()
        controller.word_repo = word_repo_factory()

        return controller, view
    return _factory
```

And in `tests/integration/test_run.py:41-58`, a fixture composes **built-in** fixtures with custom ones to patch the real `run.py` module:

```python
@pytest.fixture
def patched_dependencies(monkeypatch, mock_view_factory, mock_controller_factory):
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
```

Every integration test then just asks for `patched_dependencies` and gets a fully isolated, mocked `run.py` environment.

---

### 4. Built-in fixtures used in this codebase

Pytest ships with many fixtures; you use them the same way — just name them as parameters. This project uses four:

| Built-in fixture | What it does | Where it's used here |
|---|---|---|
| `tmp_path` | A fresh, unique temporary directory per test (cleaned up automatically) | `make_json_file` in `test_word_repository.py:11` |
| `monkeypatch` | Safely patches attributes/functions and **reverts them automatically** after the test | `test_console_view.py` (patching `os.system`, `builtins.input`, `getpass.getpass`), `test_run.py` |
| `capsys` | Captures anything written to `stdout`/`stderr` so you can assert on printed output | `test_console_view.py` (`captured = capsys.readouterr()`) |
| `mocker` | From the **pytest-mock** plugin; a convenient `Mock` factory | `test_run.py` (`mocker.Mock(...)`) |

Example from `test_console_view.py:44` combining a custom fixture with two built-ins:

```python
def test_clear_executes_correct_command(view, monkeypatch, os_name, expected_cmd):
    calls = []

    def mock_system(cmd):
        calls.append(cmd)

    monkeypatch.setattr(os, "name", os_name)
    monkeypatch.setattr(os, "system", mock_system)

    view.clear()

    assert calls == [expected_cmd]
```

`monkeypatch` is the "fixture" equivalent of `unittest.mock.patch`, but with automatic cleanup — no `with` block needed. That's why the project prefers it for attribute patching while reserving `Mock`/`patch` for object-level fakes.

---

### 5. Scope and test isolation

Every fixture in this project uses the **default `scope="function"`** — none of them pass a `scope` argument. That means:

- `player` is constructed **once per test** that requests it.
- `tmp_path` gives each test its **own** directory.
- `monkeypatch` reverts every patch **after each test**.

This is a deliberate design choice: if `test_lose_health_is_idempotent_at_zero` (test_player.py:108) mutates its player's health down to 0, the next test's `player` is a brand-new object at full health. **No test can poison another.** The cost (rebuilding objects) is negligible for in-memory objects like these.

(For completeness: pytest also offers `scope="class"`, `"module"`, `"package"`, and `"session"` for expensive resources like database connections, where you'd pair the fixture with `yield` to add teardown. This project doesn't need that — its fixtures are cheap to rebuild.)

---

### 6. Why fixtures promote DRY (the study guide's point)

The guide says: *"Fixtures promote DRY code by sharing initialization logic across test cases."* Concretely, compare the two worlds for `test_player.py`:

**Without fixtures** — every test repeats construction:

```python
def test_lose_health_decrements_by_one():
    player = Player(name="Alice", max_health=5, hangman_states=["state1", "state2", "state3"])
    initial = player.health
    player.lose_health()
    assert player.health == initial - 1

def test_health_starts_equal_to_max_health():
    player = Player(name="Alice", max_health=5, hangman_states=["state1", "state2", "state3"])
    assert player.health == player.max_health
```

**With fixtures** — construction exists in exactly one place:

```python
def test_lose_health_decrements_by_one(player):
    initial = player.health
    player.lose_health()
    assert player.health == initial - 1

def test_health_starts_equal_to_max_health(player):
    assert player.health == player.max_health
```

The benefits, all visible in this codebase:

1. **Single source of truth** — if `Player.__init__` gains a parameter, you fix `make_player` once, not in 15 tests.
2. **Tests read as scenarios** — `dead_player`, `prepared_game`, `repo_single_word` name the *situation* under test, not the plumbing.
3. **Isolation for free** — function scope means fresh state per test.
4. **Layered reuse** — semantic fixtures build on factories, and complex fixtures build on simpler ones (`prepared_game` → `game_with_players` → `game` → `constants`), so each level of setup is written once and reused by everything above it.

---

### 7. Naming conventions used in this project

The codebase is consistent, and it's worth copying:

- **`make_*` / `*_factory`** → factory fixtures that return a callable (`make_player`, `make_repo`, `make_json_file`, `view_factory`, `game_factory`, `controller_factory`).
- **Plain semantic names** → fixtures returning a ready-made object in a named state (`player`, `dead_player`, `prepared_game`, `repo_with_words`, `view`, `view_no_clear`).
- **`mock_*`** → fixtures producing `Mock` objects (`mock_player`, `mock_view_factory`).
- Fixtures are grouped at the **top of each test file** under a `# FIXTURES` banner, before the tests — so you can read all the "test vocabulary" before reading the tests.

---

### 8. Summary

A pytest fixture is a named, pytest-managed setup function that tests request by parameter name. This Hangman project demonstrates the full practical toolkit:

1. **Semantic fixtures** (`player`, `low_health_player`, `dead_player`, `prepared_game`) — pre-built objects in named states, making tests read like scenarios.
2. **Factory fixtures** (`make_player`, `make_repo`, `view_factory`, `controller_factory`) — return a callable so each test can configure its own object, with sensible defaults.
3. **Composition** — fixtures depending on fixtures form reusable ladders (`constants → game → game_with_players → prepared_game`), with each level written once.
4. **Built-in fixtures** — `tmp_path`, `monkeypatch`, `capsys`, and `mocker` handle temp files, safe patching, output capture, and mock creation.
5. **Function scope everywhere** — fresh objects per test, guaranteeing isolation.

Together these are what let the suite stay DRY: the initialization logic for a `Player`, a `Game`, a mocked `GameController`, or a JSON word file lives in exactly one fixture, and every test simply asks for the state it needs by name.

---

### 9. Quick self-check (try these to lock it in)

1. In `tests/unit/test_player.py:42-46`, trace the `dead_player` fixture line by line and explain exactly which two steps produce the "dead" state.
2. In `tests/unit/test_game.py:13-29`, list the full fixture chain behind `prepared_game` and say what each level adds on top of the one below it.
3. In `tests/unit/test_game_controller.py:65-75`, find where `controller_factory` composes the three other factories, and name the three it depends on.
4. Run `pytest tests/unit/test_player.py -v` and confirm every test passes; then, in a **scratch copy**, add a temporary `print(id(player))` inside two different tests that use the `player` fixture and verify the ids differ (proof of function scope).
5. Write a new semantic fixture `injured_player` (a player with exactly 2 health) in a scratch copy of `test_player.py`, built on `make_player`, and use it in one test.

**One-line summary:** A pytest fixture is a named, pytest-managed setup function that tests request by parameter name — this project combines **semantic fixtures** (pre-built states like `dead_player`), **factory fixtures** (`make_player`, `view_factory`), and **composition chains** (`constants → game → game_with_players → prepared_game`) so every test's setup is written once, reused everywhere, and rebuilt fresh for each test.
