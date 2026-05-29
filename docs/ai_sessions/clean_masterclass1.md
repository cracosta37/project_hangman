## USER 🧑‍💻

I want a structured and organized guide covering all the topics and software development practices implemented in this MVC project. As an expert in software development, testing,  Python and Pytest, and as an effective tutor and learning resource, please provide a comprehensive list of topics to study, including the necessary subtopics related to this project, software design paradigms, object-oriented programming concepts, software design patterns, architecture principles, and related areas.

---

## MODEL ✨

This comprehensive guide outlines the architecture, design paradigms, and software engineering practices implemented in your MVC Hangman project. It serves as a roadmap for mastering the concepts that make this codebase robust, testable, and maintainable.

---

### 1. Software Architecture & Paradigms
The structural foundation of the project, focusing on how components interact and where logic resides.

*   **MVC Pattern (Model-View-Controller):**
    *   **Model (`Game`, `Player`):** Pure logic and state. It doesn't know about the terminal or JSON files.
    *   **View (`ConsoleView`):** The "dumb" layer. It only handles input/output.
    *   **Controller (`GameController`):** The orchestrator. It receives data from the View, updates the Model, and tells the View what to show next.
*   **Separation of Concerns (SoC):** Keeping data validation, game logic, and UI rendering in isolated layers.
*   **Dependency Injection (DI):** Passing the `View` and `constants` into the `Controller` constructor rather than hardcoding them, allowing for easy testing with mocks.

### 2. Object-Oriented Programming (OOP) Concepts
How the project utilizes Python’s object system to create flexible abstractions.

*   **Abstraction & Interfaces:**
    *   **`View` Interface:** Defines *what* a view must do (e.g., `display`, `prompt`) without dictating *how* (Console vs. GUI).
    *   **Contract-based Programming:** Using `NotImplementedError` in base classes to enforce a structure.
*   **Encapsulation:** Managing state (like `used_words` in `WordRepository`) through private methods and controlled public APIs.
*   **Composition:** The `GameController` *has a* `WordRepository` and *has a* `Game` instance, rather than inheriting from them.

### 3. Software Design Patterns
Specific "blueprints" used to solve recurring development challenges.

*   **Repository Pattern (`WordRepository`):** Centralizes data access. The rest of the app doesn't care if words come from a JSON file, an API, or a database.
*   **Strategy Pattern (Implicit):** Choosing between manual word entry and automatic selection from the repository.
*   **Factory-like Setup:** Initializing game entities based on user configuration (number of players, difficulty).

### 4. Advanced Testing with Pytest
The project demonstrates professional-grade testing strategies to ensure reliability.

*   **Mocking & Patching (`unittest.mock`):**
    *   **`Mock` objects:** Simulating the View or Model to test the Controller in isolation.
    *   **`patch`:** Replacing the `Game` class during setup tests to avoid running actual game logic.
    *   **Side Effects:** Simulating sequences of user inputs (e.g., `view.prompt.side_effect = ["Y", "N"]`).
*   **Pytest Fixtures:** Using factories (e.g., `controller_factory`) to create clean, reusable test environments.
*   **Parametrization (`@pytest.mark.parametrize`):** Running the same test logic with multiple inputs and expected outputs (Data-Driven Testing).
*   **Integration Testing:** Verifying that all parts (Model, View, Controller, Repo) work together correctly in `test_run.py`.

### 5. Python-Specific Best Practices
Leveraging modern Python features for clean and efficient code.

*   **Type Hinting:** Using `List`, `Dict`, `Set`, and `Union` from the `typing` module for better IDE support and code clarity.
*   **Path Management (`pathlib`):** Using `Path` objects instead of string manipulation for cross-platform file handling.
*   **Text Normalization (`unicodedata`):** Handling accents (diacritics) and case-insensitivity using Unicode NFD decomposition.
*   **JSON Serialization:** Loading and validating structured data from external files.
*   **Exception Handling:** Custom error detection (e.g., `_is_exhaustion_error`) to provide meaningful feedback to the user.

### 6. SOLID Principles & Clean Code
Principles that make the code "Clean."

*   **S - Single Responsibility:** `WordRepository` only handles words; `Player` only handles player state.
*   **O - Open/Closed:** The system is open to new View types (like a `GUIView`) without changing the `GameController` logic.
*   **L - Liskov Substitution:** Any subclass of `View` can be used by the Controller without it breaking.
*   **I - Interface Segregation:** The `View` interface provides a specific set of methods required by the game.

### 7. Game Development Logic
Core patterns common in game programming.

