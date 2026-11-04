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

---
---

## Topic 5.2 — Parametrized Tests

### 1. What the study guide says

> **Parametrized Tests:** Using `@pytest.mark.parametrize` to run the same assertion logic against multiple sets of inputs and expected outcomes (e.g., testing letter guessing boundaries or constructor constraints).

In plain terms: a parametrized test is **one test function that pytest runs N times**, once per row of data you supply. The test *logic* stays identical; only the *inputs* (and expected results) change.

#### The problem it solves

Without parametrization, testing 5 different health values in `Player.lose_health()` would mean writing 5 nearly identical test functions:

```python
def test_lose_health_from_5(player): ...   # copy-paste
def test_lose_health_from_2(player): ...   # copy-paste
def test_lose_health_from_1(player): ...   # copy-paste
# ...
```

That violates DRY, and when a bug appears you get 5 vague failures. With parametrization, you write the logic **once** and declare the data as a table.

---

### 2. The syntax

```python
@pytest.mark.parametrize(
    "param1, param2",          # ← names of the parameters (comma-separated string)
    [
        (value1a, value2a),    # ← row 1: one test case
        (value1b, value2b),    # ← row 2: another test case
    ]
)
def test_something(param1, param2):
    # body runs once per row
```

Key rules:

- The **string** lists parameter names; they become extra arguments of the test function.
- The **list** contains one tuple per test case. With a single parameter, each row is just a value (no tuple needed).
- Pytest expands the function into **one test per row**, each with its own ID, e.g. `test_lose_health_behavior[5-4-False]`.
- Fixtures still work normally — parametrized arguments and fixtures can be mixed freely.

You can verify the expansion yourself with:

```bash
pytest tests/unit/test_player.py --collect-only
```

---

### 3. Examples from the codebase, by pattern

The codebase uses parametrization in **9 distinct patterns** (27 `@pytest.mark.parametrize` decorators across 7 test files). Let's walk through each.

#### Pattern A — Constructor constraints (multiple parameters)

`tests/unit/test_player.py:53-67`:

```python
@pytest.mark.parametrize(
    "name, max_health, states",
    [
        ("Alice", 5, ["s1", "s2"]),         # Valid case with custom states
        ("Player_123", 4, ["a", "b", "c"]), # Valid case with different name and states
        ("Bob", 1, []),                     # Valid case with empty states list
    ]
)
def test_constructor_initializes_attributes(make_player, name, max_health, states):
    player = make_player(name=name, max_health=max_health, hangman_states=states)

    assert player.name == name
    assert player.max_health == max_health
    assert player.health == max_health
    assert player.hangman_states == states
```

This is the "constructor constraints" example the study guide mentions. Notice the important combination: **parametrize supplies the data, the factory fixture `make_player` supplies the setup** (see Topic 5.1, Pattern B). The test body is written once and runs 3 times, verifying that `Player.__init__` (in `hangman/model/player.py:7`) stores every attribute correctly — including the edge case of an *empty* states list.

#### Pattern B — Boundary values (the classic use case)

`tests/unit/test_player.py:87-105`:

```python
@pytest.mark.parametrize(
    "initial_health, expected_health, expected_return",
    [
        (5, 4, False),  # Valid case with more than 1 health
        (2, 1, False),  # Valid case with exactly 2 health
        (1, 0, True),   # Valid case with exactly 1 health (transition to zero)
        (0, 0, False),  # Valid case with already zero health (should not go negative)
        (-1, 0, False), # Valid case with negative health (should be treated as zero)
    ]
)
def test_lose_health_behavior(make_player, initial_health, expected_health, expected_return):
    player = make_player(max_health=initial_health)
    player.health = initial_health

    result = player.lose_health()

    assert player.health == expected_health
    assert result is expected_return
```

This is the "letter guessing boundaries" style of test the guide refers to. Look at *why* these 5 rows were chosen — they are the **boundaries** of the logic in `Player.lose_health()` (`hangman/model/player.py:13-16`):

