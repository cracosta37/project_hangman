# 2. Object-Oriented Programming (OOP) Principles

## Topic 2.1 — Encapsulation & Information Hiding

### The core idea

Two related concepts:

- **Encapsulation**: bundling data (attributes) and the behavior that operates on that data (methods) inside a single unit — a class.
- **Information hiding**: the class keeps its *internal representation* private and exposes only a small, controlled **public interface**. Callers use the interface; they never need to know (or touch) how the data is stored internally.

The payoff: you can change *how* a class stores or computes something without breaking any code that uses it, and you can **protect invariants** (rules that must always be true) by funneling all changes through methods that enforce them.

> Python note: Python has **no real `private` keyword**. It uses *conventions*:
> - `_name` → "internal use, don't touch from outside" (soft, honor-system privacy)
> - `__name` → name-mangling (hard privacy, `self.__x` becomes `self._ClassName__x`)
>
> Your project uses the first convention everywhere — the idiomatic Python style.

---

### Example 1: `Player` — the textbook case (`hangman/model/player.py`)

```python
class Player:
    """Represents a player in the Hangman game."""

    def __init__(self, name: str, max_health: int, hangman_states: List[str]):
        self.name: str = name
        self.max_health: int = max_health
        self.health: int = max_health
        self.hangman_states: List[str] = hangman_states

    def lose_health(self) -> bool:
        previous = self.health
        self.health = max(0, self.health - 1)
        return previous > 0 and self.health == 0

    def is_alive(self) -> bool:
        return self.health > 0
```

#### What's hidden, and what's exposed?

The raw fact is `self.health`. But the *meaningful operations* are wrapped in two methods:

**`lose_health()` (player.py:13-16)** encapsulates three rules that must *always* hold together:
1. Health drops by exactly 1 per mistake.
2. Health **never goes below zero** — `max(0, self.health - 1)` clamps it.
3. It *reports* the transition: returns `True` only on the exact turn where the player dies.

**`is_alive()` (player.py:18-19)** encapsulates the definition of "alive" in one place.

#### "What if" — without encapsulation

Imagine the controller did this instead:

```python
# BAD: the controller reaches into Player's internals
player.health -= 1
if player.health == 0:
    self.game.remaining_players -= 1
```

Problems this creates:
- The "don't go negative" rule is now the *controller's* responsibility. Tomorrow someone writes `player.health -= 2` or forgets the clamp, and a player has `-3` health — an **invalid state** your game can silently propagate.
- "What does death mean?" (`health == 0`?) is now duplicated in the controller and possibly the view. Change the rule (e.g., "eliminated at health < 2") and you must hunt down every copy.
- With `lose_health()`, there is **exactly one place** where health changes, so the invariant can never be violated.

#### Who respects the boundary?

The controller never touches `health` to make decisions — it asks:

```python
# game_controller.py:156
if not player.is_alive():
    i += 1
    continue
```

And the view just *reads* the state to render the ASCII art:

```python
# console_view.py:52-53
def show_health(self, player) -> None:
    print(player.hangman_states[player.health])
```

The view is "dumb": it displays whatever the player object reports. It doesn't know or care how health is managed.

---

### Example 2: `Game` — internal state + a status-dictionary interface (`hangman/model/game.py`)

`Game` holds all the sensitive internal state (game.py:15-22):

```python
self.word: str = ""
self.unknown_word: List[str] = []
self.remaining_letters: set[str] = set()
self.remaining_players: int = 0
self.n_players: int = 0
self.remaining_spaces: int = 0
self.is_phrase: bool = False
```

None of these are ever mutated by the controller or view. Instead, `Game` exposes a **public API of action methods** that process input internally and return a *status dictionary*:

```python
def guess_letter(self, player_index: int, raw_letter: str) -> Dict[str, Any]:
    ...
```

`guess_letter()` (game.py:127-194) is where the information hiding pays off. Look at what must happen **atomically and in the right order** for one guess:

1. Validate the player index and that the player is alive (game.py:128-133)
2. Validate the raw input is a single letter (game.py:136-141)
3. Normalize it (game.py:143)
4. Check it wasn't already used (game.py:146-151)
5. **Consume** it: `self.remaining_letters.remove(letter)` (game.py:154)
6. Find all positions, reveal them in `unknown_word`, decrement `remaining_spaces` (game.py:155-156, 176-178)
7. On a miss: call `player.lose_health()`, update `remaining_players` (game.py:159-162)
8. Determine win/over and return a structured report (game.py:183-194)

The controller's entire job is to **send input in, read the report out** (game_controller.py:241-256):

