# 6. Python Best Practices & Language Features

## Topic 6.1 — Type Hinting

*Based on `docs/masterclass/_study_guide.md` (Section 6, first item) and the actual code in this project.*

### 1. What are type hints?

Type hints (formalized in **PEP 484**) are optional annotations you write next to parameters, return values, and variables to **declare what type of data is expected**. In this project they look like this:

```python
# hangman/model/player.py, line 7
def __init__(self, name: str, max_health: int, hangman_states: List[str]):
```

The `: str`, `: int`, and `: List[str]` parts are the hints. They say: *"callers should pass a string for `name`, an integer for `max_health`, and a list of strings for `hangman_states`."*

**The single most important thing a beginner must understand:** Python does **not** enforce type hints at runtime. They are *advisory*. If you call `Player(123, "five", 42)`, Python will happily create the object and only fail later when something actually tries to use the data incorrectly. The hints exist for three other consumers:

1. **You (the reader)** — they are self-documenting. `guess_letter(self, player_index: int, raw_letter: str)` tells you the contract without reading the body.
2. **Your IDE** — autocomplete, "go to definition", and refactoring tools use hints to know what `player.health` is (an `int`) or what `game.get_player(...)` returns (a `Player` or `None`).
3. **Static analyzers** — tools like `mypy` check your code *without running it* and report mismatches before you ever execute the program.

The study guide summarizes the project's intent exactly:

> *Using typing annotations (e.g., `List[str]`, `Dict[str, Any]`, `Set[str]`, `Union[str, Path]`) to improve code documentation and support IDE autocomplete features.*

Every one of those four examples appears in this codebase — let's find them.

---

### 2. The three places hints appear

#### a) Function parameters

The most common use. From the `View` interface (`hangman/view/view_interface.py`):

```python
def display(self, message: str) -> None:
    raise NotImplementedError

def prompt(self, message: str) -> str:
    raise NotImplementedError

def show_word(self, word_state: List[str]) -> None:
    raise NotImplementedError
```

Each hint documents the *contract* of the interface: `display` takes a string, `prompt` takes a string and gives one back, `show_word` takes a list of single-character strings (the revealed/hidden state of the word).

#### b) Return values

The `->` arrow declares what the function hands back. From `hangman/model/game.py`:

```python
def _normalize(self, text: str) -> str:          # line 34
def set_word(self, raw_word: str) -> Dict[str, Any]:   # line 46
def word_label(self) -> str:                     # line 249
def is_game_over(self) -> bool:                  # line 253
def get_visible_word(self) -> List[str]:         # line 256
```

And from `hangman/model/player.py`:

```python
def lose_health(self) -> bool:      # True only on the exact hit that kills the player
def is_alive(self) -> bool:
```

The `-> bool` on `lose_health` is a nice example of a hint carrying *semantic* information: reading the body, you learn it returns `previous > 0 and self.health == 0` — i.e., "did this hit eliminate the player?" The hint tells the caller that meaning in one word.

#### c) Variable annotations (instance attributes)

Hints can also be attached to variables, which is how this project documents the state of each object. From `Game.__init__` (`hangman/model/game.py`, lines 15–22):

```python
self.players: List[Player] = []
self.word: str = ""
self.unknown_word: List[str] = []
self.remaining_letters: set[str] = set()
self.remaining_players: int = 0
self.n_players: int = 0
self.remaining_spaces: int = 0
self.is_phrase: bool = False
```

And from `WordRepository.__init__` (`hangman/services/word_repository.py`, lines 26–28):

```python
self.normalized_words_by_diff: Dict[str, Set[str]] = {diff: set() for diff in self.EXPECTED_DIFFICULTIES}
self.used_words: Set[str] = set()
```

These are especially valuable here because the *initial value* is often empty (`[]`, `set()`, `""`), which gives no clue about what will live inside later. `self.players: List[Player] = []` says: "this starts empty, but it will hold `Player` objects."

---

### 3. The typing toolbox — every hint in the study guide, found in the code

The study guide lists four examples. Here is each one in context, plus a few more the codebase uses.

#### `List[str]` — a list of strings

```python
# hangman/model/player.py, line 7
def __init__(self, name: str, max_health: int, hangman_states: List[str]):
```

`List[str]` means "a list whose elements are all strings." The `HANGMAN` constant in `hangman/constants.py` is exactly such a list — 8 ASCII-art strings, one per health level — and `Player` stores it so `ConsoleView.show_health` can print the right frame:

```python
# hangman/view/console_view.py, lines 52-53
def show_health(self, player) -> None:
    print(player.hangman_states[player.health])
```

#### `Dict[str, Any]` — the "result dictionary" pattern

The `Game` model communicates with the controller through dictionaries, and the hint for all of them is `Dict[str, Any]`:

```python
# hangman/model/game.py, line 127
def guess_letter(self, player_index: int, raw_letter: str) -> Dict[str, Any]:
```

Why `Any` for the values? Because the dictionary is *heterogeneous* — different keys hold different types:

```python
return {
    "ok": True,              # bool
    "repeat": False,         # bool
    "correct": True,         # bool
    "positions": positions,  # List[int]
    "times": times,          # int
    "player_health": player.health,  # int
    "game_won": game_won,    # bool
    "winner": winner         # int or None
}
```

There is no single type that covers `bool | int | list | None`, so `Any` is the honest choice: *"the keys are strings; the values can be anything — read the docs."* (`Any` is the escape hatch of the type system — it tells the checker "trust me, don't check this.")

#### `Set[str]` — a set of strings

```python
# hangman/services/word_repository.py, line 28
self.used_words: Set[str] = set()
```

A `Set` (unordered, no duplicates) is the right container for the session-level no-repeat feature: `self.used_words.add(selection)` and `available = self.normalized_words_by_diff[key] - self.used_words` (line 159) both rely on set semantics. The hint tells you the *kind* of collection, which matters because `set` and `list` behave very differently.

#### `Union[str, Path]` — "either this or that"

```python
# hangman/services/word_repository.py, line 23
def __init__(self, file_path: Union[str, Path]):
    self.file_path = Path(file_path).resolve()
```

`Union[str, Path]` means the caller may pass a plain string (`"data/word_bank.json"`) **or** a `pathlib.Path` object. The body immediately normalizes either form into a `Path`, which is the classic reason a `Union` exists: the API is flexible at the boundary, strict inside.

#### `Optional[Player]` — "a value, or nothing"

```python
# hangman/model/game.py, line 259
def get_player(self, index: int) -> Optional[Player]:
    if 0 <= index < len(self.players):
        return self.players[index]
    return None
```

`Optional[X]` is shorthand for `Union[X, None]`. This hint is *critical* for the caller: it says "you may get `None` back, so check before using." The controller does exactly that in `run_game_loop` (`hangman/controller/game_controller.py`, lines 153–158):

```python
player = self.game.get_player(player_index)
# Skip eliminated players (non-recoverable)
if not player.is_alive():
    i += 1
    continue
```

Without the `Optional` hint, a reader (or a static checker) might assume `player` is always a `Player` and miss the `None` case.

#### `object` — "I really don't know what this is"

```python
# hangman/services/word_repository.py, line 84
def _validate_normalize(self, raw: object) -> str | None:
```

`object` is the most general *real* type — everything in Python is an instance of it. It's the right hint here because the input comes from a JSON file, which can contain strings, numbers, lists, or `null`. The method then **narrows** the type with a runtime check:

```python
if not isinstance(raw, str):
    return None
```

After that line, the checker knows `raw` is a `str`. This "wide hint in, narrow inside" pattern is the standard way to handle untrusted external data.

