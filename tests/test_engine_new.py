import unittest
from engine import Card, OnePassSolitaire, SUITS


class TestLegalMoves(unittest.TestCase):
    def _empty_game(self):
        game = OnePassSolitaire(seed=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.stock = []
        game.waste = []
        return game

    def test_draw_available_when_stock_not_empty(self):
        game = self._empty_game()
        game.stock = [Card('♠', '5')]
        moves = game.legal_moves()
        self.assertIn('draw', moves)

    def test_draw_not_available_when_stock_empty(self):
        game = self._empty_game()
        moves = game.legal_moves()
        self.assertNotIn('draw', moves)

    def test_foundation_move_from_waste(self):
        game = self._empty_game()
        game.waste = [Card('♠', 'A', face_up=True)]
        moves = game.legal_moves()
        self.assertIn('foundation', moves)

    def test_waste_to_tableau(self):
        game = self._empty_game()
        game.waste = [Card('♥', '5', face_up=True)]
        game.tableau[0] = [Card('♠', '6', face_up=True)]
        moves = game.legal_moves()
        self.assertIn(('tableau', 0), moves)

    def test_waste_to_storage(self):
        game = self._empty_game()
        game.waste = [Card('♠', '5', face_up=True)]
        moves = game.legal_moves()
        # Should have exactly one storage move (first empty slot)
        storage_moves = [m for m in moves if isinstance(m, tuple) and m[0] == 'storage']
        self.assertEqual(len(storage_moves), 1)
        self.assertEqual(storage_moves[0], ('storage', 0))

    def test_tableau_to_tableau(self):
        game = self._empty_game()
        game.tableau[0] = [Card('♥', '5', face_up=True)]
        game.tableau[1] = [Card('♠', '6', face_up=True)]
        moves = game.legal_moves()
        self.assertIn(('move', ('tableau', 0), ('tableau', 1)), moves)

    def test_tableau_to_foundation(self):
        game = self._empty_game()
        game.tableau[0] = [Card('♠', 'A', face_up=True)]
        moves = game.legal_moves()
        spade_idx = SUITS.index('♠')
        self.assertIn(('move', ('tableau', 0), ('foundation', spade_idx)), moves)

    def test_tableau_to_storage(self):
        game = self._empty_game()
        game.tableau[0] = [Card('♠', '5', face_up=True)]
        moves = game.legal_moves()
        storage_moves = [m for m in moves if isinstance(m, tuple) and m[0] == 'move'
                         and m[2][0] == 'storage']
        self.assertTrue(len(storage_moves) >= 1)

    def test_storage_to_foundation(self):
        game = self._empty_game()
        game.storage[2] = Card('♥', 'A', face_up=True)
        moves = game.legal_moves()
        heart_idx = SUITS.index('♥')
        self.assertIn(('move', ('storage', 2), ('foundation', heart_idx)), moves)

    def test_storage_to_tableau(self):
        game = self._empty_game()
        game.storage[1] = Card('♦', '5', face_up=True)
        game.tableau[0] = [Card('♣', '6', face_up=True)]
        moves = game.legal_moves()
        self.assertIn(('move', ('storage', 1), ('tableau', 0)), moves)

    def test_legal_moves_includes_storage_when_slots_empty(self):
        """Regression: is_game_over must not miss storage as a valid destination."""
        game = self._empty_game()
        # Place cards that can't go to foundation or tableau but CAN go to storage
        game.tableau[0] = [Card('♥', '4', face_up=True)]
        game.tableau[1] = [Card('♥', '7', face_up=True)]
        game.storage = [None, None, None, None]
        moves = game.legal_moves()
        # Should include storage moves for both tableau cards
        storage_moves = [m for m in moves if isinstance(m, tuple) and m[0] == 'move'
                         and m[2][0] == 'storage']
        self.assertTrue(len(storage_moves) >= 1)

    def test_no_moves_on_truly_dead_board(self):
        game = self._empty_game()
        # All red cards, no alternating possible, all storage full, no foundation moves
        red_cards = [
            Card('♥', '4', face_up=True),
            Card('♦', '7', face_up=True),
            Card('♥', '9', face_up=True),
            Card('♦', 'J', face_up=True),
            Card('♥', 'Q', face_up=True),
            Card('♦', '6', face_up=True),
            Card('♥', '8', face_up=True),
        ]
        for i in range(7):
            game.tableau[i] = [red_cards[i]]
        game.storage = [
            Card('♦', '5', face_up=True),
            Card('♥', '10', face_up=True),
            Card('♦', 'K', face_up=True),
            Card('♥', '7', face_up=True),
        ]
        moves = game.legal_moves()
        self.assertEqual(len(moves), 0)

    def test_all_legal_moves_are_executable(self):
        """Every move from legal_moves() should succeed in step()."""
        game = OnePassSolitaire(seed=42)
        # Draw a few cards to create some state
        for _ in range(5):
            game.step('draw', auto_move=False)
        moves = game.legal_moves()
        for move in moves:
            # Clone the game state to test each move independently
            test_game = OnePassSolitaire(seed=42)
            for _ in range(5):
                test_game.step('draw', auto_move=False)
            success, err = test_game.step(move, auto_move=False)
            self.assertTrue(success, f"Move {move} should be legal but got error: {err}")


class TestIsGameOver(unittest.TestCase):
    def _empty_game(self):
        game = OnePassSolitaire(seed=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.stock = []
        game.waste = []
        return game

    def test_game_over_when_no_moves(self):
        game = self._empty_game()
        red_cards = [
            Card('♥', '4', face_up=True),
            Card('♦', '7', face_up=True),
            Card('♥', '9', face_up=True),
            Card('♦', 'J', face_up=True),
            Card('♥', 'Q', face_up=True),
            Card('♦', '6', face_up=True),
            Card('♥', '8', face_up=True),
        ]
        for i in range(7):
            game.tableau[i] = [red_cards[i]]
        game.storage = [
            Card('♦', '5', face_up=True),
            Card('♥', '10', face_up=True),
            Card('♦', 'K', face_up=True),
            Card('♥', '7', face_up=True),
        ]
        self.assertTrue(game.is_game_over())

    def test_not_game_over_with_empty_storage(self):
        """If storage has an empty slot and there are cards to move, game is NOT over."""
        game = self._empty_game()
        game.tableau[0] = [Card('♠', '9', face_up=True)]
        game.storage = [None, None, None, None]
        self.assertFalse(game.is_game_over())

    def test_not_game_over_with_stock(self):
        game = self._empty_game()
        game.stock = [Card('♠', '2')]
        self.assertFalse(game.is_game_over())

    def test_game_over_on_empty_board(self):
        """Empty board with nothing to do is game over (also means game is won)."""
        game = self._empty_game()
        self.assertTrue(game.is_game_over())


class TestStateHash(unittest.TestCase):
    def test_same_state_same_hash(self):
        game1 = OnePassSolitaire(seed=42)
        game2 = OnePassSolitaire(seed=42)
        self.assertEqual(game1.state_hash(), game2.state_hash())

    def test_different_state_different_hash(self):
        game1 = OnePassSolitaire(seed=42)
        game2 = OnePassSolitaire(seed=42)
        game2.step('draw')
        self.assertNotEqual(game1.state_hash(), game2.state_hash())

    def test_hash_changes_after_move(self):
        game = OnePassSolitaire(seed=42)
        h1 = game.state_hash()
        game.step('draw')
        h2 = game.state_hash()
        self.assertNotEqual(h1, h2)

    def test_hash_is_int(self):
        game = OnePassSolitaire(seed=42)
        self.assertIsInstance(game.state_hash(), int)


class TestIsEndgame(unittest.TestCase):
    def _empty_game(self):
        game = OnePassSolitaire(seed=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.stock = []
        game.waste = []
        return game

    def test_endgame_when_stock_empty_all_face_up(self):
        game = self._empty_game()
        game.tableau[0] = [Card('♠', 'K', face_up=True), Card('♥', 'Q', face_up=True)]
        self.assertTrue(game.is_endgame())

    def test_not_endgame_when_stock_has_cards(self):
        game = self._empty_game()
        game.stock = [Card('♠', '5')]
        game.tableau[0] = [Card('♠', 'K', face_up=True)]
        self.assertFalse(game.is_endgame())

    def test_not_endgame_when_face_down_cards(self):
        game = self._empty_game()
        game.tableau[0] = [Card('♠', 'K', face_up=False), Card('♥', 'Q', face_up=True)]
        self.assertFalse(game.is_endgame())

    def test_endgame_on_empty_tableau(self):
        game = self._empty_game()
        self.assertTrue(game.is_endgame())


class TestStepAutoMoveParam(unittest.TestCase):
    def test_auto_move_true_moves_ace_to_foundation(self):
        game = OnePassSolitaire(seed=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.waste = []
        game.stock = [Card('♠', 'A')]
        game.step('draw', auto_move=True)
        spade_idx = SUITS.index('♠')
        self.assertEqual(len(game.foundations[spade_idx]), 1)

    def test_auto_move_false_leaves_ace_in_waste(self):
        game = OnePassSolitaire(seed=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.waste = []
        game.stock = [Card('♠', 'A')]
        game.step('draw', auto_move=False)
        spade_idx = SUITS.index('♠')
        self.assertEqual(len(game.foundations[spade_idx]), 0)
        self.assertEqual(len(game.waste), 1)
        self.assertEqual(game.waste[0].value, 'A')


if __name__ == "__main__":
    unittest.main()
