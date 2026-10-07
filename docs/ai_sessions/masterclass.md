# Topic 1.1 — The MVC Pattern (Model‑View‑Controller)

## What MVC is (the big idea)

MVC is a way to **split an application into three roles** so each part has *one job* and they only talk to each other through narrow, well‑defined channels:

| Role | Job | What it must NOT do |
|------|-----|---------------------|
| **Model** | Hold data + business rules (state & logic) | No printing, no reading keyboard, no files |
| **View** | Show things to the user & collect input | No game rules, no deciding what happens next |
| **Controller** | Orchestrate: take input, ask Model, tell View what to show | No rules of its own, no direct I/O |

A good analogy: a **restaurant**.
- **Model** = the kitchen (has the recipe and the food — the "logic & state").
- **View** = the waiter + plates (brings food to you, hands your order in — it has *no* idea how to cook).
- **Controller** = the host/expeditor (takes your order, sends it to the kitchen, decides what gets served and in what order).

The key benefit: **you can swap any one role without breaking the others.** Change the kitchen, the waiters stay the same. Change the waiters, the kitchen stays the same.

Your project is a textbook example of this. Let's map each role to real files.

---

## The three roles in your codebase

```
run.py  (wiring / composition root)
   │  creates a ConsoleView, passes it to the controller
   ▼
GameController  ──talks to──►  Game  (Model)
 (Controller)                  Player (Model)
   │
   └──talks to──►  ConsoleView  (View)
```

### 1. MODEL — `Game` and `Player`

The Model is everything in `hangman/model/`. Its job: **pure logic and state, zero I/O.**

**`Player`** (`hangman/model/player.py:4`) holds a single player's state:

```python
class Player:
    def __init__(self, name: str, max_health: int, hangman_states: List[str]):
        self.name = name
        self.max_health = max_health
        self.health = max_health
        ...
    def lose_health(self) -> bool:   # line 13
        previous = self.health
        self.health = max(0, self.health - 1)
        return previous > 0 and self.health == 0

    def is_alive(self) -> bool:      # line 18
        return self.health > 0
```

Notice something important: `Player` **never prints anything** and **never asks the user anything**. It just owns `health` and answers two questions: *"lose a point, did I die?"* and *"am I alive?"* That's information hiding (encapsulation) — the outside world can't fiddle with health directly; it must go through these methods.

**`Game`** (`hangman/model/game.py:8`) is the heart of the Model:

```python
class Game:
    """Pure game model: contains all rules and state but performs no I/O."""  # line 9
```

That docstring is the contract. It stores all state:

```python
self.word, self.unknown_word, self.remaining_letters,
self.remaining_players, self.n_players, self.remaining_spaces, self.is_phrase
```

And it implements the **rules**. The most important one is `guess_letter` (`game.py:127`). Watch how it works: it takes raw input, validates it, applies the rules, changes state, and **returns a plain dictionary describing what happened** — it never prints:

```python
def guess_letter(self, player_index: int, raw_letter: str) -> Dict[str, Any]:
    ...
    if not player.is_alive():
        return {"ok": False, "repeat": False, "error": "Player has been eliminated."}   # line 133
    ...
    if letter not in self.remaining_letters:
        return {"ok": False, "repeat": True, "error": f"The letter '{raw_letter}' was already used."}  # line 147
    ...
    # incorrect guess
    if times == 0:
        eliminated = player.lose_health()
        ...
        return { "ok": True, "correct": False, "eliminated": eliminated, ... }   # line 163
    # correct guess
    for pos in positions:
        self.unknown_word[pos] = letter
    ...
    return { "ok": True, "correct": True, "positions": positions, "game_won": game_won, ... }  # line 183
```

**Why return a dict instead of printing?** This is the crux of MVC. The Model *reports facts* ("the letter was wrong, player health is now 3, they're not eliminated yet"). It does **not** decide *how* to present them. The **Controller** reads that dict and decides what to show. That's the clean separation.

> **Check for yourself (great exercise):** open `hangman/model/game.py` and search for `print(` or `input(`. You'll find **none**. The Model genuinely performs no I/O.

### 2. VIEW — `ConsoleView` (+ the `View` interface)

The View is `hangman/view/`. Its job: **only display and only collect input — it's "dumb."**

There are two files, and this is an important MVC sub‑concept (program to an interface):

**`View`** (`hangman/view/view_interface.py:4`) is an **abstract interface** — a list of methods *every* view must provide:

```python
class View:
    """Abstract interface for user interaction."""
    def display(self, message: str) -> None:      # show a message
        raise NotImplementedError
    def prompt(self, message: str) -> str:        # ask the user for text
        raise NotImplementedError
    def show_word(self, word_state: List[str]):   # show the "_ _ A _" line
        raise NotImplementedError
    def show_health(self, player):                # show the hangman graphic
        raise NotImplementedError
    ...
```

**`ConsoleView`** (`hangman/view/console_view.py:8`) is one *concrete* implementation — the terminal view:

```python
class ConsoleView(View):
    def display(self, message: str) -> None:      # line 18
        print(message)

    def prompt(self, message: str) -> str:        # line 25
        try:
            return input(message)
        except (KeyboardInterrupt, EOFError):     # graceful Ctrl+C / EOF
            self.clear()
            print("\nGame interrupted. Exiting safely.\n")
            exit(0)

    def show_word(self, word_state: List[str]) -> None:   # line 49
        print(f"    {' '.join(word_state)}\n")

    def show_health(self, player) -> None:        # line 52
        print(player.hangman_states[player.health])
        print()
```

Look closely: **none of these methods contain game logic.** `show_health` doesn't compute health — it just *reads* `player.health` and picks the right ASCII graphic from a pre‑loaded list. `prompt` just calls `input()`. The View is a thin "dumb" layer that does exactly what it's told.

> Because it's built on the `View` interface, you could tomorrow write a `TkinterView` or `PygameView` (a GUI) that implements the same methods, and the rest of the app wouldn't change. That's the payoff of the interface.

### 3. CONTROLLER — `GameController`

The Controller is `hangman/controller/game_controller.py:10`. Its job: **orchestrate** — receive input, delegate rules to the Model, decide what the View shows next.

```python
class GameController:
    """
    Controller that orchestrates the interaction between the pure Game model
    and the View. All I/O is performed via the View; the Game never handles input.
    """
    def __init__(self, view: ConsoleView, constants_module):   # line 16
        self.view = view
        self.c = constants_module
        self.game = None
        ...
```

It holds references to **both** the Model and the View and is the only place they meet. The clearest example is `handle_letter_guess` (`game_controller.py:238`):