#### `None` — "this function returns nothing"

```python
# hangman/view/console_view.py, line 14
def clear(self) -> None:
```

`-> None` documents that the function's purpose is a *side effect* (clearing the screen), not producing a value.

---

### 4. Classic vs. modern syntax — and why the codebase mixes them

Python has had two generations of hint syntax, and this project uses **both**:

| Purpose | Classic (typing module) | Modern (built-in / PEP 604) | Where in this project |
|---|---|---|---|
| List of str | `List[str]` | `list[str]` (3.9+) | `List[str]` in `player.py`; `set[str]` in `game.py` line 18 |
| Dict | `Dict[str, Any]` | `dict[str, Any]` (3.9+) | `Dict[str, Any]` in `game.py` |
| Set | `Set[str]` | `set[str]` (3.9+) | `Set[str]` in `word_repository.py`; `set[str]` in `game.py` |
| X or None | `Optional[X]` | `X \| None` (3.10+) | `Optional[Player]` in `game.py`; `str \| None` in `word_repository.py` line 84 |
| X or Y | `Union[X, Y]` | `X \| Y` (3.10+) | `Union[str, Path]` in `word_repository.py` |

Notice `game.py` itself mixes styles within one file:

```python
self.unknown_word: List[str] = []        # line 17, classic
self.remaining_letters: set[str] = set() # line 18, modern
```

Both are 100% valid and mean the same thing. The modern forms are preferred in new code, but the classic forms remain fully supported.

**The key to the `str | None` line** is the first line of `word_repository.py`:

```python
from __future__ import annotations
```

This import (PEP 563) tells Python to store all annotations as *strings* instead of evaluating them when the function is defined. That's what makes `-> str | None` work on Python versions older than 3.10, where `str | None` would otherwise raise a `TypeError` at import time. It's a compatibility trick — the file uses the newest syntax while still running on older interpreters.

---

### 5. What type hints do NOT do (and how this project compensates)

Because hints are not enforced, the codebase pairs them with **runtime validation** wherever bad data would be dangerous. Compare:

```python
# The hint says "list of strings"...
def create_players(self, names: List[str]) -> Dict[str, Any]:
    # ...but the code still verifies at runtime:
    if not isinstance(names, list) or len(names) == 0:
        return {"ok": False, "error": "Players list must be non-empty."}
    for name in names:
        if not isinstance(name, str) or not name.strip():
            return {"ok": False, "error": "Player names must be non-empty strings."}
```

and:

```python
# The hint says "str"...
def get_by_difficulty(self, difficulty: str) -> str:
    if not isinstance(difficulty, str):
        raise TypeError("Difficulty must be a string.")
```

The division of labor is:

- **The hint** documents intent and helps IDEs/checkers.
- **The `isinstance` check** protects the running program from real bad input (user input, JSON files, other modules).

A good mental model: *hints are for the tools and the readers; runtime checks are for the machine.*

---

### 6. How type hints support the MVC architecture

This is where hints stop being decoration and become part of the design:

**The View contract.** `view_interface.py` is the "promise" the study guide describes (Section 1, Duck Typing vs. ABC). The hints are the *written terms* of that promise:

```python
class View:
    def display(self, message: str) -> None: ...
    def prompt(self, message: str) -> str: ...
    def show_word(self, word_state: List[str]) -> None: ...
```

Any future `PygameView` or `TkinterView` must honor these signatures.

**Dependency Injection.** `run.py` wires everything together:

```python
view = ConsoleView()
controller = GameController(view=view, constants_module=constants)
```

The controller's constructor declares what it accepts:

```python
# hangman/controller/game_controller.py, line 16
def __init__(self, view: ConsoleView, constants_module):
```

**A discrepancy worth noticing (great learning opportunity):** the study guide claims *"The controller is typed against the base interface, meaning any concrete class... can be substituted transparently."* But the actual hint is `view: ConsoleView` — the **concrete** class, not the `View` base class. The code *behaves* interface-style (it only calls the 8 contract methods), but the *hint* doesn't say so. To make the hint match the documented design intent, it should be:

```python
from hangman.view.view_interface import View

def __init__(self, view: View, constants_module):
```

This is a perfect illustration of the principle: **type hints are documentation of design intent** — when the hint and the intent disagree, the hint is lying. (Tests currently pass a `ConsoleView` or a mock, so nothing breaks at runtime either way — which is exactly why the hint matters.)

---

### 7. Inconsistencies in the codebase — a checklist for you

Real codebases are rarely 100% consistent. Here are the spots where the hinting is incomplete or mixed-style. Fixing them is excellent practice:

