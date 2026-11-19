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

---
---

## Topic 5.3 — Mocking & Stubbing (`unittest.mock`)

### 1. What the study guide says

> **Mocking & Stubbing (`unittest.mock`):** Using `Mock` objects and `patch` to isolate units. For example, testing the `GameController` behavior requires mocking user input prompts to simulate a complete sequence of game rounds without a real console loop. Using `side_effect` to return sequential inputs to simulate real-world interactive menus.

In plain terms: a **mock** is a fake object that stands in for a real dependency. You *script* what it answers, and it *records* everything it's called with — so you can test one piece of your code in complete isolation, with no terminal, no files, and no human in the loop.

---

### 2. The problem mocking solves

Look at what `GameController` depends on (`hangman/controller/game_controller.py:16-22`):

```python
def __init__(self, view: ConsoleView, constants_module):
    self.view = view
    self.c = constants_module
    self.game = None
    ...
    self.word_repo = WordRepository(BASE_DIR / "data" / "word_bank.json")
```

And look at what `ConsoleView` actually does (`hangman/view/console_view.py:25-39`):

```python
def prompt(self, message: str) -> str:
    try:
        return input(message)          # ← blocks waiting for a real human
    ...
def prompt_hidden(self, message: str) -> str:
    try:
        return getpass.getpass(prompt=message)   # ← blocks, hides typing
```

If you tried to unit-test `GameController.setup_game()` with the **real** view, the test would **hang forever** waiting for keyboard input. It would also need a real `word_bank.json` file and a real `Game` object. That's not a unit test anymore — it's a manual play-through of the game.

**Mocking** solves this: you replace the dependencies with *fake objects* that (a) return pre-programmed answers and (b) record every call they receive, so you can assert *what the controller did* without any terminal, file, or human involved.

This is only possible because of the **Dependency Injection** design (topic 1.3): the view is *passed in* through the constructor, so a test can hand in a fake instead of a `ConsoleView`.

---

### 3. Vocabulary: stub, mock, spy, fake

These terms are often used loosely. Here's the precise distinction, and how Python's `Mock` collapses them into one:

| Term | What it does | Example in this codebase |
|---|---|---|
| **Stub** | Answers calls with canned data | `view.prompt.return_value = ""` |
| **Mock** | Records calls so you can verify them | `view.display.assert_any_call(...)` |
| **Spy** | A real object with some methods replaced | `controller.handle_letter_guess = Mock(...)` |
| **Fake** | A hand-written simplified real implementation | the `Player` class in `test_console_view.py` |

In Python, `unittest.mock.Mock` is **all of the first three at once**: it returns whatever you configure *and* records every call. That's why the study guide writes "Mocking & Stubbing" as one topic.

---

### 4. The core tools

Everything in this project's tests comes from four features:

```python
from unittest.mock import patch, Mock
```

1. **`Mock()`** — creates a fake object. Any attribute you access is *automatically* another `Mock` (so `view.prompt` "just exists" without you creating it).
2. **`return_value`** — what the mock returns when called. Same value, every time.
3. **`side_effect`** — a more powerful alternative to `return_value`:
   - a **list** → returns items one by one, in order (this is the "sequential inputs" from the study guide),
   - a **callable** → called instead of the mock,
   - an **exception** → raised when the mock is called.
4. **`patch(...)`** — a context manager that *temporarily replaces* an attribute on a module for the duration of a `with` block, then restores the original.

Plus the built-in **assertion helpers** on every mock: `assert_called()`, `assert_called_once()`, `assert_called_with(...)`, `assert_any_call(...)`, `assert_not_called()`, `call_count`, `call_args`, `call_args_list`.

---

### 5. Examples from the codebase

#### Example 1 — Stubbing the View (the study guide's main example)

`tests/unit/test_game_controller.py:11-27` starts with factory fixtures that build fake versions of every dependency:

```python
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
```

Notice the list of methods — it's exactly the **8-method contract** of the `View` interface in `hangman/view/view_interface.py` (`display`, `show_title`, `prompt`, `prompt_hidden`, `pause`, `clear`, `show_word`, `show_health`). The mock "plays the role" of any view: `ConsoleView`, a future `PygameView`, whatever. This is *program to interfaces* (topic 1.4) paying off in tests.

Two details worth understanding:

- **`view.prompt` is never explicitly created.** `Mock()` auto-generates child mocks on attribute access. That's why you can just write `view.prompt.return_value = ""`.
- **`return_value = ""` is a stub.** Every time the controller calls `self.view.prompt(...)`, it gets `""` back — no keyboard involved.

The same pattern for the model and the repository (`test_game_controller.py:30-62`):

```python
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
```

Note the **nested mock**: `game.get_player` returns a *separate* `player` mock, so when the controller does `player.name` it gets `"Alice"` — which is why later assertions can check for the exact string `"Alice has been eliminated.\n"`.

And the wiring fixture (`test_game_controller.py:65-75`):

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

Two things to notice here:

1. `constants_module=Mock()` — even the constants module is faked, so the test has zero dependence on `hangman/constants.py`.
2. `controller.word_repo = word_repo_factory()` **overwrites** the real repository that `__init__` created. This is a small design smell worth knowing: ideally `WordRepository` would also be injected through the constructor (full DI, see topic 1.3 §6), and the test wouldn't need to reach in and replace it. The test works around the current design by swapping the attribute after construction.

#### Example 2 — `side_effect` for sequential inputs (the study guide's second bullet)

A stub with `return_value` always answers the same thing. But real users type *different* things on each prompt — and often type *wrong* things first. That's what `side_effect` as a **list** is for: each call to the mock pops the next item.

**2a. Simulating a retry loop.** `test_choose_normalization` (`test_game_controller.py:82-96`):

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

Now look at the code under test (`game_controller.py:28-33`):

```python
def choose_normalization(self) -> bool:
    while True:
        response = self.view.prompt("Enable accent normalization (Y/N)? ").strip().upper()
        if response in ("Y", "N"):
            return response == "Y"
        self.view.display("Invalid input. Please enter Y or N.\n")
```

With `side_effect = ["invalid", "Y"]`, the **first** `prompt()` call returns `"invalid"` (loop continues, error displayed), the **second** returns `"Y"` (loop exits, returns `True`). One test function, three simulated user behaviors — including the "user makes a mistake" path — with no terminal at all. This is exactly the study guide's "simulate real-world interactive menus."