```python
def handle_letter_guess(self, player_index: int):
    while True:
        raw_letter = self.view.prompt("Please insert a letter: ")          # 1) VIEW: get input
        result = self.game.guess_letter(player_index, raw_letter)          # 2) MODEL: apply rules

        if not result.get("ok") and not result.get("repeat"):              # 3) read Model's report
            self.view.display(result.get("error") + "\n")                  #    → show error, stop
            self.view.pause()
            return result
        if result.get("repeat"):                                           #    recoverable → ask again
            self.view.display(result.get("error") + "\n")
            continue
        break

    player = self.game.get_player(player_index)
    self.view.clear()
    if not result.get("correct"):                                          # 4) VIEW: show outcome
        self.view.display(f"Sorry, the letter '{letter_out}' is not in the {label}.\n")
        self.view.show_health(player)
        self.view.show_word(self.game.get_visible_word())
        ...
    return result
```

Read that as a loop of **View → Controller → Model → Controller → View**:
1. Ask the **View** for input.
2. Send it to the **Model** for the rules.
3. Read the Model's **status dict** and decide which branch (error / retry / wrong / right).
4. Instruct the **View** on what to display.

The Controller never guesses letters itself and never computes health — it only *routes* and *decides flow*.

---

## How it all gets wired together — `run.py` (Dependency Injection)

The final piece is the **composition root**, `run.py`:

```python
def run():
    view = ConsoleView()                                        # create the View
    controller = GameController(view=view, constants_module=constants)  # inject it
    controller.start()                                          # go
```

Notice the Controller **doesn't create its own View** — it *receives* one as a constructor argument. That's **Dependency Injection (DI)**. Two big benefits:

1. **Loose coupling:** the Controller is written against the *interface*, not the concrete console class.
2. **Testability:** in tests you can hand the controller a *fake* view instead of a real terminal.

See `tests/unit/test_game_controller.py:69` — a test builds the controller with a **Mock** view and simulates a whole game with no real keyboard:

```python
view = view_factory()                     # a Mock object
controller = GameController(view=view, constants_module=Mock())
...
view.prompt.side_effect = ["Y", "1", "2", "Alice"]   # fake "user" inputs
controller.setup_game()
```

Because of MVC + DI, the test can assert *what the controller made the view display* (`view.display.assert_any_call(...)`) without ever opening a terminal. **This is the most concrete proof that the separation is real** — if the Controller had printed directly, or created its own View, these tests would be impossible.

---

## The full data flow, one guess at a time

```
  USER (keyboard)
        │  types "a"
        ▼
 ┌─────────────────────────────────────────────┐
 │ VIEW: ConsoleView.prompt(...)  → returns "a"│   (raw I/O only)
 └─────────────────────────────────────────────┘
        │
        ▼
 ┌─────────────────────────────────────────────┐
 │ CONTROLLER: handle_letter_guess()           │   (orchestrates)
 │   └─► MODEL: Game.guess_letter(0, "a")      │   (applies rules)
 │        returns {"ok":True,"correct":True,   │
 │                 "times":1, "player_health":7, ...}
 │   └─► decides: "correct → show praise"      │
 │   └─► VIEW: display / show_health / show_word│   (shows result)
 └─────────────────────────────────────────────┘
        │
        ▼
  SCREEN (user sees updated word + hangman)
```

Each arrow crosses a **role boundary**, and each role only does its own job.

---

## Why MVC matters here (the "so what?")

- **Change the UI without touching logic.** Swap `ConsoleView` for a GUI implementing `View`; `Game`, `Player`, and `GameController` are untouched.
- **Change the rules without touching UI.** Alter health/elimination logic in `Game`; the Controller and View don't care.
- **Everything is testable.** The Model is tested with plain inputs/outputs; the Controller is tested with a Mock view; the View is tested for its display strings. No component needs the others to be tested in isolation.
- **Single Responsibility.** Each class has exactly one reason to change — which is also why the codebase stays small and readable.

---

## Quick self‑check (try these to lock it in)

1. In `hangman/model/game.py`, find a method that returns a status dict (e.g., `set_word`, `game.py:46`) and list every key it returns. Notice none of them are "print" instructions.
2. In `hangman/view/console_view.py`, find a method that does *only* I/O (`display`, `game_controller` line 18) and confirm it contains no `if` about game rules.
3. In `hangman/controller/game_controller.py`, trace `start()` → `setup_game()` → `run_game_loop()` and mark each line as **V**iew, **M**odel, or **C**ontrol.
4. Run the controller unit tests (`.venv-windows` → `pytest tests/unit/test_game_controller.py`) and observe how a Mock view lets a full game run headless.

**One‑line summary:** The **Model** (`Game`/`Player`) owns state & rules with zero I/O, the **View** (`ConsoleView`) is a dumb display/input layer behind a `View` interface, and the **Controller** (`GameController`) injects the View and routes everything — so any piece can be swapped or tested independently.

---
---

# Topic 1.2 — Separation of Concerns (SoC)

## What SoC is (the big idea)

**Separation of Concerns** is the principle that each part of a program should be responsible for **exactly one "concern"** — and a *concern* is best defined as **one reason the code might change**.

> **SoC in one sentence:** *Group code by "why it changes," so a change in one area doesn't force edits everywhere else.*

This is the **principle** that *motivates* MVC (topic 1.1). MVC tells you *how* to split by interaction role (Model/View/Controller). SoC tells you *why* that split is good, and it goes **one step further** — it also explains why your project pulled *word loading* and *configuration* into their own modules.

### Concern vs. Coupling (two words to keep straight)

- **Concern** = a category of responsibility (a "reason to change").
- **Coupling** = how much one piece *depends on / knows about* another.

SoC's goal: **many clean concerns, low coupling between them.** High cohesion *inside* each concern, low coupling *between* concerns.

---

## The concerns in your project

Your codebase is physically organized **one folder per concern**. That directory layout is the single strongest evidence of SoC:

```
hangman/
├── model/         ← CONCERN: game rules & state        (Game, Player)
├── view/          ← CONCERN: display + input / I/O      (View, ConsoleView)
├── controller/    ← CONCERN: orchestration & flow       (GameController)
├── services/      ← CONCERN: data access (word bank)    (WordRepository)
├── data/          ← CONCERN: raw data                   (word_bank.json)
└── constants.py   ← CONCERN: configuration              (MAX_HEALTH, HANGMAN art)
```

So the full set of concerns — note that **two of them (data access, configuration) exist *beyond* the M/V/C trio**:

| Concern | "Reason to change" | Lives in |
|---------|-------------------|----------|
| **Game rules & state** | The rules change (health, win/lose, repeats) | `model/` → `Game`, `Player` |
| **User I/O** | The interface changes (console → GUI → web) | `view/` → `ConsoleView` |
| **Orchestration / flow** | The flow changes (new screens, new prompts) | `controller/` → `GameController` |
| **Data access** | The word source changes (JSON → DB → API) | `services/` → `WordRepository` |
| **Configuration** | Tuning changes (max health, ASCII art) | `constants.py` |
| **Raw data** | The words themselves change | `data/word_bank.json` |

---

## The flagship example: `WordRepository` isolates the data concern

MVC (topic 1.1) never mentions the word bank — but SoC demands its own home. Look at how the **Controller** uses the repository:

```python
# hangman/controller/game_controller.py:93
selected = self.word_repo.get_by_difficulty(difficulty)
```

**That's the entire relationship.** One method call. The controller never:
- opens a file,
- parses JSON,
- validates individual words,
- normalizes unicode, or
- tracks which words were already used.

All of that is *hidden inside* `WordRepository`. Let's see what that "one method" actually shields you from — the public API is just **two** methods (`get_by_difficulty`, `reset_session`, `word_repository.py:146` and `:170`), while the private internals do the heavy lifting:

| Hidden inside `WordRepository` | Where | Concern it owns |
|-------------------------------|-------|-----------------|
| File-missing check → `FileNotFoundError` | `word_repository.py:44` | data access |
| JSON parse → `ValueError` on bad JSON | `word_repository.py:47-51` | data access |
| Accept **two** formats (dict *or* list) | `word_repository.py:53-58` | data access |
| Per-word validation (type, ≤120 chars, allowed chars, ≥2 letters) | `word_repository.py:84-117` | data quality |
| Unicode normalization (NFD, strip diacritics, collapse spaces, uppercase) | `word_repository.py:122-141` | data quality |
| **No-repeat** session tracking (`used_words` set) | `word_repository.py:159-167` | data policy |
| Random pick from available words | `word_repository.py:165` | data policy |

The user of the class (the controller) sees a clean, narrow door: *"give me a random unused word for this difficulty."* Everything messy is behind that door. **That is SoC in action — one concern, one owner, one narrow interface.**

### The payoff: change the source, touch *one* file

Suppose you later decide the word bank should come from a **SQLite database** instead of a JSON file. Because of SoC:

- `WordRepository._load()` changes (read from DB instead of `json.load`).
- **Nothing else changes.** `Game`, `Player`, `ConsoleView`, and the `GameController` still call the same `get_by_difficulty(difficulty)` and don't care *where* the word came from.

Compare that to the study guide's point: *"UI modifications (e.g., migrating from terminal to a GUI or Web View) do not require changing the core game logic."* Same logic — swap the concern, leave the rest alone.

---

## Contrast: what the code looks like *without* SoC

Imagine the same game as one tangled function (the anti-pattern every beginner writes first):

```python
# ❌ NO SoC — every concern glued together
def main():
    data = json.load(open("word_bank.json"))     # data access
    word  = random.choice(data["easy"]).upper()  # data + normalization
    health = 7                                   # game state
    while health > 0:
        letter = input("letter: ")               # I/O
        if letter in word:                       # game rules
            print("correct!")                    # display
        else:
            health -= 1
            print("wrong, health", health)       # rules + display mixed
```

Here a single function owns **six concerns at once**. Now ask: *"what if I change the word source to a database?"* You must edit this same function. *"What if I add a GUI?"* Same function. *"What if health works differently?"* Same function. **Every change ripples through the same tangled code** — that's high coupling and it's why the project grows fragile fast.

Your project's answer: **six separate modules**, each with one job, communicating only through small, well-defined calls.

---

## A subtle (but important) nuance: validation appears in two places

You might notice word validation exists in **two** classes:

- `Game.set_word()` — `game.py:46` (validates a word at **runtime**)
- `WordRepository._validate_normalize()` — `word_repository.py:84` (validates words at **load time**)

Is that a SoC violation (duplication)? **No.** It's *defense in depth at layer boundaries*, and each concern validates for a different reason:

- The **repository** validates at load time so its *internal store* is always clean (bad entries in the JSON are skipped before they ever exist in memory).
- The **game** validates at runtime because a word can arrive from a **human moderator** (manual entry in the controller, `game_controller.py:81`), not only from the repository.

The rule of thumb: **each concern owns the validation of the data it is responsible for, at the moment it takes responsibility.** That's SoC applied carefully, not accidentally.

---

## SoC vs. MVC — how they fit together

| | **MVC (1.1)** | **SoC (1.2)** |
|---|---------------|--------------|
| **What it is** | A concrete **pattern** (3 roles) | A general **principle** |
| **Splits by** | Interaction role (who talks to the user) | "Reason to change" / concern |
| **Covers** | Model, View, Controller | Those **plus** data access (`services/`) and config (`constants.py`) |
| **Relationship** | One *way to realize* SoC | The *why* behind MVC |

Think of it this way: **MVC is SoC applied to the user-interaction triangle.** Your project follows MVC *and* extends the same idea to data and configuration, which is why the architecture holds together so well.

---

## Why SoC matters here (the "so what?")

- **Change isolation.** Change the word source → only `services/`. Change the rules → only `model/`. Change the UI → only `view/`.
- **Independent testing.** Each concern has its own test file (`test_game.py`, `test_word_repository.py`, `test_console_view.py`, `test_game_controller.py`) — possible *because* the concerns are decoupled.
- **Smaller, readable modules.** No file tries to do everything; each is short enough to hold in your head.
- **Lower risk.** A bug in the word bank can't corrupt game logic, because the two never share state — they only meet through the one-method API.

---

## Quick self‑check (try these to lock it in)

1. In `hangman/controller/game_controller.py`, find **every** place the controller touches the word bank. Confirm it's *always* through `self.word_repo.get_by_difficulty(...)` / `reset_session()` — never `json` or `open()`.
2. Open `hangman/model/game.py` and confirm it contains **no** file/JSON code. The Model knows nothing about *where* words come from.
3. Search the whole project for `import json`. You should find it **only** in `services/word_repository.py`. That single search result *proves* the data concern is isolated.
4. Hypothesis test: if you moved `constants.py`'s `MAX_HEALTH` into `Game`, which concern would leak into which? (Answer: configuration leaks into the rules.) See why keeping them separate is cleaner.