1. **`view_interface.py` line 28** — `def show_health(self, player) -> None:` is the *only* method in the interface missing a parameter hint. It should be `player: Player` (importing `Player` from the model).
2. **`game.py` line 72** — `def reset_for_new_round(self, new_word: str) -> dict:` uses bare lowercase `dict` instead of `Dict[str, Any]` like its sibling `set_word`.
3. **`game.py` line 264** — `def get_remaining_letters(self) -> set:` — bare `set`; `Set[str]` (or `set[str]`) would be more precise.
4. **`game_controller.py` line 16** — `constants_module` has no hint. Modules are awkward to type (there's no standard "module" type), so leaving it un-hinted is defensible — but it's the one parameter in the DI constructor without a hint.
5. **`word_repository.py` line 7** — `from typing import Dict, List, Set, Union` imports `List`, which is never used in that file. A linter (e.g., `ruff` or `flake8`) would flag it.
6. **Style mixing** — `List[str]` vs `set[str]` in the same file (`game.py` lines 17–18). Pick one convention and apply it.

None of these are bugs — the program runs fine. They're *documentation* gaps, which is exactly the category of problem type hints exist to eliminate.

---

### 8. Verifying your hints: mypy

The project has `pytest.ini` but no static-analysis config yet. To actually *use* the hints, install and run mypy:

```powershell
pip install mypy
mypy hangman/
```

mypy reads every annotation and reports mismatches. For example, if you wrote:

```python
player = game.get_player(0)
player.name.upper()   # mypy: "Item 'None' of 'Optional[Player]' has no attribute 'name'"
```

...it would flag the missing `None` check *before* you ever ran the game. That's the payoff of the `Optional[Player]` hint on `game.py` line 259.

---

### 9. Key takeaways

1. **Type hints are documentation + tooling, not enforcement.** Python never checks them at runtime; this project pairs hints with `isinstance` checks where real safety matters.
2. **Three places to annotate:** parameters (`name: str`), return values (`-> bool`), and variables (`self.players: List[Player] = []`).
3. **The toolbox in this project:** `List[str]`, `Dict[str, Any]`, `Set[str]`, `Optional[Player]` (= `Player | None`), `Union[str, Path]`, `object` (unknown input), `Any` (heterogeneous dict values), `None` (side-effect functions).
4. **Two syntax generations coexist:** classic `typing` forms and modern `list[str]` / `str | None` forms; `from __future__ import annotations` is what lets `word_repository.py` use the newest syntax on older Python.
5. **Hints encode architecture:** the `View` interface signatures are the written contract for dependency injection — and the `view: ConsoleView` vs `view: View` discrepancy shows that a hint can *understate* your design intent.
6. **Consistency is the practice:** the six gaps in Section 7 are your exercise list — annotate `show_health`, unify `dict`/`set` return hints, drop the unused `List` import, and pick one style.

---

### Quick self‑check (try these to lock it in)

1. In `hangman/model/game.py`, find the `typing` imports (line 3) and locate one use of each: `List`, `Dict`, `Any`, `Optional`.
2. In `hangman/services/word_repository.py`, find the `from __future__ import annotations` import (line 1) and the `str | None` annotation (line 84). In a **scratch copy**, remove the future import and observe what breaks on Python < 3.10.
3. Apply the six fixes from Section 7 (annotate `show_health`, unify the bare `dict`/`set` return hints, drop the unused `List` import, pick one style) and confirm `pytest` still passes.
4. Run `mypy hangman/` (Section 8), read at least one reported issue, fix it, and re-run.

**One‑line summary:** Type hints (`name: str`, `-> Dict[str, Any]`, `self.players: List[Player]`) are *advisory* documentation that Python never enforces at runtime — they exist for readers, IDEs, and static checkers like mypy, and in this project they write down the `View` contract, the Model's result-dict API, and the design intent behind dependency injection.

---
---

## Topic 6.2 — Path Management with `pathlib.Path`

*Based on `docs/masterclass/_study_guide.md` (Section 6, second item) and the actual code in this project.*

### 1. The problem `pathlib` solves

Before `pathlib` (Python 3.4+), file paths were just **strings**, and you manipulated them with `os.path` functions and string concatenation:

```python
# The old, fragile way
path = base_dir + "\\data\\word_bank.json"   # breaks on macOS/Linux
path = os.path.join(base_dir, "data", "word_bank.json")
if os.path.exists(path):
    with open(path, "r") as fh: ...
```

Problems with that approach:

- **Platform-specific separators:** Windows uses `\`, macOS/Linux use `/`. Hardcoding one breaks the other.
- **Manual string surgery:** getting a parent directory, a filename, or an extension meant calling `os.path.dirname()`, `os.path.basename()`, etc.
- **No object model:** a path was inert data, not something you could "ask" questions of.

`pathlib.Path` fixes all of this: a path becomes an **object** with methods (`.exists()`, `.open()`, `.parent`, `.resolve()`, ...) and a `/` operator for joining. The object knows how to produce the correct separator for whatever OS it runs on.

This codebase uses `pathlib` in **three places**: `word_repository.py` (the main example), `game_controller.py` (building the path to the word bank), and the test suite (via pytest's `tmp_path` fixture).

---

### 2. `word_repository.py` — the core example

#### a) Importing and accepting flexible input

```python
# hangman/services/word_repository.py, lines 6–7
from pathlib import Path
from typing import Dict, List, Set, Union
```

```python
# line 23
def __init__(self, file_path: Union[str, Path]):
```

The constructor's type hint `Union[str, Path]` is a deliberate design choice: **callers may pass either a plain string or a `Path` object**. Both are valid:

```python
WordRepository("data/word_bank.json")          # string — fine
WordRepository(Path("data/word_bank.json"))    # Path — fine
```

This is a good API pattern: be flexible in what you accept, be strict in what you store internally.

#### b) Normalizing to an absolute `Path`

```python
# line 24
self.file_path = Path(file_path).resolve()
```

Two things happen here:

1. **`Path(file_path)`** — converts whatever was passed (string or Path) into a `Path` object. If a `Path` is passed, it's simply returned as-is, so this line is safe either way.
2. **`.resolve()`** — turns it into an **absolute, normalized** path (resolves `..`, `.`, and relative references).

Why this matters: if someone constructs the repository with a *relative* path like `"data/word_bank.json"`, the repository still stores the full absolute path internally. Every later operation (`.exists()`, `.open()`) then works regardless of the current working directory.

#### c) Path methods instead of `os.path` functions

```python
# lines 44–49
if not self.file_path.exists():
    raise FileNotFoundError(f"Word bank file not found: {self.file_path}")

try:
    with self.file_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
```

- **`self.file_path.exists()`** replaces `os.path.exists(str(path))`. The path object answers its own question — no string conversion needed.
- **`self.file_path.open("r", encoding="utf-8")`** replaces `open(str(path), "r")`. `Path.open()` behaves exactly like the built-in `open()`, but you call it *on* the path.

Notice the error message too: `f"Word bank file not found: {self.file_path}"` — a `Path` prints cleanly as a string, so it's safe to embed in messages.

**Old way vs. this codebase:**

| Task | Old way | In `word_repository.py` |
|---|---|---|
| Check file exists | `os.path.exists(str(p))` | `self.file_path.exists()` (line 44) |
| Open file | `open(str(p), "r")` | `self.file_path.open("r", encoding="utf-8")` (line 48) |
| Normalize | `os.path.abspath(p)` | `Path(p).resolve()` (line 24) |

---

### 3. `game_controller.py` — building the path to the word bank

This is where the **cross-platform joining** benefit shows most clearly.

#### a) Anchoring to the package directory with `__file__`

```python
# hangman/controller/game_controller.py, lines 5–7
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
```

Let's walk through this step by step with the real file location in this project:

| Step | Result |
|---|---|
| `__file__` | `F:\...\project_hangman\hangman\controller\game_controller.py` |
| `Path(__file__).resolve()` | same, but guaranteed **absolute** (see below) |
| `.parent` | `F:\...\project_hangman\hangman\controller` |
| `.parent.parent` | `F:\...\project_hangman\hangman` |

So `BASE_DIR` is the `hangman` package directory. Two details worth understanding:

- **Why `.resolve()` on `__file__`?** Depending on how the program is launched, `__file__` can be *relative* (e.g., `hangman/controller/game_controller.py` when you run `python run.py` from the project root). `.resolve()` guarantees an absolute path, so `BASE_DIR` is correct no matter where the user starts the program from.
- **Why `.parent.parent`?** The file lives two levels below the package root (`controller/game_controller.py`), so we climb up twice. With `os.path` this would have been the much less readable `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))`.

#### b) Joining paths with the `/` operator

```python
# line 22
self.word_repo = WordRepository(BASE_DIR / "data" / "word_bank.json")
```

The `/` operator is `pathlib`'s replacement for `os.path.join()`. It:

- **inserts the correct separator for the current OS** — on Windows this produces `F:\...\hangman\data\word_bank.json`; on Linux/macOS it would produce `/home/user/.../hangman/data/word_bank.json`. Same source code, both work.
- **chains naturally**: `BASE_DIR / "data" / "word_bank.json"` reads almost like a sentence.
- **is type-safe**: `Path / str` returns a `Path`. You can never accidentally produce a malformed string the way you can with `+` concatenation.

The result points to `hangman/data/word_bank.json`, which exists in this repository (alongside `word_bank_long.json`).

**Old way vs. this codebase:**

| Task | Old way | In `game_controller.py` |
|---|---|---|
| Package root | `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` | `Path(__file__).resolve().parent.parent` (line 7) |
| Join segments | `os.path.join(BASE_DIR, "data", "word_bank.json")` | `BASE_DIR / "data" / "word_bank.json"` (line 22) |

---

### 4. The test suite — `tmp_path` is a `Path` too

`pathlib` isn't only for production code; the tests lean on it heavily. Pytest's built-in `tmp_path` fixture **is a `pathlib.Path`** pointing to a fresh, unique temporary directory per test.

```python
# tests/unit/test_word_repository.py, lines 11–17
@pytest.fixture
def make_json_file(tmp_path):
    def _make(data, filename="words.json"):
        file_path = tmp_path / filename
        file_path.write_text(json.dumps(data), encoding="utf-8")
        return file_path
    return _make