**2b. Simulating a full multi-step setup flow.** `test_setup_game_retries_invalid_player_count` (`test_game_controller.py:174-195`) simulates an entire configuration session:

```python
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
```

The list is a **script of the whole conversation**: accept normalization → manual word → type `0` (rejected: "must be positive") → type `2` → name Alice → name Bob. The final assertion then verifies the controller passed the collected names to the model.

**2c. Two mocks with independent scripts.** `test_setup_game_retries_invalid_word` (`test_game_controller.py:198-214`) drives *two* mocks in parallel:

```python
mock_game.set_word.side_effect = [
    {"ok": False, "error": "Invalid"},   # 1st attempt rejected by model
    {"ok": True},                        # 2nd attempt accepted
]
...
view.prompt.side_effect = ["Y", "1", "1", "Alice"]
view.prompt_hidden.side_effect = ["bad", "good"]   # moderator types bad word, then good word

controller.setup_game()

assert mock_game.set_word.call_count == 2
```

The moderator "types" `bad` (model rejects), then `good` (model accepts). The test proves the controller's retry loop actually loops — `set_word` was called exactly twice.

**2d. `side_effect` raising an exception.** `test_start_exhaustion_exit_option` (`test_game_controller.py:746-769`) simulates the word repository *failing*:

```python
controller.word_repo.get_by_difficulty.side_effect = ValueError(
    "No unused words remaining"
)

view.prompt.side_effect = ["Y", "N", "2", "easy"]
view.get_choice.return_value = "3"  # exit

controller.exit_game = Mock()

controller.start()

controller.exit_game.assert_called()
```

When `side_effect` is an exception instance, calling the mock **raises it**. This lets the test exercise the controller's recovery menu (the `except ValueError` branch in `start()`, `game_controller.py:398-429`) — a code path that would be nearly impossible to trigger with the real repository unless you exhausted the word bank.

#### Example 3 — `patch`: replacing a class, and the "patch where it's looked up" rule

In `setup_game()`, the controller constructs a real `Game` (`game_controller.py:73`):

```python
self.game = Game(constants_module=self.c, normalize_input=normalize)
```

To stop that, the tests wrap the call in `patch`:

```python
with patch("hangman.controller.game_controller.Game", return_value=mock_game):
    ...
    controller.setup_game()
```

`patch` temporarily replaces the name `Game` **in the `game_controller` module's namespace** with a mock whose `return_value` is `mock_game`. So when `setup_game()` runs `Game(...)`, it actually calls the mock and gets `mock_game` back. When the `with` block ends, the original class is restored — no permanent damage to the codebase.

**The golden rule of `patch`: patch the name where it is *looked up*, not where it is *defined*.** `game_controller.py` does `from hangman.model.game import Game`, which copies the name into the `game_controller` namespace. Patching `hangman.model.game.Game` would have no effect, because the controller doesn't look there at call time. That's why the string is `"hangman.controller.game_controller.Game"`.

You'll see the same rule in the integration test `tests/integration/test_run.py:50-51`:

```python
monkeypatch.setattr(run_module, "ConsoleView", mock_view_class)
monkeypatch.setattr(run_module, "GameController", mock_controller_class)
```

`run.py` does `from hangman.view.console_view import ConsoleView`, so the name lives in the `run` module — and that's where it's patched.

**One subtle exception** in `test_main_executes_run` (`test_run.py:186-211`):

```python
monkeypatch.setattr(
    "hangman.controller.game_controller.GameController",
    mock_controller_class
)
monkeypatch.setattr(
    "hangman.view.console_view.ConsoleView",
    mock_view_class
)

runpy.run_module("run", run_name="__main__")
```

Here the test patches the **original definition sites** instead. Why? Because `runpy.run_module` *re-executes* `run.py` from scratch, so its `from ... import ...` statements run again and pick up whatever is currently in the source modules. When the import happens *after* the patch, patching the source is the right move.

#### Example 4 — Verifying interactions (the mock as a spy)

A mock that only returns values is a stub. The other half of the power is **asserting what happened**. The controller tests use all the main assertion helpers:

**`assert_called_with`** — exact arguments (`test_setup_game_retries_invalid_player_count`):

```python
mock_game.create_players.assert_called_with(["Alice", "Bob"])
```

**`assert_any_call`** — "at some point, this exact call happened" (`test_setup_game_retries_invalid_player_input`):

```python
view.display.assert_any_call("Invalid input. Please enter an integer.\n")
```

This is how the test verifies the *error message* the user would have seen, without capturing any real output.

**`assert_called` / `assert_called_once` / `assert_not_called`** — presence/absence (`test_start_resets_word_session` vs `test_start_continue_without_reset`):

```python
controller.word_repo.reset_session.assert_called()      # user chose "Y"
controller.word_repo.reset_session.assert_not_called()  # user chose "N"
```

**`call_count`** — how many times (`test_setup_game_retries_invalid_word`):

```python
assert mock_game.set_word.call_count == 2
```

**`call_args_list`** — the full call history, for *negative* assertions. `test_run_game_loop_single_player_game_over` (`test_game_controller.py:410-422`) proves that in single-player mode the "all players eliminated" message is **never** shown:

```python
view.display.assert_any_call("    GAME OVER\n")

for call in view.display.call_args_list:
    assert "All players have been eliminated" not in call.args[0]
```

`call.args[0]` is the first positional argument of each recorded `display(...)` call — i.e., the message string.

#### Example 5 — Spying: replacing a method on the object under test

Sometimes you want to test *one* method of a class while stubbing *another* method of the **same** class. `test_run_game_loop_letter_triggers_word_guess_option` (`test_game_controller.py:372-394`) does exactly that:

```python
controller.handle_letter_guess = Mock(return_value={
    "correct": True,
    "game_won": False
})

controller.handle_word_guess = Mock(return_value={
    "correct": False,
    "game_won": False
})

view.prompt.side_effect = [
    "1",  # choose letter
    "Y",  # choose to guess word
]

controller.run_game_loop()

controller.handle_word_guess.assert_called()
```

The real `run_game_loop` logic runs, but its two helper methods are replaced with mocks. The test isolates the *decision logic* of the loop ("after a correct letter guess, if the user answers Y, call `handle_word_guess`") from the guess-handling logic, which has its own dedicated tests. This is the **spy** pattern: real object, faked methods.

