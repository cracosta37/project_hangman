# 3. Software Design Patterns

## Topic 3.1 — Repository Pattern

### 1. What is the Repository Pattern?

The **Repository Pattern** is a way to isolate *where and how data is stored* from the code that *uses* the data. Instead of letting your business logic read files, query databases, or call APIs directly, you create a dedicated class — the **repository** — that:

1. **Hides the storage mechanism** (JSON file, SQLite, MySQL, a web API...) behind a simple, stable interface.
2. **Guarantees data quality** — it validates and normalizes everything before handing it out.
3. **Exposes a small public API** — the rest of the application only calls a few well-defined methods.

The mental model: the repository is a *middleman* or *manager* between your application and its data source. The rest of the app never asks "how is the data stored?" — it just asks the repository for what it needs.

> The study guide says it in one line: *"The `WordRepository` decouples data storage from application business logic. The application doesn't care if the word bank is a JSON file, a database, or an external web API."* (`docs/study_guide.md:53-54`)

---

### 2. The Repository in This Codebase: `WordRepository`

The pattern lives in `hangman/services/word_repository.py`. Look at the class docstring — it states its **contract** explicitly:

```python
# hangman/services/word_repository.py:10-18
class WordRepository:
    """
    Loads, validates, normalizes, and serves words/phrases.

    Guarantees:
    - All stored words satisfy Game.set_word() constraints
    - All internal storage is normalized
    - No-repeat enforced at session level
    """
```

That docstring is the essence of the pattern: it's a **promise** to every caller. Any code that asks the repository for a word can trust it will be clean, valid, normalized, and not repeated this session.

#### 2.1 The public API (the "interface" of the repository)

The entire public surface is just **two methods**:

```python
# hangman/services/word_repository.py:146
def get_by_difficulty(self, difficulty: str) -> str:
    """
    Return a random unused word for the given difficulty key ("EASY","MEDIUM","HARD").
    Raises ValueError if difficulty is invalid or no words are available.
    """

# hangman/services/word_repository.py:170
def reset_session(self) -> None:
    """Clear session-level used-word cache."""
```

That's it. The rest of the application only ever uses `get_by_difficulty()` and `reset_session()`.

#### 2.2 What's hidden behind that tiny API

Everything else in the class is **private implementation detail** (marked with `_`):

| Private method | Responsibility hidden from the caller |
|---|---|
| `_load()` (line 35) | File existence check, `json.load()`, accepting two JSON shapes (dict or list) |
| `_load_from_dict()` / `_load_from_list()` (lines 65, 80) | Parsing structure, ignoring unknown keys |
| `_validate_normalize()` (line 84) | Type checks, empty/length checks (max 120 chars), allowed-character checks, minimum letter count |
| `_normalize_for_internal()` (line 122) | Unicode NFD decomposition, accent stripping (`"á" → "A"`), uppercasing, space collapsing |

For example, look at how much complexity `_validate_normalize` absorbs (line 84-117): the caller never has to think about words containing digits, punctuation, being too long, or having accents. The repository silently **discards invalid entries** at load time (`_add_if_valid`, line 60), so by the time data reaches the rest of the app, it's guaranteed clean.

And normalization (line 122-141):

```python
decomposed = unicodedata.normalize("NFD", text)
filtered = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
collapsed = " ".join(filtered.split())
return collapsed.upper()
```

This is why guessing `"a"` later matches an `"á"` in the secret word — that subtle correctness rule is *encapsulated inside the repository*, not scattered across the game logic.

#### 2.3 Stateful behavior: session-level no-repeat

A repository isn't just a passive reader; this one also manages **state** about what's been handed out:

```python
# hangman/services/word_repository.py:28, 159-167
self.used_words: Set[str] = set()
...
available = self.normalized_words_by_diff[key] - self.used_words
if not available:
    raise ValueError(f"No unused words remaining for difficulty: {key}")
selection = random.choice(tuple(sorted(available)))
self.used_words.add(selection)
return selection
```

The "don't show me the same word twice this session" rule lives **entirely** inside the repository. The controller and game don't track used words at all — they simply ask, and the repository refuses to repeat. When the user wants to start fresh, the single call `reset_session()` (line 170) does it.

This is a key repository virtue: **the rules about the data live with the data**, so they can't be forgotten or duplicated in other places.

---

### 3. Who Uses the Repository — and How Little They Need to Know

The only consumer in the app is `GameController`. Notice how simple the interaction is:

```python
# hangman/controller/game_controller.py:22
self.word_repo = WordRepository(BASE_DIR / "data" / "word_bank.json")

# hangman/controller/game_controller.py:93
selected = self.word_repo.get_by_difficulty(difficulty)
```

And when the bucket runs out, the controller reacts to the repository's **error contract** (line 398-429):

```python
try:
    selected = self.word_repo.get_by_difficulty(difficulty)
except ValueError as e:
    if self._is_exhaustion_error(e):
        # offer: reset session / change difficulty / exit
        ...
        self.word_repo.reset_session()
```

The controller knows **nothing** about JSON, file paths after construction, unicode, or validation. It knows exactly two things: "give me a word for this difficulty" and "tell me `ValueError` if you can't." If tomorrow the word bank moves to a PostgreSQL database, the controller's code doesn't change one line.

---

### 4. The Two Big Payoffs of the Pattern (visible in the tests)

#### 4.1 The repository is testable in complete isolation

Because all storage logic is in one class, `tests/unit/test_word_repository.py` tests it directly — building **throwaway word banks** with pytest's `tmp_path` fixture, no real app, no console:

```python
# tests/unit/test_word_repository.py:20-24
@pytest.fixture
def make_repo(make_json_file):
    def _make(data):
        return WordRepository(make_json_file(data))
    return _make
```

This lets the test suite verify every guarantee in the docstring independently:

- `test_init_missing_file_raises_error` (line 75) → `FileNotFoundError` when the file is absent
- `test_init_invalid_json_raises_error` (line 80) → `ValueError` on broken JSON
- `test_get_by_difficulty_no_repeats` (line 232) → the no-repeat guarantee
- `test_get_by_difficulty_exhaustion` (line 240) → the exhaustion `ValueError`
- `test_get_by_difficulty_isolation` (line 265) → difficulty buckets don't leak into each other

Without the pattern, these behaviors would be entangled inside the controller/game and far harder to test in isolation.

#### 4.2 The repository can be *replaced with a fake* when testing other classes

This is the payoff of "program to the interface." In `tests/unit/test_game_controller.py`, the real repository (which needs a JSON file) is swapped for a `Mock`:

```python
# tests/unit/test_game_controller.py:56-62
@pytest.fixture
def word_repo_factory():
    def _factory():
        repo = Mock()
        repo.get_by_difficulty.return_value = "TEST"
        return repo
    return _factory

# tests/unit/test_game_controller.py:71-72
controller.game = game_factory()
controller.word_repo = word_repo_factory()
```

The controller tests now run **without any data file at all**, and can even verify *how* the repository is used:

```python
# tests/unit/test_game_controller.py:231
controller.word_repo.get_by_difficulty.assert_called_with("EASY")
# tests/unit/test_game_controller.py:724, 743
controller.word_repo.reset_session.assert_called()
controller.word_repo.reset_session.assert_not_called()
```

Because the controller only ever touches `get_by_difficulty` and `reset_session`, a mock that knows just those two methods is a *perfect* stand-in. That's the pattern working exactly as intended.

---

### 5. What "Swapping the Storage" Would Look Like

The theoretical point of the pattern is substitution. Imagine the requirements change:

**Today — JSON file:**
```python
self.word_repo = WordRepository(BASE_DIR / "data" / "word_bank.json")
```

**Tomorrow — a database (same public API, different inside):**
```python
class DatabaseWordRepository:
    """Same public API as WordRepository, backed by SQLite."""
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.used_words: Set[str] = set()
        # ... migration of load/validate/normalize logic ...

    def get_by_difficulty(self, difficulty: str) -> str:
        # SELECT ... FROM words WHERE difficulty = ?
        ...

    def reset_session(self) -> None:
        self.used_words.clear()
```

Or a **web API repository** that fetches words from a server. In every case, `GameController`'s code (`selected = self.word_repo.get_by_difficulty(difficulty)`) stays byte-for-byte identical. That is the whole promise of the pattern: **storage becomes a swappable detail**.

---

### 6. How This Connects to Other Concepts in the Study Guide

- **Abstraction (section 2):** the guide explicitly names this — *"The `WordRepository` class abstracts away file reading, JSON parsing, validation, and unicode cleanup, exposing a simple `get_by_difficulty(difficulty)` method."*
- **Single Responsibility (section 2):** `WordRepository`'s *one* reason to change is "how words are stored and served." Game rules changing doesn't touch it; UI changing doesn't touch it.
- **Separation of Concerns (section 1):** word loading, game mechanics, and I/O are in three separate places.
- **Session-Level No-Repeat (section 4):** implemented *inside* the repository as the `used_words` set.
- **Duck typing as the "interface" (section 1, Option A):** note there's no formal abstract base class like `View` — the "interface" here is simply the convention that any word source must provide `get_by_difficulty` and `reset_session`. The mock in the tests works precisely because of duck typing.

