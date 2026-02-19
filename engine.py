import random

# Card suits, values and colors
SUITS = ['♠', '♥', '♦', '♣']
VALUES = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
COLORS = {'♠': 'black', '♣': 'black', '♥': 'red', '♦': 'red'}


class Card:
    def __init__(self, suit, value, face_up=False):
        self.suit = suit
        self.value = value
        self.face_up = face_up

    def __str__(self):
        if not self.face_up:
            return "🂠"
        return f"{self.suit}{self.value}"

    def get_color(self):
        return COLORS[self.suit]

    def get_value_index(self):
        return VALUES.index(self.value)

    def flip(self):
        self.face_up = not self.face_up
        return self


class OnePassSolitaire:
    def __init__(self, seed=None):
        self.seed = seed
        self.reset_game()

    def reset_game(self):
        self.tableau = [[] for _ in range(7)]
        self.foundations = [[] for _ in range(4)]
        self.storage = [None] * 4
        self.stock = []
        self.waste = []
        self.moved_card = None

        deck = [Card(suit, value) for suit in SUITS for value in VALUES]
        if self.seed is not None:
            random.Random(self.seed).shuffle(deck)
        else:
            random.shuffle(deck)

        for col in range(7):
            for row in range(col + 1):
                card = deck.pop()
                if row == col:
                    card.face_up = True
                self.tableau[col].append(card)

        self.stock = deck

    def is_valid_tableau_move(self, card, destination_col):
        if destination_col < 0 or destination_col >= 7:
            return False
        if not self.tableau[destination_col]:
            return card.value == 'K'
        top_card = self.tableau[destination_col][-1]
        if not top_card.face_up:
            return False
        return (card.get_color() != top_card.get_color() and
                card.get_value_index() == top_card.get_value_index() - 1)

    def is_valid_foundation_move(self, card, foundation_idx):
        foundation = self.foundations[foundation_idx]
        suit_index = SUITS.index(card.suit)
        if foundation_idx != suit_index:
            return False
        if not foundation:
            return card.value == 'A'
        top_card = foundation[-1]
        return (card.suit == top_card.suit and
                card.get_value_index() == top_card.get_value_index() + 1)

    def auto_move_to_foundation(self):
        """Automatically move eligible cards to foundations where possible."""
        moved = True
        while moved:
            moved = False

            for col_idx, column in enumerate(self.tableau):
                if column and column[-1].face_up:
                    card = column[-1]
                    foundation_idx = SUITS.index(card.suit)
                    if self.is_valid_foundation_move(card, foundation_idx):
                        self.foundations[foundation_idx].append(column.pop())
                        if column and not column[-1].face_up:
                            column[-1].flip()
                        moved = True
                        break

            if not moved:
                for storage_idx, card in enumerate(self.storage):
                    if card:
                        foundation_idx = SUITS.index(card.suit)
                        if self.is_valid_foundation_move(card, foundation_idx):
                            self.foundations[foundation_idx].append(card)
                            self.storage[storage_idx] = None
                            moved = True
                            break

            if not moved and self.waste:
                card = self.waste[-1]
                foundation_idx = SUITS.index(card.suit)
                if self.is_valid_foundation_move(card, foundation_idx):
                    self.foundations[foundation_idx].append(self.waste.pop())
                    moved = True

    def foundation_count(self):
        return sum(len(pile) for pile in self.foundations)

    def step(self, move, auto_move=True):
        """Execute a move. Returns (success, error_message)."""
        if move == 'draw':
            if not self.stock:
                return (False, "No more cards in the stock pile")
            card = self.stock.pop()
            card.face_up = True
            self.waste.append(card)
            if auto_move:
                self.auto_move_to_foundation()
            return (True, None)

        elif move == 'foundation':
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

        elif isinstance(move, tuple) and move[0] == 'tableau':
            if not self.waste:
                return (False, "No card to move")
            col = move[1]
            card = self.waste[-1]
            if self.is_valid_tableau_move(card, col):
                self.tableau[col].append(self.waste.pop())
                if auto_move:
                    self.auto_move_to_foundation()
                return (True, None)
            else:
                return (False, "Invalid move to tableau")

        elif isinstance(move, tuple) and move[0] == 'storage':
            if not self.waste:
                return (False, "No card to move")
            space = move[1]
            if space < 0 or space >= 4:
                return (False, "Invalid storage space")
            if self.storage[space] is None:
                self.storage[space] = self.waste.pop()
                if auto_move:
                    self.auto_move_to_foundation()
                return (True, None)
            else:
                return (False, "Storage space is already occupied")

        elif isinstance(move, tuple) and move[0] == 'move':
            source = move[1]
            destination = move[2]

            card = None
            if source[0] == 'tableau':
                col = source[1]
                if 0 <= col < 7 and self.tableau[col] and self.tableau[col][-1].face_up:
                    card = self.tableau[col][-1]
                else:
                    return (False, "No face-up card in that tableau column")
            elif source[0] == 'storage':
                space = source[1]
                if 0 <= space < 4 and self.storage[space]:
                    card = self.storage[space]
                else:
                    return (False, "No card in that storage space")
            else:
                return (False, "Invalid source")

            if destination[0] == 'tableau':
                col = destination[1]
                if self.is_valid_tableau_move(card, col):
                    if source[0] == 'tableau':
                        self.tableau[col].append(self.tableau[source[1]].pop())
                        if self.tableau[source[1]] and not self.tableau[source[1]][-1].face_up:
                            self.tableau[source[1]][-1].flip()
                    else:
                        self.tableau[col].append(self.storage[source[1]])
                        self.storage[source[1]] = None
                    if auto_move:
                        self.auto_move_to_foundation()
                    return (True, None)
                else:
                    return (False, "Invalid tableau move")
            elif destination[0] == 'storage':
                space = destination[1]
                if self.storage[space] is None:
                    if source[0] == 'tableau':
                        self.storage[space] = self.tableau[source[1]].pop()
                        if self.tableau[source[1]] and not self.tableau[source[1]][-1].face_up:
                            self.tableau[source[1]][-1].flip()
                    else:
                        self.storage[space] = self.storage[source[1]]
                        self.storage[source[1]] = None
                    if auto_move:
                        self.auto_move_to_foundation()
                    return (True, None)
                else:
                    return (False, "Storage space is already occupied")
            elif destination[0] == 'foundation':
                suit_idx = SUITS.index(card.suit)
                if self.is_valid_foundation_move(card, suit_idx):
                    if source[0] == 'tableau':
                        self.foundations[suit_idx].append(self.tableau[source[1]].pop())
                        if self.tableau[source[1]] and not self.tableau[source[1]][-1].face_up:
                            self.tableau[source[1]][-1].flip()
                    else:
                        self.foundations[suit_idx].append(self.storage[source[1]])
                        self.storage[source[1]] = None
                    if auto_move:
                        self.auto_move_to_foundation()
                    return (True, None)
                else:
                    return (False, "Invalid foundation move")
            else:
                return (False, "Invalid destination")

        return (False, "Unknown move")

    def is_game_won(self):
        return all(len(pile) == 13 for pile in self.foundations)

    def legal_moves(self):
        """Return all valid moves in the format step() accepts."""
        moves = []

        # Draw from stock
        if self.stock:
            moves.append('draw')

        # Waste to foundation
        if self.waste:
            card = self.waste[-1]
            foundation_idx = SUITS.index(card.suit)
            if self.is_valid_foundation_move(card, foundation_idx):
                moves.append('foundation')

        # Waste to tableau
        if self.waste:
            card = self.waste[-1]
            for col in range(7):
                if self.is_valid_tableau_move(card, col):
                    moves.append(('tableau', col))

        # Waste to storage (first empty slot only — all empty slots are equivalent)
        if self.waste:
            for slot in range(4):
                if self.storage[slot] is None:
                    moves.append(('storage', slot))
                    break

        # Tableau top cards → foundation, tableau, storage
        for src_col in range(7):
            if not self.tableau[src_col]:
                continue
            card = self.tableau[src_col][-1]
            if not card.face_up:
                continue

            # To foundation
            foundation_idx = SUITS.index(card.suit)
            if self.is_valid_foundation_move(card, foundation_idx):
                moves.append(('move', ('tableau', src_col), ('foundation', foundation_idx)))

            # To other tableau columns
            for dest_col in range(7):
                if src_col != dest_col and self.is_valid_tableau_move(card, dest_col):
                    moves.append(('move', ('tableau', src_col), ('tableau', dest_col)))

            # To storage (first empty slot)
            for slot in range(4):
                if self.storage[slot] is None:
                    moves.append(('move', ('tableau', src_col), ('storage', slot)))
                    break

        # Storage → foundation, tableau
        for slot in range(4):
            if self.storage[slot] is None:
                continue
            card = self.storage[slot]

            # To foundation
            foundation_idx = SUITS.index(card.suit)
            if self.is_valid_foundation_move(card, foundation_idx):
                moves.append(('move', ('storage', slot), ('foundation', foundation_idx)))

            # To tableau
            for dest_col in range(7):
                if self.is_valid_tableau_move(card, dest_col):
                    moves.append(('move', ('storage', slot), ('tableau', dest_col)))

        return moves

    def is_game_over(self):
        """Game is over when no legal moves remain."""
        return len(self.legal_moves()) == 0

    def state_hash(self):
        """Hashable snapshot of the full board state for cycle detection."""
        parts = []
        for col in self.tableau:
            parts.append(tuple((c.suit, c.value, c.face_up) for c in col))
        for pile in self.foundations:
            parts.append(tuple((c.suit, c.value) for c in pile))
        parts.append(tuple(
            (c.suit, c.value) if c else None for c in self.storage
        ))
        parts.append(tuple((c.suit, c.value) for c in self.waste))
        parts.append(len(self.stock))
        return hash(tuple(parts))

    def is_endgame(self):
        """True when stock is empty and all tableau cards are face-up.

        In the GUI, this triggers the auto-finish animation.
        """
        if self.stock:
            return False
        return all(card.face_up for col in self.tableau for card in col)