```

Two more `Path` features in action:

- **`tmp_path / filename`** — the same `/` joining, now used to build a path inside the temp directory.
- **`file_path.write_text(...)`** — a one-liner that creates the file, writes the JSON, and closes it. The old way required `open(path, "w", encoding="utf-8")` plus a `.write()` call.

And the tests pass `Path` objects straight into the repository, which is exactly why the constructor accepts `Union[str, Path]`:

```python
# lines 75–77
def test_init_missing_file_raises_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        WordRepository(tmp_path / "missing.json")
```

```python
# lines 47–51
@pytest.fixture
def empty_repo(tmp_path):
    file_path = tmp_path / "empty.json"
    file_path.write_text("[]", encoding="utf-8")
    return WordRepository(file_path)
```

This is a nice demonstration of the **flexible-in, consistent-out** pattern: the tests hand in `Path` objects, the controller hands in a `Path` built with `/`, and `WordRepository` normalizes everything to an absolute `Path` on line 24.

---

### 5. Why this guarantees cross-platform compatibility

The study guide's key claim is that `pathlib` "guarantees cross-platform operating system compatibility." Concretely, in this codebase:

1. **No hardcoded separators anywhere.** Search the codebase: there is not a single `"\\"` or `"/"` used to *build* a path. Every join goes through `/`, which delegates to the OS.
2. **Forward slashes are accepted on Windows too.** `Path("data/word_bank.json")` works fine on Windows — `pathlib` normalizes it. So even user-supplied strings with `/` won't break the app.
3. **`resolve()` + `__file__` anchoring** means the app finds `word_bank.json` whether you launch it from the project root, from inside `hangman/`, or from anywhere else — on any OS.

If the code had used `BASE_DIR + "\\data\\word_bank.json"`, it would work on this Windows machine and silently fail on a Mac. That's the class of bug `pathlib` eliminates.

---

### 6. Pitfalls to keep in mind (beginner notes)

1. **`Path` is not a `str`.** You can't do `path + "suffix"` — that raises `TypeError`. Use `path / "suffix"`. (You *can* convert explicitly with `str(path)` when an API demands a string, but in this codebase that's never necessary.)
2. **`Path` objects are immutable.** Every operation (`.parent`, `/`, `.resolve()`) returns a **new** `Path`; the original is unchanged. That's why `BASE_DIR / "data"` doesn't modify `BASE_DIR`.
3. **`.resolve()` on a non-existent path doesn't raise** (in non-strict mode, Python 3.6+). It just makes the path absolute. That's why `WordRepository` can safely call `.resolve()` in `__init__` and then check `.exists()` separately in `_load()` — the two concerns are cleanly separated.
4. **`__file__` is not guaranteed absolute** — always pair it with `.resolve()` as `game_controller.py` does.

---

### 7. Key takeaways

1. **`pathlib.Path` turns paths from inert strings into objects** with methods: `.exists()`, `.open()`, `.write_text()`, `.parent`, `.resolve()`.
2. **The `/` operator replaces `os.path.join()`** and is what makes the code cross-platform: `BASE_DIR / "data" / "word_bank.json"` (game_controller.py:22) works identically on Windows, macOS, and Linux.
3. **`.resolve()` + `__file__`** is the idiomatic way to anchor paths to your project's own location instead of the user's working directory (game_controller.py:7).
4. **Flexible public API, normalized internals:** `WordRepository` accepts `Union[str, Path]` (word_repository.py:23) but always stores `Path(file_path).resolve()` (line 24) — so every consumer gets consistent, absolute paths.
5. **The pattern extends to tests:** pytest's `tmp_path` fixture is a `Path`, and `write_text()` makes test-file setup a one-liner (test_word_repository.py:14–15).

---

### Quick self‑check (try these to lock it in)

1. In `hangman/services/word_repository.py`, find the `from pathlib import Path` import (line 6) and the `Union[str, Path]` hint (line 23). In a scratch copy, construct the repository with a plain string and with a `Path` and confirm both work.
2. In `hangman/controller/game_controller.py`, trace `BASE_DIR` (line 7) step by step: print `Path(__file__).resolve()`, then `.parent`, then `.parent.parent`, and confirm that `BASE_DIR / "data" / "word_bank.json"` (line 22) points to `hangman/data/word_bank.json`.
3. In `tests/unit/test_word_repository.py`, find every use of `tmp_path` (lines 12, 48, 75, 80) and identify the `Path` methods used (`/` joining, `.write_text()`).
4. Experiment: temporarily replace line 22 of `game_controller.py` with the old-style `os.path.join(BASE_DIR, "data", "word_bank.json")` and line 48 of `word_repository.py` with `open(str(self.file_path), "r")` — the app will still work on Windows, but you'll feel exactly how much more fragile and verbose the string-based approach is.

**One‑line summary:** `pathlib.Path` turns file paths from fragile strings into objects — join with `/` (`BASE_DIR / "data" / "word_bank.json"`), anchor with `Path(__file__).resolve().parent.parent`, and call `.exists()`/`.open()`/`.write_text()` on the path itself — so the same code works on Windows, macOS, and Linux without a single hardcoded separator.

---
---

## Topic 6.3 — Safe input via `getpass`

*Based on `docs/masterclass/_study_guide.md` (Section 6, third item) and the actual code in this project.*

### 1. What the study guide says

> **Safe input via `getpass`:**
> * Using Python's standard `getpass.getpass` library in `ConsoleView` to allow a moderator to insert a secret word or phrase privately without displaying the letters in clear text on the screen.

In plain terms: when the person setting up the game types the secret word, the characters should **not** appear on the screen — just like typing a password. Python's standard library gives us a ready-made tool for exactly that: the `getpass` module.

---

### 2. The problem it solves

The game has two kinds of input:

| Input | Sensitive? | Method used |
|---|---|---|
| Player names, letter guesses, "Y/N" choices | No — everyone at the table should see them | `input()` (plain) |
| The secret word/phrase | **Yes** — the players must not see it | `getpass.getpass()` (hidden) |

If the secret word were entered with the normal `input()`, the letters would echo to the screen as they're typed. Anyone standing behind the moderator (or watching a screen share) could read the word before the game even starts. `getpass` fixes this by **disabling the terminal's echo** while reading the line: you type, nothing appears, and only after you press Enter does the value get returned to your program.

A minimal standalone demo you can run yourself:

```python
import getpass

name = input("Your name: ")          # echoes: "Your name: Carlos"
secret = getpass.getpass("Secret: ") # echoes: "Secret: " (nothing while typing)

print("Hello", name, "| you typed", len(secret), "hidden characters")
```

---

### 3. Where it lives in the codebase

`getpass` appears in exactly **one place in production code** — the View layer:

| File | Role |
|---|---|
| `hangman/view/console_view.py` | `import getpass` (line 2) and the `prompt_hidden()` method (lines 33–39) |
| `hangman/view/view_interface.py` | Declares `prompt_hidden()` as part of the 8-method View contract (lines 16–17) |
| `hangman/controller/game_controller.py` | *Calls* `self.view.prompt_hidden(...)` at two points (lines 81 and 390) — never touches `getpass` itself |
| `tests/unit/test_console_view.py` | Tests `prompt_hidden` by monkeypatching `getpass.getpass` (lines 140–167) |
| `tests/unit/test_game_controller.py` | Mocks `view.prompt_hidden` so controller tests need no terminal at all |

That distribution is the whole design story: **only the View knows that `getpass` exists.**

---

### 4. Code walkthrough

#### a) The contract — `hangman/view/view_interface.py`

```python
# lines 13–17
def prompt(self, message: str) -> str:
    raise NotImplementedError

def prompt_hidden(self, message: str) -> str:
    raise NotImplementedError
