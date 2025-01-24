import hangman.constants as c
import string
import getpass
import os

#
class Player:
    MAX_HEALTH = c.MAX_HEALTH

    def __init__(self, name):
        self.name = name
        self.health = Player.MAX_HEALTH

    def lose_health(self):
        self.health -= 1        
        self.show_health()

    def show_health(self):
        print(c.HANGMAN[self.health])
        print()

class Game:
    def __init__(self):
        self.n_players = 0
        self.remaining_players = 0
        self.players = []
        self.word = ""
        self.word_length = 0
        self.unknown_word = ""
        self.remaining_spaces = 0
        self.remaining_letters = list(string.ascii_uppercase)

    def play_game(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        self.create_word()
        self.create_players()

        end = False
        i = 0
        while not end:            
            turn = i % self.n_players

            if self.players[turn].health == 0:
                i += 1
                continue
            
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"Turn of {self.players[turn].name}.\n")

            end = self.play_turn(self.players[turn], turn)
            
            i += 1        
        
        self.exit_game()

    def play_turn(self, player: Player, turn):
        player.show_health()
        self.show_unknown_word()

        while True:
            try:
                insert_type = int(input("What are you going to guess? Plese type 1 for letter, 2 for word: "))
                print()
                if insert_type != 1 and insert_type != 2:
                    print("Invalid imput.\n")
                else:
                    break
            except ValueError:
                print()
                print("Invalid imput.\n")

        if insert_type == 1:
            return self.guess_letter(self.players[turn])
        else:
            return self.guess_word(self.players[turn])

    def create_word(self):
        print()
        word = getpass.getpass(prompt="Please insert the word: ").upper()
        print()
        self.word = word
        self.word_length = len(word)
        self.unknown_word = "_ " * (self.word_length - 1) + "_"
        self.remaining_spaces = self.word_length

    def create_players(self):
        while True:
            try:
                self.n_players = int(input("Please insert the number of players: "))
                print()
                if self.n_players <= 0:
                    print("The number of players must be a positive integer.\n")
                else:
                    break
            except ValueError:
                print()
                print("That's not a valid number of players.\n")

        self.remaining_players = self.n_players

        for i in range(1, self.n_players + 1):
            name = input(f"Please insert the name of the player {i}: ").title()
            print()
            self.players.append(Player(name))

    def guess_letter(self, player: Player):
        letter = input("Please insert a letter: ").upper()
        print()
        while letter not in self.remaining_letters:
            letter = input(f"{letter} was already used or is an invalid input. Please insert another one: ").upper()
            print()

        index = self.remaining_letters.index(letter)
        self.remaining_letters[index] = ""

        positions = [i for i, l in enumerate(self.word) if l == letter]
        times_guessed = len(positions)
        if times_guessed == 0:
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"Sorry. The letter {letter} in not in the word.\n")
            
            player.lose_health()
            self.show_unknown_word()

            if player.health == 0:
                self.lose_game()

            self.stop_screen()

            return self.game_over(player)

        else:
            os.system('cls' if os.name == 'nt' else 'clear')
            
            if times_guessed == 1:
                print(f"Well done! The letter {letter} appears 1 time in the word.\n")
            else:
                print(f"Well done! The letter {letter} appears {times_guessed} times in the word.\n")

        for pos in positions:
            self.unknown_word = self.unknown_word[:2*pos] + letter + self.unknown_word[2*pos+1:]

        self.remaining_spaces -= times_guessed

        if self.remaining_spaces == 0:
            os.system('cls' if os.name == 'nt' else 'clear')
            
            self.won_game()
            player.show_health()
            self.show_unknown_word()
            
            return True

        player.show_health()
        self.show_unknown_word()

        want_word = input("Do you want to guess the word? Y or N: ").upper()
        print()
        while want_word not in ["Y", "N"]:
            want_word = input("Invalid input. Please choose Y or N: ")
            print()

        if want_word == "Y":
            return self.guess_word(player)
        
        self.stop_screen()

        return False

    def guess_word(self, player: Player):
        word = input("Please insert the word: ").upper()
        print()

        if word != self.word:
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"Sorry. The word {word} is not the right word.\n")
            
            player.lose_health()
            self.show_unknown_word()

            if player.health == 0:
                self.lose_game()

            self.stop_screen()

            return self.game_over(player)

        self.unknown_word = " ".join(self.word)
                
        self.won_game()
        player.show_health()
        self.show_unknown_word()

        return True

    def show_unknown_word(self):
        print(f"    {self.unknown_word}\n")

    def stop_screen(self):
        input("Please, press Enter to continue...")

    def exit_game(self):
        input("Please, press Enter to exit...")        
    
    def won_game(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        print("Congratulatios! You won.\n")

    def lose_game(self):
        print("You lose.\n")
        print()

    def game_over(self, player: Player):
        if player.health == 0:
            self.remaining_players -= 1

        if self.remaining_players == 0:
                os.system('cls' if os.name == 'nt' else 'clear')
                print("Game over.\n")
                return True
        return False