---

### 7. Critical Eye: Where This Implementation Can Grow

As a good tutor, I'll point out one honest weakness — the controller **constructs** the repository itself with a hardcoded path:

```python
# hangman/controller/game_controller.py:22
self.word_repo = WordRepository(BASE_DIR / "data" / "word_bank.json")
```

Compare that to the `view` and `constants_module`, which are **injected** through the constructor (line 16). A more textbook version would inject the repository too:

```python
def __init__(self, view: ConsoleView, constants_module, word_repository):
    self.view = view
    self.c = constants_module
    self.word_repository = word_repository
```

...and have `run.py` wire it up. That would (a) make the controller fully testable without monkey-patching `controller.word_repo` after construction, and (b) let you choose the data source at the composition root (`run.py`) without editing the controller. The current design works fine — and the tests compensate by replacing `word_repo` after the fact — but constructor injection is the "cleaner" end-state of the same idea.

---

### Summary — The One-Minute Version

| Question | Answer in this codebase |
|---|---|
| What is the repository? | `WordRepository` (`hangman/services/word_repository.py`) |
| What does it hide? | File I/O, JSON parsing, validation, unicode normalization, no-repeat state |
| What's its public API? | `get_by_difficulty(difficulty)` and `reset_session()` |
| Who uses it? | `GameController` (lines 22, 93, 383, 400, 415) |
| What does it buy us? | Storage swappability, isolated testability, centralized data-quality rules |
| Where do we see the payoff? | `test_word_repository.py` (real repo, temp files) and `test_game_controller.py` (repo mocked out) |

If you remember one sentence: **the repository turns "the data lives in a JSON file" from a fact the whole app depends on, into a private detail one class manages.**

---
---

## Topic 3.2 — Factory Method Pattern (in Testing)

Per the study guide (docs/study_guide.md:55-57), this project uses a **factory fixture** (e.g. `make_player` in `test_player.py`) that *"encapsulates the instantiation details of test objects, allowing you to configure custom states dynamically while providing sensible defaults."*

### 1. What the pattern is

The classic GoF **Factory Method** says: *don't make the caller construct objects directly with `new`/constructor calls — route construction through a dedicated "factory" method.* In the pytest world, the factory is a **fixture that returns a callable**. The test calls it with whatever arguments it needs and gets a freshly built object.

It solves three problems at once:

| Problem | How the factory fixes it |
|---|---|
| Constructor boilerplate repeated in every test | All instantiation lives in one place |
| Every test needs slightly different state | Defaults + keyword overrides per call |
| Tests sharing one pre-built object can interfere | Each factory call returns a **fresh** instance |

#### 1.1 What "callable" actually means

In Python, a **callable** is *anything you can write `(...)` after* — anything Python knows how to invoke. There is even a built-in to check it: `callable(x)`.

```python
def make_player(name="Alice"): ...
print(callable(make_player))        # True  ← a function; you can write make_player(...)
print(callable(make_player()))      # False ← the RESULT (a dict) can't be called
print(callable(list))               # True  ← a class is callable: list() builds a list
print(callable(lambda: 1))          # True  ← lambdas are functions

class Box:
    def __call__(self, x): return x * 2
print(callable(Box()))              # True  ← an instance with __call__ is callable too
```

Observed output:

```
callable(make_player): True
callable(make_player()): False
callable(list): True
callable(Box()): True
```

So "callable" doesn't specifically mean "a function" — it means "an object Python knows how to invoke with `(...)`". Functions are the most common example, which is why in everyday code the two words are often used interchangeably.

#### 1.2 Unpacking "the factory is a fixture that returns a callable"

A **plain** fixture hands the test a *finished* object — the fixture value is the object itself, already built:

```python
@pytest.fixture
def game(constants):
    return Game(constants)      # fixture value = an already-built Game instance
```

A **factory** fixture is different: its body *does not* build the object — it **returns a function**, and that function is the callable. Look at `make_player` (tests/unit/test_player.py:9-25, shown in full in §2):

```python
@pytest.fixture
def make_player():
    def _make_player(name="Alice", max_health=5, hangman_states=None):
        ...
        return Player(...)
    return _make_player          # ← the fixture's value is this FUNCTION, not a Player
```

When a test asks for `make_player`, pytest runs the outer body once and hands the test back `_make_player`. So inside the test, the variable `make_player` **holds a callable** — until you write `make_player(...)`, nothing is built. Construction is *deferred* to the moment the test calls it:

