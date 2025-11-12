from hangman.classes import Game, ConsoleView
from hangman import constants


def run():
    view = ConsoleView()

    # Ask user whether to enable accent normalization
    while True:
        response = input("Enable accent normalization (Y/N)? ").strip().upper()
        if response in ("Y", "N"):
            normalize_input = response == "Y"
            break
        print("Invalid input. Please enter Y or N.\n")

    # Initialize the game with user-selected normalization
    game = Game(constants_module=constants, view=view, normalize_input=normalize_input)
    game.play_game()


if __name__ == "__main__":
    run()