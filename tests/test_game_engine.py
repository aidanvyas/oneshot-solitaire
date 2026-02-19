import unittest
from unittest.mock import patch
from io import StringIO

from engine import Card, OnePassSolitaire, SUITS


class TestSeedDeterminism(unittest.TestCase):
    def test_seeded_game_produces_same_deal(self):
        game1 = OnePassSolitaire(seed=42)
        game2 = OnePassSolitaire(seed=42)

        # Compare all tableau cards
        for col in range(7):
            self.assertEqual(len(game1.tableau[col]), len(game2.tableau[col]))
            for i in range(len(game1.tableau[col])):
                c1 = game1.tableau[col][i]
                c2 = game2.tableau[col][i]
                self.assertEqual(c1.suit, c2.suit)
                self.assertEqual(c1.value, c2.value)

        # Compare stock
        self.assertEqual(len(game1.stock), len(game2.stock))
        for i in range(len(game1.stock)):
            self.assertEqual(game1.stock[i].suit, game2.stock[i].suit)
            self.assertEqual(game1.stock[i].value, game2.stock[i].value)

    def test_different_seeds_produce_different_deals(self):
        game1 = OnePassSolitaire(seed=42)
        game2 = OnePassSolitaire(seed=99)
        # At least one card should differ in stock
        different = False
        for i in range(len(game1.stock)):
            if game1.stock[i].suit != game2.stock[i].suit or game1.stock[i].value != game2.stock[i].value:
                different = True
                break
        self.assertTrue(different)


class TestStepDraw(unittest.TestCase):
    def test_draw_moves_card_from_stock_to_waste(self):
        game = OnePassSolitaire(seed=1)
        stock_len_before = len(game.stock)
        waste_len_before = len(game.waste)

        success, err = game.step('draw')
        self.assertTrue(success)
        self.assertIsNone(err)
        self.assertEqual(len(game.stock), stock_len_before - 1)
        self.assertGreaterEqual(len(game.waste), waste_len_before + 1)  # >= because auto_move may consume it
        # The drawn card should be face up (if it wasn't auto-moved)
        if game.waste:
            self.assertTrue(game.waste[-1].face_up)

    def test_draw_from_empty_stock_returns_error(self):
        game = OnePassSolitaire(seed=1)
        game.stock = []
        success, err = game.step('draw')
        self.assertFalse(success)
        self.assertIsNotNone(err)
        self.assertIn("stock", err.lower())


class TestStepInvalidMoves(unittest.TestCase):
    def test_foundation_with_no_waste(self):
        game = OnePassSolitaire(seed=1)
        game.waste = []
        success, err = game.step('foundation')
        self.assertFalse(success)
        self.assertIsNotNone(err)

    def test_tableau_with_no_waste(self):
        game = OnePassSolitaire(seed=1)
        game.waste = []
        success, err = game.step(('tableau', 0))
        self.assertFalse(success)
        self.assertIsNotNone(err)

    def test_storage_with_no_waste(self):
        game = OnePassSolitaire(seed=1)
        game.waste = []
        success, err = game.step(('storage', 0))
        self.assertFalse(success)
        self.assertIsNotNone(err)

    def test_storage_occupied(self):
        game = OnePassSolitaire(seed=1)
        game.waste = [Card('♠', '5', face_up=True)]
        game.storage[0] = Card('♥', '3', face_up=True)
        success, err = game.step(('storage', 0))
        self.assertFalse(success)
        self.assertIn("occupied", err.lower())

    def test_invalid_moves_do_not_print(self):
        game = OnePassSolitaire(seed=1)
        game.waste = []
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            success, err = game.step('foundation')
            self.assertFalse(success)
            self.assertEqual(mock_stdout.getvalue(), "")

    def test_move_from_empty_tableau(self):
        game = OnePassSolitaire(seed=1)
        game.tableau[0] = []
        success, err = game.step(('move', ('tableau', 0), ('tableau', 1)))
        self.assertFalse(success)
        self.assertIsNotNone(err)

    def test_move_from_empty_storage(self):
        game = OnePassSolitaire(seed=1)
        game.storage[0] = None
        success, err = game.step(('move', ('storage', 0), ('tableau', 1)))
        self.assertFalse(success)
        self.assertIsNotNone(err)

    def test_unknown_move_returns_error(self):
        game = OnePassSolitaire(seed=1)
        success, err = game.step('nonexistent')
        self.assertFalse(success)
        self.assertIsNotNone(err)