```python
raw_letter = self.view.prompt("Please insert a letter: ")
result = self.game.guess_letter(player_index, raw_letter)

if not result.get("ok") and not result.get("repeat"):
    ...  # non-recoverable error
if result.get("repeat"):
    ...  # re-ask
```

Notice what the controller *cannot* do: it can't accidentally reveal the answer, double-count a letter, or desynchronize `remaining_spaces` from `unknown_word`, because it has no access path to do those things. All state transitions are **centralized** — which the study guide calls "State Management" in section 3.

#### Defensive copies — a subtle but important technique

```python
def get_visible_word(self) -> List[str]:        # game.py:256-257
    return list(self.unknown_word)

def get_remaining_letters(self) -> set:         # game.py:264-265
    return set(self.remaining_letters)
```

These return **copies**, not the live objects. If they returned the real list/set, the view could do `game.get_visible_word()[0] = "X"` and corrupt game state without ever calling a method. Copying on read closes that leak. This is information hiding in its strictest form: you get *information*, not a *handle*.

(Contrast with `get_player()` at game.py:259-262, which deliberately returns the real `Player` object — but that's fine because `Player` itself enforces its own invariants through its methods.)

#### The `_` convention in action

```python
def _normalize(self, text: str) -> str:   # game.py:34
```

The leading underscore says: "this is an implementation detail. Outside code (including the controller) should not call it." It *can* call it (Python won't stop it), but the name signals it's not part of the public contract. `WordRepository` uses this heavily: `_load`, `_add_if_valid`, `_validate_normalize`, `_normalize_for_internal` are all private; only `get_by_difficulty()` and `reset_session()` are public (word_repository.py:146, 170).

---

### Example 3: `WordRepository` — hiding complexity, not just data

Encapsulation isn't only about protecting data; it's also about **hiding how something is done**. `WordRepository` (word_repository.py) internally does:

- resolving a `Path` (line 24)
- checking file existence (line 44)
- parsing JSON with error translation (lines 47-51)
- accepting two different file formats (lines 53-56)
- validating every entry: type, length ≤ 120, allowed characters, ≥ 2 letters (lines 84-117)
- unicode normalization to a canonical form (lines 122-141)
- session-level no-repeat bookkeeping via `used_words` (lines 159-167)

But its **entire public interface is two methods**:

```python
selected = self.word_repo.get_by_difficulty(difficulty)   # controller line 93
self.word_repo.reset_session()                            # controller line 383
```

The controller never imports `json`, never opens the file, never knows words are stored in `normalized_words_by_diff`. If you later swapped the JSON file for a SQLite database or a web API, **only the repository internals would change** — the controller code above stays identical. That's information hiding enabling the Repository pattern (section 3 of the guide).

---

### The boundary in the MVC structure

You can see encapsulation expressed architecturally:

| Component | May read | May modify |
|---|---|---|
| `Game` (model) | its own state, `Player` objects | everything — but only through its own methods |
| `GameController` | status dicts, `get_visible_word()`, `is_game_over()` | nothing in the model directly |
| `ConsoleView` (view) | data passed to it as arguments | nothing at all — it just prints |

The controller is the only component that *calls* model methods; the view never calls any. Each layer depends on the next one's **public interface only** — that's the "low coupling" the guide mentions in 2.4.

---

### Honest caveats (worth knowing as a beginner)

1. **Python privacy is a promise, not an enforcement.** `player.health = 0` is perfectly valid Python from anywhere. You'll even see it in *your tests*, e.g. `test_player.py:100` (`player.health = initial_health`) and `test_game.py:105` — tests commonly set state directly to create a starting condition, then exercise one method. That's an accepted practice: tests are inside the "trusted" boundary.
2. **`Game` itself reaches into `Player`** in one place — `reset_for_new_round()` does `p.health = p.max_health` (game.py:93) instead of a `player.reset()` method. It works, but the "cleaner" design would add a method to `Player`. A good exercise for you: add `def restore_health(self)` to `Player` and use it there, so *no* health mutation exists outside the `Player` class.
3. The real enforcement tools in Python, if you ever need them: **`@property`** (custom get/set logic with validation) and `__name` mangling. For most application code — like this project — the `_` convention plus discipline is the idiomatic choice.

---

### Summary

| Concept | Where to see it |
|---|---|
| Methods wrapping state changes | `Player.lose_health()` / `is_alive()` — player.py:13-19 |
| Invariant protection | `max(0, ...)` clamp; letter consumed exactly once |
| Centralized rules | `Game.guess_letter()` — all 8 steps in one method, game.py:127 |
| Structured results instead of state poking | status dicts (`ok`, `repeat`, `correct`, `eliminated`, `game_won`…) |
| Defensive copies | `get_visible_word()`, `get_remaining_letters()` — game.py:256-265 |
| `_` internal convention | `_normalize`, `_load`, `_validate_normalize` |
| Hiding complexity | `WordRepository`'s 2-method public API over ~150 lines of machinery |

The one-sentence version: **callers interact with *what a class does*, never with *what a class contains*.**

---
---

## Topic 2.2 — Abstraction

**Abstraction** means exposing *only what a component does* while hiding *how it does it*. Callers work with a simple, stable interface; the complex internals can change without touching the callers.

In Python there are **two related uses of the word**, and this codebase demonstrates both:

1. **Hiding complexity** — wrapping messy mechanics behind a simple method (e.g. `WordRepository`, `Game`).
2. **Abstract = "general, not concrete"** — a class that defines a contract but not a behavior (e.g. the `View` base class), versus a *concrete* class that implements it (e.g. `ConsoleView`).

Let's walk through each with real code.

---

### Example 1: `WordRepository` — hiding complexity behind one simple method

This is the flagship example from the study guide. Look at the public API (`hangman/services/word_repository.py:146`):

```python
def get_by_difficulty(self, difficulty: str) -> str:
    """
    Return a random unused word for the given difficulty key ("EASY","MEDIUM","HARD").
    Raises ValueError if difficulty is invalid or no words are available.
    """
```

That's the **whole interface the rest of the program needs**: give it a difficulty, get a word back. But inside that class, all this complexity is hidden:

| Hidden inside `WordRepository` | Where |
|---|---|
| File existence check + `FileNotFoundError` | `_load()` line 44 |
| File reading + JSON parsing + `ValueError` on bad JSON | `_load()` lines 47–51 |
| Accepting two different JSON formats (dict or list) | `_load_from_dict` / `_load_from_list`, lines 65–82 |
| Per-word validation (type, empty, >120 chars, allowed characters, min 2 letters) | `_validate_normalize()` lines 84–117 |
| Unicode normalization (NFD decomposition, accent stripping, uppercasing, space collapsing) | `_normalize_for_internal()` lines 122–141 |
| Session-level no-repeat bookkeeping (`used_words` set) | `get_by_difficulty()` lines 159–167 |
| Random selection with a deterministic tie-break (`sorted`) | line 165 |

Notice the class docstring (`word_repository.py:11–18`) states the **guarantees of the abstraction** — this is the *contract*:

```python
"""
Loads, validates, normalizes, and serves words/phrases.

Guarantees:
- All stored words satisfy Game.set_word() constraints
- All internal storage is normalized
- No-repeat enforced at session level
"""
```

#### The payoff: the caller is trivially simple

In `hangman/controller/game_controller.py:91–97` the controller just does:

```python
while True:
    try:
        selected = self.word_repo.get_by_difficulty(difficulty)
    except ValueError as e:
        self.view.display(str(e) + "\n")
        difficulty = self.choose_difficulty()
        continue
```

The controller has **no idea** (and doesn't need to know) that words come from a JSON file, that accents are stripped, that duplicates are filtered, or that used words are remembered. It only knows:
- input: a difficulty string
- output: a word
- failure: a `ValueError`

**Why this matters:** if tomorrow the word bank moves from a JSON file to a SQLite database or a web API, you rewrite the *inside* of `WordRepository` and the controller doesn't change one line. That's the abstraction paying off.

#### Abstraction vs. encapsulation, side by side

These two concepts are often confused; `WordRepository` shows the difference clearly:

- **Abstraction** = the *design-level* "what": `get_by_difficulty(difficulty) -> str`. The shape of the interface.
- **Encapsulation** = the *implementation-level* "how it's protected": the `_load`, `_validate_normalize`, `_normalize_for_internal` methods and the `used_words` / `normalized_words_by_diff` attributes use the leading-underscore convention (lines 26–28), signaling "internal detail, don't touch."

Abstraction decides *what to hide*; encapsulation is the *mechanism* that hides it.

---

### Example 2: the `View` base class — an *abstract* contract

Now the second meaning. `hangman/view/view_interface.py` defines a class that describes **what every view must be able to do**, without doing anything itself:

```python
class View:
    """Abstract interface for user interaction."""

    def display(self, message: str) -> None:
        raise NotImplementedError

    def show_title(self) -> None:
        raise NotImplementedError

    def prompt(self, message: str) -> str:
        raise NotImplementedError

    def prompt_hidden(self, message: str) -> str:
        raise NotImplementedError

    def pause(self, message: str = "Press Enter to continue...") -> None:
        raise NotImplementedError

    def clear(self) -> None:
        raise NotImplementedError

    def show_word(self, word_state: List[str]) -> None:
        raise NotImplementedError

    def show_health(self, player) -> None:
        raise NotImplementedError
```

That's **8 methods = the contract**: "any view I accept must be able to display a message, prompt for input, show the word state, show a player's health, and so on."

The **concrete** implementation is `ConsoleView` (`hangman/view/console_view.py:8`), which inherits from `View` and actually implements each method:

```python
class ConsoleView(View):
    """Handles all console-based input and output operations."""

    def display(self, message: str) -> None:
        print(message)

    def show_word(self, word_state: List[str]) -> None:
        print(f"    {' '.join(word_state)}\n")

    def show_health(self, player) -> None:
        print(player.hangman_states[player.health])
        print()
```

Because `GameController` only ever talks to `self.view` through those 8 methods (e.g. `self.view.show_word(self.game.get_visible_word())` at `game_controller.py:163`), you could write a `PygameView` or `TkinterView` class that implements the same 8 methods, swap it in, and the controller would work unchanged.

#### Two ways to enforce the contract (Option A vs Option B)

The study guide highlights a deliberate design choice here:

**Option A — Duck typing + `NotImplementedError` (this project's choice).** `View` is a *regular* class, so nothing is enforced by the language — it's a documented promise. Any object with those 8 methods works, even without inheriting from `View` ("if it quacks like a duck..."). The failure mode is **late**: a subclass that forgets to override `show_word` runs fine until someone actually *calls* `show_word`, at which point it raises `NotImplementedError`.

**Option B — ABC (Abstract Base Class).** You'd write:

```python
import abc

class View(abc.ABC):
    @abc.abstractmethod
    def display(self, message: str) -> None: ...
```

Now the *language* enforces the contract: creating an incomplete subclass fails **at construction** with a `TypeError`. This is **early / fail-fast** failure.

#### The test that freezes the decision

`tests/unit/test_view_interface.py` guards this design with two kinds of tests:

1. `test_all_methods_raise_not_implemented` (line 36) — parametrized over all 8 methods, proves each one in the base class really does `raise NotImplementedError`, so the "late failure" behavior is intentional and tested:

```python
@pytest.mark.parametrize("method_name, args", [
    ("display", ("Hello",)),
    ("prompt", ("Enter something:",)),
    ...
])
def test_all_methods_raise_not_implemented(view_instance, method_name, args):
    method = getattr(view_instance, method_name)
    with pytest.raises(NotImplementedError):
        method(*args)
```

2. `test_view_is_instantiable` (line 163) — asserts that `View()` **can** be instantiated:

```python
def test_view_is_instantiable():
    """The interface can currently be instantiated (non-ABC design)."""
    view = View()
    assert isinstance(view, View)
```

This test is a **design tripwire**: if someone later "fixes" `View` into a true ABC (Option B), `View()` would raise `TypeError` and this test would fail immediately, forcing the design change to be made on purpose and visibly — instead of silently changing failure timing for everyone.

---

### Example 3: `Game` — behavior-level abstraction of game rules

The third example is subtler. `Game` (`hangman/model/game.py:8`) is a "pure game model: contains all rules and state but performs no I/O." The abstraction here is **behavioral**: the controller never implements game rules itself. It calls one method and reads a structured result.

Look at `guess_letter` (`game.py:127`). All the hard logic is *inside*: input validation, normalizing the letter (stripping accents), checking repeats, finding all matching positions in the word, decrementing health on a miss, detecting elimination, and detecting a win. It hands back a **status dictionary**:

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

The controller's job shrinks to *interpreting* that dictionary (`game_controller.py:240–256`):

```python
while True:
    raw_letter = self.view.prompt("Please insert a letter: ")
    result = self.game.guess_letter(player_index, raw_letter)

    # Non-recoverable error → exit handler
    if not result.get("ok") and not result.get("repeat"):
        self.view.display(result.get("error", "Invalid operation.") + "\n")
        self.view.pause()
        return result

    # Recoverable error → retry input
    if result.get("repeat"):
        self.view.display(result.get("error", "Invalid input.") + "\n")
        continue

    # Valid input
    break
```

Notice the **abstraction boundary in action**:

- The controller does **not** know how a guess is normalized, how positions are found, or when the game is won — it just reads `result["correct"]`, `result["game_won"]`, `result["winner"]`.
- It does **not** modify game state directly. It never writes to `game.word`, `game.unknown_word`, or a player's `health`. All state changes happen *inside* model methods (`guess_letter`, `set_word`, `create_players`), which also return status dicts like `{"ok": False, "error": "..."}` so the controller can display errors without knowing which rule was broken.
- Even the "is the game over?" check is abstracted: the controller calls `self.game.is_game_over()` (`game.py:253`) instead of re-deriving the win/loss condition itself.

**Why this matters:** the entire rule set is testable in isolation with zero I/O (that's exactly what `tests/unit/test_game.py` does), and if the rules change — say, health is restored between rounds, or repeated letters no longer count — only `Game` changes.

---

### How abstraction pays off in the tests (tying it together)

Because the controller depends on the *abstract* `View` contract rather than on real console I/O, `tests/unit/test_game_controller.py:14` can do:

```python
view = Mock()
...
controller = GameController(view=view, constants_module=Mock())
```

A `Mock()` object "implements" any contract automatically — every method returns a controllable fake value. So a full game round can be simulated without a terminal. This only works *because* the code was written against the abstraction (the 8-method contract), not against `ConsoleView` specifically.

---

### Summary

| Abstraction | Hidden complexity | Simple interface exposed |
|---|---|---|
| `WordRepository` | file I/O, JSON parsing, validation, unicode cleanup, no-repeat state | `get_by_difficulty(difficulty) -> str` |
| `View` (abstract) | which UI technology, how text is rendered, how input is read | 8 contract methods (`display`, `prompt`, `show_word`, ...) |
| `ConsoleView` (concrete) | platform details (`cls` vs `clear`, `getpass`, Ctrl+C handling) | the same 8 methods, actually implemented |
| `Game` | normalization, letter matching, health/elimination, win detection | `guess_letter(...) -> status dict` |

The through-line: **every caller in this codebase only ever sees a small, stable interface**, and all the fiddly mechanics (files, unicode, I/O, rules) are locked behind it. That is what makes the project testable, swappable (JSON → database, console → GUI), and maintainable.

---
---

## Topic 2.3 — Single Responsibility Principle (SRP)

### The principle in one sentence

**A class should have only *one reason to change*.** In practice: each class owns exactly one job (one "responsibility"), and everything in that class serves that job. If you can name two unrelated reasons why you'd edit a class, it probably has two responsibilities and should be split.

Your study guide (`docs/study_guide.md:39-43`) states the project's version of SRP directly:

> - `Player` maintains identity and health.
> - `Game` maintains multi-player states and applies round-based game rules.
> - `WordRepository` manages the loading, validation, and history of game words.

Let's see each one in the code.

---

### Responsibility 1: `Player` — identity and health only

`hangman/model/player.py` is only 19 lines. Its entire job: *know who it is and how much health it has left.*

```python
class Player:
    """Represents a player in the Hangman game."""

    def __init__(self, name: str, max_health: int, hangman_states: List[str]):
        self.name: str = name
        self.max_health: int = max_health
        self.health: int = max_health
        self.hangman_states: List[str] = hangman_states

    def lose_health(self) -> bool:
        previous = self.health
        self.health = max(0, self.health - 1)
        return previous > 0 and self.health == 0

    def is_alive(self) -> bool:
        return self.health > 0
```

- **Its single reason to change:** anything about how a player's *health/identity* works — e.g., "health decreases by 2 instead of 1", or "players get a shield". You'd edit only `player.py`.
- **What it deliberately does NOT do:**
  - It never prints anything. Notice `hangman_states` is just *stored data* here; the actual drawing happens in the View — `ConsoleView.show_health` prints it (`hangman/view/console_view.py:52-54`).
  - It never guesses letters, never checks if the word is complete, never touches files.
  - It even hides its internal state behind methods: you call `lose_health()` / `is_alive()` instead of reading `player.health` directly (that's the Encapsulation item in the same section of the guide working hand-in-hand with SRP).

**Counter-example (SRP violation):** imagine `Player` also had a `print_my_health()` method with a `print()` inside. Then you'd have *two* reasons to change it: health rules, and display format. Later, when you move from console to a GUI, you'd have to hunt through the model to find the printing code. This project avoids that by keeping `Player` I/O-free.

---

### Responsibility 2: `Game` — the rules and round state only

`hangman/model/game.py:8-9` is self-documenting about its single job:

```python
class Game:
    """Pure game model: contains all rules and state but performs no I/O."""
```

Its one responsibility: *apply the rules of a hangman round and track whose turn it is / what remains.*

```python
def guess_letter(self, player_index: int, raw_letter: str) -> Dict[str, Any]:
    ...
    if letter not in self.remaining_letters:
        return {..., "repeat": True, "error": f"The letter '{raw_letter}' was already used."}
    self.remaining_letters.remove(letter)
    positions = [i for i, l in enumerate(self.word) if l == letter]
    ...
    if times == 0:
        eliminated = player.lose_health()
        ...
```

Everything in this class serves the "game rules" job:

| Method | Serves the rule of... |
|---|---|
| `set_word` (`game.py:46`) | what a valid secret word is |
| `guess_letter` / `guess_word` | how a guess affects health, spaces, elimination |
| `reset_for_new_round` (`game.py:72`) | what carries over between rounds |
| `is_game_over`, `get_visible_word` | exposing round state for others to read |

Key SRP observations:

1. **No I/O.** The docstring "performs no I/O" is a deliberate contract. `Game` never calls `print` or `input` — all of that is the View's job. So if you later build a `PygameView` or `TkinterView` (as the guide's *Program to Interfaces* item mentions), `game.py` doesn't change at all.
2. **It delegates instead of absorbing other classes' jobs.** When a guess is wrong, `Game` calls `player.lose_health()` (`game.py:160`) rather than doing `player.health -= 1` itself. The *mechanics of health* remain `Player`'s responsibility; `Game` only uses the result. (One small nuance: `reset_for_new_round` sets `p.health = p.max_health` directly at `game.py:93` — a minor shortcut you could later move into a `Player.reset()` method to keep the principle strict.)
3. **It returns status dictionaries instead of printing messages.** See the `{"ok": ..., "error": ...}` results. `Game` *decides* "that letter was repeated"; the *displaying* of the error message is the Controller/View's job. That's how one class keeps one reason to change.

**Counter-example:** if `Game.guess_letter` contained `print("Wrong letter!")` and `input("Try again: ")`, then a change in console formatting or a move to a GUI would force edits in the rules engine — and you couldn't unit-test the rules without a terminal.

---

### Responsibility 3: `WordRepository` — word data management only

`hangman/services/word_repository.py:10-18` announces its job in the docstring:

```python
class WordRepository:
    """
    Loads, validates, normalizes, and serves words/phrases.

    Guarantees:
    - All stored words satisfy Game.set_word() constraints
    - All internal storage is normalized
    - No-repeat enforced at session level
    """
```

Its single responsibility: *be the gatekeeper of word data* — reading the JSON file, rejecting bad entries, normalizing unicode, and serving one unused word per call.

```python
def get_by_difficulty(self, difficulty: str) -> str:
    ...
    available = self.normalized_words_by_diff[key] - self.used_words
    if not available:
        raise ValueError(f"No unused words remaining for difficulty: {key}")
    selection = random.choice(tuple(sorted(available)))
    self.used_words.add(selection)
    return selection
```

Note the beautiful boundary in that method: `WordRepository` **knows nothing about the game** — it doesn't ask who the players are, doesn't check health, doesn't print. It just hands back a clean word and tracks the "history" (the `used_words` set) so a word is never repeated in a session. And conversely, `Game.set_word` (`game.py:46`) **knows nothing about files** — it only validates that a word is usable in a round. The two responsibilities stay on separate sides of the wall.

- **Its single reason to change:** anything about *where words come from or how they're cleaned* — e.g., switching from a JSON file to a database or a web API. The rest of the app only ever calls `get_by_difficulty(...)`, so it never changes (this is exactly why the guide lists it under both SRP and the Repository pattern).
- **What it does NOT do:** no printing, no game rules, no player logic. Its only "talk" with the outside is method arguments, return values, and raised exceptions (`FileNotFoundError`, `ValueError`).

**Counter-example:** if `WordRepository` also decided *how many lives a player gets* (mixing game rules into data storage) or if `Game` opened the JSON file itself (mixing file I/O into rules), you'd have classes with two reasons to change — and every new difficulty system or new word source would ripple through the code.

---

### How SRP pays off in this project

1. **MVC falls out naturally.** SRP is the micro-level version of Separation of Concerns:
   - Model = `Player` + `Game` (rules and state, zero I/O)
   - View = `ConsoleView` (`console_view.py:8-9`: "Handles all console-based input and output operations")
   - Controller = `GameController` (`game_controller.py:10-14`: "orchestrates the interaction... All I/O is performed via the View")
2. **Each class gets its own clean test file** — `test_player.py`, `test_game.py`, `test_word_repository.py`, `test_console_view.py`, `test_game_controller.py`. Because `Player` has no I/O, `test_player.py` can test health logic in microseconds with no terminal involved. That's a direct benefit of SRP.
3. **Change isolation (the practical test of SRP).** Ask for each change "which files would I touch?":
   - New hangman drawing → `constants.py` + `ConsoleView` only.
   - Players get 5 lives instead of 6 → `constants.py` (`MAX_HEALTH`) only.
   - Words come from an API → `WordRepository` only.
   - Add a "double-elimination" rule → `Game` only.
   
   Each change has exactly one home — that's SRP working.

### A quick heuristic for you as a beginner

When writing (or reviewing) a class, run this check:

1. Can you state its responsibility in **one sentence**? (`Player`: "tracks a player's name and health.")
2. Does every method in the class **serve that sentence**? (If you find a `print()` in `Game` or a `json.load` in `Player`, you've found a second responsibility.)
3. Does it **talk to other classes only through their public methods**, never by reaching into their internals? (The one exception in this codebase is `game.py:93`, `p.health = p.max_health` — a small pragmatic shortcut, worth knowing about so you can decide for yourself when strictness is worth it.)

If you can pass all three, your class follows SRP — and so does every class in this Hangman codebase.

---
---

## Topic 2.4 — High Cohesion & Low Coupling

### 1. The two ideas in plain English

These are two different qualities of a class:

- **Cohesion** looks *inside* a class: do all its methods belong together around **one single job**?
  - *High cohesion* = every method in the class is about the same thing. (Good)
  - *Low cohesion* = a grab-bag of unrelated methods. (Bad — a "god class")

- **Coupling** looks at the *lines between* classes: how much does one class depend on the **internal details** of another?
  - *Low coupling* = classes only talk through small, well-defined doors (method calls + parameters). You can change one without touching the other. (Good)
  - *High coupling* = a class reaches into another class's private fields/implementation. Change one and the other breaks. (Bad)

**One-sentence summary:** cohesion is about the *inside* of a box; coupling is about the *thinness of the lines* between boxes. You want each box tightly focused, but the lines between boxes thin and formal.

#### Restaurant analogy

- The **kitchen** is highly cohesive — it *only* cooks. Every station (grill, pastry, sauté) is about food.
- The kitchen is loosely coupled to the **dining room** — they communicate through one small, defined channel: a ticket goes in, a dish comes out. The cook never sees the customer's name or payment method.
- If the cook also had to take the money *and* set the tables (high coupling), changing the payment system would force a redesign of the cooking.

Map that to Hangman:

| Role | Kitchen (logic) | Waiter (I/O) | Manager (coordination) | Pantry (data) |
|------|-----------------|--------------|------------------------|---------------|
| Class | `Game`, `Player` | `ConsoleView` | `GameController` | `WordRepository` |

---

### 2. The dependency map (the visual signature of low coupling)

```
                     run.py   (composition root)
                   /    |     \
          ConsoleView  |      constants
                       v
               GameController
                 /     |      \
              View    Game   WordRepository
             (iface)   |
                       Player
```

The arrows point in **one direction only**. The Model (`Game`/`Player`) and the View point at *nothing* in the app. Only the Controller and `run.py` know about the other pieces. That one-way flow is exactly what low coupling looks like on a diagram.

---

### 3. High Cohesion — one job per class

#### `Player` — "a single player's identity and health"

`hangman/model/player.py:4-19`
```python
class Player:
    def __init__(self, name, max_health, hangman_states): ...
    def lose_health(self) -> bool: ...
    def is_alive(self) -> bool: ...
```
All three members revolve around **one topic**: how much life this player has. There is no word logic, no guessing, no printing. `Player` doesn't even know what a "guess" is.

#### `WordRepository` — "load, validate, and serve words"

`hangman/services/word_repository.py:10-172` — every method serves the word bank:
- `_load`, `_load_from_dict`, `_load_from_list`, `_add_if_valid` → get words in from the file
- `_validate_normalize`, `_normalize_for_internal` → clean + canonicalize them
- `get_by_difficulty`, `reset_session` → hand them out

It never displays anything and never scores a guess. *"I am the word bank, and that's all I do."*

#### `Game` — "all the rules and state of a round"

`hangman/model/game.py:8-265`:
- Setup: `set_word`, `create_players`, `reset_for_new_round`
- Rules: `guess_letter`, `guess_word`
- State queries: `is_game_over`, `get_visible_word`, `get_player`, `get_remaining_letters`, `word_label`

All of it is "the rules of Hangman." The docstring at `game.py:9` says it outright: *"Pure game model: contains all rules and state but performs no I/O."* There is no `print` and no `input` anywhere in the file.

#### `ConsoleView` — "all console input/output"

`hangman/view/console_view.py:8-54`: `clear`, `display`, `show_title`, `prompt`, `prompt_hidden`, `pause`, `show_word`, `show_health`. Every method either reads the keyboard or writes the screen. Zero game logic.

#### `GameController` — "orchestrate the flow"

`hangman/controller/game_controller.py:10-438`: the `choose_*` config prompts, `setup_game`, `run_game_loop`, `handle_letter_guess`, `handle_word_guess`, `start`, `exit_game`. Its job is to *decide what happens next* and *pass messages* between View and Model. It never implements a rule itself — it delegates (e.g., it calls `self.game.guess_letter(...)` at `game_controller.py:242` and just reacts to the result).

**How to spot low cohesion (the anti-pattern):** a class named `GameManager` that also does `print()`, reads the word file, *and* scores guesses. That's a god class. This project deliberately split that into four classes — which is *why* each one is cohesive.

---

### 4. Low Coupling — thin, defined doors between classes

**(a) Dependencies are handed in, not hard-wired (Dependency Injection)**
`run.py:6-9`
```python
def run():
    view = ConsoleView()
    controller = GameController(view=view, constants_module=constants)
    controller.start()
```
The controller does **not** build a `ConsoleView` itself. It *receives* a `view` through its constructor (`game_controller.py:16`). So the controller is coupled to *anything that behaves like a View*, not to the concrete `ConsoleView`. This is the single most important low-coupling move in the project.

**(b) The controller talks to the view only through the 8-method contract**
Throughout the controller you only ever see calls like:
```python
self.view.display(...)
self.view.prompt(...)
self.view.show_word(self.game.get_visible_word())
self.view.show_health(player)
self.view.pause(...)
```
(e.g., `game_controller.py:161-163`). Never `print()`/`input()` inside the controller. So `ConsoleView`, a hypothetical `PygameView`, or a `Mock` are all interchangeable, as long as they implement the 8 methods declared in `view_interface.py:4-29`. The door is thin and fixed.

**(c) The Model returns data — it doesn't expose its insides**
`Game.guess_letter` (`game.py:127-194`) returns a **dictionary** describing the outcome:
```python
return {
    "ok": True, "repeat": False, "correct": True,
    "positions": positions, "times": times,
    "eliminated": False, "player_health": player.health,
    "game_won": game_won, "game_over": ..., "winner": winner
}
```
The controller reads only those keys. It never touches `game.word` or `game.unknown_word`. A dictionary is a small, read-only contract — a thin door. Change how `Game` stores its word internally and the controller won't notice.

**(d) The View is "dumb" and stateless**
`ConsoleView` holds no game knowledge. Even `show_health` (`console_view.py:52-53`) just prints what it's *given*:
```python
def show_health(self, player) -> None:
    print(player.hangman_states[player.health])
```
It's handed a `player` and prints. It doesn't decide who's alive or what health *means*.

**(e) Config is injected, not scattered**
`MAX_HEALTH = 7` and the ASCII art live in `constants.py:1-59`. `Game` receives `constants_module` as a parameter (`game.py:11`) and reads `self.c.MAX_HEALTH` (`game.py:118`). `Player` receives `max_health` and `hangman_states` via its constructor (`player.py:7`). The magic values aren't hard-coupled into the logic — you can swap the constants module for a test double without editing `Game` or `Player`.

**(f) `WordRepository` is a black box**
It depends only on the standard library (`json`, `pathlib`, `random`, `unicodedata`) plus a `file_path` handed to it (`word_repository.py:23`). It has no import of `Game`, `View`, or the controller. Swap the JSON file for a database or an API and *only this one file* changes.

---

### 5. Why you should care: the payoff is testability

Low coupling isn't a virtue for its own sake — it pays off in your test suite. Because the controller only talks to a *View-shaped* object, a test injects a `Mock` and drives a whole game **without a real terminal**:

`tests/unit/test_game_controller.py:11-27`
```python
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
If the controller called `input()`/`print()` directly (high coupling), this would be impossible — you'd have to fake the keyboard and capture the screen.

Same story for the model — `Player` takes everything through its constructor, so a test builds any state with no I/O (`tests/unit/test_player.py:10-25`). And `test_view_interface.py:163-166` even pins the deliberate choice that `View()` stays instantiable (duck-typed contract, not a hard ABC).

The chain: **Cohesion** lets you test each box *alone*. **Low coupling** lets you test the boxes *together* with cheap fakes.

---

### 6. One honest nuance (for going further)

The design is low-coupling in spirit, but a couple of spots read *internal attributes* directly instead of going through a method. Recognizing this makes you a better reviewer:
- `game_controller.py:151-152` uses `self.game.is_game_over()` (a method — good) but also `self.game.n_players` and `self.game.remaining_players` (direct attribute reads).
- `console_view.py:53` reads `player.health` / `player.hangman_states` directly.

These work fine today and are common in small projects. To tighten coupling to 100%, you'd add small query methods (e.g., `Game.player_count()`) and pass pre-formatted text into the view. The real skill is learning to tell the difference between **calling a door** and **reaching through a wall**.

**TL;DR for 2.4:** each class (`Player`, `Game`, `WordRepository`, `ConsoleView`, `GameController`) is *highly cohesive* because every method serves one job, and they are *loosely coupled* because they interact only through injected references and well-defined method contracts (the 8-method `View` interface and `Game`'s result dictionaries) — which is precisely what makes the whole suite mockable in `tests/`.