```

`prompt_hidden` is one of the 8 verbs every view must provide. Notice it has the **exact same signature** as `prompt`: `(message: str) -> str`. That means the rest of the program can treat "ask for a visible answer" and "ask for a hidden answer" as interchangeable operations — the only difference is *how* the answer is collected.

#### b) The implementation — `hangman/view/console_view.py`

```python
# lines 1–5
import os
import getpass          # ← line 2: the only production import of getpass
from typing import List

from .view_interface import View
```

```python
# lines 25–39
def prompt(self, message: str) -> str:
    try:
        return input(message)                    # visible typing
    except (KeyboardInterrupt, EOFError):
        self.clear()
        print("\nGame interrupted. Exiting safely.\n")
        exit(0)

def prompt_hidden(self, message: str) -> str:
    try:
        return getpass.getpass(prompt=message)   # ← hidden typing
    except (KeyboardInterrupt, EOFError):
        self.clear()
        print("\nGame interrupted. Exiting safely.\n")
        exit(0)
```

Three things to notice:

1. **`getpass.getpass(prompt=message)`** — the module-level function takes the prompt string and returns the typed line as a `str`, with echo disabled while typing.
2. **Identical interrupt handling to `prompt`.** `getpass` can also be interrupted with `Ctrl+C` (`KeyboardInterrupt`) or hit end-of-input (`EOFError`). The view catches both, clears the screen, prints a friendly message, and exits with code `0` — the same "graceful exit" guarantee the study guide lists under topic 6.5 (Interrupt Handling). This matters because `getpass` temporarily puts the terminal into a special no-echo state; a clean exit path keeps the console in a sane state.
3. **The method returns the raw string.** No validation happens here — the view stays "dumb" (per the MVC description in section 1 of the guide). Validation is the Model's job.

#### c) The call sites — `hangman/controller/game_controller.py`

The controller asks for the secret word in two moments of the game flow:

**At game setup** (lines 78–85):

```python
if source == "1":
    # Manual (current behavior)
    while True:
        raw_word = self.view.prompt_hidden("Please insert the word or phrase: ")
        result = self.game.set_word(raw_word)
        if result.get("ok"):
            break
        self.view.display(result.get("error", "Invalid word or phrase.") + "\n")
```

**When starting a new round** (lines 388–394):

```python
if source == "1":
    while True:
        raw_word = self.view.prompt_hidden("Please insert the new word or phrase: ")
        result = self.game.reset_for_new_round(raw_word)
        if result.get("ok"):
            break
        self.view.display(result.get("error", "Invalid word or phrase.") + "\n")
```

Read the contrast with the surrounding code: player names and letter guesses use `self.view.prompt(...)` (visible), while the word uses `self.view.prompt_hidden(...)` (hidden). The controller never imports `getpass` and never knows *how* the hiding works — it just picks the right verb. That's **Separation of Concerns** in action: if you later build a `TkinterView` or `WebView`, its `prompt_hidden` could be a password field or an API parameter instead of `getpass`, and the controller wouldn't change a single line.

---

### 5. How `getpass` works under the hood (briefly)

For a beginner, it's enough to know it "hides the typing," but here's the one-paragraph version:

- On **Windows**, it uses the console API to turn off the `ENABLE_ECHO_INPUT` flag while reading, then restores it.
- On **Unix/macOS**, it uses `termios` to disable the `ECHO` flag on the terminal, reads the line, and restores the original settings.
- It also disables the line-editing/history mechanism, so the secret isn't saved to shell history or scrollback.
- If no real terminal is attached (e.g., input is piped), it falls back to reading from `/dev/tty` or stdin — which is why tests never call the real function (see below).

---

### 6. How the codebase tests it

#### a) Unit-testing the View — `tests/unit/test_console_view.py`

The real `getpass.getpass` would block waiting for a human, so the tests **monkeypatch** it:

```python
# lines 140–145
def test_prompt_hidden_returns_input(view, monkeypatch):
    monkeypatch.setattr(getpass, "getpass", lambda prompt: "secret")

    result = view.prompt_hidden("Password:")

    assert result == "secret"
```

`monkeypatch.setattr(getpass, "getpass", ...)` temporarily replaces the function with a lambda that returns `"secret"` — and pytest reverts it automatically after the test. The second test proves the interrupt path:

```python
# lines 148–167
@pytest.mark.parametrize("exception", [KeyboardInterrupt, EOFError])
def test_prompt_hidden_handles_interrupt(view, monkeypatch, exception):
    def raise_exception(prompt):
        raise exception

    monkeypatch.setattr(getpass, "getpass", raise_exception)
    ...
    with pytest.raises(SystemExit) as e:
        view.prompt_hidden("Password:")

    assert e.value.code == 0
    assert clear_called
```

This is the study guide's "Mocking & Stubbing" topic applied to `getpass`: fake the I/O boundary, never the logic.

#### b) Unit-testing the Controller — `tests/unit/test_game_controller.py`

At the controller level, the *entire view* is a `Mock`, so `prompt_hidden` is just an attribute you script:

```python
view.prompt_hidden.return_value = "word"        # one canned answer
...
view.prompt_hidden.side_effect = ["bad", "good"] # sequential answers:
                                                 # first attempt invalid, second valid