class TestStepAutoMoveToFoundation(unittest.TestCase):
    def test_ace_auto_moves_to_foundation(self):
        game = OnePassSolitaire(seed=1)
        # Clear state for controlled test
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.waste = []

        # Put an Ace in stock so drawing it triggers auto-move
        game.stock = [Card('♠', 'A', face_up=False)]
        success, err = game.step('draw')
        self.assertTrue(success)
        self.assertIsNone(err)
        # Ace of spades should have been auto-moved to foundation index 0
        spade_idx = SUITS.index('♠')
        self.assertEqual(len(game.foundations[spade_idx]), 1)
        self.assertEqual(game.foundations[spade_idx][0].value, 'A')

    def test_sequential_auto_move(self):
        game = OnePassSolitaire(seed=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.waste = []

        # Pre-place Ace of hearts on foundation
        heart_idx = SUITS.index('♥')
        game.foundations[heart_idx] = [Card('♥', 'A', face_up=True)]

        # Put 2 of hearts on tableau and Ace of spades in stock
        # Drawing Ace of spades should auto-move it, then 2 of hearts should auto-move too
        game.tableau[0] = [Card('♥', '2', face_up=True)]
        game.stock = [Card('♠', 'A', face_up=False)]

        success, err = game.step('draw')
        self.assertTrue(success)

        spade_idx = SUITS.index('♠')
        self.assertEqual(len(game.foundations[spade_idx]), 1)
        self.assertEqual(len(game.foundations[heart_idx]), 2)


class TestFoundationCount(unittest.TestCase):
    def test_empty_foundations(self):
        game = OnePassSolitaire(seed=1)
        game.foundations = [[] for _ in range(4)]
        self.assertEqual(game.foundation_count(), 0)

    def test_some_cards_in_foundations(self):
        game = OnePassSolitaire(seed=1)
        game.foundations = [
            [Card('♠', 'A', face_up=True)],
            [Card('♥', 'A', face_up=True), Card('♥', '2', face_up=True)],
            [],
            [Card('♣', 'A', face_up=True), Card('♣', '2', face_up=True), Card('♣', '3', face_up=True)],
        ]
        self.assertEqual(game.foundation_count(), 6)

    def test_full_foundations(self):
        game = OnePassSolitaire(seed=1)
        game.foundations = [
            [Card(s, v, face_up=True) for v in ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']]
            for s in SUITS
        ]
        self.assertEqual(game.foundation_count(), 52)


class TestNoArgConstructor(unittest.TestCase):
    def test_no_arg_constructor(self):
        game = OnePassSolitaire()
        self.assertIsNone(game.seed)
        # Should still deal 28 tableau cards + 24 stock cards
        total_tableau = sum(len(col) for col in game.tableau)
        self.assertEqual(total_tableau, 28)
        self.assertEqual(len(game.stock), 24)


class TestStepMoveCommand(unittest.TestCase):
    def test_move_tableau_to_tableau(self):
        game = OnePassSolitaire(seed=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.waste = []

        # Place a red 5 on col 0, and a black 6 on col 1
        game.tableau[0] = [Card('♥', '5', face_up=True)]
        game.tableau[1] = [Card('♠', '6', face_up=True)]

        success, err = game.step(('move', ('tableau', 0), ('tableau', 1)))
        self.assertTrue(success)
        self.assertIsNone(err)
        self.assertEqual(len(game.tableau[0]), 0)
        self.assertEqual(len(game.tableau[1]), 2)

    def test_move_storage_to_tableau(self):
        game = OnePassSolitaire(seed=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.waste = []

        game.storage[0] = Card('♦', '5', face_up=True)
        game.tableau[0] = [Card('♣', '6', face_up=True)]

        success, err = game.step(('move', ('storage', 0), ('tableau', 0)))
        self.assertTrue(success)
        self.assertIsNone(err)
        self.assertIsNone(game.storage[0])
        self.assertEqual(len(game.tableau[0]), 2)

    def test_move_tableau_to_storage(self):
        game = OnePassSolitaire(seed=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.waste = []

        game.tableau[0] = [Card('♠', '5', face_up=True)]

        success, err = game.step(('move', ('tableau', 0), ('storage', 0)))
        self.assertTrue(success)
        self.assertIsNone(err)
        self.assertEqual(len(game.tableau[0]), 0)
        self.assertIsNotNone(game.storage[0])

    def test_move_tableau_to_foundation(self):
        game = OnePassSolitaire(seed=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.waste = []

        game.tableau[0] = [Card('♠', 'A', face_up=True)]
        spade_idx = SUITS.index('♠')

        success, err = game.step(('move', ('tableau', 0), ('foundation', spade_idx)))
        self.assertTrue(success)
        self.assertIsNone(err)
        self.assertGreaterEqual(len(game.foundations[spade_idx]), 1)

    def test_move_invalid_tableau_move(self):
        game = OnePassSolitaire(seed=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.waste = []

        # Same color, can't stack
        game.tableau[0] = [Card('♠', '5', face_up=True)]
        game.tableau[1] = [Card('♣', '6', face_up=True)]

        success, err = game.step(('move', ('tableau', 0), ('tableau', 1)))
        self.assertFalse(success)
        self.assertIsNotNone(err)

    def test_move_flips_next_card(self):
        game = OnePassSolitaire(seed=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.waste = []

        # Face-down card under face-up card
        game.tableau[0] = [Card('♣', 'K', face_up=False), Card('♥', '5', face_up=True)]
        game.tableau[1] = [Card('♠', '6', face_up=True)]

        success, err = game.step(('move', ('tableau', 0), ('tableau', 1)))
        self.assertTrue(success)
        # The previously face-down card should now be face up
        self.assertTrue(game.tableau[0][0].face_up)


class TestStepFoundationAndTableauFromWaste(unittest.TestCase):
    def test_waste_to_foundation(self):
        game = OnePassSolitaire(seed=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.stock = []
        game.waste = [Card('♠', 'A', face_up=True)]

        success, err = game.step('foundation')
        self.assertTrue(success)
        spade_idx = SUITS.index('♠')
        self.assertEqual(len(game.foundations[spade_idx]), 1)

    def test_waste_to_tableau(self):
        game = OnePassSolitaire(seed=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.stock = []

        game.tableau[0] = [Card('♠', '6', face_up=True)]
        game.waste = [Card('♥', '5', face_up=True)]

        success, err = game.step(('tableau', 0))
        self.assertTrue(success)
        self.assertEqual(len(game.tableau[0]), 2)

    def test_waste_to_storage(self):
        game = OnePassSolitaire(seed=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.stock = []
        game.waste = [Card('♠', '5', face_up=True)]

        success, err = game.step(('storage', 2))
        self.assertTrue(success)
        self.assertIsNotNone(game.storage[2])

    def test_invalid_waste_to_foundation(self):
        game = OnePassSolitaire(seed=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.stock = []
        game.waste = [Card('♠', '5', face_up=True)]

        success, err = game.step('foundation')
        self.assertFalse(success)
        self.assertIsNotNone(err)


if __name__ == "__main__":
    unittest.main()
