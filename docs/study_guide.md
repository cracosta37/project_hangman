# Comprehensive Study Guide: MVC Hangman Project

This comprehensive guide outlines the architecture, design paradigms, and software engineering practices implemented in your MVC Hangman project. It serves as a roadmap for mastering the concepts that make this codebase robust, testable, and maintainable.

---

### 1. Software Architecture & Paradigms
The structural foundation of the project, focusing on how components interact and where logic resides.

*   **MVC Pattern (Model-View-Controller):**
    *   **Model ([Game](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/hangman/model/game.py) & [Player](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/hangman/model/player.py)):** Pure logic and state. It contains game rules, player health, and letter tracking. It does not perform any console input/output (I/O) or interact with the file system.
    *   **View ([ConsoleView](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/hangman/view/console_view.py)):** The representation and user interaction layer. It prints the word state, displays the hangman ASCII graphics, and gathers user input. It is designed to be "dumb" and only execute display operations instructed by the controller.
    *   **Controller ([GameController](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/hangman/controller/game_controller.py)):** The orchestrator. It receives user inputs from the View, delegates business rules and validation to the Model, and determines the flow of screens and prompts in the View.
*   **Separation of Concerns (SoC):**
    *   Keeping word loading ([WordRepository](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/hangman/services/word_repository.py)), game mechanics ([Game](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/hangman/model/game.py)), and user I/O ([ConsoleView](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/hangman/view/console_view.py)) isolated.
    *   This ensures that UI modifications (e.g., migrating from terminal to a GUI or Web View) do not require changing the core game logic.