**One-line summary:** **SoC** means grouping code by *reason to change* — in this project that's `model/` (rules), `view/` (I/O), `controller/` (flow), `services/` (data), and `constants.py` (config) — so any single change (new UI, new word source, new rule) touches **one** module and ripples nowhere else.

---
---

# Topic 1.3 — Dependency Injection (DI)

## 1. What is Dependency Injection?

**Dependency Injection** is a technique where an object does **not** create the other objects it needs (its *dependencies*) internally. Instead, those dependencies are **passed in from outside** — usually through the constructor.

A simple analogy:

- **Without DI:** a restaurant where the chef grows the vegetables, raises the chickens, and bakes the bread himself. Everything is tied together.
- **With DI:** the chef receives the ingredients from a supplier. The chef's job stays focused, and if you change the supplier (or test with fake ingredients), the chef's work doesn't change.

The key terms:

- **Dependency** — anything an object needs to do its job (a view, a config module, a data repository...).
- **Inject** — "hand it in" from outside, typically as a constructor argument.
- **Loose coupling** — the object depends on *what it needs* (a contract), not on *how that thing was built*.

The most common form is **constructor injection**, which is exactly what this codebase uses.

---

## 2. The main example: the View injected into `GameController`

### 2.1 The dependency the controller needs

The controller's entire job is to orchestrate I/O: show the board, ask for a guess, print errors. It needs a *view* object, but it does **not** decide what kind of view. Look at its constructor:

```python
# hangman/controller/game_controller.py:16
def __init__(self, view: ConsoleView, constants_module):
    self.view = view
    self.c = constants_module
```

The controller **never writes** `view = ConsoleView()` inside itself. It simply stores what it was given. Everywhere in its methods it calls `self.view.display(...)`, `self.view.prompt(...)`, `self.view.show_word(...)` — e.g.:

```python
# game_controller.py:161-163
self.view.display(f"Player: {player.name}.\n")
self.view.show_health(player)
self.view.show_word(self.game.get_visible_word())
```

### 2.2 The contract: the `View` interface

The controller relies on a *contract*, defined in `hangman/view/view_interface.py:4`:

```python
class View:
    """Abstract interface for user interaction."""

    def display(self, message: str) -> None: raise NotImplementedError
    def prompt(self, message: str) -> str:   raise NotImplementedError
    def show_word(self, word_state: List[str]) -> None: raise NotImplementedError
    ...
```

`ConsoleView` (hangman/view/console_view.py:8) fulfils that contract by implementing each method with real `print`/`input` calls. Because the controller only ever calls methods declared in `View`, **any** class implementing those same methods could be handed in — a `PygameView`, a `TkinterView`, a web view, or a fake for tests. That is the study guide's point: *"any concrete class (e.g., `ConsoleView`, `PygameView`, `TkinterView`) can be substituted transparently."*

> **Tutor's note (honest observation):** in the actual code the parameter is typed as `view: ConsoleView` (the concrete class), while the study guide says the controller is "typed against the base interface." Functionally it works fine, but the *textbook-correct* version — and a good exercise for you — would be:
> ```python
> from hangman.view.view_interface import View
>
> def __init__(self, view: View, constants_module):
> ```
> That makes the "program to an interface, not to an implementation" rule visible in the type hints.

### 2.3 Where the injection happens: the composition root

Someone still has to create the `ConsoleView` and hand it over. That "wiring" code lives in the **composition root** — the entry point of the application, `run.py:6-9`:

```python
def run():
        view = ConsoleView()
        controller = GameController(view=view, constants_module=constants)
        controller.start()
```

The **composition root** is the single place that knows the concrete classes and assembles the object graph. Everything else (controller, model, views) stays ignorant of the concrete details.

---

## 3. A second example: the `constants` module injected

DI isn't only for objects — this project also injects a **module** (a bag of configuration values) as a dependency.

`hangman/constants.py` holds configuration: `MAX_HEALTH = 7` and the `HANGMAN` ASCII art list. Instead of the model and controller importing it themselves and hard-coding it, it is passed in:

```python
# game_controller.py:16-18
def __init__(self, view: ConsoleView, constants_module):
    self.view = view
    self.c = constants_module
```

```python
# hangman/model/game.py:11-12
def __init__(self, constants_module, normalize_input: bool = True):
    self.c = constants_module
```

Notice the chain in `setup_game` (game_controller.py:73): the controller forwards its own injected `self.c` to the `Game` model:

```python
self.game = Game(constants_module=self.c, normalize_input=normalize)
```