```python
def test_something(make_player):
    p1 = make_player()                          # call 1 → fresh Player("Alice", 5)
    p2 = make_player(name="Bob", max_health=1)  # call 2 → fresh Player("Bob", 1)
```

That is the opening sentence, unpacked:

- **"the factory is a fixture that returns a callable"** → `@pytest.fixture def make_player(): ... return _make_player`
- **"the test calls it with whatever arguments it needs"** → `make_player(name="Bob", max_health=1)`
- **"and gets a freshly built object"** → each call runs `Player(...)` again, so every call is a brand-new instance with no shared state.

#### 1.3 What the callable buys you

| Plain fixture (`return Game(...)`) | Factory fixture (`return _make_player`) |
|---|---|
| Object built **once, immediately** when the fixture runs | Object built **each time** the test calls the function |
| Always the same shape — no per-test customization | Different arguments per call (`make_player(max_health=1)`) |
| Can't compute arguments at call time | Can: `make_player(max_health=max(health, 1))` (test_player.py:132) |

The third row is the decisive one: a plain fixture's return value is **fixed before the test body runs**, so it can never adapt to the test's parameters. The callable only "decides" when it is actually invoked — which is why §3 notes that "a static fixture can't adapt per call."

### 2. The core factory: `make_player`

tests/unit/test_player.py:9-25:

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

Mechanics of how pytest runs this:

1. A test asks for `make_player` in its signature.
2. pytest runs the fixture **once per test** and receives the inner closure `_make_player` — *not* a `Player`.
3. The test then calls `make_player(...)` **as many times as it wants**, with any arguments, getting a brand-new `Player` each time.

Two deliberate details worth noticing:

- **Sensible defaults** — `name="Alice"`, `max_health=5`, so the most common case is a zero-argument call: `make_player()`.
- **`None` sentinel for the mutable default** — `hangman_states=None` followed by substitution inside the function. If it were `hangman_states=["state1", ...]` directly, all calls would share the same list object (the classic Python mutable-default trap). The `None` check guarantees each call gets its own list.

#### 2.1 Convention or mechanics? — why the sentinel is required

Those two bullets are not a matter of taste — they are forced by one Python rule:

> **Default argument values are evaluated exactly once — when the `def` line executes (at import time) — and the resulting object is shared by every call that omits that argument.**

That rule explains both bullets at once:

- `name="Alice"` / `max_health=5` — `str` and `int` are **immutable**. All calls do share the same `"Alice"` object, but nobody can mutate a string or int in place, so sharing is harmless. Writing the sensible value directly is fine and maximizes ergonomics (a zero-argument `make_player()` "just works").
- `hangman_states=None` — a `list` is **mutable**, so writing it directly would turn the shared-object rule into cross-call contamination. Live demo:

```python
# --- BAD: mutable default written directly ---
def make_player_bad(name='Alice', states=['s1', 's2']):
    return {'name': name, 'states': states}

a = make_player_bad()
b = make_player_bad()
print('same list object?', a['states'] is b['states'])
a['states'].append('boom')
print('b after mutating a:', b['states'])

# --- GOOD: None sentinel + substitution inside ---
def make_player_good(name='Alice', states=None):
    if states is None:
        states = ['s1', 's2']
    return {'name': name, 'states': states}

a = make_player_good()
b = make_player_good()
print('same list object?', a['states'] is b['states'])
a['states'].append('boom')
print('b after mutating a:', b['states'])

# --- why: defaults are captured ONCE, at def-time ---
print('default captured at def:', make_player_bad.__defaults__)
```

Observed output:

```
same list object? True
b after mutating a: ['s1', 's2', 'boom']
same list object? False
b after mutating a: ['s1', 's2']
default captured at def: ('Alice', ['s1', 's2', 'boom'])
```

Three findings:

1. Two calls, **one** list (`is` → `True`).
2. Mutating one call's list **leaks into the other**.
3. The clincher: `make_player_bad.__defaults__` shows `('Alice', ['s1', 's2', 'boom'])` — **the default object itself was permanently mutated for the whole process lifetime**, including for tests running later in the session.

So what does the sentinel actually do? `None` is just an immutable marker meaning "the caller gave me nothing". The substitution line executes **inside the function body, at call time**, so each invocation constructs its *own* list. That is the entire trick — it moves object creation from def-time to call-time.

