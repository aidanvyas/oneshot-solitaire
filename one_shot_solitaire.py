"""Command-line interface for One-Pass Solitaire."""

from __future__ import annotations

import contextlib
import subprocess
import sys

from rich.console import Console

from engine import NUM_STORAGE_SLOTS, NUM_TABLEAU_COLS, SUITS, OnePassSolitaire

console = Console()

MIN_CMD_PARTS = 2
MOVE_CMD_PARTS = 3


def clear_screen() -> None:
    """Clear the terminal screen."""
    subprocess.run(  # noqa: S603
        "cls" if sys.platform == "win32" else "clear",
        shell=False,
        check=False,
    )


def _display_storage(game: OnePassSolitaire) -> None:
    """Print the storage area."""
    console.print("Storage:", end=" ")
    for i, card in enumerate(game.storage):
        label = f"{i + 1}:{card}" if card else f"{i + 1}:___"
        console.print(label, end=" ")
    console.print("\n")


def _display_foundations(game: OnePassSolitaire) -> None:
    """Print the foundation piles."""
    console.print("Foundations:", end=" ")
    for i, pile in enumerate(game.foundations):
        label = f"{SUITS[i]}:{pile[-1].value}" if pile else f"{SUITS[i]}:___"
        console.print(label, end=" ")
    console.print("\n")


def _display_tableau(game: OnePassSolitaire) -> None:
    """Print the tableau columns."""
    console.print("Tableau:")
    max_height = max(len(pile) for pile in game.tableau)
    for row in range(max_height):
        for col in range(NUM_TABLEAU_COLS):
            if row < len(game.tableau[col]):
                console.print(f"{game.tableau[col][row]}", end="\t")
            else:
                console.print(" ", end="\t")
        console.print()
    console.print("", end="")
    for i in range(NUM_TABLEAU_COLS):
        console.print(f"{i + 1}", end="\t")
    console.print("\n")


def display_game(game: OnePassSolitaire) -> None:
    """Display the current game state in the terminal."""
    clear_screen()
    console.print(f"Stock: {len(game.stock)} cards remaining\n")
    _display_storage(game)
    _display_foundations(game)
    _display_tableau(game)
    waste_label = f"{game.waste[-1]}" if game.waste else "None"
    console.print(f"Current card: {waste_label}")


def _print_commands() -> None:
    """Print the available command list."""
    console.print("\nCommands:")
    console.print("d - Draw card from stock")
    console.print("f - Move card to foundation")
    console.print("t <col> - Move card to tableau column")
    console.print("s <space> - Move card to storage space")
    console.print("m <source> <destination> - Move from tableau/storage")
    console.print("q - Quit game")
    console.print("r - Reset game")
    console.print("h - Help")


def _parse_tableau_cmd(command: str) -> tuple[str, int] | None:
    """Parse a 't <col>' command, returning the move or None."""
    parts = command.split()
    if len(parts) < MIN_CMD_PARTS:
        console.print("Invalid command format. Use 't <column number>'")
        return None
    try:
        col = int(parts[1]) - 1
    except ValueError:
        console.print("Invalid command format. Use 't <column number>'")
        return None
    if 0 <= col < NUM_TABLEAU_COLS:
        return ("tableau", col)
    console.print("Invalid column number (1-7)")
    return None


def _parse_storage_cmd(command: str) -> tuple[str, int] | None:
    """Parse an 's <space>' command, returning the move or None."""
    parts = command.split()
    if len(parts) < MIN_CMD_PARTS:
        console.print("Invalid command format. Use 's <space number>'")
        return None
    try:
        space = int(parts[1]) - 1
    except ValueError:
        console.print("Invalid command format. Use 's <space number>'")
        return None
    if 0 <= space < NUM_STORAGE_SLOTS:
        return ("storage", space)
    console.print("Invalid storage space (1-4)")
    return None


def _parse_move_source(source: str) -> tuple[str, int] | None:
    """Parse a move source token like 't1' or 's2'."""
    if source.startswith("t"):
        try:
            src = ("tableau", int(source[1:]) - 1)
            if 0 <= src[1] < NUM_TABLEAU_COLS:
                return src
        except ValueError:
            pass
    elif source.startswith("s"):
        try:
            src = ("storage", int(source[1:]) - 1)
            if 0 <= src[1] < NUM_STORAGE_SLOTS:
                return src
        except ValueError:
            pass
    return None