```python
def lose_health(self) -> bool:
    previous = self.health
    self.health = max(0, self.health - 1)
    return previous > 0 and self.health == 0
```

| Row | What it pins down |
|---|---|
| `5 → 4` | Normal decrement, no special behavior |
| `2 → 1` | One step above the critical boundary |
| `1 → 0` | **The transition to zero** — the only case where the method returns `True` |
| `0 → 0` | The `max(0, ...)` floor: health must never go negative |
| `-1 → 0` | Defensive: even corrupted negative state is clamped to 0 |

Boundary testing is the single most valuable application of `parametrize`: bugs almost always hide at the edges (`0`, `1`, negative, empty), and a table makes it impossible to "forget" an edge.

The same file has a third example (lines 122–135), `test_is_alive`, parametrizing `health` over `(5, 3, 1, 0)` to pin down that `is_alive()` is `True` for any positive health and `False` exactly at zero.

#### Pattern C — Input → output tables (normalization)

`tests/unit/test_game.py:52-64`:

```python
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
```

This is a **table-driven test**: each row is an `(input, expected_output)` pair for `Game._normalize()` (`hangman/model/game.py:34`). One row per *behavioral category* (None, case, accents, phrases, whitespace) — not one row per possible string. That's the right granularity: you're covering the *kinds* of input, not enumerating the universe.

The most thorough version in the project is `test_normalize_for_internal` in `tests/unit/test_word_repository.py:196-207`, which adds the tricky Unicode cases:

```python
@pytest.mark.parametrize("input_text,expected", [
    ("hello", "HELLO"),
    ("  hello   world  ", "HELLO WORLD"),
    ("café", "CAFE"),
    ("Árbol Niño", "ARBOL NINO"),
    ("hello\tworld\npython", "HELLO WORLD PYTHON"),
    ("well-being", "WELL-BEING"),
    ("e\u0301", "E"),            # combining acute accent
    ("\u0301\u0301", ""),        # combining characters only
])
def test_normalize_for_internal(input_text, expected):
    assert WordRepository._normalize_for_internal(input_text) == expected
```

The last two rows are especially valuable: they test the NFD decomposition logic (topic 4.1 of the guide) at the byte level, including the degenerate case of *only* combining marks, which must normalize to an empty string.

#### Pattern D — Invalid inputs (single parameter, shared assertion)

`tests/unit/test_game.py:78-85`:

```python
@pytest.mark.parametrize(
    "word",
    [None, "   ", "A", "HELLO!"], # Invalid inputs: None, empty, single letter, invalid character
)
def test_set_word_invalid_inputs(game, word):
    result = game.set_word(word)

    assert result["ok"] is False
```

Here there's only **one parameter and no per-row expected value**, because every row must produce the *same* outcome: rejection. This is the most compact form of the decorator. The comment on the list documents what each row represents.

The same pattern appears in `test_word_repository.py`:

- Lines 88–91: `@pytest.mark.parametrize("invalid_root", [123, "hello"])` — non-dict, non-list JSON roots must raise `TypeError`.
- Lines 177–184: `test_validate_normalize_invalid_cases` — 9 invalid values (non-strings, empty, bad characters, too short) all must return `None`.
- Lines 247–250: `test_get_by_difficulty_requires_string` — `[123, None, [], {}]` must all raise `TypeError`.

#### Pattern E — Parametrizing exception types

`tests/unit/test_console_view.py:118-137`:

```python
@pytest.mark.parametrize("exception", [KeyboardInterrupt, EOFError])
def test_prompt_handles_interrupt(view, monkeypatch, exception):
    def raise_exception(_):
        raise exception

    monkeypatch.setattr(builtins, "input", raise_exception)
    ...
    with pytest.raises(SystemExit) as e:
        view.prompt("Enter:")

    assert e.value.code == 0
    assert clear_called
```