The consequence in this codebase is concrete: `Player` stores the list (`player.hangman_states`) and `ConsoleView.show_health` indexes into it (console_view.py:53). If two `Player`s shared one list, mutating one player's graphic array would silently mutate the other's — and in tests, one test's modification of a player's states would leak into every later test that called `make_player()` without states, the classic **order-dependent flaky test**.

| Default type | Direct value | `None` sentinel |
|---|---|---|
| Immutable (`str`, `int`, `tuple`) | safe, idiomatic | also works, but pointless |
| Mutable (`list`, `dict`, `set`) | **bug** (shared state) | required to get a fresh object per call |

For mutable defaults, the `None` sentinel (or an equivalent — build the list unconditionally in the body, or `field(default_factory=list)` in a dataclass) is the only correct pattern. For immutables, the plain default is the ergonomic choice — which is exactly why `make_player` mixes the two: `"Alice"`/`5` direct, `hangman_states` via sentinel.

### 3. Using the factory: same test, many states

**Custom overrides** — tests/unit/test_player.py:61-67:

```python
def test_constructor_initializes_attributes(make_player, name, max_health, states):
    player = make_player(name=name, max_health=max_health, hangman_states=states)
    assert player.name == name
    ...
```

**Parametrized sweep** — tests/unit/test_player.py:97-105. Without the factory, each of the 5 parameter rows would need its own `Player(...)` construction:

```python
def test_lose_health_behavior(make_player, initial_health, expected_health, expected_return):
    player = make_player(max_health=initial_health)
    player.health = initial_health
    result = player.lose_health()
    assert player.health == expected_health
    assert result is expected_return
```

**Computing arguments at call time** — tests/unit/test_player.py:131-135:

```python
def test_is_alive(make_player, health, expected):
    player = make_player(max_health=max(health, 1))  # max_health must be >= 1 to reach 0 later
    player.health = health
    assert player.is_alive() is expected
```

Note the test *derives* the constructor argument from the parameter (`max(health, 1)`). That logic only makes sense with a callable factory — a static fixture can't adapt per call.

### 4. Semantic fixtures built ON the factory

tests/unit/test_player.py:32-46 — this is the payoff of the pattern. Once the factory exists, "named state" fixtures become one-liners:

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
#### 4.1 Now tests read by *behavior*, not by setup

That payoff is what "reads as behavior, not setup" means: the **visible body of the test describes what the game does** (the rule being checked), while **how the test objects are built is hidden behind a fixture name that states the intent in plain English.** The same test, two ways:

**Without a semantic fixture** (calling the factory directly):

```python
def test_is_alive_after_transition(make_player):
    player = make_player(max_health=1)   # ← setup detail in the body
    player.lose_health()

    assert player.is_alive() is False
```

The body mixes two kinds of information:

1. **Setup**: `make_player(max_health=1)` — a construction detail. A reader must *decode* it: "max_health=1... means a player one hit from death?"
2. **Behavior**: `lose_health()`, then `is_alive() is False` — the actual rule.

**With the semantic fixture** (tests/unit/test_player.py:138-141):

```python
def test_is_alive_after_transition(low_health_player):
    low_health_player.lose_health()

    assert low_health_player.is_alive() is False
```

The setup line is gone from the body. The starting condition is now stated in the **fixture name** — `low_health_player` is a word from the game's own vocabulary. The test reads top to bottom like a rule from the game's rulebook:

> *"A low-health player takes one hit → they are no longer alive."*

The setup wasn't deleted — it was **relocated** into the fixture definitions above (test_player.py:37-46): the "how" lives there once, and states like `dead_player` become *domain words*. Any test that needs one reads like a specification:

```python
def test_something_about_elimination(dead_player):
    ...
```

Why it matters:

1. **Tests become documentation.** `test name + fixture names` compose a readable sentence about the rules. A reviewer can skim the suite and understand the game's behavior without reading a single `Player(...)` call.
2. **The "how" is edited in one place.** If "low health" ever comes to mean `max_health=2`, or the constructor signature changes, you edit the one fixture — every test that reads as behavior stays byte-for-byte identical.
3. **Attention goes to the point of the test.** The whole body is the thing under test; zero lines are scaffolding.

One nuance: some tests still call the factory directly in the body — e.g. `test_is_alive` (test_player.py:132): `make_player(max_health=max(health, 1))`. That's deliberate: the argument is **computed per call** from the test's parameters, so there is no stable, nameable state to hide behind. Semantic fixtures pay off exactly when the starting condition is a **named state** in the game's vocabulary — "a dead player", "a repo with words", "a prepared game" — which is when the test can read as pure behavior.