```

The `side_effect` list simulates the real retry loop in `setup_game()`: the first hidden input is rejected by `game.set_word(...)`, the second is accepted. No terminal, no `getpass`, no human — the whole "moderator types a secret word" flow is exercised in milliseconds.

---

### 7. Key takeaways

1. **`getpass.getpass(prompt)` is the standard-library way to read a secret line without echoing it.** It's the same mechanism behind password prompts everywhere in Python.
2. **Use it only for secrets.** This project uses it exclusively for the word/phrase; everything else uses plain `input()`. Hiding non-sensitive input would just confuse players.
3. **Keep it in the View.** The only production import of `getpass` is in `console_view.py`. The controller calls `view.prompt_hidden(...)` and the interface guarantees the method exists — so the hiding mechanism is swappable per platform (terminal, GUI, web).
4. **Wrap it in the same interrupt handling as every other prompt.** `KeyboardInterrupt`/`EOFError` → clear screen, friendly message, `exit(0)`.
5. **Test it by patching, never by typing.** `monkeypatch.setattr(getpass, "getpass", ...)` in view tests; `view.prompt_hidden.return_value / side_effect` in controller tests.

---

### Quick self‑check (try these to lock it in)

1. In `hangman/view/console_view.py`, find the `import getpass` (line 2) and the `prompt_hidden` method (lines 33–39). Compare it with `prompt` (lines 25–31) and note that the only difference is the call: `input(message)` vs `getpass.getpass(prompt=message)`.
2. In `hangman/controller/game_controller.py`, find the two `prompt_hidden` call sites (lines 81 and 390) and the nearby plain `prompt` calls (e.g., line 107) — identify which inputs are hidden and which are visible, and why.
3. In `tests/unit/test_console_view.py`, read `test_prompt_hidden_returns_input` (lines 140–145) and `test_prompt_hidden_handles_interrupt` (lines 148–167), then run `pytest -k prompt_hidden` and confirm both pass with no terminal interaction.
4. Experiment: temporarily replace `getpass.getpass(prompt=message)` (line 35) with `input(message)`, run `python run.py`, choose manual word entry, and watch the word echo on screen as you type. Revert the change afterwards — that single-line diff is the entire observable effect of this topic.

**One‑line summary:** `getpass.getpass()` reads a line without echoing the characters to the screen, and this project confines it to a single place — `ConsoleView.prompt_hidden()` (console_view.py:35) — so the controller can request the secret word through the View contract (game_controller.py:81, 390) while the hiding mechanism stays swappable per platform and testable by monkeypatching.

---

---

## Topic 6.4 — Module Initialization & Run Execution

*Based on `docs/masterclass/_study_guide.md` (Section 6, fourth item) and the actual code in this project.*

### 1. What the study guide says

> **Module Initialization & Run Execution:**
> *Leveraging package-level imports via `__init__.py` and segregating the application runner (`if __name__ == "__main__":` entrypoint in `run.py`).*

That one bullet actually contains **two distinct mechanisms** that work together:

| Mechanism | Question it answers | Where in this project |
|---|---|---|
| **Package initialization** (`__init__.py`) | *"How does Python know a folder is a package, and what runs when the package is first imported?"* | `hangman/__init__.py` + 3 subpackage `__init__.py` files (all empty) |
| **Run execution** (`if __name__ == "__main__":`) | *"When does the program actually start, and how can the same file be imported without starting?"* | `run.py` (13 lines) + `tests/integration/test_run.py` |

The payoff of combining them: **the game can be launched by a human (`python run.py`) and dissected by a test suite (`import run`) using the exact same file.** That duality is the whole design story of this topic.

---

### 2. The map — where each piece lives

```
project_hangman/
├── run.py                      ← THE entrypoint (top-level script, NOT inside a package)
├── pytest.ini                  ← [pytest] pythonpath = .   (makes `import run` work in tests)
├── hangman/                    ← top-level package
│   ├── __init__.py             ← empty (0 lines)
│   ├── constants.py            ← MAX_HEALTH, HANGMAN frames, ...
│   ├── data/
│   │   ├── word_bank.json
│   │   └── word_bank_long.json
│   ├── model/
│   │   ├── __init__.py         ← empty
│   │   ├── game.py             ← `from .player import Player`        (relative import)
│   │   └── player.py
│   ├── view/
│   │   ├── __init__.py         ← empty
│   │   ├── view_interface.py   ← the 8-method View contract
│   │   └── console_view.py     ← `from .view_interface import View`  (relative import)
│   ├── controller/
│   │   ├── __init__.py         ← empty
│   │   └── game_controller.py  ← absolute imports (lines 1–3)
│   └── services/
│       └── word_repository.py  ← ⚠ no __init__.py here (see §4.4)
└── tests/
    ├── unit/...
    └── integration/test_run.py ← `import run as run_module` + runpy
```

Two structural facts drive everything below:

1. **`run.py` sits *outside* the `hangman` package.** It is a plain top-level script. That's why it can only use *absolute* imports (`from hangman.view.console_view import ...`) — relative imports (`from .x import y`) only exist *inside* a package.
2. **Every module inside `hangman/` is reachable by a dotted path** (`hangman.model.game`, `hangman.view.console_view`, ...) because each directory is marked as a package by an `__init__.py`.

---

### 3. Part A — Package initialization: what `__init__.py` actually does

#### a) The three jobs of `__init__.py`

When Python encounters `import hangman` (or any import that passes through `hangman`), it:

1. **Recognizes the directory as a package.** A folder with an `__init__.py` is a *regular package*. Without the file it would be a *namespace package* (PEP 420, Python 3.3+) — still importable, but with different, looser semantics.
2. **Executes `__init__.py` exactly once** (the first time, per process). Whatever code you put there runs *at import time*, before the importing module continues.
3. **Becomes the package's "front door."** Common uses: re-exporting the public API (`from .game import Game` so users can write `from hangman.model import Game`), defining `__all__`, or initializing package-level state.

#### b) This project's choice: empty marker files

All four `__init__.py` files in this codebase are **completely empty** (0 lines):

```
hangman/__init__.py            → empty
hangman/model/__init__.py      → empty
hangman/view/__init__.py       → empty
hangman/controller/__init__.py → empty
```

Empty is a *deliberate* minimalist style, and it has three consequences you can verify in the code:

- **No import-time side effects.** Importing `hangman` never runs game logic, never touches the file system, never prints anything. Imports stay fast and side-effect-free.
- **No re-exports.** Because nothing is re-exported, every import in the codebase must name the *full module path*. Compare what you see everywhere:
  ```python
  # run.py, line 1 — full path to the module
  from hangman.view.console_view import ConsoleView
  ```
  You will *not* find `from hangman.view import ConsoleView` anywhere — that would require a re-export in `hangman/view/__init__.py`, which doesn't exist.
- **No circular-import risk from the package layer.** Circular imports usually start when `__init__.py` files eagerly import submodules. With empty files, that failure mode simply doesn't exist.

#### c) What "executed once" means — the `sys.modules` cache

Every module Python executes is cached in `sys.modules` under its dotted name. Look at who imports `ConsoleView`:

```python
# run.py, line 1
from hangman.view.console_view import ConsoleView

# hangman/controller/game_controller.py, line 2
from hangman.view.console_view import ConsoleView
```

Two import statements, but `console_view.py` is **executed exactly once** per process. The second import just looks up the already-cached module in `sys.modules` and grabs the `ConsoleView` attribute from it. This caching is also why the integration tests can patch *one* place and affect *all* importers (see §5.4).

#### d) The anomaly: `hangman/services/` has no `__init__.py`

If you list the tree carefully, `hangman/services/` contains only `word_repository.py` — **no `__init__.py`**. Yet this import works perfectly:

```python
# hangman/controller/game_controller.py, line 3
from hangman.services.word_repository import WordRepository
```

Why? Because Python 3 falls back to treating `services/` as a **namespace package** (PEP 420). It's importable, but it's *inconsistent* with the other four subpackages that all have explicit (empty) `__init__.py` files. This is a classic "real codebase" wart: nothing is broken, but a linter or a future teammate would expect the marker file. Adding an empty `hangman/services/__init__.py` is a safe, zero-risk consistency fix — a good first exercise.

#### e) Relative vs. absolute imports — both styles, in one project

The codebase uses **both** import styles, and each appears where it makes sense:

| Style | Example | Where |
|---|---|---|
| **Relative** (`.` = "my own package") | `from .view_interface import View` | `console_view.py` line 5 |
| **Relative** | `from .player import Player` | `game.py` line 5 |
| **Absolute** (from project root) | `from hangman.model.game import Game` | `game_controller.py` line 1 |
| **Absolute** | `from hangman.view.console_view import ConsoleView` | `game_controller.py` line 2, `run.py` line 1 |
| **Package-level** (submodule *through* the package) | `from hangman import constants` | `run.py` line 3 |

Notes for a beginner:

- **Relative imports only work inside a package.** `run.py` is top-level, so it *must* use absolute imports — there is no "current package" for a `.` to refer to.
- **`from hangman import constants`** (run.py line 3) is the "package-level import" the study guide mentions. It imports the *submodule* `constants` through the package and binds the name `constants` in `run.py`'s namespace, so line 8 can write `constants_module=constants`. (The alternative `import hangman.constants` would bind only the name `hangman`, forcing `hangman.constants.MAX_HEALTH` everywhere.)
- **Relative imports survive package renames.** If you renamed `hangman/` to `hangman2/`, the two relative imports keep working untouched; the absolute ones would all need editing. Absolute imports are more explicit; relative ones are more robust. Both are idiomatic — the project just mixes them.

---

### 4. Part B — `run.py`: the segregated application runner

#### a) The whole file (13 lines)

```python
# run.py
from hangman.view.console_view import ConsoleView        # line 1
from hangman.controller.game_controller import GameController  # line 2
from hangman import constants                            # line 3