The parameter here isn't data — it's an **exception class**. The contract being tested (from `ConsoleView.prompt` in `hangman/view/console_view.py:25-31`) is: *both* `Ctrl+C` (`KeyboardInterrupt`) *and* end-of-input (`EOFError`) must trigger the same safe shutdown: clear the screen and `exit(0)`. Parametrizing the exception type guarantees the two code paths in the `except (KeyboardInterrupt, EOFError):` clause are each exercised.

This exact pattern is repeated 3 times in the file (lines 118, 148, 188) for `prompt`, `prompt_hidden`, and `pause` — the three methods that read user input.

#### Pattern F — Platform-dependent behavior

`tests/unit/test_console_view.py:40-56`:

```python
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
```

This tests the one-liner in `ConsoleView.clear()` (`hangman/view/console_view.py:14-16`):

```python
os.system('cls' if os.name == 'nt' else 'clear')
```

Since you can't be on Windows and Linux at the same time, parametrization + `monkeypatch` lets you **simulate both platforms** in one test: `os.name == "nt"` → `cls`, `os.name == "posix"` → `clear`. This is a great example of parametrization combined with the `monkeypatch` fixture (Topic 5.1, §4).

#### Pattern G — Contract testing by method name (the "meta" use)

`tests/unit/test_view_interface.py:21-44`:

```python
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
    method = getattr(view_instance, method_name)

    with pytest.raises(NotImplementedError):
        method(*args)
```

This is the most sophisticated use in the project. The parameters are **the method name and its argument tuple**, and the body uses `getattr` + `method(*args)` to call whatever method the row specifies. It encodes the entire 8-method contract of the `View` interface (topic 1.5 of the guide) as data. Note the rows for `pause` with zero and one argument — both must work because `pause` has a default parameter.

The same file has lighter versions:

- Lines 84–93: `test_methods_require_argument` — parametrizes 5 method names, each must raise `TypeError` when called with no arguments.
- Lines 121–128: `test_display_edge_cases` — parametrizes message strings (`""`, `" "`, `"\n"`, a 1000-char string, ...).
- Lines 131–142: `test_show_word_edge_cases` — parametrizes word-state lists (`[]`, `["_"]`, `["a","b","c"]`).
- Lines 145–156: `test_display_invalid_types` / `test_show_word_invalid_types` — parametrizes wrong *types* (`None`, `123`, `[]`, `{}`).

#### Pattern H — Simulating interactive sequences (parametrize + mocks)

`tests/unit/test_game_controller.py:82-96`:

```python
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
```

Here the parameter is a **list of simulated keystrokes**, fed into the mock view via `side_effect` (topic 5.3 of the guide). The third row is the interesting one: it simulates a user typing garbage first, then a valid answer — testing the controller's *retry loop* in one row. The same pattern is used for `choose_word_source` (lines 99–113), `choose_difficulty` (lines 116–130), and `choose_reset_session` (lines 133–147).

This shows a powerful idiom: **parametrize the *scenario* (a sequence of user actions), not just a single value**.

#### Pattern I — Parametrizing "stages" in integration tests

`tests/integration/test_run.py:138-179`:

```python
@pytest.mark.parametrize("exception_stage", ["view", "controller", "start"])
def test_run_propagates_exceptions(mocker, monkeypatch, exception_stage):
    """Ensures that run() does not silently swallow exceptions."""
    if exception_stage == "view":
        monkeypatch.setattr(run_module, "ConsoleView",
                            mocker.Mock(side_effect=RuntimeError("view error")))
    else:
        ...
    if exception_stage == "controller":
        ...
    with pytest.raises(RuntimeError):
        run_module.run()
```

The parameter is a **stage label** (`"view"`, `"controller"`, `"start"`), and the test body uses `if/else` to set up the corresponding failure. This is the one place in the codebase where parametrization is used as a *label* rather than pure data, because the setup logic genuinely differs per case. It's a reasonable trade-off (one test, three clear failure points in `run()`), but it's worth knowing the boundary: **when each row needs materially different setup or assertions, separate test functions are usually clearer**.

---

### 4. How pytest expands these tests

