import os
import getpass
from typing import List

from .view_interface import View


class ConsoleView(View):
    """Handles all console-based input and output operations."""

    def __init__(self, use_clear: bool = True):
        self.use_clear = use_clear

    def clear(self) -> None:
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

    def show_word(self, word_state: List[str]) -> None:
        print(f"    {' '.join(word_state)}\n")

    def show_health(self, player) -> None:
        print(player.hangman_states[player.health])
        print()