def run():                                               # line 6
        view = ConsoleView()                             # line 7
        controller = GameController(view=view, constants_module=constants)  # line 8
        controller.start()                               # line 9


if __name__ == "__main__":                               # line 12
    run()                                                # line 13
```

Every line of this file is a design decision. Let's take them apart.

#### b) The `__name__` mechanism — the core of "run execution"

Every Python module has a built-in attribute `__name__`:

- When a file is **executed directly** (`python run.py`), Python sets its `__name__` to the string `"__main__"`.
- When a file is **imported** (`import run`), its `__name__` is its module name — `"run"`.

So the guard on line 12:

```python
if __name__ == "__main__":
    run()
```

means: *"start the game only if I am the program the user asked to run — not if I am merely being imported."*

The two execution paths through the same file:

| | `python run.py` | `import run` (as in tests) |
|---|---|---|
| `__name__` | `"__main__"` | `"run"` |
| Lines 1–3 (imports) | execute | execute |
| Line 6 (`def run():`) | defines the function | defines the function |
| Line 12 guard | **True → `run()` executes → game starts** | **False → nothing happens** |
| Side effects | full interactive game | none — silent, instant import |

That second column is the entire reason the guard exists: **it makes the entrypoint import-safe.** Without it, the moment a test did `import run`, the game would boot and block waiting for keyboard input.

#### c) Why wrap the startup in a `run()` function instead of writing it under the guard?

You *could* write:

```python
if __name__ == "__main__":
    view = ConsoleView()
    controller = GameController(view=view, constants_module=constants)
    controller.start()
```

and it would work for a human. But the project deliberately factors out `run()` (line 6) for four reasons:

1. **Testability.** The integration tests call `run_module.run()` directly (test_run.py lines 66, 72, 86, 125, 179) with mocked dependencies. A bare guard block would be untestable in isolation.
2. **The guard becomes a one-liner.** "When to start" (the guard) and "what to start" (the function body) are separated — each is trivially readable.
3. **Reusability.** Any other launcher (a `python -m` script, a GUI wrapper, a demo harness) can call `run()` without duplicating the wiring.
4. **It marks the composition root.** `run()` is the *only* place in the entire codebase that instantiates concrete classes and wires them together:

   ```python
   view = ConsoleView()
   controller = GameController(view=view, constants_module=constants)
   ```

   This is the "segregating the application runner" half of the study guide's bullet. Every other module is wiring-agnostic: the controller receives its view and constants *by injection* (its constructor, `game_controller.py` line 16: `def __init__(self, view: ConsoleView, constants_module):`), the model knows nothing about views, and the view knows nothing about the model. Only `run.py` knows that *this* game uses *this* console view. Swap in a `TkinterView` later and the diff is confined to `run.py`.

#### d) Why `python run.py` can find the `hangman` package at all

When you run `python run.py`, Python automatically puts **the directory containing the script** (the project root) at the front of `sys.path`. That's what makes `from hangman.view.console_view import ConsoleView` resolvable — `hangman/` is a sibling of `run.py`.

The test suite needs the same fact, but pytest doesn't run `run.py` as a script, so the project supplies it explicitly in `pytest.ini`:

```ini
[pytest]
pythonpath = .
```

`pythonpath = .` tells pytest (≥ 7) to prepend the project root to `sys.path` before collecting tests. That single line is what makes `import run as run_module` (test_run.py line 3) and `import hangman...` work in every test file, no matter where pytest is launched from.

---

### 5. The full execution trace of `python run.py`

Walking through what the interpreter actually does, in order:

1. **Create the `__main__` module** and start executing `run.py` top to bottom.
2. **Line 1** — `from hangman.view.console_view import ConsoleView`:
   - `hangman` not in `sys.modules` → execute `hangman/__init__.py` (empty) → cache as `hangman`.
   - `hangman.view` not cached → execute `hangman/view/__init__.py` (empty) → cache.
   - Execute `hangman/view/console_view.py`. Its line 5 (`from .view_interface import View`) triggers execution of `hangman/view/view_interface.py` first (defines `View`), then `ConsoleView` is defined.
3. **Line 2** — `from hangman.controller.game_controller import GameController`:
   - `hangman` already cached → **not re-executed**.
   - Execute `hangman/controller/__init__.py` (empty).
   - Execute `hangman/controller/game_controller.py`, whose own imports cascade:
     - line 1 → `hangman/model/__init__.py` (empty), then `game.py`, whose line 5 (`from .player import Player`) executes `player.py` first;
     - line 2 → `console_view` already cached, just re-binds the name;
     - line 3 → `hangman/services/` (namespace package, no `__init__.py`) → executes `word_repository.py`.
   - Module-level line 7 also runs: `BASE_DIR = Path(__file__).resolve().parent.parent` — a harmless import-time computation (see §6, pitfall 6).
4. **Line 3** — `from hangman import constants` → executes `hangman/constants.py` (defines `MAX_HEALTH`, the `HANGMAN` ASCII frames, ...).
5. **Line 6** — `def run():` merely *defines* the function object. Its body does not run yet.
6. **Line 12** — `__name__` is `"__main__"` → guard is **True** → `run()` executes:
   - line 7: `view = ConsoleView()`;
   - line 8: `controller = GameController(view=view, constants_module=constants)` — note the constructor *also* builds `WordRepository(BASE_DIR / "data" / "word_bank.json")` (game_controller.py line 22), which reads and validates the JSON word bank;
   - line 9: `controller.start()` (game_controller.py line 361) → `setup_game()` → the interactive game begins.

Contrast with `import run`: steps 2–5 are identical, but step 6's guard is **False** — the import finishes silently with the game never started. *Same file, two behaviors, decided by one string comparison.*

---

### 6. Part C — "Run execution" in the test suite (`tests/integration/test_run.py`)

The study guide's Section 5 promises this:

> *Simulating the entrypoint (`run.py`) in `test_run.py` using `runpy` to test system initialization and coordinate module configurations under simulated execution blocks.*

Here is how the file delivers on that, test by test.

#### a) Importing the entrypoint — `import run as run_module` (line 3)

```python
import run as run_module
```

This works because of `pythonpath = .` in `pytest.ini`, and it is *safe* because of the `__main__` guard: importing `run` executes only the imports and the `def run():` — no game, no prompts, no blocking. The guard is what converts the entrypoint from "a program" into "a testable module."

#### b) The core wiring tests (lines 65–88)

The `patched_dependencies` fixture (lines 41–58) replaces the names *inside `run.py`'s namespace* with mocks:

```python
monkeypatch.setattr(run_module, "ConsoleView", mock_view_class)
monkeypatch.setattr(run_module, "GameController", mock_controller_class)
```

Then three tests verify the composition root's contract:

```python
def test_run_creates_view_instance(patched_dependencies):
    run_module.run()
    patched_dependencies["view_class"].assert_called_once_with()
```

```python
def test_run_creates_controller_with_correct_dependencies(patched_dependencies):
    run_module.run()
    ...
    assert kwargs["view"] is patched_dependencies["view_instance"]
    assert kwargs["constants_module"] is run_module.constants
```

```python
def test_run_calls_controller_start(patched_dependencies):
    run_module.run()
    patched_dependencies["controller_instance"].start.assert_called_once_with()