If `Player.__init__` ever changes its signature, you edit **one** factory, not every fixture and test. That is the DRY benefit the study guide highlights in section 5 (Pytest Fixtures).

### 5. A second example: factories composed in a chain

tests/unit/test_word_repository.py:11-44 shows the same idea scaled up — a factory *of* a factory:

```python
@pytest.fixture
def make_json_file(tmp_path):
    def _make(data, filename="words.json"):
        file_path = tmp_path / filename
        file_path.write_text(json.dumps(data), encoding="utf-8")
        return file_path
    return _make

@pytest.fixture
def make_repo(make_json_file):          # a factory that depends on another factory
    def _make(data):
        return WordRepository(make_json_file(data))
    return _make

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

The layering is:

```
make_json_file  (builds a file with any content)
      └── make_repo  (builds a WordRepository from any data)
              ├── repo_with_words   (semantic: 3 difficulties)
              └── repo_single_word  (semantic: 1 word)
```

Each layer hides one more detail (path handling, JSON serialization, construction), so tests can say `make_repo([...])` without knowing anything about `tmp_path` or `json.dumps`.

### 6. Factory vs. plain fixture — the contrast

tests/unit/test_game.py:13-29 shows the *other* style used in this codebase, for comparison:

```python
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

These fixtures **return finished objects with no customization points**. They're fine when every test wants exactly that state. The moment a test needs a *variant* (different word, different player count), a plain fixture can't help — you'd have to build the object by hand in the test, duplicating setup logic. The factory exists precisely for that "variants" case:

- **Plain fixture** → "give me the standard object" (zero arguments, one shape).
- **Factory fixture** → "give me a builder I can parameterize per call."

### Key takeaways

1. A factory fixture = `@pytest.fixture` that **returns a callable**; the test — not the fixture — controls **when** the object is built and **with what arguments**, and every call returns a fresh instance.
2. Defaults make the common case cheap; keyword arguments make the unusual case possible.
3. Every call produces a fresh object → test isolation comes for free.
4. Default values are evaluated **once at def-time**: immutable defaults (`str`, `int`) are safe to write directly, mutable defaults (`list`, `dict`, `set`) must go through a `None` sentinel (or equivalent) so each call gets its own object.
5. Semantic fixtures (`dead_player`, `repo_with_words`) are thin wrappers over the factory that turn construction details into **named states** — the test body then contains only behavior and reads like a sentence from the game's rulebook.
6. Factories compose: `make_repo` wraps `make_json_file`, hiding file-system details one level at a time.
7. This is the testing-side twin of the production **Repository Pattern** in the same section of the guide: both patterns are about *hiding how objects/artifacts come into existence*.

**One-line summary:** A factory fixture returns a *callable* so construction happens at call-time with per-call arguments; the `None` sentinel is the mechanical (not stylistic) fix for Python's once-at-def-time default evaluation; and semantic fixtures lift the construction details out of the test body so the suite reads as behavior, not setup.

---
---

## Topic 3.3 — State Management / State Transition

From the study guide (`docs/study_guide.md:58-59`):

> *The `Game` maintains variables representing state transitions (e.g., `remaining_players`, `remaining_spaces`, `game_won`, `game_over`). Methods return structured results reflecting these transitions, ensuring that state checks remain centralized.*

Let me break this down for you as a beginner, using the actual code.

---

### 1. What "state" means

The **state** of a program is simply the collection of values that describe "what is true right now." In a game, that's the most natural way to think: *who is playing, what word is hidden, how many letters are left, who is alive, has anyone won?*

In this project, the **single source of truth** for game state is the `Game` class (`hangman/model/game.py:8`). Its constructor initializes every state variable (`game.py:15-22`):

```python
self.players: List[Player] = []      # who is in the game
self.word: str = ""                  # the secret word (normalized)
self.unknown_word: List[str] = []    # what the player can see ("_ _ A _")
self.remaining_letters: set[str] = set()  # letters not yet guessed
self.remaining_players: int = 0      # players still alive
self.n_players: int = 0              # total players
self.remaining_spaces: int = 0       # unfilled letter slots
self.is_phrase: bool = False         # word or phrase?
```

Note there is **no** `game_won` or `game_over` field stored here. That's an important design decision we'll see in section 4 — those are **derived** from the stored state.

State also lives one level *inside* each `Player` (`player.py:10-11`):

```python
self.max_health: int = max_health
self.health: int = max_health
```

and in the `WordRepository` (`word_repository.py:28`):

```python
self.used_words: Set[str] = set()   # session-level no-repeat state
```