The same trick appears in the `start()` tests, where `setup_game`, `run_game_loop`, and `exit_game` are all mocked so the test focuses purely on the "play again?" loop:

```python
controller.setup_game = Mock()
controller.run_game_loop = Mock()
controller.exit_game = Mock()
```

#### Example 6 — Making randomness deterministic

`WordRepository.get_by_difficulty` picks a word with `random.choice`, which makes tests flaky (they pass or fail by luck). `tests/unit/test_word_repository.py:277-279` removes the luck:

```python
def test_get_by_difficulty_mocked_random(repo_with_words):
    with patch("random.choice", return_value="CAT"):
        assert repo_with_words.get_by_difficulty("easy") == "CAT"
```

`patch("random.choice", ...)` works because `word_repository.py` calls `random.choice(...)` — the lookup happens on the `random` module at call time, so patching `random.choice` intercepts it. The rest of the repository (file reading, normalization, validation) runs for real; only the coin flip is faked. **Mock the boundary (randomness, time, network, disk), not the logic.**

#### Example 7 — The integration test of `run.py`

`tests/integration/test_run.py` is the most complete showcase. It uses the `mocker` fixture, which comes from the **`pytest-mock`** plugin — a thin wrapper around `unittest.mock` that adds automatic cleanup (so you don't need `with patch(...)` blocks).

**7a. Mocking a *class* and its *instance* separately** (`test_run.py:10-19`):

```python
@pytest.fixture
def mock_view_factory(mocker):
    def _factory():
        mock_view_instance = mocker.Mock(name="ConsoleViewInstance")
        mock_view_class = mocker.Mock(name="ConsoleView", return_value=mock_view_instance)
        return mock_view_class, mock_view_instance
    return _factory
```

`run.py` does `view = ConsoleView()`. So the test needs **two** mocks: a class mock whose `return_value` is the instance mock. (The `name=` argument is only for readable debug output — it does *not* affect identity.)

**7b. Verifying the wiring (dependency injection, tested)** (`test_run.py:71-82`):

```python
def test_run_creates_controller_with_correct_dependencies(patched_dependencies):
    run_module.run()

    patched_dependencies["controller_class"].assert_called_once()
    _, kwargs = patched_dependencies["controller_class"].call_args

    assert "view" in kwargs
    assert "constants_module" in kwargs
    assert kwargs["view"] is patched_dependencies["view_instance"]
    assert kwargs["constants_module"] is run_module.constants
```

This test proves `run()` passes the *same* view object it created into the controller — the DI contract from topic 1.3, verified mechanically. `call_args` returns `(args, kwargs)` of the last call; `is` checks object identity.

**7c. Verifying execution *order* with callable `side_effect`s** (`test_run.py:95-131`):

```python
call_order = []

def view_constructor():
    call_order.append("view_created")
    return mock_view_instance

def controller_constructor(*args, **kwargs):
    call_order.append("controller_created")
    return mock_controller_instance

def start():
    call_order.append("start_called")

mock_controller_instance.start.side_effect = start
...
run_module.run()

assert call_order == ["view_created", "controller_created", "start_called"]
```

**7d. Verifying exceptions propagate** (`test_run.py:138-179`):

```python
monkeypatch.setattr(
    run_module,
    "ConsoleView",
    mocker.Mock(side_effect=RuntimeError("view error"))
)
...
with pytest.raises(RuntimeError):
    run_module.run()
```

`test_run_propagates_exceptions` parametrizes three failure stages and uses `side_effect=RuntimeError(...)` to make each mock blow up, then asserts `run()` doesn't swallow it.

---

### 6. Contrast: `monkeypatch` and hand-rolled fakes (not every fake is a `Mock`)

`tests/unit/test_console_view.py` tests the *real* `ConsoleView` — so it can't mock the view itself. Instead it mocks the **lower-level boundaries** the view depends on, using pytest's built-in `monkeypatch` (which does the same replace-and-restore job as `patch`, but with plain functions):

```python
# test_console_view.py:110-115
def test_prompt_returns_input(view, monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda msg: "user_input")

    result = view.prompt("Enter:")

    assert result == "user_input"
```

and

```python
# test_console_view.py:44-56
def test_clear_executes_correct_command(view, monkeypatch, os_name, expected_cmd):
    calls = []

    def mock_system(cmd):
        calls.append(cmd)

    monkeypatch.setattr(os, "name", os_name)
    monkeypatch.setattr(os, "system", mock_system)

    view.clear()

    assert calls == [expected_cmd]
```

`os.system` is replaced with a plain function that records the command — proving `clear()` runs `cls` on Windows and `clear` on POSIX, without actually clearing any screen.

There's also a **hand-rolled fake** in the same file — the simplest possible stand-in, no `Mock` needed (`test_console_view.py:26-33`):

```python
@pytest.fixture
def mock_player():
    class Player:
        def __init__(self):
            self.health = 1
            self.hangman_states = ["state0", "state1", "state2"]

    return Player()
```

`ConsoleView.show_health` only touches `player.health` and `player.hangman_states`, so a 5-line class is clearer than a `Mock`. **Rule of thumb: use a plain fake when the dependency is tiny; use `Mock` when it's large or you need call recording.**

---

### 7. Best practices visible in this codebase

1. **Mock at the boundaries, not the logic.** The tests fake I/O (`input`, `getpass`, `os.system`), randomness (`random.choice`), and collaborator objects — never the game rules themselves. `test_game.py` and `test_player.py` contain *zero* mocks: pure logic needs no fakes.
2. **Patch where the name is looked up.** `"hangman.controller.game_controller.Game"`, `run_module.ConsoleView` — always the module that *uses* the name.
3. **`return_value` vs `side_effect`:** use `return_value` for "always the same answer"; use a `side_effect` list for "a script of answers"; use an exception for "this call fails."
4. **A `side_effect` list is consumed in order** and raises `StopIteration` if the code calls the mock more times than the list has items — a useful accidental guard: if your script is too short, the test fails loudly.
5. **Keep mocks minimal.** `view_factory` stubs only the contract methods. Over-stubbing hides bugs; under-stubbing makes tests flaky.
6. **Assert on behavior, not implementation.** The tests check user-visible outcomes (exact display strings, `create_players(["Alice", "Bob"])`, `reset_session` called or not) rather than internal variable states.
7. **Next step to explore: `spec`.** This codebase doesn't use it, but `Mock(spec=View)` would make the mock only allow attributes that exist on `View` — so a typo like `view.promt` fails immediately instead of silently creating a new child mock.

> **Tutor's note (honest observation):** the `get_choice` method stubbed in `view_factory` (`test_game_controller.py:24`) is **not part of the `View` interface** — the same contract deviation flagged in topic 1.4 §6.2. The mock happily fabricates it, which is exactly why the real `ConsoleView` would crash with `AttributeError` if that code path ever ran in production.

---

### 8. Summary: study guide bullet → code

| Study guide claim | Where to see it |
|---|---|
| "Using `Mock` objects ... to isolate units" | `view_factory`, `game_factory`, `word_repo_factory` in `tests/unit/test_game_controller.py` |
| "...mocking user input prompts to simulate a complete sequence of game rounds without a real console loop" | `test_setup_game_retries_invalid_player_count` (6-step prompt script), `test_run_game_loop_*` tests |
| "Using `side_effect` to return sequential inputs to simulate real-world interactive menus" | `test_choose_normalization` (`["invalid", "Y"]`), `test_setup_game_retries_invalid_word` (`["bad", "good"]`) |
| `patch` to isolate units | `patch("hangman.controller.game_controller.Game", ...)`; `patch("random.choice", ...)` in `test_word_repository.py` |
| (Bonus) exception simulation | `side_effect = ValueError(...)` in `test_start_exhaustion_exit_option` |
| (Bonus) integration-level mocking | `tests/integration/test_run.py` with `pytest-mock`'s `mocker` fixture |

**The one-sentence takeaway:** `Mock` lets you *script* what a dependency answers (`return_value` / `side_effect`) and *audit* what the unit did with it (`assert_*` helpers), while `patch` lets you swap real classes for fakes at the exact point where they're looked up — which is what turns an interactive, file-dependent console game into a suite of fast, deterministic, human-free tests.

---

### 9. Quick self-check (try these to lock it in)

1. In `tests/unit/test_game_controller.py:11-27`, list the attributes configured on the `view` mock and match each one to a method in `hangman/view/view_interface.py`. Which one does *not* exist in the interface?
2. In a **scratch copy** of `test_choose_normalization`, change the third row to `(["invalid", "X", "Y"], True)` and re-run. Explain why the test still passes, and what `view.display` would have been called with in between.
3. In `test_setup_game_retries_invalid_word`, delete the second item from `mock_game.set_word.side_effect` and re-run. What exception do you get, and why?
4. In a scratch copy, change `patch("hangman.controller.game_controller.Game", ...)` to `patch("hangman.model.game.Game", ...)` and observe the test failing. Explain using the "patch where it's looked up" rule.
5. Write a new test in a scratch copy of `test_game_controller.py` that uses `side_effect` to simulate a user who types three invalid difficulty values before a valid one, and assert the error message was displayed three times.

**One-line summary:** A **mock** is a fake stand-in you *script* with `return_value`/`side_effect` (canned answers, sequential "keystrokes", or raised exceptions) and *audit* with `assert_*` helpers, while **`patch`** temporarily swaps a real class for a fake at the module where it's looked up — together they let this project test the interactive `GameController` and the `run.py` wiring headlessly, deterministically, and without a single real keystroke.

---
---

## Topic 5.4 — Exception Testing

### 1. What the study guide says

> **Exception Testing:** Validating that correct exceptions are raised under failure conditions using `pytest.raises` (e.g., validating that the word repository properly raises `FileNotFoundError` or `ValueError` on bad inputs).

In plain terms: most tests check the **happy path** — "give valid input, get valid output." But real software spends a lot of its life on the **failure path**: the word bank file is missing, the JSON is corrupted, the player presses `Ctrl+C` mid-game, the difficulty bucket runs out of words. **Exception testing** is the practice of deliberately forcing a failure condition and asserting that the code reacts with the **correct exception type** (and, ideally, the correct behavior around it). In pytest, the tool for this is the `pytest.raises` context manager.

---

### 2. The problem it solves

Without exception tests, a "fix" that silently changes error behavior passes the whole suite:

- `WordRepository` starts returning an empty dict instead of raising when the file is missing → the game crashes later, in a confusing place, with a different error.
- `ConsoleView` stops handling `Ctrl+C` gracefully → the player sees a raw traceback instead of a clean exit.
- `run()` gets wrapped in a blanket `try/except: pass` to "make errors go away" → real failures vanish silently.

Exception tests freeze the **error contract**: *this* failure must produce *this* exception, with *this* behavior around it. They are the only tests that can catch a regression in code you never exercise in normal play.

---

### 3. The syntax: `pytest.raises`

```python
with pytest.raises(SomeException):
    code_that_should_fail()
```

Three rules to understand:

1. **If the code raises `SomeException`** → the test **passes**. The exception is *caught* by the `with` block, so it doesn't crash the test run.
2. **If the code raises a *different* exception** (or no exception at all) → the test **fails**. This is the crucial part: `pytest.raises` is not just "expect *some* error," it's "expect *this specific* error."
3. **You can capture the exception** with `as e` and inspect it: `e.value` is the exception instance, so you can check attributes like `e.value.code` or the message.

There's also an optional `match=` argument (not used in this codebase, but good to know) that regex-matches the exception message:

```python
with pytest.raises(ValueError, match="Invalid difficulty"):
    ...
```

---

### 4. Examples from the codebase

#### Example 1 — `WordRepository`: the study guide's flagship example

This is the exact example the guide cites. Look at the **source** first, `hangman/services/word_repository.py:35-58`, to see what the code *promises* to raise:

```python
def _load(self) -> None:
    if not self.file_path.exists():
        raise FileNotFoundError(f"Word bank file not found: {self.file_path}")   # line 45

    try:
        with self.file_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Word bank file is not valid JSON: {self.file_path}") from exc  # line 51

    if isinstance(data, dict):
        self._load_from_dict(data)
    elif isinstance(data, list):
        self._load_from_list(data)
    else:
        raise TypeError("Word bank root must be either an object (dict) or an array (list).")  # line 58
```

Notice the deliberate choice of **three different exception types** for three different failure modes:

| Failure | Exception | Why this type |
|---|---|---|
| File doesn't exist | `FileNotFoundError` | It's an I/O problem — Python's own `open()` would raise this too, so callers can catch it uniformly |
| File exists but isn't valid JSON | `ValueError` | The *type* is right (it's a file), but the *value* (its contents) is wrong |
| JSON root is a number or string | `TypeError` | The *type* of the data is wrong |

