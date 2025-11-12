import string
import os
import getpass
import unicodedata


# ======================================================================
# Abstract View Layer
# ======================================================================

class View:
    """Abstract interface for user interaction."""

    def display(self, message: str) -> None:
        raise NotImplementedError

    def prompt(self, message: str) -> str:
        raise NotImplementedError

    def prompt_hidden(self, message: str) -> str:
        raise NotImplementedError

    def pause(self, message: str = "Press Enter to continue...") -> None:
        raise NotImplementedError

    def clear(self) -> None:
        raise NotImplementedError

    def show_word(self, word_state: list[str]) -> None:
        raise NotImplementedError

    def show_health(self, player) -> None:
        raise NotImplementedError


# ======================================================================
# Concrete Console View Implementation
# ======================================================================

class ConsoleView(View):
    """Handles all console-based input and output operations."""

    def __init__(self, use_clear: bool = True):
        self.use_clear = use_clear

    def clear(self) -> None:
        """Clear console screen."""
        if self.use_clear:
            os.system('cls' if os.name == 'nt' else 'clear')

    def display(self, message: str) -> None:
        print(message)

    def prompt(self, message: str) -> str:
        try:
            return input(message)
        except (KeyboardInterrupt, EOFError):
            print("\nGame interrupted. Exiting safely.\n")
            exit(0)

    def prompt_hidden(self, message: str) -> str:
        try:
            return getpass.getpass(prompt=message)
        except (KeyboardInterrupt, EOFError):
            print("\nGame interrupted. Exiting safely.\n")
            exit(0)

    def pause(self, message: str = "Press Enter to continue...") -> None:
        try:
            input(message)
        except (KeyboardInterrupt, EOFError):
            print("\nGame interrupted. Exiting safely.\n")
            exit(0)

    def show_word(self, word_state: list[str]) -> None:
        print(f"    {' '.join(word_state)}\n")

    def show_health(self, player) -> None:
        print(player._hangman_states[player.health])
        print()


# ======================================================================
# Player Model
# ======================================================================

class Player:
    """Represents a player in the Hangman game."""

    def __init__(self, name: str, max_health: int, hangman_states: list[str]):
        self._name = name
        self._max_health = max_health
        self._health = max_health
        self._hangman_states = hangman_states

    @property
    def name(self) -> str:
        return self._name

    @property
    def health(self) -> int:
        return self._health

    def lose_health(self, view: View = None) -> bool:
        """
        Decrement player’s health by one and display updated health if view provided.
        Returns True if the player has just been eliminated.
        """
        previous_health = self._health
        self._health = max(0, self._health - 1)
        if view:
            self.show_health(view)
        return previous_health > 0 and self._health == 0

    def show_health(self, view: View) -> None:
        """Delegate visualization to the view layer."""
        view.show_health(self)


# ======================================================================
# Core Game Logic
# ======================================================================

