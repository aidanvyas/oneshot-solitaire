"""Tests for the core game engine step/move logic."""

import unittest
from io import StringIO
from unittest.mock import patch

from engine import SUITS, Card, OneShotSolitaire

INITIAL_TABLEAU_CARDS = 28
INITIAL_STOCK_SIZE = 24
FULL_DECK = 52


class TestSeedDeterminism(unittest.TestCase):
    """Tests for seed-based deterministic dealing."""

    def test_seeded_game_produces_same_deal(self) -> None:
        """Verify that the same seed produces identical deals."""
        game1 = OneShotSolitaire(seed=42)
        game2 = OneShotSolitaire(seed=42)

        # Compare all tableau cards
        for col in range(7):
            assert len(game1.tableau[col]) == len(game2.tableau[col])
            for i in range(len(game1.tableau[col])):
                c1 = game1.tableau[col][i]
                c2 = game2.tableau[col][i]
                assert c1.suit == c2.suit
                assert c1.value == c2.value

        # Compare stock
        assert len(game1.stock) == len(game2.stock)
        for i in range(len(game1.stock)):
            assert game1.stock[i].suit == game2.stock[i].suit
            assert game1.stock[i].value == game2.stock[i].value

    def test_different_seeds_produce_different_deals(self) -> None:
        """Verify that different seeds produce different deals."""
        game1 = OneShotSolitaire(seed=42)
        game2 = OneShotSolitaire(seed=99)
        # At least one card should differ in stock
        different = False
        for i in range(len(game1.stock)):
            if (
                game1.stock[i].suit != game2.stock[i].suit
                or game1.stock[i].value != game2.stock[i].value
            ):
                different = True
                break
        assert different


class TestStepDraw(unittest.TestCase):
    """Tests for the draw step action."""

    def test_draw_moves_card_from_stock_to_waste(self) -> None:
        """Verify that draw moves a card from stock to waste."""
        game = OneShotSolitaire(seed=1)
        stock_len_before = len(game.stock)
        waste_len_before = len(game.waste)

        success, err = game.step("draw")
        assert success
        assert err is None
        assert len(game.stock) == stock_len_before - 1
        assert (
            len(game.waste) >= waste_len_before + 1
        )  # >= because auto_move may consume it
        # The drawn card should be face up (if it wasn't auto-moved)
        if game.waste:
            assert game.waste[-1].face_up

    def test_draw_from_empty_stock_returns_error(self) -> None:
        """Verify that drawing from empty stock returns an error."""
        game = OneShotSolitaire(seed=1)
        game.stock = []
        success, err = game.step("draw")
        assert not success
        assert err is not None
        assert "stock" in err.lower()


class TestStepInvalidMoves(unittest.TestCase):
    """Tests for invalid move error handling."""

    def test_foundation_with_no_waste(self) -> None:
        """Verify that foundation move with empty waste fails."""
        game = OneShotSolitaire(seed=1)
        game.waste = []
        success, err = game.step("foundation")
        assert not success
        assert err is not None

    def test_tableau_with_no_waste(self) -> None:
        """Verify that tableau move with empty waste fails."""
        game = OneShotSolitaire(seed=1)
        game.waste = []
        success, err = game.step(("tableau", 0))
        assert not success
        assert err is not None

    def test_storage_with_no_waste(self) -> None:
        """Verify that storage move with empty waste fails."""
        game = OneShotSolitaire(seed=1)
        game.waste = []
        success, err = game.step(("storage", 0))
        assert not success
        assert err is not None

    def test_storage_occupied(self) -> None:
        """Verify that moving to an occupied storage slot fails."""
        game = OneShotSolitaire(seed=1)
        game.waste = [Card("♠", "5", face_up=True)]
        game.storage[0] = Card("♥", "3", face_up=True)
        success, err = game.step(("storage", 0))
        assert not success
        assert "occupied" in err.lower()

    def test_invalid_moves_do_not_print(self) -> None:
        """Verify that invalid moves produce no stdout output."""
        game = OneShotSolitaire(seed=1)
        game.waste = []
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            success, _err = game.step("foundation")
            assert not success
            assert mock_stdout.getvalue() == ""

    def test_move_from_empty_tableau(self) -> None:
        """Verify that moving from an empty tableau column fails."""
        game = OneShotSolitaire(seed=1)
        game.tableau[0] = []
        success, err = game.step(("move", ("tableau", 0), ("tableau", 1)))
        assert not success
        assert err is not None

    def test_move_from_empty_storage(self) -> None:
        """Verify that moving from an empty storage slot fails."""
        game = OneShotSolitaire(seed=1)
        game.storage[0] = None
        success, err = game.step(("move", ("storage", 0), ("tableau", 1)))
        assert not success
        assert err is not None

    def test_unknown_move_returns_error(self) -> None:
        """Verify that an unknown move type returns an error."""
        game = OneShotSolitaire(seed=1)
        success, err = game.step("nonexistent")
        assert not success
        assert err is not None


