from hangman.model.game import Game
from hangman.view.console_view import ConsoleView
from hangman.services.word_repository import WordRepository

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class GameController:
    """
    Controller that orchestrates the interaction between the pure Game model
    and the View. All I/O is performed via the View; the Game never handles input.
    """

    def __init__(self, view: ConsoleView, constants_module):
        self.view = view
        self.c = constants_module
        self.game = None

        self.word_repo = WordRepository(BASE_DIR / "data" / "word_bank.json")
    
    # ==============================
    # CONFIGURATION
    # ==============================

    def choose_normalization(self) -> bool:
        while True:
            response = self.view.prompt("Enable accent normalization (Y/N)? ").strip().upper()
            if response in ("Y", "N"):
                return response == "Y"
            self.view.display("Invalid input. Please enter Y or N.\n")
    
    def choose_word_source(self) -> str:
        while True:
            choice = self.view.prompt(
                "Select word source: 1 = manual (moderator), 2 = automatic (by difficulty): "
            ).strip()
            if choice in ("1", "2"):
                return choice
            self.view.display("Invalid input. Please enter 1 or 2.\n")
    
    def choose_difficulty(self) -> str:
        while True:
            diff = self.view.prompt(
                "Select difficulty: EASY, MEDIUM, HARD: "
            ).strip().upper()
            if diff in ("EASY", "MEDIUM", "HARD"):
                return diff
            self.view.display("Invalid difficulty. Choose EASY, MEDIUM, or HARD.\n")
    
    def choose_reset_session(self) -> bool:
        while True:
            choice = self.view.prompt(
                "Reset word history for the new game? (Y/N): "
            ).strip().upper()
            if choice in ("Y", "N"):
                return choice == "Y"
            self.view.display("Invalid input. Please choose Y or N.\n")
    
    def _is_exhaustion_error(self, error: ValueError) -> bool:
        return "No unused words remaining" in str(error)
    
    # ==============================
    # SETUP
    # ==============================

    def setup_game(self):
        self.view.clear()
        self.view.show_title()     
        normalize = self.choose_normalization()
        self.game = Game(constants_module=self.c, normalize_input=normalize)

        # Word setup (manual or automatic)
        source = self.choose_word_source()

        if source == "1":
            # Manual (current behavior)
            while True:
                raw_word = self.view.prompt_hidden("Please insert the word or phrase: ")
                result = self.game.set_word(raw_word)
                if result.get("ok"):
                    break
                self.view.display(result.get("error", "Invalid word or phrase.") + "\n")

        else:
            # Automatic (by difficulty)
            difficulty = self.choose_difficulty()

            while True:
                try:
                    selected = self.word_repo.get_by_difficulty(difficulty)
                except ValueError as e:
                    self.view.display(str(e) + "\n")
                    difficulty = self.choose_difficulty()
                    continue

                result = self.game.set_word(selected)
                if result.get("ok"):
                    break

            self.view.display("A word or phrase has been selected automatically.\n")

        # Players setup
        while True:
            n_raw = self.view.prompt("Please insert the number of players: ")
            try:
                n = int(n_raw)
                if n <= 0:
                    self.view.display("The number of players must be positive.\n")
                    continue
            except ValueError:
                self.view.display("Invalid input. Please enter an integer.\n")
                continue

            names = []
            for i in range(1, n + 1):
                while True:
                    name = self.view.prompt(f"Please insert the name of player {i}: ").strip().title()
                    if not name:
                        self.view.display("Name cannot be empty.\n")
                        continue
                    if any(existing.lower() == name.lower() for existing in names):
                        self.view.display("That name is already taken. Please choose another name.\n")
                        continue
                    names.append(name)
                    break

            res = self.game.create_players(names)
            if res.get("ok"):
                break
            self.view.display(res.get("error", "Invalid player configuration.") + "\n")

    # ======================================================================
    # GAME LOOP
    # ======================================================================

    def run_game_loop(self):
        self.view.clear()
        i = 0
        winner_player = None

        while not self.game.is_game_over() and self.game.remaining_players > 0:
            player_index = i % self.game.n_players
            player = self.game.get_player(player_index)

            # Skip eliminated players (non-recoverable)
            if not player.is_alive():
                i += 1
                continue

            self.view.clear()
            self.view.display(f"Turn of {player.name}.\n")
            self.view.show_health(player)
            self.view.show_word(self.game.get_visible_word())

            # Guess type selection
            while True:
                try:
                    label = self.game.word_label()
                    insert_type = int(self.view.prompt(f"Guess type: 1 for letter, 2 for {label}: "))
                    if insert_type not in (1, 2):
                        self.view.display("Invalid input. Please enter 1 or 2.\n")
                        continue
                    break
                except ValueError:
                    self.view.display("Invalid input. Please enter 1 or 2.\n")

            # Call guess handler
            if insert_type == 1:
                result = self.handle_letter_guess(player_index)
            else:
                result = self.handle_word_guess(player_index)

            # Store winner reported by model
            if isinstance(result, dict):
                if result.get("game_won") and result.get("winner") is not None:
                    winner_index = result["winner"]
                    winner_player = self.game.get_player(winner_index)
            
            # Offer full-word guess (only if letter guess was correct and game is not already won)
            if  insert_type == 1 and result.get("correct") and not result.get("game_won"):
                while True:
                    label = self.game.word_label()
                    choice = self.view.prompt(f"Do you want to guess the {label}? (Y/N): ").strip().upper()
                    if choice not in ("Y", "N"):
                        self.view.display("Invalid input. Please choose Y or N.\n")
                        continue
                    break
            
                if choice == "Y":
                    result = self.handle_word_guess(player_index)

                    if isinstance(result, dict):
                        if result.get("game_won") and result.get("winner") is not None:
                            winner_index = result["winner"]
                            winner_player = self.game.get_player(winner_index)

            i += 1

        # ==================================================================
        # FINAL OUTCOME DISPLAY
        # ==================================================================

        if winner_player is not None:
            self.view.clear()
            self.view.display(f"Congratulations, {winner_player.name}! You won!\n")
            self.view.show_health(winner_player)
            self.view.show_word(self.game.get_visible_word())

        elif self.game.remaining_spaces == 0:
            # Rare fallback
            label = self.game.word_label()
            self.view.display(f"Game finished. The {label} was:\n")
            self.view.show_word(self.game.get_visible_word())

        else:
            self.view.display("All players have been eliminated. Game over.\n")

        self.view.pause("Press Enter to continue...")

    # ======================================================================
    # LETTER HANDLER
    # ======================================================================

    def handle_letter_guess(self, player_index: int):
        # Input + validation loop (Model handles all validation)
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
                self.view.display(result.get("error", "Invalid operation.") + "\n")
                continue

            # Valid input
            break

        # Normalize only for display
        letter_out = raw_letter.strip().upper()

        # Retrieve player **once**
        player = self.game.get_player(player_index)

        self.view.clear()

        # Incorrect guess
        if not result.get("correct"):
            label = self.game.word_label()
            self.view.display(f"Sorry, the letter '{letter_out}' is not in the {label}.\n")
            self.view.show_health(player)
            self.view.show_word(self.game.get_visible_word())

            if result.get("eliminated"):
                self.view.display(f"{player.name} has been eliminated.\n")

            self.view.pause()
            return result

        # Correct guess
        times = result.get("times", 0)
        label = self.game.word_label()
        self.view.display(
            f"Well done! The letter '{letter_out}' appears {times} time"
            f"{'s' if times > 1 else ''} in the {label}.\n"
        )
        self.view.show_health(player)
        self.view.show_word(self.game.get_visible_word())
       
        return result

    # ======================================================================
    # FULL-WORD HANDLER
    # ======================================================================

    def handle_word_guess(self, player_index: int):
        # Input + validation loop
        while True:
            label = self.game.word_label()
            raw_guess = self.view.prompt(f"Please insert the {label}: ")

            # Delegate validation and logic to the Model
            result = self.game.guess_word(player_index, raw_guess)

            # Non-recoverable error → exit handler
            if not result.get("ok") and not result.get("repeat"):
                self.view.display(result.get("error", "Invalid operation.") + "\n")
                self.view.pause()
                return result

            # Recoverable error → retry input
            if result.get("repeat"):
                self.view.display(result.get("error", "Invalid operation.") + "\n")
                continue

            # Valid attempt → exit loop
            break

        # Normalize only for display output
        guess_out = raw_guess.strip().upper()

        # Retrieve the player exactly once
        player = self.game.get_player(player_index)

        self.view.clear()

        # Incorrect guess
        if not result.get("correct"):
            label = self.game.word_label()
            self.view.display(f"Sorry, '{guess_out}' is not the correct {label}.\n")
            self.view.show_health(player)
            self.view.show_word(self.game.get_visible_word())

            if result.get("eliminated"):
                self.view.display(f"{player.name} has been eliminated.\n")

            self.view.pause()
            return result

        # Correct guess
        self.view.clear()
        label = self.game.word_label()
        self.view.display(f"Well done! The {label} '{guess_out}' is the correct {label}.\n")
        self.view.show_health(player)
        self.view.show_word(self.game.get_visible_word())

        self.view.pause()

        return result


    # ======================================================================
    # APPLICATION LIFECYCLE
    # ======================================================================

    def start(self):
        # Full setup including player names
        self.setup_game()

        while True:
            self.run_game_loop()
            self.view.clear()
            self.view.show_title()

            # Ask if the user wants another round
            while True:
                choice = self.view.prompt("Start a new game with the same players? (Y/N): ").strip().upper()
                if choice in ("Y", "N"):
                    break
                self.view.display("Invalid input. Please choose Y or N.\n")

            if choice == "N":
                return self.exit_game()

            # Optionally reset word session cache (NO-REPEAT MODE)
            reset_words = self.choose_reset_session()
            if reset_words:
                self.word_repo.reset_session()
            
            # Reset game with a new word (ask again for source)
            source = self.choose_word_source()

            if source == "1":
                while True:
                    raw_word = self.view.prompt_hidden("Please insert the new word or phrase: ")
                    result = self.game.reset_for_new_round(raw_word)
                    if result.get("ok"):
                        break
                    self.view.display(result.get("error", "Invalid word or phrase.") + "\n")
            else:
                difficulty = self.choose_difficulty()

                while True:
                    try:
                        selected = self.word_repo.get_by_difficulty(difficulty)

                    except ValueError as e:
                        if self._is_exhaustion_error(e):
                            self.view.display(
                                f"{e}\n"
                                "Recovery options:\n"
                                "1) Reset word history for this session\n"
                                "2) Choose a different difficulty\n"
                                "3) Exit game\n"
                            )

                            choice = self.view.get_choice(["1", "2", "3"])

                            if choice == "1":
                                self.word_repo.reset_session()
                                continue

                            if choice == "2":
                                difficulty = self.choose_difficulty()
                                continue

                            # choice == "3"
                            return self.exit_game() # Exit game entirely (leave start())

                        else:
                            # Non-exhaustion error (e.g., invalid difficulty)
                            self.view.display(str(e) + "\n")
                            difficulty = self.choose_difficulty()
                            continue

                    # Successful selection
                    result = self.game.reset_for_new_round(selected)
                    if result.get("ok"):
                        break
    
    def exit_game(self) -> None:
        self.view.pause("Press Enter to exit...")
        self.view.clear()