def _parse_move_dest(destination: str) -> tuple[str, int] | None:
    """Parse a move destination token like 't3', 's1', or 'f'."""
    if destination.startswith("t"):
        try:
            dest = ("tableau", int(destination[1:]) - 1)
            if 0 <= dest[1] < NUM_TABLEAU_COLS:
                return dest
        except ValueError:
            pass
    elif destination.startswith("s"):
        try:
            dest = ("storage", int(destination[1:]) - 1)
            if 0 <= dest[1] < NUM_STORAGE_SLOTS:
                return dest
        except ValueError:
            pass
    elif destination.startswith("f"):
        suit_idx = -1
        if len(destination) > 1:
            with contextlib.suppress(ValueError):
                suit_idx = int(destination[1:]) - 1
        return ("foundation", suit_idx)
    return None


def _parse_move_cmd(command: str) -> tuple | None:
    """Parse an 'm <src> <dest>' compound move command."""
    parts = command.split()
    if len(parts) != MOVE_CMD_PARTS:
        return None
    src = _parse_move_source(parts[1])
    if src is None:
        return None
    dest = _parse_move_dest(parts[2])
    if dest is None:
        return None
    return ("move", src, dest)


_SIMPLE_COMMANDS = {
    "q": "quit",
    "r": "reset",
    "d": "draw",
    "f": "foundation",
    "h": "help",
}


def _try_parse_command(command: str) -> str | tuple | None:
    """Parse a single command string into a move, or None if invalid."""
    if command in _SIMPLE_COMMANDS:
        return _SIMPLE_COMMANDS[command]
    if command.startswith("t "):
        return _parse_tableau_cmd(command)
    if command.startswith("s "):
        return _parse_storage_cmd(command)
    if command.startswith("m "):
        return _parse_move_cmd(command)
    console.print("Invalid command")
    return None


def get_user_move() -> str | tuple:
    """Prompt the user for a move command and return the parsed move."""
    while True:
        try:
            _print_commands()
            command = input("\nEnter command: ").lower().strip()
            result = _try_parse_command(command)
            if result is not None:
                return result
        except EOFError:
            console.print("Error processing input")


def show_help() -> None:
    """Display the help screen with all game rules and commands."""
    clear_screen()
    console.print("=== ONE-PASS SOLITAIRE HELP ===\n")
    console.print(
        "GOAL: Move all cards to the foundation piles,"
        " arranged by suit from Ace to King.\n",
    )
    console.print("COMMANDS:")
    console.print(
        "  d - Draw a card from the stock pile (only one pass through the deck)",
    )
    console.print(
        "  f - Move the current card to a foundation pile (if legal)",
    )
    console.print("  t <col> - Move the current card to tableau column <col> (1-7)")
    console.print(
        "  s <space> - Move the current card to storage space <space> (1-4)",
    )
    console.print(
        "  m <source> <destination> - Move a card from one place to another",
    )
    console.print(
        "    Sources: t1-t7 (tableau columns 1-7), s1-s4 (storage spaces 1-4)",
    )
    console.print("    Destinations: t1-t7, s1-s4, f (foundation)")
    console.print("  r - Reset the game")
    console.print("  q - Quit the game")
    console.print("  h - Show this help screen\n")
    console.print("RULES:")
    console.print("  - Tableau: Build down with alternating colors (red/black)")
    console.print("  - Foundations: Build up by suit (starting with Ace)")
    console.print("  - Only Kings can be placed on empty tableau columns")
    console.print("  - Storage spaces can hold any single card")
    console.print("  - You can only go through the stock pile once")


def play(seed: int | None = None) -> None:
    """Run the main game loop."""
    game = OnePassSolitaire(seed=seed)
    game.auto_move_to_foundation()

    while True:
        display_game(game)

        if game.is_game_won():
            console.print("\nCongratulations! You've won the game!")
            input("Press Enter to start a new game...")
            game.reset_game()
            continue

        if game.is_game_over():
            console.print("\nGame over! No more legal moves available.")
            input("Press Enter to start a new game...")
            game.reset_game()
            continue

        move = get_user_move()

        if move == "quit":
            sys.exit(0)
        elif move == "reset":
            game.reset_game()
            continue
        elif move == "help":
            show_help()
            input("Press Enter to continue...")
            continue

        success, err = game.step(move)
        if not success:
            console.print(f"\n{err}")
            input("Press Enter to continue...")


if __name__ == "__main__":
    play()
