import json
import random
from pathlib import Path
from typing import Dict, List, Set


class WordRepository:
    """
    Responsible ONLY for loading and serving words.
    No game logic, no I/O with the user, no view dependencies.
    """

    def __init__(self, file_path: str):
        self.file_path = Path(file_path).resolve()
        self.words: Dict[str, List[str]] = {}
        self.used_words: Set[str] = set()

        self._load()

    def _load(self) -> None:
        if not self.file_path.exists():
            raise FileNotFoundError(f"Word bank not found: {self.file_path}")

        with open(self.file_path, "r", encoding="utf-8") as f:
            self.words = json.load(f)

    def get_by_difficulty(self, difficulty: str) -> str:
        difficulty = difficulty.strip().upper()

        if difficulty not in self.words:
            raise ValueError(f"Invalid difficulty level: {difficulty}")

        available = list(
            set(self.words[difficulty]) - self.used_words
        )

        if not available:
            raise ValueError(
                f"No more unused words remaining for difficulty: {difficulty}"
            )

        word = random.choice(available)
        self.used_words.add(word)

        return word

    def reset_session(self) -> None:
        """Clears session word history (used words)."""
        self.used_words.clear()