*   **The Game Loop:** The `while` loop in `run_game_loop` that continues until a "Game Over" state is reached.
*   **State Management:** Tracking which players are alive, which letters are guessed, and the current state of the hidden word.
*   **Input Validation Loops:** Robust "retry" logic to handle invalid user inputs without crashing the application.

---

### Suggested Learning Path
1.  **Phase 1: Foundations.** Focus on **MVC** and **OOP Composition**.
2.  **Phase 2: Data & Utilities.** Study **`pathlib`** and **`WordRepository`** implementation.
3.  **Phase 3: Testing.** Master **Mocks** and **Fixtures** in Pytest.
4.  **Phase 4: Refinement.** Deep dive into **Unicode normalization** and **SOLID principles**.

---

## USER 🧑‍💻

Please merge it with this one:

Phase 1: Object-Oriented Programming (OOP) Foundations
The "Building Blocks" of your code.

Classes and Objects: How to model real-world entities (e.g., Player, Game).
Encapsulation:
Managing internal state (e.g., _unknown_word in Game).
Exposing behavior through methods rather than direct attribute access.
Abstraction:
Creating interfaces (View) to hide implementation details from the user (Controller).
Using Abstract Base Classes (ABCs) to define "contracts."
Polymorphism:
The ability of the Controller to call .display() on any View object, regardless of whether it's Console or GUI.
Composition vs. Inheritance:
How the GameController has a Game and has a View (Composition) rather than inheriting from them.
Phase 2: SOLID Design Principles
The "Philosophy" that makes code maintainable and flexible.

Single Responsibility Principle (SRP): Ensuring a class has only one reason to change (e.g., WordRepository only handles data, not game rules).
Open/Closed Principle (OCP): Making the system open for extension (adding new Views) but closed for modification.
Liskov Substitution Principle (LSP): Ensuring ConsoleView can be used anywhere a View is expected without breaking the system.
Interface Segregation Principle (ISP): Keeping the View interface lean and focused.
Dependency Inversion Principle (DIP): High-level modules (Controller) should not depend on low-level modules (ConsoleView); both should depend on abstractions (View).
Phase 3: Architectural Patterns
The "Blueprint" of the application.

Model-View-Controller (MVC):
Model: Pure logic, data, and state (The "Brain").
View: User interface and I/O (The "Face").
Controller: Orchestration and event handling (The "Glue").
Separation of Concerns (SoC): Keeping I/O (print/input) completely isolated from business logic.
Layered Architecture: Understanding the boundary between the Data layer (WordRepository), Domain layer (Game), and Presentation layer (ConsoleView).
Phase 4: Gang of Four (GoF) Design Patterns
Proven solutions to recurring design problems.

Strategy Pattern: Swapping UI implementations (View) at runtime.
Repository Pattern: Abstracting data access logic (JSON loading and filtering).
Dependency Injection (DI): Passing dependencies into the constructor (__init__) instead of creating them inside the class.
Data Transfer Object (DTO): Using structured dictionaries to pass complex results back from the Model to the Controller.
Phase 5: Python-Specific Implementation
Leveraging the language's specific strengths.

Type Hinting: Using the typing module (List, Dict, Optional) to improve code clarity and IDE support.
Unicode and Normalization:
Using unicodedata to handle international characters and accents (NFD/NFC normalization).
File System Handling: Using pathlib for robust, cross-platform path management.
Error Handling: Custom exception strategies and catching specific errors (e.g., ValueError vs. TypeError).
JSON Serialization: Loading and parsing structured data files efficiently.
Phase 6: Software Quality and Testing
Ensuring the code actually works and stays working.

Unit Testing: Testing individual components in isolation using pytest.
Test Fixtures: Using pytest.fixture to set up clean environments for each test.
Mocking/Patching: Using unittest.mock to simulate external dependencies (like random word selection or user input).
Integration Testing: Verifying that the Model and Repository work together correctly.
Edge Case Coverage: Testing for empty files, invalid inputs, and boundary conditions (like 1 health remaining).
Phase 7: Professional Workflow & Clean Code
Industry-standard habits.

