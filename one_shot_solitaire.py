import os
import sys

from engine import Card, OnePassSolitaire, SUITS, VALUES, COLORS


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def display_game(game):
    clear_screen()

    print(f"Stock: {len(game.stock)} cards remaining\n")

    print("Storage:", end=" ")
    for i, card in enumerate(game.storage):
        if card:
            print(f"{i+1}:{card}", end=" ")
        else:
            print(f"{i+1}:___", end=" ")
    print("\n")

    print("Foundations:", end=" ")
    for i, pile in enumerate(game.foundations):
        if not pile:
            print(f"{SUITS[i]}:___", end=" ")
        else:
            print(f"{SUITS[i]}:{pile[-1].value}", end=" ")
    print("\n")

    print("Tableau:")
    max_height = max(len(pile) for pile in game.tableau)
    for row in range(max_height):
        for col in range(7):
            if row < len(game.tableau[col]):
                print(f"{game.tableau[col][row]}", end="\t")
            else:
                print(" ", end="\t")
        print()

    print("\n", end="")
    for i in range(7):
        print(f"{i+1}", end="\t")
    print("\n")

    if game.waste:
        print(f"Current card: {game.waste[-1]}")
    else:
        print("Current card: None")


def get_user_move():
    while True:
        try:
            print("\nCommands:")
            print("d - Draw card from stock")
            print("f - Move card to foundation")
            print("t <col> - Move card to tableau column")
            print("s <space> - Move card to storage space")
            print("m <source> <destination> - Move from tableau/storage")
            print("q - Quit game")
            print("r - Reset game")
            print("h - Help")

            command = input("\nEnter command: ").lower().strip()

            if command == 'q':
                return 'quit'
            elif command == 'r':
                return 'reset'
            elif command == 'd':
                return 'draw'
            elif command == 'f':
                return 'foundation'
            elif command == 'h':
                return 'help'
            elif command.startswith('t '):
                try:
                    col = int(command.split()[1]) - 1
                    if 0 <= col < 7:
                        return ('tableau', col)
                    else:
                        print("Invalid column number (1-7)")
                except (ValueError, IndexError):
                    print("Invalid command format. Use 't <column number>'")
            elif command.startswith('s '):
                try:
                    space = int(command.split()[1]) - 1
                    if 0 <= space < 4:
                        return ('storage', space)
                    else:
                        print("Invalid storage space (1-4)")
                except (ValueError, IndexError):
                    print("Invalid command format. Use 's <space number>'")
            elif command.startswith('m '):
                parts = command.split()
                if len(parts) == 3:
                    source = parts[1]
                    destination = parts[2]

                    # Process source
                    if source.startswith('t'):
                        try:
                            src = ('tableau', int(source[1:]) - 1)
                            if not (0 <= src[1] < 7):
                                print("Invalid source column (1-7)")
                                continue
                        except ValueError:
                            print("Invalid source format. Use 't<number>'")
                            continue
                    elif source.startswith('s'):
                        try:
                            src = ('storage', int(source[1:]) - 1)
                            if not (0 <= src[1] < 4):
                                print("Invalid storage space (1-4)")
                                continue
                        except ValueError:
                            print("Invalid source format. Use 's<number>'")
                            continue
                    else:
                        print("Invalid source. Use 't<number>' or 's<number>'")
                        continue

                    # Process destination
                    if destination.startswith('t'):
                        try:
                            dest = ('tableau', int(destination[1:]) - 1)
                            if not (0 <= dest[1] < 7):
                                print("Invalid destination column (1-7)")
                                continue
                        except ValueError:
                            print("Invalid destination format. Use 't<number>'")
                            continue
                    elif destination.startswith('s'):
                        try:
                            dest = ('storage', int(destination[1:]) - 1)
                            if not (0 <= dest[1] < 4):
                                print("Invalid storage space (1-4)")
                                continue
                        except ValueError:
                            print("Invalid destination format. Use 's<number>'")
                            continue
                    elif destination.startswith('f'):
                        suit_idx = -1
                        if len(destination) > 1:
                            try:
                                suit_idx = int(destination[1:]) - 1
                            except ValueError:
                                pass
                        dest = ('foundation', suit_idx)
                    else:
                        print("Invalid destination. Use 't<number>', 's<number>', or 'f'")
                        continue

                    return ('move', src, dest)
                else:
                    print("Invalid move format. Use 'm <source> <destination>'")
            else:
                print("Invalid command")
        except Exception as e:
            print(f"Error: {e}")


def show_help():
    clear_screen()
    print("=== ONE-PASS SOLITAIRE HELP ===\n")
    print("GOAL: Move all cards to the foundation piles, arranged by suit from Ace to King.\n")
    print("COMMANDS:")
    print("  d - Draw a card from the stock pile (only one pass through the deck)")
    print("  f - Move the current card to a foundation pile (if legal)")
    print("  t <col> - Move the current card to tableau column <col> (1-7)")
    print("  s <space> - Move the current card to storage space <space> (1-4)")
    print("  m <source> <destination> - Move a card from one place to another")
    print("    Sources: t1-t7 (tableau columns 1-7), s1-s4 (storage spaces 1-4)")
    print("    Destinations: t1-t7, s1-s4, f (foundation)")
    print("  r - Reset the game")
    print("  q - Quit the game")
    print("  h - Show this help screen\n")
    print("RULES:")
    print("  - Tableau: Build down with alternating colors (red/black)")
    print("  - Foundations: Build up by suit (starting with Ace)")
    print("  - Only Kings can be placed on empty tableau columns")
    print("  - Storage spaces can hold any single card")
    print("  - You can only go through the stock pile once")


def play(seed=None):
    game = OnePassSolitaire(seed=seed)
    game.auto_move_to_foundation()

    while True:
        display_game(game)

        if game.is_game_won():
            print("\nCongratulations! You've won the game!")
            input("Press Enter to start a new game...")
            game.reset_game()
            continue

        if game.is_game_over():
            print("\nGame over! No more legal moves available.")
            input("Press Enter to start a new game...")
            game.reset_game()
            continue

        move = get_user_move()

        if move == 'quit':
            sys.exit(0)
        elif move == 'reset':
            game.reset_game()
            continue
        elif move == 'help':
            show_help()
            input("Press Enter to continue...")
            continue

        success, err = game.step(move)
        if not success:
            print(f"\n{err}")
            input("Press Enter to continue...")


if __name__ == "__main__":
    play()