class TestStepAutoMoveToFoundation(unittest.TestCase):
    """Tests for automatic card movement to foundations."""

    def test_ace_auto_moves_to_foundation(self) -> None:
        """Verify that an ace drawn from stock auto-moves to foundation."""
        game = OneShotSolitaire(seed=1)
        # Clear state for controlled test
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.waste = []

        # Put an Ace in stock so drawing it triggers auto-move
        game.stock = [Card("♠", "A", face_up=False)]
        success, err = game.step("draw")
        assert success
        assert err is None
        # Ace of spades should have been auto-moved to foundation index 0
        spade_idx = SUITS.index("♠")
        assert len(game.foundations[spade_idx]) == 1
        assert game.foundations[spade_idx][0].value == "A"

    def test_sequential_auto_move(self) -> None:
        """Verify that sequential auto-moves chain correctly."""
        game = OneShotSolitaire(seed=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.waste = []

        # Pre-place Ace of hearts on foundation
        heart_idx = SUITS.index("♥")
        game.foundations[heart_idx] = [Card("♥", "A", face_up=True)]

        # Put 2 of hearts on tableau and Ace of spades in stock.
        # Drawing Ace should auto-move it, then 2 of hearts chains.
        game.tableau[0] = [Card("♥", "2", face_up=True)]
        game.stock = [Card("♠", "A", face_up=False)]

        success, _err = game.step("draw")
        assert success

        spade_idx = SUITS.index("♠")
        assert len(game.foundations[spade_idx]) == 1
        expected_hearts = 2
        assert len(game.foundations[heart_idx]) == expected_hearts


class TestFoundationCount(unittest.TestCase):
    """Tests for the foundation_count method."""

    def test_empty_foundations(self) -> None:
        """Verify that empty foundations return count of zero."""
        game = OneShotSolitaire(seed=1)
        game.foundations = [[] for _ in range(4)]
        assert game.foundation_count() == 0

    def test_some_cards_in_foundations(self) -> None:
        """Verify that foundation count sums cards across all suits."""
        game = OneShotSolitaire(seed=1)
        game.foundations = [
            [Card("♠", "A", face_up=True)],
            [Card("♥", "A", face_up=True), Card("♥", "2", face_up=True)],
            [],
            [
                Card("♣", "A", face_up=True),
                Card("♣", "2", face_up=True),
                Card("♣", "3", face_up=True),
            ],
        ]
        expected_count = 1 + 2 + 0 + 3
        assert game.foundation_count() == expected_count

    def test_full_foundations(self) -> None:
        """Verify that full foundations return count of 52."""
        game = OneShotSolitaire(seed=1)
        game.foundations = [
            [
                Card(s, v, face_up=True)
                for v in [
                    "A",
                    "2",
                    "3",
                    "4",
                    "5",
                    "6",
                    "7",
                    "8",
                    "9",
                    "10",
                    "J",
                    "Q",
                    "K",
                ]
            ]
            for s in SUITS
        ]
        assert game.foundation_count() == FULL_DECK


class TestNoArgConstructor(unittest.TestCase):
    """Tests for the no-argument constructor."""

    def test_no_arg_constructor(self) -> None:
        """Verify that constructor without seed deals correctly."""
        game = OneShotSolitaire()
        assert game.seed is None
        # Should still deal 28 tableau cards + 24 stock cards
        total_tableau = sum(len(col) for col in game.tableau)
        assert total_tableau == INITIAL_TABLEAU_CARDS
        assert len(game.stock) == INITIAL_STOCK_SIZE


class TestStepMoveCommand(unittest.TestCase):
    """Tests for the move command between zones."""

    def test_move_tableau_to_tableau(self) -> None:
        """Verify that a card can move between tableau columns."""
        game = OneShotSolitaire(seed=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.waste = []

        # Place a red 5 on col 0, and a black 6 on col 1
        game.tableau[0] = [Card("♥", "5", face_up=True)]
        game.tableau[1] = [Card("♠", "6", face_up=True)]

        success, err = game.step(("move", ("tableau", 0), ("tableau", 1)))
        assert success
        assert err is None
        assert len(game.tableau[0]) == 0
        expected_col_len = 2
        assert len(game.tableau[1]) == expected_col_len

    def test_move_storage_to_tableau(self) -> None:
        """Verify that a card can move from storage to tableau."""
        game = OneShotSolitaire(seed=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.waste = []

        game.storage[0] = Card("♦", "5", face_up=True)
        game.tableau[0] = [Card("♣", "6", face_up=True)]

        success, err = game.step(("move", ("storage", 0), ("tableau", 0)))
        assert success
        assert err is None
        assert game.storage[0] is None
        expected_col_len = 2
        assert len(game.tableau[0]) == expected_col_len

    def test_move_tableau_to_storage(self) -> None:
        """Verify that a card can move from tableau to storage."""
        game = OneShotSolitaire(seed=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.waste = []

        game.tableau[0] = [Card("♠", "5", face_up=True)]

        success, err = game.step(("move", ("tableau", 0), ("storage", 0)))
        assert success
        assert err is None
        assert len(game.tableau[0]) == 0
        assert game.storage[0] is not None

    def test_move_tableau_to_foundation(self) -> None:
        """Verify that a card can move from tableau to foundation."""
        game = OneShotSolitaire(seed=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.waste = []

        game.tableau[0] = [Card("♠", "A", face_up=True)]
        spade_idx = SUITS.index("♠")

        success, err = game.step(("move", ("tableau", 0), ("foundation", spade_idx)))
        assert success
        assert err is None
        assert len(game.foundations[spade_idx]) >= 1

    def test_move_invalid_tableau_move(self) -> None:
        """Verify that same-color tableau stacking fails."""
        game = OneShotSolitaire(seed=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.waste = []

        # Same color, can't stack
        game.tableau[0] = [Card("♠", "5", face_up=True)]
        game.tableau[1] = [Card("♣", "6", face_up=True)]

        success, err = game.step(("move", ("tableau", 0), ("tableau", 1)))
        assert not success
        assert err is not None

    def test_move_flips_next_card(self) -> None:
        """Verify that moving exposes and flips the card underneath."""
        game = OneShotSolitaire(seed=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.waste = []

        # Face-down card under face-up card
        game.tableau[0] = [Card("♣", "K", face_up=False), Card("♥", "5", face_up=True)]
        game.tableau[1] = [Card("♠", "6", face_up=True)]

        success, _err = game.step(("move", ("tableau", 0), ("tableau", 1)))
        assert success
        # The previously face-down card should now be face up
        assert game.tableau[0][0].face_up


class TestStepFoundationAndTableauFromWaste(unittest.TestCase):
    """Tests for moving cards from waste to foundation and tableau."""

    def test_waste_to_foundation(self) -> None:
        """Verify that waste ace moves to foundation."""
        game = OneShotSolitaire(seed=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.stock = []
        game.waste = [Card("♠", "A", face_up=True)]

        success, _err = game.step("foundation")
        assert success
        spade_idx = SUITS.index("♠")
        assert len(game.foundations[spade_idx]) == 1

    def test_waste_to_tableau(self) -> None:
        """Verify that waste card moves to a valid tableau column."""
        game = OneShotSolitaire(seed=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.stock = []

        game.tableau[0] = [Card("♠", "6", face_up=True)]
        game.waste = [Card("♥", "5", face_up=True)]

        success, _err = game.step(("tableau", 0))
        assert success
        expected_col_len = 2
        assert len(game.tableau[0]) == expected_col_len

    def test_waste_to_storage(self) -> None:
        """Verify that waste card moves to an empty storage slot."""
        game = OneShotSolitaire(seed=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.stock = []
        game.waste = [Card("♠", "5", face_up=True)]

        success, _err = game.step(("storage", 2))
        assert success
        assert game.storage[2] is not None

    def test_invalid_waste_to_foundation(self) -> None:
        """Verify that non-ace waste card cannot go to empty foundation."""
        game = OneShotSolitaire(seed=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.stock = []
        game.waste = [Card("♠", "5", face_up=True)]

        success, err = game.step("foundation")
        assert not success
        assert err is not None


if __name__ == "__main__":
    unittest.main()