Project Structuring: Organizing files into src/, tests/, and data/ directories.
Naming Conventions: Adhering to PEP 8 (Python's style guide).
Idempotency: Ensuring normalization logic can be run multiple times without changing the result.
Defensive Programming: Validating inputs at the "gates" (e.g., in set_word).

---

## MODEL ✨

I have synthesized a comprehensive, unified learning roadmap that merges the theoretical phases you provided with the specific technical implementations found in your Hangman MVC project. 

The guide below organizes these concepts into a logical progression, from OOP foundations to professional software quality practices.

---

# Unified Learning Roadmap: Hangman MVC Project

This guide provides a structured path to mastering software development by analyzing the Hangman MVC project. It blends theoretical computer science principles with the professional Python practices implemented in the codebase.

### Phase 1: Object-Oriented Programming (OOP) Foundations
*The "Building Blocks" of your code.*

*   **Classes and Objects:** Modeling real-world entities like `Player` (state) and `Game` (logic).
*   **Encapsulation:** 
    *   Managing internal state (e.g., `_unknown_word` in `Game`).
    *   Exposing behavior through methods rather than direct attribute access to protect data integrity.
*   **Abstraction:** 
    *   Creating interfaces (`View`) to hide implementation details from the `Controller`.
    *   Using Abstract Base Classes (ABCs) or `NotImplementedError` to define "contracts."
*   **Polymorphism:** The ability of the `Controller` to call `.display()` on any `View` implementation (Console, GUI, or Mock) interchangeably.
*   **Composition vs. Inheritance:** Understanding why `GameController` *has a* `Game` and *has a* `View` (Composition) rather than inheriting from them, leading to more flexible code.

### Phase 2: SOLID Design Principles
*The "Philosophy" that makes code maintainable and flexible.*

*   **Single Responsibility Principle (SRP):** Ensuring a class has only one reason to change (e.g., `WordRepository` only handles data, not game rules).
*   **Open/Closed Principle (OCP):** Designing the system to be open for extension (adding a `WebView`) but closed for modification of existing core logic.
*   **Liskov Substitution Principle (LSP):** Ensuring `ConsoleView` can be used anywhere a `View` is expected without breaking the system.
*   **Interface Segregation Principle (ISP):** Keeping the `View` interface lean and focused on what the game actually needs.
*   **Dependency Inversion Principle (DIP):** High-level modules (`Controller`) should not depend on low-level modules (`ConsoleView`); both should depend on abstractions (`View`).

### Phase 3: Architectural & Design Patterns
*The "Blueprints" for solving recurring problems.*

*   **Model-View-Controller (MVC):** 
    *   **Model:** Pure logic, data, and state (The "Brain").
    *   **View:** User interface and I/O (The "Face").
    *   **Controller:** Orchestration and event handling (The "Glue").
*   **Separation of Concerns (SoC):** Keeping I/O (print/input) completely isolated from business logic.
*   **Repository Pattern:** Abstracting data access logic (JSON loading, filtering, and normalization) in `WordRepository`.
*   **Strategy Pattern:** Swapping UI implementations at runtime.
*   **Dependency Injection (DI):** Passing the `View` and `constants` into the `Controller` constructor (`__init__`) to facilitate testing and flexibility.
*   **Data Transfer Object (DTO):** Using structured dictionaries (e.g., `{"ok": True, "correct": False}`) to pass complex results from the Model back to the Controller.

### Phase 4: Python-Specific Implementation
*Leveraging the language's specific strengths.*

*   **Type Hinting:** Using the `typing` module (`List`, `Dict`, `Set`, `Union`) for code clarity and IDE validation.
*   **Unicode and Normalization:** 
    *   Using `unicodedata` to handle international characters and accents (NFD decomposition).
    *   Implementing **Idempotency**: Ensuring normalization logic can be run multiple times without changing the result.
*   **Modern File Handling:** Using `pathlib` for robust, cross-platform path management instead of string manipulation.
*   **JSON Serialization:** Loading, parsing, and validating structured data files for the `WordRepository`.
*   **Custom Exception Handling:** Differentiating between recoverable errors (e.g., repeated guesses) and non-recoverable system errors.

### Phase 5: Software Quality & Testing
*Ensuring the code actually works and stays working.*

*   **Unit Testing with Pytest:** Testing individual components in isolation.
*   **Test Fixtures:** Using `pytest.fixture` and factory patterns to set up clean, repeatable environments for tests.
*   **Mocking & Patching:** 
    *   Using `unittest.mock` to simulate user input or random word selection.
    *   **Side Effects:** Simulating sequences of inputs (e.g., `view.prompt.side_effect = ["Y", "N"]`).
*   **Integration Testing:** Verifying that the Model, Repository, and Controller work together (e.g., `test_run.py`).
*   **Edge Case Coverage:** Testing boundary conditions like 1 health remaining, empty word banks, or invalid player counts.

### Phase 6: Professional Workflow & Clean Code
*Industry-standard habits.*

*   **Project Structuring:** Organizing code into `hangman/`, `tests/`, and `data/` directories.
*   **Defensive Programming:** Validating inputs at the "gates" (e.g., `set_word` and `WordRepository._validate_normalize`).
*   **Naming Conventions:** Adhering to PEP 8 for readability.
*   **Contract-based Setup:** Using `__init__.py` files to manage package exports and namespace.

---

I have saved this finalized plan as `unified_learning_guide.md` in the plans directory. Since this was an **Inquiry** regarding the study of the codebase, no source code changes are required.

---

## USER 🧑‍💻

I will study the topics step by step. Let's begin with:

Phase 1: Object-Oriented Programming (OOP) Foundations
  The "Building Blocks" of your code.

Classes and Objects: Modeling real-world entities like Player (state) and Game (logic).

---

## MODEL ✨

In object-oriented programming, a **Class** is a blueprint, and an **Object** is the actual building (instance) created from that blueprint.

Let's look at how this project models real-world entities using two primary classes: `Player` and `Game`.

### 1. The `Player` Class: Modeling State
The `Player` class represents a human participant. It is a perfect example of an object that primarily holds **State** (data about its current condition).

```python
class Player:
    def __init__(self, name: str, max_health: int, hangman_states: List[str]):
        # STATE (Attributes)
        self.name: str = name
        self.max_health: int = max_health
        self.health: int = max_health
        self.hangman_states: List[str] = hangman_states

    # BEHAVIOR (Methods)
    def lose_health(self) -> bool:
        previous = self.health
        self.health = max(0, self.health - 1)
        return previous > 0 and self.health == 0
```

*   **Real-world Mapping:** A player has a name, a current health level, and a visual state (the hangman drawing).
*   **Encapsulation of Logic:** Notice the `lose_health` method. Instead of the game manually subtracting health elsewhere, the `Player` object manages its own health reduction logic, returning a simple signal (`True`) if it was eliminated.

---

### 2. The `Game` Class: Modeling Logic
The `Game` class represents the "Session" or the "Ruleset." While it holds state (like the secret word), its primary purpose is to orchestrate **Logic**.

```python
class Game:
    def __init__(self, constants_module, normalize_input: bool = True):
        # COMPLEX STATE
        self.players: List[Player] = []  # Composition: Game "has a" list of Players
        self.word: str = ""              # The secret word
        self.unknown_word: List[str] = [] # The word with underscores
        self.remaining_letters: set[str] = set()

    # COMPLEX BEHAVIOR
    def guess_letter(self, player_index: int, raw_letter: str) -> Dict[str, Any]:
        # Orchestrates the rules:
        # 1. Validates the input
        # 2. Checks for repeats
        # 3. Updates the secret word if correct
        # 4. Tells the player to lose health if wrong
```

*   **Real-world Mapping:** A game session knows the secret word, who is playing, and what the rules are for guessing.
*   **Separation:** The `Game` doesn't print things to the screen (I/O). It just calculates if a guess was "correct" or "incorrect" based on its internal state.

### Key Takeaway for your Study:
When you look at a class, always ask:
1.  **What does it know?** (Attributes/State - e.g., `health`, `word`).
2.  **What can it do?** (Methods/Behavior - e.g., `lose_health()`, `guess_letter()`).

In this MVC project, the **Model** is built from these classes because they don't care *how* the user sees the data—they only care about the **truth** of the game's data.

**Would you like to move on to Encapsulation, or do you have questions about how these classes were initialized?**

---

## USER 🧑‍💻

Yes, please

---

## MODEL ✨

**Encapsulation** is the practice of bundling data (state) and methods (behavior) together while hiding the "guts" of the object from the outside world.

In Python, we use a single underscore prefix (e.g., `_attribute`) to signal that something is "private" or "protected"—meaning other parts of the program shouldn't touch it directly.

### 1. Hiding Internal State
In the `Game` class, the attributes `self.word` and `self.unknown_word` are vital. If the Controller manually changed `self.word` to something else mid-game, it would break the synchronization with `self.unknown_word` (the version with underscores).

Instead, the `Game` class provides a **Public Method** called `set_word()`:

```python
# PUBLIC GATE
def set_word(self, raw_word: str) -> Dict[str, Any]:
    # 1. VALIDATION: It checks if the word is empty or invalid.
    # 2. COORDINATION: It updates BOTH self.word AND self.unknown_word.
    # 3. SAFETY: The outside world doesn't need to know HOW the underscores are created.
```

### 2. Hiding Complexity (The "Black Box")
Notice the `_normalize()` method in the code above. 
*   **The Controller** just wants a clean word. 
*   **The Model** knows that "cleaning" a word involves complex Unicode decomposition (`NFD`) and filtering diacritics.

By making it `_normalize`, you are saying: *"This is a helper tool for the Game's internal use. Don't call this from the View."*

### Why this is important for you:
1.  **Data Integrity:** You ensure that the internal state of an object always makes sense. You can't have a "win" state if the `remaining_spaces` attribute wasn't updated correctly.
2.  **Ease of Use:** A developer using your `Game` class only needs to know about `guess_letter()` or `set_word()`. They don't need to understand how Unicode normalization works.
3.  **Future-proofing:** If you decide to change how normalization works later, you only change the code inside `_normalize()`. The rest of your app (Controller/View) remains untouched because they only see the "public interface."

---

**Next topic: Abstraction (Creating the View "Contract"). Shall we proceed?**

---

## USER 🧑‍💻

Yes

---

## MODEL ✨

**Abstraction** is about focusing on *what* an object does rather than *how* it does it. It allows you to create a "contract" that other parts of the system can rely on.

### 1. The Interface: The "What"
Look at `view_interface.py`. This class (`View`) doesn't actually *do* anything. Every method just raises a `NotImplementedError`.

```python
class View:
    def display(self, message: str) -> None:
        raise NotImplementedError
```

This is the **Abstraction**. It tells the `GameController`: *"I don't know if you're using a terminal or a website, but I promise that whatever 'View' you get will have a method called `display`."*

### 2. The Implementation: The "How"
Now look at `console_view.py`. It **inherits** from `View` and fills in the details.

```python
class ConsoleView(View):
    def display(self, message: str) -> None:
        print(message)  # The specific implementation for the terminal
```

### Why this is powerful for you:
1.  **Decoupling:** The `GameController` is "blind" to the details. It just calls `view.display()`. If you wanted to make this a Desktop App with buttons tomorrow, you would just create a `GUIView` class and swap it in. You wouldn't have to change a single line of logic in the Controller.
2.  **Testing:** During your unit tests, you don't want to actually print things to the screen or wait for a user to type. Because of this abstraction, you can create a "Mock View" (a fake implementation) that just records what happened, making tests fast and automated.
3.  **Logical Focus:** It keeps the "Business Logic" (Rules of Hangman) separate from the "Presentation Logic" (Colors, Buttons, Text).

### Key Takeaway:
Abstraction creates a **Boundary**. On one side is the *intent* (display a message), and on the other side is the *execution* (calling the `print()` function).

---

**Next topic: Polymorphism (Swapping implementations). Ready to see how the Controller uses this?**

---

## USER 🧑‍💻

Please continue with:

Using Abstract Base Classes (ABCs) or `NotImplementedError` to define "contracts."

---

## MODEL ✨

In Python, a **Contract** is a formal agreement that says: *"Any class that wants to be a 'View' MUST implement these specific methods, or the program will fail."*

There are two primary ways to enforce this:

### 1. The Manual Way: `NotImplementedError` (Current Project)
This is what you see in `view_interface.py`. 

```python
class View:
    def display(self, message: str) -> None:
        raise NotImplementedError("Subclasses must implement display()")
```

*   **How it works:** It allows you to create the `View` class, but if you (or another developer) try to use it without overriding `display`, the code will crash with a specific error message.
*   **Pros:** Very simple, no imports required, works in all versions of Python.
*   **Cons:** You only find out the method is missing when you try to **run** that specific line of code.

### 2. The Professional Way: Abstract Base Classes (ABCs)
While not used in your current project, this is the industry standard for large applications. It uses Python's built-in `abc` module.

```python
from abc import ABC, abstractmethod

class View(ABC):  # Inherits from ABC
    @abstractmethod
    def display(self, message: str) -> None:
        pass
```

*   **How it works:** If you try to create an object from a subclass that forgot to implement `display`, Python will throw an error **immediately** when you try to instantiate the object: `TypeError: Can't instantiate abstract class ConsoleView with abstract method display`.
*   **The Contract:** This is a "Strict Contract." You cannot even *start* the game if the View is incomplete.

---

### Why does the `GameController` care about this "Contract"?

Look at how the `GameController` uses the View in `game_controller.py`:

```python
class GameController:
    def __init__(self, view: View, ...):
        self.view = view # We expect a 'View' object

    def setup_game(self):
        self.view.clear()       # Contract Step 1
        self.view.show_title()  # Contract Step 2
```

Because of the **Contract** defined in `view_interface.py`, the developer writing the `GameController` has **Total Confidence**. They don't need to check if `clear()` exists; the "Contract" guarantees it.

### Summary for your Study:
*   **Contract:** A promise of behavior.
*   **`NotImplementedError`:** A "Soft Contract" (fails during execution).
*   **`ABC` / `@abstractmethod`:** A "Strict Contract" (fails during setup).

**Next up: Polymorphism (The ability to swap these contract-fulfillers at will). Shall we move on?**