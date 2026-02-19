import unittest
from engine import Card, OnePassSolitaire
from benchmark.text_protocol import render_game_state, parse_move


class TestCardToAscii(unittest.TestCase):
    """Test the card_to_ascii helper via render output."""

    def test_card_formats_in_render(self):
        game = OnePassSolitaire(seed=42)
        output = render_game_state(game, turn_number=0)
        # Rendered output should contain suit-letter + value patterns
        self.assertIn("Turn 0", output)


class TestRenderGameState(unittest.TestCase):
    def _make_game(self):
        """Create a game with a known, manually-configured state."""
        game = OnePassSolitaire.__new__(OnePassSolitaire)
        game.stock = [Card('♠', '3'), Card('♦', '7')]
        game.waste = [Card('♠', '5', face_up=True)]
        game.foundations = [
            [Card('♠', 'A', True), Card('♠', '2', True), Card('♠', '3', True)],
            [],
            [Card('♦', 'A', True)],
            [],
        ]
        game.storage = [
            Card('♥', '7', face_up=True),
            None,
            Card('♣', 'J', face_up=True),
            None,
        ]
        game.tableau = [
            [Card('♠', '9', False), Card('♠', '9', False), Card('♠', '9', True), Card('♥', '8', True), Card('♣', '7', True)],
            [Card('♦', 'Q', False), Card('♦', 'Q', True)],
            [Card('♥', 'K', True), Card('♠', 'Q', True), Card('♥', 'J', True), Card('♦', '10', True)],
            [],
            [Card('♣', '4', False), Card('♣', '4', False), Card('♣', '4', False), Card('♣', '4', True)],
            [Card('♠', '6', False), Card('♠', '6', True)],
            [Card('♦', '8', False), Card('♦', '8', False), Card('♦', '8', True)],
        ]
        return game

    def test_header_with_turn_number(self):
        game = self._make_game()
        output = render_game_state(game, turn_number=14)
        self.assertIn("=== GAME STATE (Turn 14) ===", output)

    def test_stock_count(self):
        game = self._make_game()
        output = render_game_state(game, turn_number=0)
        self.assertIn("Stock: 2 cards remaining", output)

    def test_waste_with_card(self):
        game = self._make_game()
        output = render_game_state(game)
        self.assertIn("Waste: S5", output)

    def test_waste_empty(self):
        game = self._make_game()
        game.waste = []
        output = render_game_state(game)
        self.assertIn("Waste: empty", output)

    def test_foundation_with_cards(self):
        game = self._make_game()
        output = render_game_state(game)
        self.assertIn("Spades:", output)
        self.assertIn("A 2 3", output)

    def test_foundation_empty(self):
        game = self._make_game()
        output = render_game_state(game)
        self.assertIn("Hearts:", output)
        # Hearts foundation is empty
        lines = output.split("\n")
        hearts_line = [l for l in lines if "Hearts:" in l][0]
        self.assertIn("empty", hearts_line)

    def test_foundation_single_card(self):
        game = self._make_game()
        output = render_game_state(game)
        lines = output.split("\n")
        diamonds_line = [l for l in lines if "Diamonds:" in l][0]
        self.assertIn("A", diamonds_line)

    def test_face_down_cards_shown_as_question_marks(self):
        game = self._make_game()
        output = render_game_state(game)
        self.assertIn("??", output)
        # Col 1 has 2 face-down then face-up cards
        lines = output.split("\n")
        col1_line = [l for l in lines if "Col 1:" in l][0]
        self.assertTrue(col1_line.count("??") == 2)

    def test_empty_tableau_column(self):
        game = self._make_game()
        output = render_game_state(game)
        lines = output.split("\n")
        col4_line = [l for l in lines if "Col 4:" in l][0]
        self.assertIn("[empty]", col4_line)

    def test_storage_display(self):
        game = self._make_game()
        output = render_game_state(game)
        self.assertIn("[H7]", output)
        self.assertIn("[empty]", output)
        self.assertIn("[CJ]", output)

    def test_ends_with_your_move(self):
        game = self._make_game()
        output = render_game_state(game)
        self.assertTrue(output.strip().endswith("Your move:"))


class TestParseMove(unittest.TestCase):
    def test_draw(self):
        self.assertEqual(parse_move('d'), 'draw')

    def test_foundation(self):
        self.assertEqual(parse_move('f'), 'foundation')

    def test_tableau(self):
        self.assertEqual(parse_move('t 3'), ('tableau', 2))

    def test_storage(self):
        self.assertEqual(parse_move('s 1'), ('storage', 0))

    def test_move_tableau_to_tableau(self):
        self.assertEqual(
            parse_move('m t1 t3'),
            ('move', ('tableau', 0), ('tableau', 2)),
        )

    def test_move_storage_to_tableau(self):
        self.assertEqual(
            parse_move('m s2 t5'),
            ('move', ('storage', 1), ('tableau', 4)),
        )

    def test_move_tableau_to_foundation(self):
        self.assertEqual(
            parse_move('m t3 f'),
            ('move', ('tableau', 2), ('foundation', -1)),
        )

    def test_move_storage_to_foundation(self):
        self.assertEqual(
            parse_move('m s1 f'),
            ('move', ('storage', 0), ('foundation', -1)),
        )

    def test_move_tableau_to_storage(self):
        self.assertEqual(
            parse_move('m t2 s3'),
            ('move', ('tableau', 1), ('storage', 2)),
        )

    def test_move_storage_to_storage(self):
        self.assertEqual(
            parse_move('m s1 s4'),
            ('move', ('storage', 0), ('storage', 3)),
        )

    def test_extra_whitespace(self):
        self.assertEqual(parse_move('  d  '), 'draw')
        self.assertEqual(parse_move('  t   3  '), ('tableau', 2))
        self.assertEqual(parse_move('  m  t1  t3  '), ('move', ('tableau', 0), ('tableau', 2)))

    def test_mixed_case(self):
        self.assertEqual(parse_move('D'), 'draw')
        self.assertEqual(parse_move('T 3'), ('tableau', 2))
        self.assertEqual(parse_move('M T1 T3'), ('move', ('tableau', 0), ('tableau', 2)))
        self.assertEqual(parse_move('F'), 'foundation')

    def test_llm_style_draw(self):
        self.assertEqual(parse_move("I'll draw a card: d"), 'draw')

    def test_llm_style_tableau(self):
        self.assertEqual(parse_move("My move is t 3"), ('tableau', 2))

    def test_llm_style_move(self):
        result = parse_move("I want to move: m t1 t3")
        self.assertEqual(result, ('move', ('tableau', 0), ('tableau', 2)))

    def test_garbage_returns_none(self):
        self.assertIsNone(parse_move(''))
        self.assertIsNone(parse_move('hello world'))
        self.assertIsNone(parse_move('xyz 123'))
        self.assertIsNone(parse_move(None))


if __name__ == '__main__':
    unittest.main()
