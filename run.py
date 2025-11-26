from hangman.view.console_view import ConsoleView
from hangman.controller.game_controller import GameController
from hangman import constants


def run():
        view = ConsoleView()
        controller = GameController(view=view, constants_module=constants)
        controller.start()


if __name__ == "__main__":
    run()