Now the **tests** in `tests/unit/test_word_repository.py` pin those promises down:

```python
# tests/unit/test_word_repository.py:75-77
def test_init_missing_file_raises_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        WordRepository(tmp_path / "missing.json")
```

- `tmp_path` is a built-in pytest fixture that gives each test a fresh, unique temporary directory (topic 5.1, §4). `tmp_path / "missing.json"` is a path that **does not exist** — that's the failure condition.
- If someone "refactored" `_load()` to return an empty dict instead of raising, this test would fail, because no exception would be raised at all.

```python
# tests/unit/test_word_repository.py:80-85
def test_init_invalid_json_raises_error(tmp_path):
    file_path = tmp_path / "words.json"
    file_path.write_text("{ invalid json }", encoding="utf-8")

    with pytest.raises(ValueError):
        WordRepository(file_path)
```

Here the test *manufactures* the failure: it writes a file containing garbage, then asserts the repository converts the low-level `json.JSONDecodeError` into a friendlier `ValueError`. (The source does this with `raise ValueError(...) from exc` — **exception chaining** — so the original JSON error is preserved in the traceback for debugging, while callers only need to handle one clean type.)

```python
# tests/unit/test_word_repository.py:88-91
@pytest.mark.parametrize("invalid_root", [123, "hello"])  # Non-dict, non-list types
def test_invalid_root_types(make_repo, invalid_root):
    with pytest.raises(TypeError):
        make_repo(invalid_root)
```

