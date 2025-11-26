from typing import List


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