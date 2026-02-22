"""One-Shot Solitaire game engine."""

from __future__ import annotations

import random

# Card suits, values and colors
SUITS = ["♠", "♥", "♦", "♣"]
VALUES = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
COLORS = {"♠": "black", "♣": "black", "♥": "red", "♦": "red"}

NUM_TABLEAU_COLS = 7
NUM_STORAGE_SLOTS = 4
NUM_FOUNDATION_PILES = 4
FULL_DECK_SIZE = 52
CARDS_PER_SUIT = 13


class Card:
    """A playing card with suit, value, and face-up state."""

    def __init__(self, suit: str, value: str, *, face_up: bool = False) -> None:
        """Initialize a card."""
        self.suit = suit
        self.value = value
        self.face_up = face_up

    def __str__(self) -> str:
        """Return string representation of the card."""
        if not self.face_up:
            return "🂠"
        return f"{self.suit}{self.value}"

    def get_color(self) -> str:
        """Return the color of the card ('red' or 'black')."""
        return COLORS[self.suit]

    def get_value_index(self) -> int:
        """Return the index of the card value in VALUES."""
        return VALUES.index(self.value)

    def flip(self) -> Card:
        """Flip the card face-up/face-down and return self."""
        self.face_up = not self.face_up
        return self


class OneShotSolitaire:
    """One-shot solitaire game with FreeCell-style storage slots."""

    def __init__(self, game_id: int | None = None) -> None:
        """Initialize a new game.

        Args:
            game_id: Unique identifier that determines the deal. If None, a
                random game_id is generated automatically. Two games with the
                same game_id will always produce the same deal.

        """
        self.game_id: int = (
            game_id if game_id is not None else random.randrange(1, 2**32)
        )
        self.reset_game()

    def reset_game(self) -> None:
        """Reset the game to a fresh deal."""
        self.tableau: list[list[Card]] = [[] for _ in range(NUM_TABLEAU_COLS)]
        self.foundations: list[list[Card]] = [[] for _ in range(NUM_FOUNDATION_PILES)]
        self.storage: list[Card | None] = [None] * NUM_STORAGE_SLOTS
        self.stock: list[Card] = []
        self.waste: list[Card] = []
        self.moved_card: Card | None = None

        deck = [Card(suit, value) for suit in SUITS for value in VALUES]
        random.Random(self.game_id).shuffle(deck)

        for col in range(NUM_TABLEAU_COLS):
            for row in range(col + 1):
                card = deck.pop()
                if row == col:
                    card.face_up = True
                self.tableau[col].append(card)

        self.stock = deck

        # Auto-draw the first card so the game starts with a playable waste.
        card = self.stock.pop()
        card.face_up = True
        self.waste.append(card)

    def is_valid_tableau_move(self, card: Card, destination_col: int) -> bool:
        """Check if a card can be placed on a tableau column."""
        if destination_col < 0 or destination_col >= NUM_TABLEAU_COLS:
            return False
        if not self.tableau[destination_col]:
            return card.value == "K"
        top_card = self.tableau[destination_col][-1]
        if not top_card.face_up:
            return False
        return (
            card.get_color() != top_card.get_color()
            and card.get_value_index() == top_card.get_value_index() - 1
        )

    def is_valid_foundation_move(self, card: Card, foundation_idx: int) -> bool:
        """Check if a card can be placed on a foundation pile."""
        foundation = self.foundations[foundation_idx]
        suit_index = SUITS.index(card.suit)
        if foundation_idx != suit_index:
            return False
        if not foundation:
            return card.value == "A"
        top_card = foundation[-1]
        return (
            card.suit == top_card.suit
            and card.get_value_index() == top_card.get_value_index() + 1
        )

    def _auto_move_tableau(self) -> bool:
        """Try to auto-move a tableau top card to its foundation."""
        for _col_idx, column in enumerate(self.tableau):
            if column and column[-1].face_up:
                card = column[-1]
                foundation_idx = SUITS.index(card.suit)
                if self.is_valid_foundation_move(card, foundation_idx):
                    self.foundations[foundation_idx].append(column.pop())
                    if column and not column[-1].face_up:
                        column[-1].flip()
                    return True
        return False

    def _auto_move_storage(self) -> bool:
        """Try to auto-move a storage card to its foundation."""
        for storage_idx, card in enumerate(self.storage):
            if card:
                foundation_idx = SUITS.index(card.suit)
                if self.is_valid_foundation_move(card, foundation_idx):
                    self.foundations[foundation_idx].append(card)
                    self.storage[storage_idx] = None
                    return True
        return False

    def _auto_move_waste(self) -> bool:
        """Try to auto-move the waste top card to its foundation."""
        if self.waste:
            card = self.waste[-1]
            foundation_idx = SUITS.index(card.suit)
            if self.is_valid_foundation_move(card, foundation_idx):
                self.foundations[foundation_idx].append(self.waste.pop())
                return True
        return False

    def auto_move_to_foundation(self) -> None:
        """Automatically move eligible cards to foundations where possible."""
        moved = True
        while moved:
            moved = (
                self._auto_move_tableau()
                or self._auto_move_storage()
                or self._auto_move_waste()
            )

    def foundation_count(self) -> int:
        """Return the total number of cards in all foundation piles."""
        return sum(len(pile) for pile in self.foundations)

    def _step_draw(self, *, auto_move: bool) -> tuple[bool, str | None]:
        """Handle the 'draw' move."""
        if not self.stock:
            return (False, "No more cards in the stock pile")
        card = self.stock.pop()
        card.face_up = True
        self.waste.append(card)
        if auto_move:
            self.auto_move_to_foundation()
        return (True, None)

    def _step_foundation(self, *, auto_move: bool) -> tuple[bool, str | None]:
        """Handle the 'foundation' move (waste to foundation)."""
        if not self.waste:
            return (False, "No card to move")
        card = self.waste[-1]
        for i, suit in enumerate(SUITS):
            if card.suit == suit and self.is_valid_foundation_move(card, i):
                self.foundations[i].append(self.waste.pop())
                if auto_move:
                    self.auto_move_to_foundation()
                return (True, None)
        return (False, "Cannot move this card to any foundation pile")

    def _step_tableau(
        self,
        col: int,
        *,
        auto_move: bool,
    ) -> tuple[bool, str | None]:
        """Handle waste-to-tableau move."""
        if not self.waste:
            return (False, "No card to move")
        card = self.waste[-1]
        if self.is_valid_tableau_move(card, col):
            self.tableau[col].append(self.waste.pop())
            if auto_move:
                self.auto_move_to_foundation()
            return (True, None)
        return (False, "Invalid move to tableau")

    def _step_storage(
        self,
        space: int,
        *,
        auto_move: bool,
    ) -> tuple[bool, str | None]:
        """Handle waste-to-storage move."""
        if not self.waste:
            return (False, "No card to move")
        if space < 0 or space >= NUM_STORAGE_SLOTS:
            return (False, "Invalid storage space")
        if self.storage[space] is None:
            self.storage[space] = self.waste.pop()
            if auto_move:
                self.auto_move_to_foundation()
            return (True, None)
        return (False, "Storage space is already occupied")

    def _resolve_source_tableau(self, col: int) -> tuple[Card | None, str | None]:
        """Resolve a tableau column as a move source."""
        if (
            0 <= col < NUM_TABLEAU_COLS
            and self.tableau[col]
            and self.tableau[col][-1].face_up
        ):
            return self.tableau[col][-1], None
        return None, "No face-up card in that tableau column"

    def _resolve_source_storage(self, space: int) -> tuple[Card | None, str | None]:
        """Resolve a storage slot as a move source."""
        if 0 <= space < NUM_STORAGE_SLOTS and self.storage[space]:
            return self.storage[space], None
        return None, "No card in that storage space"

    def _resolve_source_foundation(self, idx: int) -> tuple[Card | None, str | None]:
        """Resolve a foundation pile as a move source."""
        if 0 <= idx < NUM_FOUNDATION_PILES and self.foundations[idx]:
            return self.foundations[idx][-1], None
        return None, "No card in that foundation pile"

    def _resolve_source(
        self,
        source: tuple[str, int],
    ) -> tuple[Card | None, str | None]:
        """Resolve the source card for a move command."""
        resolvers = {
            "tableau": self._resolve_source_tableau,
            "storage": self._resolve_source_storage,
            "foundation": self._resolve_source_foundation,
        }
        resolver = resolvers.get(source[0])
        if resolver:
            return resolver(source[1])
        return None, "Invalid source"

    def _flip_tableau_top(self, col: int) -> None:
        """Flip the top card of a tableau column if it is face-down."""
        if self.tableau[col] and not self.tableau[col][-1].face_up:
            self.tableau[col][-1].flip()

    def _step_move_to_tableau(
        self,
        source: tuple[str, int],
        card: Card,
        col: int,
        *,
        auto_move: bool,
    ) -> tuple[bool, str | None]:
        """Handle move-to-tableau destination."""
        if not self.is_valid_tableau_move(card, col):
            return (False, "Invalid tableau move")
        if source[0] == "tableau":
            self.tableau[col].append(self.tableau[source[1]].pop())
            self._flip_tableau_top(source[1])
        elif source[0] == "foundation":
            self.tableau[col].append(self.foundations[source[1]].pop())
        else:
            self.tableau[col].append(self.storage[source[1]])
            self.storage[source[1]] = None
        if auto_move:
            self.auto_move_to_foundation()
        return (True, None)

    def _step_move_to_storage(
        self,
        source: tuple[str, int],
        space: int,
        *,
        auto_move: bool,
    ) -> tuple[bool, str | None]:
        """Handle move-to-storage destination."""
        if self.storage[space] is not None:
            return (False, "Storage space is already occupied")
        if source[0] == "tableau":
            self.storage[space] = self.tableau[source[1]].pop()
            self._flip_tableau_top(source[1])
        else:
            self.storage[space] = self.storage[source[1]]
            self.storage[source[1]] = None
        if auto_move:
            self.auto_move_to_foundation()
        return (True, None)

    def _step_move_to_foundation(
        self,
        source: tuple[str, int],
        card: Card,
        *,
        auto_move: bool,
    ) -> tuple[bool, str | None]:
        """Handle move-to-foundation destination."""
        suit_idx = SUITS.index(card.suit)
        if not self.is_valid_foundation_move(card, suit_idx):
            return (False, "Invalid foundation move")
        if source[0] == "tableau":
            self.foundations[suit_idx].append(self.tableau[source[1]].pop())
            self._flip_tableau_top(source[1])
        else:
            self.foundations[suit_idx].append(self.storage[source[1]])
            self.storage[source[1]] = None
        if auto_move:
            self.auto_move_to_foundation()
        return (True, None)

    def _step_move(
        self,
        move: tuple,
        *,
        auto_move: bool,
    ) -> tuple[bool, str | None]:
        """Handle compound move commands (source -> destination)."""
        source = move[1]
        destination = move[2]

        card, err = self._resolve_source(source)
        if card is None:
            return (False, err)

        if destination[0] == "tableau":
            return self._step_move_to_tableau(
                source,
                card,
                destination[1],
                auto_move=auto_move,
            )
        if destination[0] == "storage":
            return self._step_move_to_storage(
                source,
                destination[1],
                auto_move=auto_move,
            )
        if destination[0] == "foundation":
            return self._step_move_to_foundation(
                source,
                card,
                auto_move=auto_move,
            )
        return (False, "Invalid destination")

    def step(
        self,
        move: str | tuple,
        *,
        auto_move: bool = False,
    ) -> tuple[bool, str | None]:
        """Execute a move. Return (success, error_message)."""
        if move == "draw":
            return self._step_draw(auto_move=auto_move)

        if move == "foundation":
            return self._step_foundation(auto_move=auto_move)

        if isinstance(move, tuple) and move[0] == "tableau":
            return self._step_tableau(move[1], auto_move=auto_move)

        if isinstance(move, tuple) and move[0] == "storage":
            return self._step_storage(move[1], auto_move=auto_move)

        if isinstance(move, tuple) and move[0] == "move":
            return self._step_move(move, auto_move=auto_move)

        return (False, "Unknown move")

    def is_game_won(self) -> bool:
        """Check if all cards are in the foundations."""
        return all(len(pile) == CARDS_PER_SUIT for pile in self.foundations)

    def _waste_moves(self) -> list:
        """Collect legal moves originating from the waste pile."""
        if not self.waste:
            return []
        moves = []
        card = self.waste[-1]
        foundation_idx = SUITS.index(card.suit)
        if self.is_valid_foundation_move(card, foundation_idx):
            moves.append("foundation")
        moves.extend(
            ("tableau", col)
            for col in range(NUM_TABLEAU_COLS)
            if self.is_valid_tableau_move(card, col)
        )
        for slot in range(NUM_STORAGE_SLOTS):
            if self.storage[slot] is None:
                moves.append(("storage", slot))
                break
        return moves

    def _is_pointless_king_move(self, src_col: int, dest_col: int) -> bool:
        """Return True if moving a lone king to an empty column (no progress)."""
        card = self.tableau[src_col][-1]
        return (
            card.value == "K"
            and not self.tableau[dest_col]
            and len(self.tableau[src_col]) == 1
        )

    def _tableau_moves(self) -> list:
        """Collect legal moves originating from tableau columns."""
        moves = []
        for src_col in range(NUM_TABLEAU_COLS):
            if not self.tableau[src_col]:
                continue
            card = self.tableau[src_col][-1]
            if not card.face_up:
                continue
            self._collect_tableau_col_moves(moves, card, src_col)
        return moves

    def _collect_tableau_col_moves(
        self,
        moves: list,
        card: Card,
        src_col: int,
    ) -> None:
        """Append all legal moves for a single tableau column's top card."""
        foundation_idx = SUITS.index(card.suit)
        if self.is_valid_foundation_move(card, foundation_idx):
            moves.append(
                ("move", ("tableau", src_col), ("foundation", foundation_idx)),
            )

        for dest_col in range(NUM_TABLEAU_COLS):
            if src_col == dest_col:
                continue
            if not self.is_valid_tableau_move(card, dest_col):
                continue
            if self._is_pointless_king_move(src_col, dest_col):
                continue
            moves.append(
                ("move", ("tableau", src_col), ("tableau", dest_col)),
            )

        for slot in range(NUM_STORAGE_SLOTS):
            if self.storage[slot] is None:
                moves.append(
                    ("move", ("tableau", src_col), ("storage", slot)),
                )
                break

    def _storage_moves(self) -> list:
        """Collect legal moves originating from storage slots."""
        moves = []
        for slot in range(NUM_STORAGE_SLOTS):
            if self.storage[slot] is None:
                continue
            card = self.storage[slot]

            foundation_idx = SUITS.index(card.suit)
            if self.is_valid_foundation_move(card, foundation_idx):
                moves.append(
                    ("move", ("storage", slot), ("foundation", foundation_idx)),
                )

            moves.extend(
                ("move", ("storage", slot), ("tableau", dest_col))
                for dest_col in range(NUM_TABLEAU_COLS)
                if self.is_valid_tableau_move(card, dest_col)
            )
        return moves

    def legal_moves(self) -> list:
        """Return all valid moves in the format step() accepts."""
        moves: list = []

        if self.stock:
            moves.append("draw")

        moves.extend(self._waste_moves())
        moves.extend(self._tableau_moves())
        moves.extend(self._storage_moves())

        return moves

    def is_game_over(self) -> bool:
        """Return True when no legal moves remain."""
        return len(self.legal_moves()) == 0

    def state_hash(self) -> int:
        """Return a hashable snapshot of the full board state for cycle detection."""
        parts: list = [
            tuple((c.suit, c.value, c.face_up) for c in col) for col in self.tableau
        ]
        parts.extend(
            tuple((c.suit, c.value) for c in pile) for pile in self.foundations
        )
        parts.append(tuple((c.suit, c.value) if c else None for c in self.storage))
        parts.append(tuple((c.suit, c.value) for c in self.waste))
        parts.append(len(self.stock))
        return hash(tuple(parts))

    def is_endgame(self) -> bool:
        """Return True when the game is trivially winnable.

        Conditions: stock empty, all tableau cards face-up, and waste has at
        most one card (so no buried inaccessible cards remain).
        """
        if self.stock:
            return False
        if len(self.waste) > 1:
            return False
        return all(card.face_up for col in self.tableau for card in col)