```

Together they pin down exactly what `run()` must do: construct the view, inject it (plus the `constants` module) into the controller, and call `start()`. If someone "improves" `run.py` and forgets the `constants_module` argument, `test_run_creates_controller_with_correct_dependencies` fails immediately.

#### c) Execution order (lines 95–131)

`test_run_execution_order` records the sequence with side-effect functions and asserts the exact order:

```python
assert call_order == [
    "view_created",
    "controller_created",
    "start_called"
]
```

This freezes the lifecycle: **view first, then controller (which needs the view), then start.**

#### d) Exception propagation (lines 138–179)

```python
@pytest.mark.parametrize("exception_stage", ["view", "controller", "start"])
def test_run_propagates_exceptions(mocker, monkeypatch, exception_stage):
    ...
    with pytest.raises(RuntimeError):
        run_module.run()
```

One test, three stages: a failure while constructing the view, while constructing the controller, or inside `start()` must **bubble out of `run()`** — the entrypoint must never silently swallow errors. (Compare with the view's own prompts, which *do* catch `KeyboardInterrupt`/`EOFError` on purpose — that's topic 6.5's territory.)

#### e) The `__main__` path itself — `test_main_executes_run` (lines 186–211)

This is the most instructive test in the file, because it exercises the guard:

```python
def test_main_executes_run(monkeypatch, mocker):
    mock_controller = mocker.Mock()
    mock_controller.start = mocker.Mock()
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

Three mechanisms are at work:

1. **`runpy.run_module("run", run_name="__main__")`** re-executes `run.py` in a *fresh* module namespace with `__name__` forced to `"__main__"` — i.e., it simulates `python run.py` without spawning a subprocess. The `run_name` argument is the key: by default `runpy` would set `__name__` to `"run"`, which would make the guard false and the test meaningless.
2. **Why patch the *source* modules, not `run_module`'s attributes?** Because `runpy` re-executes the file from scratch, re-running lines 1–2:
   ```python
   from hangman.view.console_view import ConsoleView
   from hangman.controller.game_controller import GameController
   ```
   Those `from ... import ...` statements re-bind the names in the *new* namespace by reading the attributes off the (already cached) source modules. If the test had patched only `run_module.ConsoleView`, the re-execution would have overwritten the mock with the real class. Patching `hangman.view.console_view.ConsoleView` at the source means the re-executed import picks up the mock. (This is the `sys.modules` caching from §3c working *for* the test.)
3. **The assertion** — `mock_controller.start.assert_called_once()` — proves the complete chain: guard fired → `run()` ran → view built → controller built → `start()` called. The entire "run execution" path, verified in milliseconds with no terminal.

---

### 7. Why this design is good (best-practice summary)

1. **Single, segregated entrypoint.** One file, one command (`python run.py`), one place that knows the concrete classes. The rest of the codebase is wiring-agnostic — the direct payoff of the DI design from Section 1 of the guide.
2. **Import-safe by construction.** The `__main__` guard makes the entrypoint a first-class importable module, which is what makes the whole integration test suite possible.
3. **Minimal package initialization.** Empty `__init__.py` files = zero import-time side effects, zero re-export magic, zero circular-import surface. The package structure is visible in the import paths instead of hidden in `__init__` files.
4. **The test suite mirrors the architecture.** `test_run.py` tests exactly the seams this topic creates: the wiring in `run()`, the order of construction, exception propagation, and the `__main__` guard itself.

---

### 8. Pitfalls & beginner notes

1. **Importing executes.** Any top-level code in a module runs at import time. The guard exists precisely to keep the *game-starting* code out of the import path. If `run.py` had a bare top-level `view = ConsoleView()`, every `import run` would construct a view.
2. **`__init__.py` runs at import time too.** Heavy work there (reading files, connecting to services) slows *every* import and is the classic source of circular-import bugs. Empty files sidestep both.
3. **The missing `hangman/services/__init__.py`.** It works (namespace package, PEP 420) but is inconsistent with the other four subpackages. Adding an empty file is a safe consistency fix.
4. **`run()`'s body is indented 8 spaces** (run.py lines 7–9) instead of the PEP 8 standard 4. It's *valid* Python — indentation just has to be consistent within a block — but a formatter like `black` would normalize it.
5. **`from hangman import constants` vs `import hangman.constants`.** The former binds the name `constants` (used on line 8); the latter binds only `hangman`, forcing `hangman.constants.MAX_HEALTH` style access. Both trigger identical execution.
6. **Module-level code in `game_controller.py`** — `BASE_DIR = Path(__file__).resolve().parent.parent` (line 7) — runs at import time. Harmless here (pure path computation), but a reminder that *any* top-level statement is an import-time side effect.
7. **Each module executes exactly once per process** (`sys.modules` caching). That's why `console_view.py` is imported by both `run.py` and `game_controller.py` yet runs only once — and why patching a name at its source module affects all importers (see §6e).

---

### 9. Key takeaways

1. **`__init__.py` marks a directory as a package and runs once at first import.** This project keeps all four of them *empty*: pure markers, no side effects, no re-exports — so every import names the full module path (`from hangman.view.console_view import ConsoleView`).
2. **`hangman/services/` is the odd one out** — no `__init__.py`, working as a PEP 420 namespace package. Inconsistent, not broken.
3. **`if __name__ == "__main__":` is what makes a file dual-natured:** executed directly → `__name__ == "__main__"` → the game starts; imported → `__name__ == "run"` → only definitions happen. The guard is the entire reason `import run` is safe.
4. **`run()` is the composition root:** the only place that instantiates `ConsoleView` and `GameController` and injects the `constants` module (run.py lines 7–8). Factoring it into a function (instead of inlining under the guard) is what makes it testable and reusable.
5. **`pythonpath = .` in `pytest.ini`** puts the project root on `sys.path` for tests, mirroring what `python run.py` does automatically for the script.
6. **`test_run.py` verifies the whole topic:** wiring (lines 65–88), construction order (lines 95–131), exception propagation (lines 138–179), and the `__main__` guard via `runpy.run_module("run", run_name="__main__")` (lines 186–211) — patching the *source* modules because `runpy` re-executes the imports.

---

### Quick self‑check (try these to lock it in)

1. **Feel the guard.** In a scratch copy of `run.py`, delete the `if __name__ == "__main__":` line and call `run()` unconditionally at the top level. Then run `pytest tests/integration/test_run.py` and watch the tests break — the game now starts at *import* time. Restore the guard and watch them pass again.
2. **See `__init__.py` execute.** Add `print("hangman package initialized")` to `hangman/__init__.py` and run `python run.py`. It prints exactly once, before anything else — even though `run.py` never mentions `__init__.py`. Then add the same print to `hangman/view/__init__.py` and observe the order of the two lines.
3. **Try the re-export pattern.** In a scratch copy, add `from .console_view import ConsoleView` to `hangman/view/__init__.py` and change run.py line 1 to `from hangman.view import ConsoleView`. It works — now you understand why the project *chose not to* do this (no re-exports, full paths everywhere).
4. **Fix the anomaly.** Create an empty `hangman/services/__init__.py`, run the full test suite, and confirm nothing changes. You've just made the package structure uniform.
5. **Trace the path.** Run `python run.py` from the project root, then from a completely different directory using the full file path (`python "F:\...\project_hangman\run.py"`). Both work — print `sys.path[0]` at the top of `run.py` to see *why* (it's the script's directory, not your current directory).

**One‑line summary:** Empty `__init__.py` files mark `hangman/` as a side-effect-free package whose modules are imported by full dotted path, while `run.py` — the sole composition root — uses `if __name__ == "__main__":` to start the game only when executed directly, so the very same file can be imported by `test_run.py` (with `pythonpath = .` and `runpy.run_module(..., run_name="__main__")`) to verify the wiring, the order, and the guard itself.
