"""Tests for OneShotSolitaire game rules (tableau, foundation, game-over)."""

import unittest

from engine import Card, OneShotSolitaire


class TestOneShotSolitaireRules(unittest.TestCase):
    """Verify core solitaire rule enforcement."""

    def setUp(self) -> None:
        """Create a blank game state for each test."""
        self.game = OneShotSolitaire()
        # Start from a controlled state.
        self.game.tableau = [[] for _ in range(7)]
        self.game.foundations = [[] for _ in range(4)]
        self.game.storage = [None] * 4
        self.game.stock = []
        self.game.waste = []

    def test_valid_tableau_move_alternating_descending(self) -> None:
        """Accept a move when colour alternates and rank descends."""
        self.game.tableau[0] = [Card("♠", "6", face_up=True)]
        card = Card("♥", "5", face_up=True)
        assert self.game.is_valid_tableau_move(card, 0)

    def test_invalid_tableau_move_same_color(self) -> None:
        """Reject a move when both cards share the same colour."""
        self.game.tableau[0] = [Card("♦", "6", face_up=True)]
        card = Card("♥", "5", face_up=True)
        assert not self.game.is_valid_tableau_move(card, 0)

    def test_valid_foundation_move_empty_accepts_ace(self) -> None:
        """An ace may be placed on an empty foundation."""
        card = Card("♣", "A", face_up=True)
        assert self.game.is_valid_foundation_move(card, 3)

    def test_game_over_true_when_no_moves(self) -> None:
        """Game is over when no legal moves remain."""
        # Fill tableau with face-up red cards so no alternating-color moves exist.
        red_cards = [
            Card("♥", "4", face_up=True),
            Card("♦", "7", face_up=True),
            Card("♥", "9", face_up=True),
            Card("♦", "J", face_up=True),
            Card("♥", "Q", face_up=True),
            Card("♦", "6", face_up=True),
            Card("♥", "8", face_up=True),
        ]
        for i in range(7):
            self.game.tableau[i] = [red_cards[i]]
        self.game.storage = [
            Card("♦", "5", face_up=True),
            Card("♥", "10", face_up=True),
            Card("♦", "K", face_up=True),
            Card("♥", "7", face_up=True),
        ]
        assert self.game.is_game_over()

    def test_game_over_false_when_stock_exists(self) -> None:
        """Game is not over while the stock still has cards."""
        self.game.stock = [Card("♠", "2", face_up=False)]
        assert not self.game.is_game_over()

    def test_game_over_false_with_empty_storage_and_face_up(self) -> None:
        """Game is not over when a storage-to-tableau move is available."""
        self.game.tableau[0] = [Card("♠", "9", face_up=True)]
        self.game.waste = [Card("♦", "8", face_up=True)]
        self.game.storage = [None, Card("♣", "4", face_up=True), None, None]
        assert not self.game.is_game_over()


if __name__ == "__main__":
    unittest.main()
