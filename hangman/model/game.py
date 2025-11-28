import string
import unicodedata
from typing import List, Dict, Any, Optional

from .player import Player


class Game:
    """Pure game model: contains all rules and state but performs no I/O."""

    def __init__(self, constants_module, normalize_input: bool = True):
        self.c = constants_module
        self.normalize_input = normalize_input

        self.players: List[Player] = []
        self.word: str = ""
        self.unknown_word: List[str] = []
        self.remaining_letters: set[str] = set()
        self.remaining_players: int = 0
        self.n_players: int = 0
        self.remaining_spaces: int = 0

        if self.normalize_input:
            base_letters = string.ascii_uppercase
        else:
            base_letters = string.ascii_uppercase + "ÑÁÉÍÓÚÜÇ"
        self.remaining_letters = set(base_letters)

    # ---------------------------
    # Normalization
    # ---------------------------

    def _normalize(self, text: str) -> str:
        text = text or ""
        if not self.normalize_input:
            return text.upper()
        normalized = unicodedata.normalize("NFD", text)
        filtered = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        return filtered.upper()

    # ---------------------------
    # Word setup
    # ---------------------------

    def set_word(self, raw_word: str) -> Dict[str, Any]:
        if raw_word is None:
            return {"ok": False, "error": "No word provided."}

        word = raw_word.strip()
        if len(word) == 0:
            return {"ok": False, "error": "The word cannot be empty."}

        letters_only = [ch for ch in word if ch.isalpha()]
        if len(letters_only) < 2:
            return {"ok": False, "error": "The word must contain at least two letters."}

        if not all(ch.isalpha() or ch in {" ", "-"} for ch in word):
            return {"ok": False, "error": "The word can only contain letters, spaces, or hyphens."}

        normalized = self._normalize(word)
        self.word = normalized
        self.unknown_word = ["_" if ch.isalpha() else ch for ch in normalized]
        self.remaining_spaces = sum(ch == "_" for ch in self.unknown_word)
        return {"ok": True}
    
    # ---------------------------
    # Round reset
    # ---------------------------

    def reset_for_new_round(self, new_word: str) -> dict:
        """
        Reset all game state except the existing players.
        Players keep their names; their health is restored.
        """
        # Normalize letters depending on the original setting
        if self.normalize_input:
            base_letters = string.ascii_uppercase
        else:
            base_letters = string.ascii_uppercase + "ÑÁÉÍÓÚÜÇ"

        # Reset remaining letters
        self.remaining_letters = set(base_letters)

        # Reset the chosen word
        result = self.set_word(new_word)
        if not result.get("ok"):
            return result

        # Reset each player's health
        for p in self.players:
            p.health = p.max_health

        # Reset counters dependent on players
        self.remaining_players = self.n_players

        return {"ok": True}

    # ---------------------------
    # Players
    # ---------------------------

    def create_players(self, names: List[str]) -> Dict[str, Any]:
        if not isinstance(names, list) or len(names) == 0:
            return {"ok": False, "error": "Players list must be non-empty."}

        cleaned = []
        for name in names:
            if not isinstance(name, str) or not name.strip():
                return {"ok": False, "error": "Player names must be non-empty strings."}
            cleaned.append(name.strip().title())

        lowered = [n.lower() for n in cleaned]
        if len(set(lowered)) != len(lowered):
            return {"ok": False, "error": "Player names must be unique (case-insensitive)."}

        self.players = [Player(n, self.c.MAX_HEALTH, self.c.HANGMAN) for n in cleaned]
        self.n_players = len(self.players)
        self.remaining_players = self.n_players
        return {"ok": True}

    # ---------------------------
    # Letter guess (with repeat state)
    # ---------------------------

    def guess_letter(self, player_index: int, raw_letter: str) -> Dict[str, Any]:
        if player_index < 0 or player_index >= len(self.players):
            return {"ok": False, "repeat": False, "error": "Invalid player index."}

        player = self.players[player_index]
        if not player.is_alive():
            return {"ok": False, "repeat": False, "error": "Player has been eliminated."}

        # invalid raw input
        if not raw_letter or len(raw_letter.strip()) != 1 or not raw_letter.strip().isalpha():
            return {
                "ok": False,
                "repeat": True,
                "error": "Please provide a single alphabetic letter."
            }

        letter = self._normalize(raw_letter.strip().upper())

        # repeated letter
        if letter not in self.remaining_letters:
            return {
                "ok": False,
                "repeat": True,
                "error": f"The letter '{raw_letter}' was already used."
            }

        # consume letter
        self.remaining_letters.remove(letter)
        positions = [i for i, l in enumerate(self.word) if l == letter]
        times = len(positions)

        # incorrect guess
        if times == 0:
            eliminated = player.lose_health()
            if eliminated:
                self.remaining_players -= 1
            return {
                "ok": True,
                "repeat": False,
                "correct": False,
                "positions": [],
                "eliminated": eliminated,
                "player_health": player.health,
                "game_won": False,
                "game_over": self.remaining_players <= 0,
                "winner": None
            }

        # correct guess
        for pos in positions:
            self.unknown_word[pos] = letter
        self.remaining_spaces -= times

        game_won = self.remaining_spaces == 0
        winner = player_index if game_won else None

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

    # ---------------------------
    # Full-word guess
    # ---------------------------

    def guess_word(self, player_index: int, raw_guess: str) -> Dict[str, Any]:
        if player_index < 0 or player_index >= len(self.players):
            return {"ok": False, "repeat": False, "error": "Invalid player index."}

        player = self.players[player_index]
        if not player.is_alive():
            return {"ok": False, "repeat": False, "error": "Player has been eliminated."}

        if not raw_guess or not isinstance(raw_guess, str):
            return {"ok": False, "repeat": True, "error": "Invalid guess."}

        guess = self._normalize(raw_guess.strip().upper())
        if not all(ch.isalpha() or ch in {" ", "-"} for ch in guess):
            return {"ok": False, "repeat": True, "error": "Invalid input. Only letters allowed."}

        if guess != self.word:
            eliminated = player.lose_health()
            if eliminated:
                self.remaining_players -= 1
            return {
                "ok": True,
                "repeat": False,
                "correct": False,
                "eliminated": eliminated,
                "player_health": player.health,
                "game_won": False,
                "game_over": self.remaining_players <= 0,
                "winner": None
            }

        # correct word
        self.unknown_word = list(self.word)
        self.remaining_spaces = 0

        return {
            "ok": True,
            "repeat": False,
            "correct": True,
            "eliminated": False,
            "player_health": player.health,
            "game_won": True,
            "game_over": self.remaining_players <= 0,
            "winner": player_index
        }

    # ---------------------------
    # Helpers
    # ---------------------------

    def is_game_over(self) -> bool:
        return self.remaining_players <= 0 or self.remaining_spaces == 0

    def get_visible_word(self) -> List[str]:
        return list(self.unknown_word)

    def get_player(self, index: int) -> Optional[Player]:
        if 0 <= index < len(self.players):
            return self.players[index]
        return None

    def get_remaining_letters(self) -> set:
        return set(self.remaining_letters)