This shows exception testing **composing with parametrization** (topic 5.2): the same assertion runs once for `123` and once for `"hello"`. If the code ever started accepting a string root, only that parametrized case would fail — pinpointing exactly which input broke the contract.

**The public API: `get_by_difficulty`.** The same file tests the runtime API, not just construction:

```python
# tests/unit/test_word_repository.py:240-244
def test_get_by_difficulty_exhaustion(repo_single_word):
    repo_single_word.get_by_difficulty("easy")   # 1st call: succeeds, takes "CAT"

    with pytest.raises(ValueError):
        repo_single_word.get_by_difficulty("easy")  # 2nd call: bucket is empty
```

This is a **stateful** exception test: the failure only exists *after* the first call has consumed the only word. The test encodes a sequence — "do the happy thing once, then the failure must appear."

```python
# tests/unit/test_word_repository.py:247-250
@pytest.mark.parametrize("value", [123, None, [], {}])  # Non-string types
def test_get_by_difficulty_requires_string(repo_with_words, value):
    with pytest.raises(TypeError):
        repo_with_words.get_by_difficulty(value)

# tests/unit/test_word_repository.py:253-255
def test_get_by_difficulty_invalid_key(repo_with_words):
    with pytest.raises(ValueError):
        repo_with_words.get_by_difficulty("invalid")

# tests/unit/test_word_repository.py:258-262
def test_get_by_difficulty_empty_bucket(make_repo):
    repo = make_repo({"easy": ["cat"]})

    with pytest.raises(ValueError):
        repo.get_by_difficulty("medium")
```

Read these three together and a clear **error taxonomy** emerges, which is the real lesson of this section:

- **Wrong type** (`123`, `None`, `[]`, `{}`) → `TypeError`
- **Right type, wrong value** (`"invalid"` isn't a known difficulty) → `ValueError`
- **Right type, right value, but no data left** (empty bucket) → `ValueError`

The tests don't just say "it errors out" — they freeze the *distinction* between these cases. If a future refactor accidentally swapped `TypeError` for `ValueError` in `get_by_difficulty`, the parametrized test would catch it immediately.

#### Example 2 — The `View` interface: testing the *contract*

`hangman/view/view_interface.py:4-29` is the abstract base class. Every method body is just:

```python
def display(self, message: str) -> None:
    raise NotImplementedError
```

As topic 1.5 explains, this project chose **duck typing + `NotImplementedError`** instead of an ABC: the base class is a *promise*, and calling an un-overridden method is a contract violation that should blow up loudly. The tests in `tests/unit/test_view_interface.py` enforce that promise:

```python
# tests/unit/test_view_interface.py:21-44
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
```

This is a **contract test**: it says "no matter what arguments you pass, an unimplemented view method must always fail with `NotImplementedError`." It's parametrized across all 8 interface methods, including edge-case arguments (empty list, a bare `object()`), so the contract holds even at the boundaries.

There's a second, subtler exception test in the same file:

```python
# tests/unit/test_view_interface.py:84-93
@pytest.mark.parametrize(
    "method_name",
    ["display", "prompt", "prompt_hidden", "show_word", "show_health"]
)
def test_methods_require_argument(view_instance, method_name):
    """Methods requiring arguments should raise TypeError when missing."""
    method = getattr(view_instance, method_name)

    with pytest.raises(TypeError):
        method()
```

Here the exception under test is **Python's own** `TypeError` for a missing required argument. The test verifies the *signatures* of the interface: these five methods must keep requiring an argument. If someone added a default value to `display(message="")`, this test would fail — protecting the interface's shape, not just its behavior.

#### Example 3 — `ConsoleView`: testing *recovery* behavior, not just the exception

This is the most instructive example in the codebase, because it shows that exception testing is often about **what happens around** the exception.

The source, `hangman/view/console_view.py:25-31`:

```python
def prompt(self, message: str) -> str:
    try:
        return input(message)
    except (KeyboardInterrupt, EOFError):
        self.clear()
        print("\nGame interrupted. Exiting safely.\n")
        exit(0)
```

When the user hits `Ctrl+C` (`KeyboardInterrupt`) or the input stream ends (`EOFError`), the view cleans up (clears the screen, prints a farewell) and exits **gracefully with code 0** — not with an ugly traceback.

The test, `tests/unit/test_console_view.py:118-137`:

```python
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
```

Let's dissect every piece, because this test does **four** things at once:

1. **Manufacturing the failure.** You can't press `Ctrl+C` inside a test, so the test *simulates* it: `monkeypatch.setattr(builtins, "input", raise_exception)` replaces the built-in `input()` with a function that raises the exception. Parametrization runs the whole scenario twice — once for `KeyboardInterrupt`, once for `EOFError`.
2. **Asserting the exception type.** `exit(0)` raises `SystemExit`, so `pytest.raises(SystemExit)` verifies the view exits *cleanly* rather than crashing with the raw `KeyboardInterrupt`.
3. **Asserting the exit code.** `as e` captures the exception, and `e.value.code == 0` verifies it's a *graceful* exit (code 0 = success), not an error exit. This is the "inspect the exception" pattern in action.
4. **Asserting side effects.** `clear_called` verifies the cleanup (`self.clear()`) actually ran before the exit. An implementation that forgot the cleanup would pass the exception check but fail this assertion.

The same pattern is repeated for `prompt_hidden` (patching `getpass.getpass` instead of `input`, lines 148-167) and `pause` (lines 188-207) — three prompts, three graceful-exit guarantees.

#### Example 4 — `run.py`: testing that exceptions are *not swallowed*

The last category is the inverse: sometimes the correct behavior is that an exception **propagates** out of a function instead of being silently caught. `tests/integration/test_run.py:138-179`:

```python
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
    # ... (similar setup for "controller" and "start" stages) ...

    with pytest.raises(RuntimeError):
        run_module.run()
```

`run.py:6-9` is a tiny orchestrator:

```python
def run():
        view = ConsoleView()
        controller = GameController(view=view, constants_module=constants)
        controller.start()
```

The test injects a `RuntimeError` at each of the three stages (view construction, controller construction, `start()`) using `Mock(side_effect=...)` — a mock that raises instead of returning (topic 5.3, §4) — and asserts that `run()` lets the error bubble up. Why does this matter? Because a common "helpful" refactor is to wrap `run()` in a blanket `try/except: pass` to "make errors go away." That would hide real failures. This test freezes the rule: **`run()` must not swallow exceptions.**

---

### 5. Patterns and takeaways

Pulling the whole codebase together, here are the reusable lessons from this topic:

1. **Test the *specific* exception type, never "some error."** `pytest.raises(ValueError)` and `pytest.raises(TypeError)` are different tests. This codebase's `WordRepository` deliberately maps failure modes to distinct built-in types (file missing → `FileNotFoundError`, bad value → `ValueError`, wrong type → `TypeError`, unimplemented contract method → `NotImplementedError`, clean shutdown → `SystemExit`), and the tests lock each mapping in place.
2. **Manufacture the failure condition deliberately.** Every exception test needs a way to *force* the bad state. The codebase uses four techniques:
   - **Bad data on disk** — write `"{ invalid json }"` to a `tmp_path` file.
   - **Bad arguments** — pass `123`, `None`, `"invalid"` directly.
   - **State manipulation** — call `get_by_difficulty("easy")` once to exhaust the bucket, then expect the failure.
   - **Mocking/monkeypatching** — replace `input`/`getpass` with functions that raise, or give a `Mock` a `side_effect` that raises.
3. **Assert more than the type.** The strongest tests in the codebase check the *whole* failure behavior: `e.value.code == 0` (the exit code of `SystemExit` — graceful, not a crash), `clear_called` (cleanup side effects ran before the exit), and the exception *propagating* out of `run()` (the negative guarantee).
4. **Exception tests compose with everything else.** You'll see `pytest.raises` combined with `@pytest.mark.parametrize` (one assertion, many failure inputs), `monkeypatch` (simulating interrupts), `Mock.side_effect` (simulating component failures), and factory fixtures (`make_repo`, `repo_single_word`). That's exactly what the study guide means when it says the codebase "uses all of these combinations."
5. **Exception tests are *design* tests.** Several of these tests don't verify behavior at all — they verify **decisions**: `test_all_methods_raise_not_implemented` freezes the "duck typing + `NotImplementedError`" design choice (topic 1.5); `test_methods_require_argument` freezes the interface signatures; `test_run_propagates_exceptions` freezes the "no silent swallowing" rule. If someone later "improves" the code in a way that breaks one of these decisions, the test fails *loudly and immediately*, forcing the change to be made on purpose.

**Quick reference: where to look in this repo**

| File | What it exception-tests |
|---|---|
| `tests/unit/test_word_repository.py` | `FileNotFoundError`, `ValueError`, `TypeError` on load and on `get_by_difficulty` |
| `tests/unit/test_view_interface.py` | `NotImplementedError` contract, `TypeError` for missing arguments |
| `tests/unit/test_console_view.py` | `SystemExit` (code 0) + cleanup on `KeyboardInterrupt`/`EOFError` |
| `tests/integration/test_run.py` | `RuntimeError` propagation through all three startup stages |

---

### 6. Quick self-check (try these to lock it in)

1. In a **scratch copy** of `tests/unit/test_word_repository.py:75-77`, change `FileNotFoundError` to `OSError` and re-run — the test still passes (why? `FileNotFoundError` is a *subclass* of `OSError`). Then change it to `ValueError` and explain why it now fails.
2. In a scratch copy of `hangman/services/word_repository.py`, change the `raise TypeError(...)` at line 58 to `raise ValueError(...)`, run `pytest tests/unit/test_word_repository.py -v`, and watch `test_invalid_root_types` fail. That's the "frozen distinction" from Example 1 in action.
3. In a scratch copy of `tests/unit/test_console_view.py:133-136`, delete the `assert e.value.code == 0` line. The test still passes — explain what behavior is no longer protected.
4. In a scratch copy of `hangman/view/console_view.py`, remove the `self.clear()` call from `prompt`'s `except` block, run `pytest tests/unit/test_console_view.py -k interrupt`, and explain which assertion catches the change.
5. Write a new test in a scratch copy of `test_word_repository.py` that uses `pytest.raises(ValueError, match="Invalid difficulty")` to verify the *message* of the error raised by `get_by_difficulty("invalid")`.

**One-line summary:** Exception testing with `pytest.raises` means *deliberately creating the failure, asserting the exact exception type the design promises, and checking the surrounding behavior (exit codes, cleanup, propagation)* — and in this codebase it doubles as a guardrail that freezes deliberate design decisions.

---
---

## Topic 5.5 — Integration Testing

### 1. What the study guide says

> **Integration Testing:** Simulating the entrypoint (`run.py`) in `test_run.py` using `runpy` to test system initialization and coordinate module configurations under simulated execution blocks.

In plain terms: a **unit test** asks "does this one class behave correctly when its collaborators are fakes?" An **integration test** asks "are the real pieces actually *wired together* correctly, and does the system *start*?" This project's integration suite lives in `tests/integration/test_run.py` and targets the application's **composition root** — the 13-line `run.py` that creates the view, injects it into the controller, and starts the game.

---

### 2. The problem it solves: the wiring blind spot

The unit tests in this project build every class in complete isolation. For example, `tests/unit/test_game_controller.py:65-75` constructs the controller with a mocked view and then overwrites `controller.game` and `controller.word_repo` with mocks:

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

Every collaborator is a `Mock`, so the unit suite can never catch a bug in the *glue* — the code that decides which objects get created and passed to whom. That glue is `run.py`, and it's exactly the kind of code where a one-character typo (a missing keyword argument, a deleted line) breaks the app at launch while every unit test stays green.

**Integration tests close that gap:** they run the *real* wiring code and only mock the terminal components (the view and the controller), so the seams between them are exercised for real.

---

### 3. The code under test: `run.py`

The entire "system" being integrated is 13 lines (`run.py:1-13`):

```python
from hangman.view.console_view import ConsoleView
from hangman.controller.game_controller import GameController
from hangman import constants


def run():
        view = ConsoleView()
        controller = GameController(view=view, constants_module=constants)
        controller.start()


if __name__ == "__main__":
    run()
```

Three integration points to verify:

1. `ConsoleView()` is instantiated.
2. `GameController` receives **that exact view instance** plus the **real `constants` module** (the Dependency Injection contract from topic 1.3).
3. `controller.start()` is called, and exceptions are not swallowed.

---

### 4. Examples from the codebase: `tests/integration/test_run.py`

The project separates tests by type into folders — `tests/unit/` and `tests/integration/`. The integration file is organized in four bands: factory fixtures, a semantic fixture, core wiring tests, and the `__main__` execution path. Let's walk through each.

#### Example 1 — Factory fixtures: mocking a *class* and its *instance*

`tests/integration/test_run.py:10-19`:

```python
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
```

Two ideas at work:

- **Factory fixture pattern** (topic 5.1, Pattern B): the fixture returns a *callable* so each test gets a fresh, independent mock pair.
- **Mocking a class, not just an object.** `mock_view_class` is a `Mock` whose `return_value` is `mock_view_instance`. When `run()` executes `view = ConsoleView()`, it calls the mock class and gets back *that same* `mock_view_instance` — which is what lets a later test assert that the controller received exactly the object the "factory" produced.

`mock_controller_factory` (`test_run.py:22-34`) does the identical thing for `GameController`.

#### Example 2 — The semantic fixture: patching at the point of use

`tests/integration/test_run.py:41-58`:

```python
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
```

Key techniques:

- **`monkeypatch.setattr`** (pytest's built-in, topic 5.1 §4) replaces an attribute and **automatically restores it after the test** — no manual cleanup, no risk of one test's mock leaking into the next.
- **Patch where the name is looked up, not where it's defined** (topic 5.3, Example 3). `run.py` does `from hangman.view.console_view import ConsoleView`, which binds the name `ConsoleView` into `run`'s own namespace. So the fixture patches `run_module.ConsoleView` — the name *as seen by `run.py`*. Patching `hangman.view.console_view.ConsoleView` here would have no effect, because `run.py` already holds its own reference. (This subtlety pays off again in Example 6.)
- **Structured return value.** The dict gives each test readable access: `patched_dependencies["view_instance"]`, etc.

#### Example 3 — The core wiring tests

**3a. The view is created** (`test_run.py:65-68`):

```python
def test_run_creates_view_instance(patched_dependencies):
    run_module.run()

    patched_dependencies["view_class"].assert_called_once_with()
```

The *real* `run()` executes; the test asserts the (mocked) `ConsoleView` class was called exactly once with no arguments.

**3b. The controller receives the correct dependencies — the heart of the file** (`test_run.py:71-82`):

```python
def test_run_creates_controller_with_correct_dependencies(patched_dependencies):
    run_module.run()

    patched_dependencies["controller_class"].assert_called_once()

    _, kwargs = patched_dependencies["controller_class"].call_args

    assert "view" in kwargs
    assert "constants_module" in kwargs

    assert kwargs["view"] is patched_dependencies["view_instance"]
    assert kwargs["constants_module"] is run_module.constants
```

This is the most important test in the file. It inspects `call_args` — the recorded arguments of the last call to the mock — and checks:

- `kwargs["view"] is patched_dependencies["view_instance"]` — the **identity check** (`is`, not `==`). The controller must receive the *very same object* that `run()` created, not a copy or a different instance. This is exactly what Dependency Injection promises: one view instance shared across the system.
- `kwargs["constants_module"] is run_module.constants` — the **real** constants module (max health, ASCII graphics, etc.) is injected, not a mock.

If someone refactored `run.py` to `GameController(view)` — forgetting `constants_module` — this test fails immediately, while every unit test would still be green.

**3c. The game actually starts** (`test_run.py:85-88`):

```python
def test_run_calls_controller_start(patched_dependencies):
    run_module.run()

    patched_dependencies["controller_instance"].start.assert_called_once_with()
```

Creating the objects isn't enough — `run()` must call `start()`. A classic real-world bug: someone deletes that line, the app launches and silently does nothing.

#### Example 4 — Execution order: `side_effect` as a call logger

`tests/integration/test_run.py:95-131`:

```python
def test_run_execution_order(mocker, monkeypatch):
    """
    Ensures the correct sequence:
    1. View created
    2. Controller created
    3. Controller.start() called
    """
    call_order = []

    mock_view_instance = mocker.Mock()
    def view_constructor():
        call_order.append("view_created")
        return mock_view_instance

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
```

This test uses a different mocking style: instead of `Mock` classes, it injects **plain functions** as the "constructors," each appending to a shared `call_order` list. `side_effect` (topic 5.3, §4) is used here as a *call logger* rather than a sequential-input simulator.

Why does order matter? Because `run()` passes the view *into* the controller's constructor — the view must exist first. If someone reordered the lines, the app would crash with a `NameError` at startup. The test freezes the intended initialization sequence.

#### Example 5 — Parametrized exception propagation

`tests/integration/test_run.py:138-179` (also covered in topic 5.4, Example 4):

```python
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
```

One parametrized test (topic 5.2, Pattern I) running three scenarios:

| `exception_stage` | What fails | Where the error is injected |
|---|---|---|
| `"view"` | `ConsoleView()` | class mock's `side_effect` |
| `"controller"` | `GameController(...)` | class mock's `side_effect` |
| `"start"` | `controller.start()` | instance mock's `start.side_effect` |

The assertion is the same for all three: `run()` must let the `RuntimeError` **propagate** — it must not wrap the wiring in a `try/except` that swallows the failure. A composition root that silently dies is far harder to debug than one that crashes loudly.

#### Example 6 — The `__main__` test: `runpy` and the "simulated execution block"

`tests/integration/test_run.py:186-211` — the test the study guide specifically calls out:

```python
def test_main_executes_run(monkeypatch, mocker):
    """
    Tests that when run.py is executed as __main__, it calls run() and thus starts the game.
    """

    # Mock controller instance
    mock_controller = mocker.Mock()
    mock_controller.start = mocker.Mock()

    # Mock classes
    mock_controller_class = mocker.Mock(return_value=mock_controller)
    mock_view_class = mocker.Mock()

    # Patch ORIGINAL import sources
    monkeypatch.setattr(
        "hangman.controller.game_controller.GameController",
        mock_controller_class
    )
    monkeypatch.setattr(
        "hangman.view.console_view.ConsoleView",
        mock_view_class
    )

    runpy.run_module("run", run_name="__main__")

    mock_controller.start.assert_called_once()
```

Three concepts are packed into this test:

**a) `runpy.run_module("run", run_name="__main__")`.** `runpy` re-executes a module *as if you had run it from the command line*. The crucial argument is `run_name="__main__"`: it sets the module's `__name__` to `"__main__"` during execution, so the guard

```python
if __name__ == "__main__":
    run()
```

actually fires. This is the study guide's "simulated execution block" — we simulate `python run.py` **in-process**, without spawning a subprocess, without a real terminal, and without a real game loop (the view and controller are still mocks).

**b) Why the patching strategy changes here.** Notice the comment `# Patch ORIGINAL import sources`. In the earlier tests we patched `run_module.ConsoleView` (the name in `run`'s namespace). Here we patch `hangman.view.console_view.ConsoleView` and `hangman.controller.game_controller.GameController` — the *source* modules.

Why? Because `runpy.run_module` **re-executes** `run.py` from scratch. Its `from hangman.view.console_view import ConsoleView` statements run again and re-bind the names in `run`'s namespace — pulling whatever is currently in the source modules. Since we patched the sources, the fresh re-execution picks up the mocks. This is a concrete example of the golden rule from topic 5.3: **patch where the name is looked up at the moment of use.**

**c) What it guards.** If someone "cleaned up" `run.py` and deleted the `if __name__ == "__main__":` block (or renamed `run`), the app would do nothing when launched — and no unit test would notice. This test is the only one that exercises that guard.

