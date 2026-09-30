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