**Key rule of this project:** only the class that *owns* a piece of state is allowed to mutate it. The controller never does `player.health -= 1` — it can't, because the model exposes methods, not raw access to logic.

---

### 2. State transitions: events that change the state

A **state transition** is an *event* (a method call) that moves the game from one state to another. In this codebase, every transition is a method on `Game`, and each one does exactly one thing: validate input → mutate state → return a report.

#### Transition 1: `set_word` — "a word has been chosen" (`game.py:46-66`)

```python
normalized = self._normalize(word)
self.word = normalized
self.unknown_word = ["_" if ch.isalpha() else ch for ch in normalized]
self.remaining_spaces = sum(ch == "_" for ch in self.unknown_word)
self.is_phrase = (" " in word or "-" in word)
return {"ok": True}
```

One event flips four state variables at once: the secret word, its visible mask, the counter of unfilled slots, and the word/phrase flag.

#### Transition 2: `create_players` — "players have joined" (`game.py:104-121`)

```python
self.players = [Player(n, self.c.MAX_HEALTH, self.c.HANGMAN) for n in cleaned]
self.n_players = len(self.players)
self.remaining_players = self.n_players
```

#### Transition 3: `guess_letter` — the heart of the game (`game.py:127-194`)

A single guess can trigger a *chain* of state changes:

```python
# consume letter from the pool (game.py:154)
self.remaining_letters.remove(letter)

# incorrect guess → player loses health (game.py:159-173)
if times == 0:
    eliminated = player.lose_health()
    if eliminated:
        self.remaining_players -= 1
    return {
        "ok": True, "repeat": False, "correct": False,
        "eliminated": eliminated,
        "player_health": player.health,
        "game_won": False,
        "game_over": self.remaining_players <= 0,
        "winner": None
    }

# correct guess → reveal letters, reduce spaces (game.py:176-194)
for pos in positions:
    self.unknown_word[pos] = letter
self.remaining_spaces -= times

game_won = self.remaining_spaces == 0
winner = player_index if game_won else None
```

Notice the player-level transition is delegated: `player.lose_health()` (`player.py:13-16`) is where the health decrement actually happens:

```python
def lose_health(self) -> bool:
    previous = self.health
    self.health = max(0, self.health - 1)
    return previous > 0 and self.health == 0
```

The `max(0, ...)` clamp and the "was this the killing blow?" return value are encapsulated in the `Player` — the `Game` only reacts to the boolean.

#### Transition 4: `reset_for_new_round` — a *partial* reset (`game.py:72-98`)

Not every transition is a full reset. A new round keeps the players but restores everything else:

```python
self.remaining_letters = set(base_letters)   # fresh letter pool
result = self.set_word(new_word)             # fresh word/mask/spaces
for p in self.players:
    p.health = p.max_health                  # players recover
self.remaining_players = self.n_players      # counter restored
return {"ok": True}
```

This is a classic state transition: `PLAYING → (round over) → PLAYING again`, with only *some* state preserved.

---

### 3. Derived state: compute, don't store

Rather than storing `game_won` / `game_over` as fields that must be manually kept in sync, the model *computes* them on demand (`game.py:253-254`):

```python
def is_game_over(self) -> bool:
    return self.remaining_players <= 0 or self.remaining_spaces == 0
```

**Why this matters for beginners:** if you stored a `self.game_over = False` flag, you'd have to remember to set it in *every* method that could end the game, and it would go stale if any mutation path forgot. Deriving it from the two variables that actually cause game over means it *cannot* disagree with the state. Same idea with `Player.is_alive()` (`player.py:18-19`) — derived from `health`, never stored.

The controller's main loop is driven entirely by this derived state (`game_controller.py:151`):

```python
while not self.game.is_game_over() and self.game.remaining_players > 0:
```

The loop doesn't "know" how the game ends; it just re-queries the model each iteration.

---

### 4. Structured results: transitions report themselves

Here's the second half of the study guide's sentence — *methods return structured results reflecting these transitions*. Look at what `guess_letter` returns:

```python
return {
    "ok": True,
    "repeat": False,
    "correct": True,
    "positions": positions,
    "times": times,
    "eliminated": False,
    "player_health": player.health,
    "game_won": game_won,
    "game_over": self.remaining_players <= 0,
    "winner": winner
}
```

This dict is a **snapshot of the transition**: what happened, and which states changed. It encodes three categories of outcome:

| Situation | Example return | Meaning |
|---|---|---|
| Rejected, retryable | `{"ok": False, "repeat": True, "error": "already used"}` | bad input or repeated letter — ask again |
| Rejected, fatal | `{"ok": False, "repeat": False, "error": "eliminated"}` | cannot continue — leave the handler |
| Accepted | `{"ok": True, ..., "game_won": ...}` | state actually changed |