---

### 5. What bugs does this catch that unit tests can't?

| Bug in `run.py` | Caught by |
|---|---|
| Forgetting `constants_module=constants` | `test_run_creates_controller_with_correct_dependencies` |
| Passing a *different* view instance to the controller | same test (the `is` identity check) |
| Reordering: controller created before view | `test_run_execution_order` |
| Deleting `controller.start()` | `test_run_calls_controller_start` |
| Wrapping `run()` in a `try/except: pass` | `test_run_propagates_exceptions` |
| Deleting the `__main__` guard | `test_main_executes_run` |

Every one of these is a "the app won't start" bug that a 100%-green unit suite would happily miss.

---

### 6. Patterns and takeaways

1. **Integration tests test the seams, not the logic.** Here the "seam" is the composition root `run.py`: the place where `ConsoleView`, `GameController`, and `constants` are wired together.
2. **Mock the leaves, run the glue.** The real `run()` executes; only the terminal components (view, controller) are mocked. That's the opposite of unit tests, where the class under test is real and *everything around it* is mocked.
3. **Identity assertions (`is`) verify DI wiring** — that the same object flows from creation to injection.
4. **`monkeypatch.setattr`** gives automatic cleanup; **`side_effect`** doubles as a call logger or an error injector; **`call_args`** lets you inspect exactly what a constructor received.
5. **`runpy.run_module(..., run_name="__main__")`** simulates launching the program in-process, letting you test the `__main__` guard without a subprocess.
6. **Patch at the lookup site:** patch `run_module.ConsoleView` when calling `run()` directly, but patch the source modules when `runpy` re-executes the file and re-binds the names.