The benefits here (matching the study guide's "Configuration Externalization"):

- If you want a different max health or different graphics, you create a different constants module and inject it — **no code changes**.
- Tests can pass a `Mock()` as constants and not care about the real values at all.

---

## 4. The payoff: testing without a real terminal

This is the whole *reason* DI exists, and the codebase proves it in `tests/unit/test_game_controller.py`.

### 4.1 Injecting a fake view

The `controller_factory` fixture (test_game_controller.py:66-75) builds a controller with a **`Mock` instead of a real view**:

```python
@pytest.fixture
def controller_factory(view_factory, game_factory, word_repo_factory):
    def _factory():
        view = view_factory()                      # <- a Mock, not a ConsoleView
        controller = GameController(view=view, constants_module=Mock())
        controller.game = game_factory()           # <- a Mock model too
        controller.word_repo = word_repo_factory() # <- a Mock repository
        return controller, view
    return _factory
```

The `view_factory` fixture (lines 11-27) just creates `view = Mock()` and gives its methods harmless default return values. Because of DI, this "drop-in fake" satisfies the controller completely — the controller doesn't know or care that it isn't a `ConsoleView`.

### 4.2 Simulating a whole game session

With the real `ConsoleView`, testing the controller would require a human typing at a terminal. With the injected mock, the test **scripts the user's keystrokes** using `side_effect`:

```python
# test_game_controller.py:208-215
with patch("hangman.controller.game_controller.Game", return_value=mock_game):
    view.prompt.side_effect = ["Y", "1", "1", "Alice"]
    view.prompt_hidden.side_effect = ["bad", "good"]

    controller.setup_game()

assert mock_game.set_word.call_count == 2
```

Read this like a story: the simulated user answers `"Y"` (enable normalization), `"1"` (manual word source), `"1"` (one player), `"Alice"` (name); the hidden prompt first returns `"bad"` (rejected by the model → retry) then `"good"` (accepted). The test then asserts the model received `set_word` **twice**. No terminal, no keyboard, instant and repeatable.

### 4.3 Checking the exact output sequence

Because `view` is a mock, every call the controller makes is **recorded**, so tests can verify what the player would have seen:

```python
# test_game_controller.py:490
view.display.assert_any_call("Sorry, the letter 'Z' is not in the word.\n")

# test_game_controller.py:369
view.display.assert_any_call("Player: Alice.\n")

# test_game_controller.py:603
for call in view.display.call_args_list:
    assert "has been eliminated" not in call.args[0]
```

That last pattern is worth studying: it asserts a message was *not* printed — something you could never verify reliably against a real console.

This is exactly what the study guide describes: *"allows tests to inject mock versions of the view, checking output sequences without opening a real terminal or expecting actual keyboard inputs."*

---

## 5. Contrast: what the code would look like **without** DI

To really see the value, here is the tightly-coupled alternative:

```python
# BAD: no DI
from hangman.view.console_view import ConsoleView
from hangman import constants

class GameController:
    def __init__(self):
        self.view = ConsoleView()        # hard-coded dependency
        self.c = constants               # hard-coded dependency
```

Problems with that version:

1. **Untestable in isolation** — every controller test would print to the real console and block on real `input()`.
2. **Unswap-able** — migrating to a GUI or web frontend means editing the controller.
3. **Hidden configuration** — the constants are baked in; changing `MAX_HEALTH` behavior in tests is impossible.

With DI, the controller file contains **zero** `ConsoleView()` instantiations. Its only imports of concrete UI code exist today because of the type hint; the behavior depends purely on the constructor arguments.

---

## 6. One more thing to notice: where DI is *not* applied yet

As a careful reader, compare the two dependencies of the controller:

```python
# game_controller.py:16-22
def __init__(self, view: ConsoleView, constants_module):
    self.view = view
    self.c = constants_module
    ...
    self.word_repo = WordRepository(BASE_DIR / "data" / "word_bank.json")  # created internally!
```

`view` and `constants_module` are injected, but `word_repo` is **constructed inside** the controller with a hard-coded file path. In tests it works around this by overwriting the attribute after construction (test_game_controller.py:72: `controller.word_repo = word_repo_factory()`). A more consistent design would inject it the same way:

```python
def __init__(self, view: View, constants_module, word_repo: WordRepository):
```

This is a great self-exercise: apply constructor injection to `word_repo`, update `run.py` (the composition root) to pass a real `WordRepository`, and update the test fixtures accordingly. You'll end up with a fully DI-consistent object graph.

---

## 7. Summary

| Concept | Where you see it in this codebase |
|---|---|
| Dependency passed via constructor | `GameController(view=..., constants_module=...)` at game_controller.py:16; `Game(constants_module=...)` at game.py:11 |
| Composition root (wiring) | `run.py:6-9` creates `ConsoleView` and injects it |
| Program to an interface | `View` base class (view_interface.py:4) defines the contract the controller calls |
| Loose coupling benefit | A `PygameView`/`TkinterView` could replace `ConsoleView` with no controller changes |
| Testability benefit | `test_game_controller.py` injects a `Mock` view, scripts keystrokes with `side_effect`, and asserts exact output sequences |
| Configuration externalization | `constants` module injected instead of imported and hard-coded |

The one-sentence takeaway: **DI means "give me what I need, don't make me build it"** — and in this project it's what turns an interactive terminal game into something that can be tested line by line with pure pytest.

---

# Topic 1.4: Program to Interfaces, Not Implementations

## 1. The core idea in one sentence

Write your code so it depends on a **contract** ("a view *can* display, prompt, and clear"), never on a **specific machine** that fulfills it ("a *console* view"). The concrete class is a **pluggable detail** chosen at the very last moment, at the edge of the program.

Think of it like a power socket: your lamp (the controller) depends on "a 230V socket", not on "the exact socket wired into this wall by this specific electrician". You can swap sockets (console view, GUI view, mock view) and the lamp keeps working — as long as every socket follows the same standard (the interface).

In design-patterns language this is the **Liskov Substitution Principle** plus **dependency inversion**: high-level modules (the controller) must not depend on low-level modules (a specific view); both should depend on an abstraction.

---

## 2. The three roles in your codebase

Your project is a textbook example. There are exactly three actors:

| Role | Class | File |
|---|---|---|
| **The contract (interface)** | `View` | `hangman/view/view_interface.py` |
| **The implementation** | `ConsoleView` | `hangman/view/console_view.py` |
| **The consumer** | `GameController` | `hangman/controller/game_controller.py` |
| **The "wiring" (composition root)** | `run()` | `run.py` |

### 2.1 The contract: `View` (`hangman/view/view_interface.py:4`)

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

Read this class and answer one question: **does it say anything about *how*?** No. No `print`, no `os.system`, no `getpass`. It only declares **8 verbs** and their signatures (parameter names, types, defaults, return types). That's the whole contract:

- `display(message) -> None` — "you can show a message"
- `prompt(message) -> str` — "you can ask a question and hand back a string"
- `pause(message=...) -> None` — "you can wait; note the default argument is part of the contract too"
- ...and so on.

`raise NotImplementedError` is Python's idiomatic "this method is a promise, not a body" marker. It means: *if you ever call this method on something that forgot to override it, you get a loud, immediate error* — instead of silently doing nothing.

### 2.2 The implementation: `ConsoleView` (`hangman/view/console_view.py:8`)

```python
class ConsoleView(View):
    """Handles all console-based input and output operations."""

    def display(self, message: str) -> None:
        print(message)

    def prompt(self, message: str) -> str:
        try:
            return input(message)
        except (KeyboardInterrupt, EOFError):
            ...
            exit(0)

    def show_word(self, word_state: List[str]) -> None:
        print(f"    {' '.join(word_state)}\n")
    # ...
```

This is where all the *how* lives: `print`, `input`, `getpass`, `os.system('cls'/'clear')`, Ctrl+C handling. The inheritance `ConsoleView(View)` is the declaration: **"I guarantee everything the View contract promises, here's my recipe for each promise."**

### 2.3 The consumer: `GameController` (`hangman/controller/game_controller.py`)

Now look at how the controller uses its view. Scan through `setup_game`, `run_game_loop`, `handle_letter_guess`... every single interaction goes through the **contract verbs**:

```python
self.view.clear()                                   # game_controller.py:70
self.view.show_title()                              # game_controller.py:71
response = self.view.prompt("Enable accent ...")    # game_controller.py:30
self.view.prompt_hidden("Please insert the word...")# game_controller.py:81
self.view.show_health(player)                       # game_controller.py:162
self.view.show_word(self.game.get_visible_word())   # game_controller.py:163
self.view.pause("Press Enter to continue...")       # game_controller.py:232
```

Nowhere in the controller does it say `print(...)`, `input(...)`, or `isinstance(self.view, ConsoleView)`. The controller treats `self.view` as a **black box that obeys the 8-verb contract**. It genuinely doesn't know — and doesn't care — whether the box is a terminal, a window, or a fake.

### 2.4 The wiring: `run.py` (the composition root)

The *only* place in the entire program where the implementation is named:

```python
def run():
        view = ConsoleView()                                        # ← the choice is made here, once
        controller = GameController(view=view, constants_module=constants)
        controller.start()
```

This is **dependency injection** in action: the controller receives the view through its constructor (`game_controller.py:16`) instead of building it itself. So the substitution point is isolated to 3 lines in `run.py`.

---

## 3. The payoff #1: transparent substitution

Because the controller only speaks the `View` language, this hypothetical class would be a **drop-in replacement**:

```python
from hangman.view.view_interface import View

class PygameView(View):
    def display(self, message: str) -> None:
        # draw text on a pygame surface...
        ...
    def prompt(self, message: str) -> str:
        # wait for keyboard events, return the typed string
        ...
    def show_health(self, player) -> None:
        # render the hangman figure as sprites using player.hangman_states
        ...
    # ... all 8 methods ...
```

And to switch the whole game from terminal to window, you change **one line** in `run.py`:

```python
view = PygameView()   # was: ConsoleView()
```

Zero changes to `GameController`, `Game`, `Player`, `WordRepository`. This is exactly what the study guide means by: *"UI modifications (e.g., migrating from terminal to a GUI) do not require changing the core game logic."*

Note what `PygameView` must **not** be tempted to do: invent extra requirements on the model. The contract only hands it `word_state: List[str]` and a `player` object, so it must work with that. Symmetrically, the controller must only ever call the 8 contract methods — if it needed a 9th capability, the correct move is to *grow the interface first*, then implement it in every view.

---

## 4. The payoff #2: testability (the big one)

This is where the principle pays for itself, and your test suite shows it beautifully.

### 4.1 `tests/unit/test_game_controller.py:11-27`

```python
@pytest.fixture
def view_factory():
    def _factory():
        view = Mock()
        view.prompt.return_value = ""
        view.prompt_hidden.return_value = ""
        view.display.return_value = None
        # ...
        return view
    return _factory
```

A `Mock` is, effectively, a class that "implements" *any* interface on demand. Because the controller only speaks the `View` contract, a `Mock` **is a valid View as far as the controller is concerned**. So the entire controller can be tested:

- **without opening a terminal** (no `input()` to hang on),
- **without any real display**,
- by feeding scripted answers: `view.prompt.side_effect = ["Y", "1", "2", "Alice", "Bob"]` (test_game_controller.py:182-189),
- and by *asserting on the exact output sequence*: `view.display.assert_any_call("That name is already taken. Please choose another name.\n")` (test_game_controller.py:273).

Imagine instead the controller had done `input()`/`print()` directly (the "programming to the implementation" anti-pattern). Testing it would require real stdin/stdout, monkeypatching builtins, and you could never verify "the user saw message A *then* was asked B". The interface is what makes the 700+ line controller testable line by line.

### 4.2 `tests/unit/test_view_interface.py` — policing the contract itself

The second test file is dedicated to the interface. Two highlights:

- `test_all_methods_raise_not_implemented` (line 36): parametrized over **all 8 methods**, verifying the abstract contract still exists — i.e., `View` itself must never acquire a real body.
- `test_all_methods_exist` (line 173): guards against *accidentally deleting* a contract method, which would silently break every implementation.
- `test_pause_signature` (line 75): even the **default argument value** of `pause` is asserted as part of the contract.

Together they mean: the contract is treated as a first-class, versioned artifact — change it deliberately, and the tests tell you.

---

## 5. Python-specific notes

- **Duck typing vs. ABC.** Python doesn't force interfaces. You could have used `abc.ABC` + `@abstractmethod`, which makes `PygameView` *fail at construction* if it forgets one method. This project instead uses the lighter "base class + `raise NotImplementedError`" convention (see `test_view_is_instantiable`, test_view_interface.py:163, which even documents that this is a deliberate "non-ABC design"). Both are valid; the ABC version is stricter, the current version is more Pythonic/loose.
- **Type hints document the intent.** `prompt(self, message: str) -> str` in the interface is where the contract's *typing* lives; implementations inherit that expectation.
- **The Liskov check you can do mentally:** everywhere you see `self.view.X(...)` in the controller, `X` must exist in `View` with a compatible signature. If that's always true, any `View` subclass is swappable.

---

## 6. Two real deviations in this codebase (great critical-thinking exercises)

A good tutor points at the blemishes, because they're where you learn fastest. There are two places where this project *bends* the very principle it preaches:

### 6.1 The type hint says the wrong class — `game_controller.py:16`

```python
def __init__(self, view: ConsoleView, constants_module):
```

The annotation says `ConsoleView` (the **implementation**), but the study guide says the controller "is typed against the base interface". The code still *behaves* correctly (it only calls contract methods, and `run.py` injects a `ConsoleView`), and in tests a `Mock` slips in because Python doesn't enforce annotations. But the annotation is a lie that will confuse future readers and IDEs. The principled fix:

```python
from hangman.view.view_interface import View

def __init__(self, view: View, constants_module):
```

Now the *type system itself* encodes "any View will do" — and if someone passes a `PygameView`, it's honest; if they pass a random object, mypy will complain.

### 6.2 A contract violation the mocks hide — `game_controller.py:412`

```python
choice = self.view.get_choice(["1", "2", "3"])
```

`get_choice` is **not in the `View` interface** (`view_interface.py`) and **not implemented in `ConsoleView`** (`console_view.py`). Two consequences:

1. In production, if the word bank runs dry during `start()`, the real app would crash with `AttributeError: 'ConsoleView' object has no attribute 'get_choice'` — the interface promised 8 verbs, and the consumer demanded a 9th.
2. The tests never catch it, because `Mock` happily fabricates *any* attribute: `view.get_choice.return_value = "1"` (test_game_controller.py:24). This is the classic danger of mocking: **a mock is too permissive — it validates that you called things, not that the object you called them on is actually allowed to have them.**

The correct fix, following the principle: add `get_choice` (or reuse `prompt` in a loop, which needs no interface change) to `View` first, then implement it in `ConsoleView`, then use it in the controller. That's the workflow — *grow the contract, then grow the implementations* — that keeps the substitution guarantee intact.

---

## 7. Checklist to verify the principle in any codebase

1. Find the base/abstract class with `NotImplementedError` (or ABC) bodies → that's the **interface**.
2. Find who *constructs* the concrete class. It should be exactly **one place** at the program's edge (here: `run.py`).
3. Grep the consumer for the concrete class name. It should appear **nowhere** except imports in the wiring file. (Here it *does* appear — in the type hint at `game_controller.py:16` — that's the deviation.)
4. Grep the consumer for method calls on the injected dependency; verify each one exists in the interface. (Here: `get_choice` fails this check.)
5. Check the tests: are they injecting a `Mock`/fake for that dependency? If yes, the principle is working for you.

**Bottom line:** `View` is a *promise*, `ConsoleView` is *one way of keeping it*, `GameController` is *the one who trusts the promise*, and `run.py` is *the one who picks the keeper*. Keep those four roles separated, and swapping terminal → GUI → mock becomes a one-line change — which is precisely what makes this codebase testable and extensible.

---
---

# Topic 1.5 — Duck Typing vs. ABC: Two Ways to Enforce a Contract

*Deep dive into the "Duck typing vs. ABC" note from Topic 1.4 (§5), including the `test_view_is_instantiable` evidence explained line by line.*

## 1. The problem being solved

`GameController` calls 8 methods on `self.view` (`display`, `prompt`, `show_word`, ...). The `View` base class is a *promise*: "anything I accept must have these 8 methods." But in Python that promise is just documentation — **the language enforces nothing** (unlike Java or C#). So the real question is:

> *When, and how, does a `PygameView` that forgot to implement `show_word` get caught?*

There are two valid answers. This project deliberately picks the looser one.

## 2. Option A — what this project does: base class + `raise NotImplementedError`

```python
# hangman/view/view_interface.py
class View:
    def display(self, message: str) -> None:
        raise NotImplementedError
    # ... 8 methods, all "empty promises"
```

Two ideas combined:

1. **Duck typing** — "if it quacks like a duck, it's a duck." Python judges an object by what it *can do*, not what it *declares*. A class that has the 8 methods works as a view **even if it never inherits from `View`**. There is no formal "implements" keyword in Python.
2. **`raise NotImplementedError`** — a loud trap. If some view forgets to override a method, calling it crashes *at that exact call* with `NotImplementedError` instead of silently doing nothing.

**When it fails: late.** You can construct `PygameView()` perfectly fine. The error only appears when the game actually reaches that method (e.g., the first `show_word` call during play).

## 3. Option B — ABC: the stricter alternative

```python
import abc

class View(abc.ABC):
    @abc.abstractmethod
    def display(self, message: str) -> None: ...
    # ... all 8 methods marked @abstractmethod
```

Now Python *itself* enforces the contract. A `PygameView(View)` that forgets even one method fails **at construction**:

```python
view = PygameView()
# TypeError: Can't instantiate abstract class PygameView
#            with abstract method show_word
```

**When it fails: early (fail-fast)** — at the single line in `run.py` where the view is created, before any game logic runs.

## 4. Side by side

| | Duck typing + `NotImplementedError` (current) | ABC |
|---|---|---|
| A view forgets a method | Crashes at runtime, when that method is first called | Crashes immediately at `PygameView()` |
| Can you call `View()` itself? | **Yes** | **No** → `TypeError` |
| Must a view inherit from `View`? | No — any object with the 8 methods works | Yes |
| Enforced by | Tests + convention | The language itself |
| Style | Loose, "Pythonic" | Strict, closer to Java/C# interfaces |

## 5. The evidence: `test_view_is_instantiable`

### 5.1 The vocabulary: what does "instantiable" mean?

**To instantiate** a class means to *create an object from it* — the parentheses:

```python
View()        # ← these parentheses are "instantiation"
view = View()
```

So **"View is instantiable"** simply means: *the line `view = View()` is allowed and doesn't crash.* That's all the word means.

### 5.2 What the test does, line by line

```python
# tests/unit/test_view_interface.py:163
def test_view_is_instantiable():
    """The interface can currently be instantiated (non-ABC design)."""
    view = View()                          # create a View object
    assert isinstance(view, View)          # check it really is one
```

- `view = View()` — "make me a View object." If the project used an ABC, **this exact line would crash** with `TypeError` (see §5.4, section 1).
- `assert isinstance(view, View)` — `assert` means "I promise this is true; if it's false, the test fails." `isinstance(view, View)` asks "is `view` an object of class `View`?" Trivially yes, but it makes the intent explicit.

In plain English the test says: **"I expect `View()` to work. If it ever stops working, something changed in the design."**

### 5.3 Why this is *evidence*

> **A passing test is a frozen decision.**

The author of this test sat down at some moment and asked: *"Should `View` be a true ABC (un-instantiable), or a loose base class (instantiable)?"* They **chose** the loose design — and then wrote that choice down *as a test*, so the decision can't be silently erased later.

The docstring is the author talking to the future reader:

```python
"""The interface can currently be instantiated (non-ABC design)."""
```

"non-ABC design" = *"Hey, I know ABCs are a popular way to do this. I deliberately did NOT use one. This test exists so nobody 'fixes' it by accident."*

Now imagine a month from now someone reads a blog post saying "always use ABCs!" and rewrites the interface:

```python
import abc

class View(abc.ABC):
    @abc.abstractmethod
    def display(self, message: str) -> None: ...
```

Then `pytest` runs and `test_view_is_instantiable` **fails immediately**:

```
tests/unit/test_view_interface.py:165: in test_view_is_instantiable
    view = View()
E   TypeError: Can't instantiate abstract class View ...
```

The test catches the design change and forces a conscious decision: "do I really want ABC now? Then I must also delete/rewrite this test." The design can only change **on purpose, with a visible test change** — never by accident.

### 5.4 Live demo: loose vs. strict, observed

A self-contained script (save as `abc_demo.py`, run with `python3 abc_demo.py`):

```python
import abc

# ---------- Design A: what the project actually has (loose) ----------
class ViewLoose:
    def display(self, message):
        raise NotImplementedError

# ---------- Design B: the stricter ABC alternative ----------
class ViewStrict(abc.ABC):
    @abc.abstractmethod
    def display(self, message):
        ...

# 1) Can you create an object of the BASE class itself?
ViewLoose()          # works
ViewStrict()         # TypeError

# 2) A "bad" view that forgets to implement display()
class BadLoose(ViewLoose):
    pass             # forgot display!
class BadStrict(ViewStrict):
    pass             # forgot display!

BadLoose()           # works (no complaint yet!)
BadStrict()          # TypeError

# 3) When does the "bad loose view" finally explode?
bad = BadLoose()
bad.display("hello") # NotImplementedError — at CALL time
```

Observed output (addresses abbreviated):

```
=== 1) Can you create an object of the BASE class itself? ===
Loose  design: ViewLoose()  -> <__main__.ViewLoose object at 0x...>
Strict design: ViewStrict() -> TypeError: Can't instantiate abstract class ViewStrict without an implementation for abstract method 'display'

=== 2) A 'bad' view that forgets to implement display() ===
Loose  design: BadLoose()  -> <__main__.BadLoose object at 0x...>  (construction OK!)
Strict design: BadStrict() -> TypeError: Can't instantiate abstract class BadStrict without an implementation for abstract method 'display'

=== 3) When does the 'bad loose view' finally explode? ===
bad.display('hello') -> NotImplementedError
It only failed HERE, at CALL time, long after construction.
```

| Question | Loose design (this project) | ABC design |
|---|---|---|
| Can I do `View()`? | ✅ Yes — that's exactly what the test checks | ❌ `TypeError` — the test would fail |
| `BadView(View)` forgets `display` — can I do `BadView()`? | ✅ Yes (no complaint yet!) | ❌ `TypeError` right at construction |
| When does `BadView` finally break? | **Late**: first `bad.display(...)` call → `NotImplementedError` | **Early**: it's never built in the first place |

That last row is the *price* of the loose design: it's more permissive, so mistakes surface later. The project compensates by testing the contract heavily — `test_all_methods_raise_not_implemented` (line 36), `test_all_methods_exist` (line 173), and `test_pause_signature` (line 75) in the same file.

## 6. The beginner mental model

> **In Python, tests are written promises. A test like `test_view_is_instantiable` doesn't just check behavior — it records *which design was chosen on purpose*, so the choice stays visible and protected.**

You'll see this pattern everywhere in professional code: a seemingly odd test with a docstring explaining *why* something is the way it is. That's not redundancy — it's documentation that the computer actually enforces for you, every time `pytest` runs.

## 7. Quick self-check (try these to lock it in)

1. Run the §5.4 demo. Confirm the three observations: the loose base class is instantiable, the bad loose subclass is instantiable, and it only explodes at call time.
2. In a **scratch copy** (not the real file), convert `hangman/view/view_interface.py` to an ABC, run `pytest tests/unit/test_view_interface.py`, and watch `test_view_is_instantiable` fail. Revert.
3. In `tests/unit/test_view_interface.py:165`, imagine changing `View()` to `ConsoleView()`. The test would still pass — so it would *not* catch a "switch to ConsoleView" change. What assertion would guarantee "View itself must stay the base class"? (Hint: `type(view) is View`.)

**One‑line summary:** The project enforces the `View` contract with the looser Pythonic convention (duck typing + `raise NotImplementedError`), and `test_view_is_instantiable` is the *evidence* that this was a deliberate "non-ABC design" — a passing test that freezes the decision and makes any switch to ABC a visible, on-purpose change.

---
---

# Topic 2.1 — Encapsulation & Information Hiding

## The core idea

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

## Example 1: `Player` — the textbook case (`hangman/model/player.py`)

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

### What's hidden, and what's exposed?

The raw fact is `self.health`. But the *meaningful operations* are wrapped in two methods:

**`lose_health()` (player.py:13-16)** encapsulates three rules that must *always* hold together:
1. Health drops by exactly 1 per mistake.
2. Health **never goes below zero** — `max(0, self.health - 1)` clamps it.
3. It *reports* the transition: returns `True` only on the exact turn where the player dies.

**`is_alive()` (player.py:18-19)** encapsulates the definition of "alive" in one place.

### "What if" — without encapsulation

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

### Who respects the boundary?

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

## Example 2: `Game` — internal state + a status-dictionary interface (`hangman/model/game.py`)

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

### Defensive copies — a subtle but important technique

```python
def get_visible_word(self) -> List[str]:        # game.py:256-257
    return list(self.unknown_word)

def get_remaining_letters(self) -> set:         # game.py:264-265
    return set(self.remaining_letters)
```

These return **copies**, not the live objects. If they returned the real list/set, the view could do `game.get_visible_word()[0] = "X"` and corrupt game state without ever calling a method. Copying on read closes that leak. This is information hiding in its strictest form: you get *information*, not a *handle*.

(Contrast with `get_player()` at game.py:259-262, which deliberately returns the real `Player` object — but that's fine because `Player` itself enforces its own invariants through its methods.)

### The `_` convention in action

```python
def _normalize(self, text: str) -> str:   # game.py:34
```

The leading underscore says: "this is an implementation detail. Outside code (including the controller) should not call it." It *can* call it (Python won't stop it), but the name signals it's not part of the public contract. `WordRepository` uses this heavily: `_load`, `_add_if_valid`, `_validate_normalize`, `_normalize_for_internal` are all private; only `get_by_difficulty()` and `reset_session()` are public (word_repository.py:146, 170).

---

## Example 3: `WordRepository` — hiding complexity, not just data

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

## The boundary in the MVC structure

You can see encapsulation expressed architecturally:

| Component | May read | May modify |
|---|---|---|
| `Game` (model) | its own state, `Player` objects | everything — but only through its own methods |
| `GameController` | status dicts, `get_visible_word()`, `is_game_over()` | nothing in the model directly |
| `ConsoleView` (view) | data passed to it as arguments | nothing at all — it just prints |

The controller is the only component that *calls* model methods; the view never calls any. Each layer depends on the next one's **public interface only** — that's the "low coupling" the guide mentions in 2.4.

---

## Honest caveats (worth knowing as a beginner)

1. **Python privacy is a promise, not an enforcement.** `player.health = 0` is perfectly valid Python from anywhere. You'll even see it in *your tests*, e.g. `test_player.py:100` (`player.health = initial_health`) and `test_game.py:105` — tests commonly set state directly to create a starting condition, then exercise one method. That's an accepted practice: tests are inside the "trusted" boundary.
2. **`Game` itself reaches into `Player`** in one place — `reset_for_new_round()` does `p.health = p.max_health` (game.py:93) instead of a `player.reset()` method. It works, but the "cleaner" design would add a method to `Player`. A good exercise for you: add `def restore_health(self)` to `Player` and use it there, so *no* health mutation exists outside the `Player` class.
3. The real enforcement tools in Python, if you ever need them: **`@property`** (custom get/set logic with validation) and `__name` mangling. For most application code — like this project — the `_` convention plus discipline is the idiomatic choice.

---

## Summary

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