*   **Dependency Injection (DI):**
    *   Passing the [View](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/hangman/view/view_interface.py) interface and the `constants` module as constructor arguments to the [GameController](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/hangman/controller/game_controller.py#L16).
    *   This makes components loosely coupled and allows tests to inject mock versions of the view, checking output sequences without opening a real terminal or expecting actual keyboard inputs.
*   **Program to Interfaces, Not Implementations:**
    *   Defining the abstract [View](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/hangman/view/view_interface.py) base class interface with standard methods like `display`, `prompt`, and `show_word`.
    *   The controller is typed against the base interface, meaning any concrete class (e.g., `ConsoleView`, `PygameView`, `TkinterView`) can be substituted transparently as long as it adheres to the contract.

---

### 2. Object-Oriented Programming (OOP) Principles
The core object-oriented concepts applied to design clean and maintainable classes.

*   **Encapsulation & Information Hiding:**
    *   Keeping internal state protected. For instance, [Player](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/hangman/model/player.py) exposes methods like `lose_health()` and `is_alive()` rather than letting external classes manually decrement or check its health field.
    *   The [Game](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/hangman/model/game.py) class processes letter inputs internally and returns a status dictionary outlining correct/incorrect placement, preventing direct modification of game variables by the view or controller.
*   **Abstraction:**
    *   Hiding complex background mechanics. The [WordRepository](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/hangman/services/word_repository.py) class abstracts away file reading, JSON parsing, validation, and unicode cleanup, exposing a simple `get_by_difficulty(difficulty)` method to its users.
*   **Single Responsibility Principle (SRP):**
    *   Each class has a single reason to change:
        *   [Player](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/hangman/model/player.py) maintains identity and health.
        *   [Game](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/hangman/model/game.py) maintains multi-player states and applies round-based game rules.
        *   [WordRepository](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/hangman/services/word_repository.py) manages the loading, validation, and history of game words.
*   **High Cohesion & Low Coupling:**
    *   Classes are highly cohesive because their internal methods focus entirely on a single logical component.
    *   Coupling is low because classes interact strictly through defined methods and parameter inputs, rather than accessing global states or cross-referencing internal details.

---

### 3. Software Design Patterns
Re-usable design patterns that solve common software construction problems.

*   **Repository Pattern:**
    *   The [WordRepository](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/hangman/services/word_repository.py) decouples data storage from application business logic. The application doesn't care if the word bank is a JSON file, a database, or an external web API; it interacts with the repository class to receive data.
*   **Factory Method Pattern (in Testing):**
    *   In the test files (e.g., [test_player.py](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/tests/unit/test_player.py#L9-L26)), a factory fixture `make_player` is used.
    *   This encapsulates the instantiation details of test objects, allowing you to configure custom states dynamically while providing sensible defaults.
*   **State Management / State Transition:**
    *   The [Game](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/hangman/model/game.py) maintains variables representing state transitions (e.g., `remaining_players`, `remaining_spaces`, `game_won`, `game_over`). Methods return structured results reflecting these transitions, ensuring that state checks remain centralized.

---

### 4. Data Handling & Input Processing
Techniques used to handle user input securely, cleanly, and predictably.

*   **Unicode Normalization & Accent Removal:**
    *   Applying `unicodedata.normalize("NFD", text)` to decompose accented characters (e.g., "á" becomes "a" + combining acute accent) and removing diacritics (Mn category characters) in [WordRepository._normalize_for_internal](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/hangman/services/word_repository.py#L123-L141).
    *   This ensures that accent differences do not break character matching during the game (e.g., guessing "a" matches "á").
*   **Sanitization and Validation:**
    *   Checking strings for characters outside of allowed alphabets, hyphens, and spaces.
    *   Discarding invalid values and preventing errors like word duplication, length violations, or empty values.
*   **Session-Level No-Repeat:**
    *   Tracking previously used words using a `used_words` set inside [WordRepository](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/hangman/services/word_repository.py#L28) to prevent displaying the same word twice in a single session.
*   **Configuration Externalization:**
    *   Moving constant values like maximum health and ASCII hangman graphics into a standalone [constants.py](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/hangman/constants.py) module rather than scatter-storing them within classes.

---

### 5. Software Testing & Pytest Framework
Developing a reliable test suite using standard Python testing tools to guarantee code correctness.

*   **Pytest Fixtures:**
    *   Structuring reusable test environments (e.g., `player`, `low_health_player`, `dead_player` in [test_player.py](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/tests/unit/test_player.py#L32-L46)).
    *   Fixtures promote DRY (Don't Repeat Yourself) code by sharing initialization logic across test cases.
*   **Parametrized Tests:**
    *   Using `@pytest.mark.parametrize` to run the same assertion logic against multiple sets of inputs and expected outcomes (e.g., testing letter guessing boundaries or constructor constraints).
*   **Mocking & Stubbing (`unittest.mock`):**
    *   Using `Mock` objects and `patch` to isolate units. For example, testing the [GameController](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/hangman/controller/game_controller.py) behavior requires mocking user input prompts to simulate a complete sequence of game rounds without a real console loop.
    *   Using `side_effect` to return sequential inputs to simulate real-world interactive menus.
*   **Exception Testing:**
    *   Validating that correct exceptions are raised under failure conditions using `pytest.raises` (e.g., validating that the word repository properly raises `FileNotFoundError` or `ValueError` on bad inputs).
*   **Integration Testing:**
    *   Simulating the entrypoint ([run.py](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/run.py)) in [test_run.py](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/tests/integration/test_run.py) using `runpy` to test system initialization and coordinate module configurations under simulated execution blocks.

---

### 6. Python Best Practices & Language Features
Idiomatic Python structures used to enforce clean coding guidelines.

*   **Type Hinting:**
    *   Using typing annotations (e.g., `List[str]`, `Dict[str, Any]`, `Set[str]`, `Union[str, Path]`) to improve code documentation and support IDE autocomplete features.
*   **Path Management with `pathlib.Path`:**
    *   Using the `Path` library instead of raw string concatenations for file path logic (e.g., inside [word_repository.py](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/hangman/services/word_repository.py#L24)), guaranteeing cross-platform operating system compatibility (Windows/macOS/Linux).
*   **Safe input via `getpass`:**
    *   Using Python's standard `getpass.getpass` library in [ConsoleView](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/hangman/view/console_view.py#L33) to allow a moderator to insert a secret word or phrase privately without displaying the letters in clear text on the screen.
*   **Module Initialization & Run Execution:**
    *   Leveraging package-level imports via `__init__.py` and segregating the application runner (`if __name__ == "__main__":` entrypoint in [run.py](file:///F:/Online%20courses/Self%20study/Python/Object%20oriented%20programming/Project%20Hangman/project_hangman/run.py#L12)).
*   **Interrupt Handling:**
    *   Handling `KeyboardInterrupt` and `EOFError` in view prompts to exit the game cleanly and restore console state if the player terminates execution prematurely (e.g., via `Ctrl+C`).