class Game:
    """
    Core Hangman game with accent normalization and robust elimination logic.

    The view layer is decoupled from the game mechanics to allow alternative
    interfaces (GUI, web, or testing mocks).
    """

    def __init__(self, constants_module, view: View = None, normalize_input: bool = True):
        self.c = constants_module
        self.view = view or ConsoleView()
        self.normalize_input = normalize_input

        self.players: list[Player] = []
        self.word: str = ""
        self.unknown_word: list[str] = []

        # Letter set adapts to normalization setting
        if normalize_input:
            base_letters = string.ascii_uppercase
        else:
            base_letters = string.ascii_uppercase + "ÑÁÉÍÓÚÜÇ"
        self.remaining_letters: set[str] = set(base_letters)

        self.remaining_players = 0
        self.n_players = 0
        self.remaining_spaces = 0

    # ------------------------------------------------------------------
    # Main Game Loop
    # ------------------------------------------------------------------

    def play_game(self):
        self.view.clear()
        self._create_word()
        self._create_players()

        end = False
        i = 0

        while not end and self.remaining_players > 0:
            player = self.players[i % self.n_players]

            # Skip eliminated players
            if player.health == 0:
                i += 1
                continue

            self.view.clear()
            self.view.display(f"Turn of {player.name}.\n")
            end = self._play_turn(player)
            i += 1

        self._exit_game()

    # ------------------------------------------------------------------
    # Normalization Utilities
    # ------------------------------------------------------------------

    def _normalize_word(self, text: str) -> str:
        """Normalize accented characters if enabled."""
        if not self.normalize_input:
            return text.upper()

        normalized = unicodedata.normalize("NFD", text)
        filtered = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        return filtered.upper()

    # ------------------------------------------------------------------
    # Word Setup
    # ------------------------------------------------------------------

    def _create_word(self):
        """Create a valid word with optional accent normalization."""
        while True:
            word = self.view.prompt_hidden("Please insert the word: ").strip()

            if len(word) == 0:
                self.view.display("The word cannot be empty.\n")
                continue

            # Ensure at least two alphabetic characters
            letters_only = [ch for ch in word if ch.isalpha()]
            if len(letters_only) < 2:
                self.view.display("The word must contain at least two letters.\n")
                continue

            if not all(ch.isalpha() or ch in {" ", "-"} for ch in word):
                self.view.display("The word can only contain letters, spaces, or hyphens.\n")
                continue
            break

        normalized = self._normalize_word(word)
        self.word = normalized
        self.unknown_word = ["_" if ch.isalpha() else ch for ch in normalized]
        self.remaining_spaces = sum(ch == "_" for ch in self.unknown_word)

    # ------------------------------------------------------------------
    # Player Setup
    # ------------------------------------------------------------------

    def _create_players(self):
        """Ask for number of players and enforce unique names."""
        while True:
            try:
                n = int(self.view.prompt("Please insert the number of players: "))
                if n <= 0:
                    self.view.display("The number of players must be positive.\n")
                else:
                    self.n_players = n
                    break
            except ValueError:
                self.view.display("Invalid input. Please enter an integer.\n")

        self.remaining_players = self.n_players

        for i in range(1, self.n_players + 1):
            while True:
                name = self.view.prompt(f"Please insert the name of player {i}: ").strip().title()
                if not name:
                    self.view.display("Name cannot be empty.\n")
                    continue
                if any(p.name.lower() == name.lower() for p in self.players):
                    self.view.display("That name is already taken. Please choose another name.\n")
                    continue
                break
            self.players.append(Player(name, self.c.MAX_HEALTH, self.c.HANGMAN))

    # ------------------------------------------------------------------
    # Turn and Guess Logic
    # ------------------------------------------------------------------

    def _play_turn(self, player: Player) -> bool:
        player.show_health(self.view)
        self.view.show_word(self.unknown_word)

        while True:
            try:
                insert_type = int(self.view.prompt("Guess type: 1 for letter, 2 for word: "))
                if insert_type not in (1, 2):
                    self.view.display("Invalid input. Please enter 1 or 2.\n")
                else:
                    break
            except ValueError:
                self.view.display("Invalid input. Please enter 1 or 2.\n")

        return self._guess_letter(player) if insert_type == 1 else self._guess_word(player)

    def _guess_letter(self, player: Player) -> bool:
        while True:
            raw_letter = self.view.prompt("Please insert a letter: ").strip().upper()
            if len(raw_letter) != 1 or not raw_letter.isalpha():
                self.view.display("Invalid input. Please enter a single letter.\n")
                continue

            letter = self._normalize_word(raw_letter)
            if letter not in self.remaining_letters:
                self.view.display(f"'{raw_letter}' was already used. Try another letter.\n")
                continue
            break

        self.remaining_letters.remove(letter)
        positions = [i for i, l in enumerate(self.word) if l == letter]
        times_guessed = len(positions)

        self.view.clear()
        if times_guessed == 0:
            self.view.display(f"Sorry, the letter '{raw_letter}' is not in the word.\n")
            eliminated = player.lose_health(self.view)
            if eliminated:
                self.remaining_players -= 1
                self.view.display(f"{player.name} has been eliminated.\n")

            self.view.show_word(self.unknown_word)
            self.view.pause()
            return self._game_over()

        for pos in positions:
            self.unknown_word[pos] = letter
        self.remaining_spaces -= times_guessed

        if self.remaining_spaces == 0:
            self._won_game(player)
            return True

        self.view.display(
            f"Well done! The letter '{raw_letter}' appears {times_guessed} time"
            f"{'s' if times_guessed > 1 else ''} in the word.\n"
        )
        self.view.show_word(self.unknown_word)

        while True:
            want_word = self.view.prompt("Do you want to guess the word? (Y/N): ").strip().upper()
            if want_word not in ("Y", "N"):
                self.view.display("Invalid input. Please choose Y or N.\n")
                continue
            break

        if want_word == "Y":
            return self._guess_word(player)

        self.view.pause()
        return False

    def _guess_word(self, player: Player) -> bool:
        guess = self._normalize_word(self.view.prompt("Please insert the word: ").strip().upper())

        if not all(ch.isalpha() or ch in {" ", "-"} for ch in guess):
            self.view.display("Invalid input. Only letters, spaces, or hyphens allowed.\n")
            return False

        self.view.clear()
        if guess != self.word:
            self.view.display(f"Sorry, '{guess}' is not the correct word.\n")
            eliminated = player.lose_health(self.view)
            if eliminated:
                self.remaining_players -= 1
                self.view.display(f"{player.name} has been eliminated.\n")

            self.view.show_word(self.unknown_word)
            self.view.pause()
            return self._game_over()

        self.unknown_word = list(self.word)
        self._won_game(player)
        return True

    # ------------------------------------------------------------------
    # Display and Game End Logic
    # ------------------------------------------------------------------

    def _exit_game(self):
        self.view.pause("Press Enter to exit...")

    def _won_game(self, player: Player):
        self.view.clear()
        self.view.display(f"Congratulations, {player.name}! You won!\n")
        player.show_health(self.view)
        self.view.show_word(self.unknown_word)

    def _game_over(self) -> bool:
        if self.remaining_players <= 0:
            self.view.clear()
            self.view.display("All players have been eliminated. Game over.\n")
            return True
        return False