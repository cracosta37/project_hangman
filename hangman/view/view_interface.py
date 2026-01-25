from typing import List


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