The controller consumes these reports without ever inspecting model internals (`game_controller.py:240-256`):

```python
result = self.game.guess_letter(player_index, raw_letter)

# Non-recoverable error → exit handler
if not result.get("ok") and not result.get("repeat"):
    self.view.display(result.get("error", "Invalid operation.") + "\n")
    self.view.pause()
    return result

# Recoverable error → retry input
if result.get("repeat"):
    self.view.display(result.get("error", "Invalid operation.") + "\n")
    continue

# Valid input
break
```

And the winner is read straight from the transition report (`game_controller.py:184-187`):

```python
if result.get("game_won") and result.get("winner") is not None:
    winner_index = result["winner"]
    winner_player = self.game.get_player(winner_index)
```

**The payoff — "state checks remain centralized":** the only place in the entire codebase that decides *what* a win, a loss, or an elimination is, is `Game`. The controller and view only *react* to the reports. If the rules changed (say, wrong guesses cost 2 health), you'd edit `guess_letter` and nothing else.

---

### 5. The big picture: the app as a state machine

Putting the transitions together, the whole application is a small state machine:

```
            setup_game()                    run_game_loop()
  [START] ───────────────► [PLAYING] ──────────────────────────┐
                          ▲        │                           │
                          │        │ all players eliminated    │ someone wins
                          │        ▼                           ▼
                          │     [GAME OVER] ──────────── [WON]
                          │        │                           │
                          └────────┴── reset_for_new_round() ──┘
                                     (Y: new round, players kept,
                                      health restored, new word)
                                     (N: exit_game())
```

The transitions are the controller's lifecycle methods:

- `[START] → [PLAYING]`: `setup_game()` (`game_controller.py:69`) calls `set_word` + `create_players`.
- `[PLAYING]` internal transitions: `guess_letter` / `guess_word` on each turn.
- `[PLAYING] → [GAME OVER]/[WON]`: detected via `is_game_over()` in the loop condition.
- `[GAME OVER] → [PLAYING]`: the `start()` loop (`game_controller.py:365-375`) asks "new game?", then `reset_for_new_round()` (`game.py:72`).
- `→ [EXIT]`: `exit_game()` (`game_controller.py:436`).

There's even a state transition *inside* the word repository: `get_by_difficulty` moves a word from "available" to "used" (`word_repository.py:159-167`), and `reset_session` clears that state (`word_repository.py:172`).

---

### 6. How the tests prove the transitions

The test suite is essentially a map of the state machine. In `tests/unit/test_game.py`:

```python
def test_is_game_over_false_when_game_active(prepared_game):        # line 331
    assert game.is_game_over() is False

def test_is_game_over_when_no_players_remaining(prepared_game):     # line 334
    prepared_game.remaining_players = 0
    assert game.is_game_over() is True

def test_is_game_over_when_word_completed(prepared_game):           # line 339
    prepared_game.remaining_spaces = 0
    assert game.is_game_over() is True
```

And transition reports are asserted directly (e.g., `test_game.py:252`, `311-313`):

```python
assert result["game_won"] is True
assert prepared_game.remaining_spaces == 0
```

In `tests/unit/test_game_controller.py:350`, the controller tests simulate transitions without a real game by mocking the model:

```python
controller.game.is_game_over.side_effect = [False, True]
```

i.e., "the first loop check says still playing, the second says over" — proving the controller reacts correctly to *state changes*, not to specific words.

---

### Summary for beginners

1. **State = data.** `Game` owns `remaining_players`, `remaining_spaces`, `remaining_letters`, `unknown_word`; `Player` owns `health`. Each class owns its own state.
2. **Transition = event.** Methods like `guess_letter` (`game.py:127`) and `reset_for_new_round` (`game.py:72`) are the *only* doors through which state changes.
3. **Derive, don't duplicate.** `is_game_over()` (`game.py:253`) and `is_alive()` (`player.py:18`) compute state from state — no stale flags.
4. **Report the change.** Each transition returns a dict (`game_won`, `game_over`, `eliminated`, `repeat`, `winner`) so the controller orchestrates screens purely from reports — state logic stays centralized in the model.
5. **The controller is just the edges of a state machine**: setup → play loop (driven by `is_game_over()`) → outcome → new round or exit.

A good exercise: add a rule like "two players sharing the same name gets a bonus letter" and see how few places you need to touch — because every transition already funnels through the `Game` model.