**How to run it:**

```bash
# just the integration tests
pytest tests/integration -v

# the whole suite (unit + integration)
pytest -v
```

---

### 7. Quick self-check (try these to lock it in)

1. In a **scratch copy** of `run.py`, change `GameController(view=view, constants_module=constants)` to `GameController(view)` and run `pytest tests/integration -v`. Which test fails, and which assertion line tells you why?
2. In a scratch copy of `run.py`, change the controller line to `GameController(view=ConsoleView(), constants_module=constants)` — creating a *second* view for the controller. Run the integration suite and explain which assertions fail, and why the `is` identity check matters.
3. In a scratch copy of `test_run.py`, change `runpy.run_module("run", run_name="__main__")` to `runpy.run_module("run")` (no `run_name`). What happens to `mock_controller.start.assert_called_once()`, and why?
4. In a scratch copy of `test_main_executes_run`, change the two `monkeypatch.setattr` calls to patch `run_module.ConsoleView` / `run_module.GameController` instead of the source modules. Explain why the mocks are no longer used (hint: when does `run.py`'s `from ... import` execute relative to your patch?).
5. Write a new integration test in a scratch copy of `test_run.py` that asserts `run()` calls `ConsoleView()` with **no arguments** and `GameController` with **no positional arguments** (keyword arguments only), using `call_args`.

**One-line summary:** An integration test runs the *real* wiring code — here the 13-line composition root `run.py` — with only the terminal components mocked, using `monkeypatch` to patch at the lookup site, `call_args` + `is` to verify the DI wiring, `side_effect` to log call order and inject failures, and `runpy.run_module(..., run_name="__main__")` to simulate the program launch — proving the system actually starts, not just that each piece works in isolation.