Each row becomes an independent test with a generated ID built from the parameter values:

```
tests/unit/test_player.py::test_constructor_initializes_attributes[Alice-5-states0]
tests/unit/test_player.py::test_lose_health_behavior[5-4-False]
tests/unit/test_player.py::test_lose_health_behavior[1-0-True]
tests/unit/test_game.py::test_set_word_invalid_inputs[None]
tests/unit/test_game.py::test_set_word_invalid_inputs[HELLO!]
tests/unit/test_console_view.py::test_prompt_handles_interrupt[KeyboardInterrupt]
tests/unit/test_console_view.py::test_prompt_handles_interrupt[EOFError]
```

Practical consequences:

- **Precise failure reports.** If the `1 → 0` boundary breaks, you see `test_lose_health_behavior[1-0-True] FAILED` — you know exactly which case failed without reading the code.
- **Run a single case:** `pytest "tests/unit/test_player.py::test_lose_health_behavior[1-0-True]"`
- **Filter by substring:** `pytest -k "1-0-True"`
- **Count:** the project's 27 `@pytest.mark.parametrize` decorators expand into well over 100 individual test cases.

---

### 5. Best practices visible in this codebase

1. **Comment every row.** Almost every table has a trailing comment (`# transition to zero`, `# edge case: empty list`). The table is documentation of *which behaviors* are covered.
2. **Parametrize data, let fixtures do setup.** `make_player`, `game`, `controller_factory` build the objects; the decorator only varies the inputs. This keeps the decorator readable.
3. **One row per behavioral category, not per value.** `test_normalization` has 6 rows covering 6 *kinds* of input — not 26 rows for every letter.
4. **Target the boundaries.** `0`, `1`, negative, empty, `None`, wrong types — the rows are chosen where bugs hide.
5. **Keep the body identical.** If you find yourself writing `if` branches inside a parametrized test (Pattern I), ask whether the cases really share one behavior.
6. **Combine with other tools freely.** Parametrization composes with fixtures, `monkeypatch`, `Mock.side_effect`, and `pytest.raises` — the codebase uses all of these combinations.

---

### 6. When to use (and not use) it

| Use `parametrize` when... | Prefer separate tests when... |
|---|---|
| Same logic, different data (validation, normalization) | Each case needs different setup or different assertions |
| You're pinning boundary values | The cases represent genuinely different *scenarios* with distinct flows |
| You're checking a contract across many methods (Pattern G) | A case is rare/special enough to deserve its own name |
| You're simulating input sequences (Pattern H) | — |

---

### 7. Quick self-check (try these to lock it in)

1. Run `pytest tests/unit/test_player.py --collect-only` and count how many individual tests `test_lose_health_behavior` expands into. Then run just the `[1-0-True]` case and confirm it passes on its own.
2. In a **scratch copy** of `tests/unit/test_player.py:87-95`, add a sixth row `(3, 2, False)` and re-run the test. Then, in a scratch copy of `hangman/model/player.py`, delete the `max(0, ...)` floor in `lose_health` and watch which parametrized rows fail — and why the `0` and `-1` rows are the ones that catch it.
3. In `tests/unit/test_console_view.py:40-43`, add a third row for a hypothetical third platform and explain what `monkeypatch` line would make it pass.
4. Find all 27 uses of `@pytest.mark.parametrize` in the project (`grep -rn "parametrize" tests/`) and classify each one into one of the 9 patterns above.
5. Write a new parametrized test in a scratch copy of `test_player.py` for `is_alive()` that covers the boundary between alive and dead, using the `make_player` factory.

**One-line summary:** `@pytest.mark.parametrize` turns one test function into a table-driven suite — the **string** names the parameters, the **list** holds the cases, and pytest runs the body once per row with individually reported results — and this project uses it to lock down constructor constraints, health boundaries, Unicode normalization tables, invalid-input rejection, interrupt handling, platform-specific commands, the `View` interface contract, simulated user-input sequences, and exception propagation at each startup stage.
