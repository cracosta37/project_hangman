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
