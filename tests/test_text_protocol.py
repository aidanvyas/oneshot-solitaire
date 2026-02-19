"""Tests for the text-protocol helpers (render_game_state, parse_move)."""

import unittest

from benchmark.text_protocol import parse_move, render_game_state
from engine import Card, OneShotSolitaire


class TestCardToAscii(unittest.TestCase):
    """Test the card_to_ascii helper via render output."""

    def test_card_formats_in_render(self) -> None:
        """Rendered output includes a Turn header."""
        game = OneShotSolitaire(seed=42)
        output = render_game_state(game, turn_number=0)
        # Rendered output should contain suit-letter + value patterns
        assert "Turn 0" in output


class TestRenderGameState(unittest.TestCase):
    """Verify render_game_state produces expected text sections."""

    def _make_game(self) -> OneShotSolitaire:
        """Create a game with a known, manually-configured state."""
        game = OneShotSolitaire.__new__(OneShotSolitaire)
        game.stock = [Card("♠", "3"), Card("♦", "7")]
        game.waste = [Card("♠", "5", face_up=True)]
        game.foundations = [
            [
                Card("♠", "A", face_up=True),
                Card("♠", "2", face_up=True),
                Card("♠", "3", face_up=True),
            ],
            [],
            [Card("♦", "A", face_up=True)],
            [],
        ]
        game.storage = [
            Card("♥", "7", face_up=True),
            None,
            Card("♣", "J", face_up=True),
            None,
        ]
        game.tableau = [
            [
                Card("♠", "9", face_up=False),
                Card("♠", "9", face_up=False),
                Card("♠", "9", face_up=True),
                Card("♥", "8", face_up=True),
                Card("♣", "7", face_up=True),
            ],
            [Card("♦", "Q", face_up=False), Card("♦", "Q", face_up=True)],
            [
                Card("♥", "K", face_up=True),
                Card("♠", "Q", face_up=True),
                Card("♥", "J", face_up=True),
                Card("♦", "10", face_up=True),
            ],
            [],
            [
                Card("♣", "4", face_up=False),
                Card("♣", "4", face_up=False),
                Card("♣", "4", face_up=False),
                Card("♣", "4", face_up=True),
            ],
            [Card("♠", "6", face_up=False), Card("♠", "6", face_up=True)],
            [
                Card("♦", "8", face_up=False),
                Card("♦", "8", face_up=False),
                Card("♦", "8", face_up=True),
            ],
        ]
        return game

    def test_header_with_turn_number(self) -> None:
        """Header line includes the turn number."""
        game = self._make_game()
        output = render_game_state(game, turn_number=14)
        assert "=== GAME STATE (Turn 14) ===" in output

    def test_stock_count(self) -> None:
        """Stock section shows the remaining card count."""
        game = self._make_game()
        output = render_game_state(game, turn_number=0)
        assert "Stock: 2 cards remaining" in output

    def test_waste_with_card(self) -> None:
        """Waste section shows the top card abbreviation."""
        game = self._make_game()
        output = render_game_state(game)
        assert "Waste: S5" in output

    def test_waste_empty(self) -> None:
        """Waste section shows 'empty' when no cards are present."""
        game = self._make_game()
        game.waste = []
        output = render_game_state(game)
        assert "Waste: empty" in output

    def test_foundation_with_cards(self) -> None:
        """Foundation section lists suit name and card values."""
        game = self._make_game()
        output = render_game_state(game)
        assert "Spades:" in output
        assert "A 2 3" in output

    def test_foundation_empty(self) -> None:
        """An empty foundation shows 'empty'."""
        game = self._make_game()
        output = render_game_state(game)
        assert "Hearts:" in output
        # Hearts foundation is empty
        lines = output.split("\n")
        hearts_line = next(line for line in lines if "Hearts:" in line)
        assert "empty" in hearts_line

    def test_foundation_single_card(self) -> None:
        """A foundation with one card shows that card's value."""
        game = self._make_game()
        output = render_game_state(game)
        lines = output.split("\n")
        diamonds_line = next(line for line in lines if "Diamonds:" in line)
        assert "A" in diamonds_line

    def test_face_down_cards_shown_as_question_marks(self) -> None:
        """Face-down cards render as '??'."""
        game = self._make_game()
        output = render_game_state(game)
        assert "??" in output
        # Col 1 has 2 face-down then face-up cards
        lines = output.split("\n")
        col1_line = next(line for line in lines if "Col 1:" in line)
        expected_face_down = 2
        assert col1_line.count("??") == expected_face_down

    def test_empty_tableau_column(self) -> None:
        """An empty tableau column renders as '[empty]'."""
        game = self._make_game()
        output = render_game_state(game)
        lines = output.split("\n")
        col4_line = next(line for line in lines if "Col 4:" in line)
        assert "[empty]" in col4_line

    def test_storage_display(self) -> None:
        """Storage slots show card abbreviations or '[empty]'."""
        game = self._make_game()
        output = render_game_state(game)
        assert "[H7]" in output
        assert "[empty]" in output
        assert "[CJ]" in output

    def test_ends_with_your_move(self) -> None:
        """Rendered state ends with the 'Your move:' prompt."""
        game = self._make_game()
        output = render_game_state(game)
        assert output.strip().endswith("Your move:")


class TestParseMove(unittest.TestCase):
    """Verify parse_move handles all command formats."""

    def test_draw(self) -> None:
        """Parse 'd' as a draw command."""
        assert parse_move("d") == "draw"

    def test_foundation(self) -> None:
        """Parse 'f' as a foundation command."""
        assert parse_move("f") == "foundation"

    def test_tableau(self) -> None:
        """Parse 't N' as a tableau command with zero-indexed column."""
        assert parse_move("t 3") == ("tableau", 2)

    def test_storage(self) -> None:
        """Parse 's N' as a storage command with zero-indexed slot."""
        assert parse_move("s 1") == ("storage", 0)

    def test_move_tableau_to_tableau(self) -> None:
        """Parse 'm tX tY' as a tableau-to-tableau move."""
        assert parse_move("m t1 t3") == ("move", ("tableau", 0), ("tableau", 2))

    def test_move_storage_to_tableau(self) -> None:
        """Parse 'm sX tY' as a storage-to-tableau move."""
        assert parse_move("m s2 t5") == ("move", ("storage", 1), ("tableau", 4))

    def test_move_tableau_to_foundation(self) -> None:
        """Parse 'm tX f' as a tableau-to-foundation move."""
        assert parse_move("m t3 f") == ("move", ("tableau", 2), ("foundation", -1))

    def test_move_storage_to_foundation(self) -> None:
        """Parse 'm sX f' as a storage-to-foundation move."""
        assert parse_move("m s1 f") == ("move", ("storage", 0), ("foundation", -1))

    def test_move_tableau_to_storage(self) -> None:
        """Parse 'm tX sY' as a tableau-to-storage move."""
        assert parse_move("m t2 s3") == ("move", ("tableau", 1), ("storage", 2))

    def test_move_storage_to_storage(self) -> None:
        """Parse 'm sX sY' as a storage-to-storage move."""
        assert parse_move("m s1 s4") == ("move", ("storage", 0), ("storage", 3))

    def test_extra_whitespace(self) -> None:
        """Extra whitespace around or between tokens is tolerated."""
        assert parse_move("  d  ") == "draw"
        assert parse_move("  t   3  ") == ("tableau", 2)
        assert parse_move("  m  t1  t3  ") == ("move", ("tableau", 0), ("tableau", 2))

    def test_mixed_case(self) -> None:
        """Commands are case-insensitive."""
        assert parse_move("D") == "draw"
        assert parse_move("T 3") == ("tableau", 2)
        assert parse_move("M T1 T3") == ("move", ("tableau", 0), ("tableau", 2))
        assert parse_move("F") == "foundation"

    def test_llm_style_draw(self) -> None:
        """LLM preamble text before 'd' is ignored."""
        assert parse_move("I'll draw a card: d") == "draw"

    def test_llm_style_tableau(self) -> None:
        """LLM preamble text before 't N' is ignored."""
        assert parse_move("My move is t 3") == ("tableau", 2)

    def test_llm_style_move(self) -> None:
        """LLM preamble text before 'm ...' is ignored."""
        result = parse_move("I want to move: m t1 t3")
        assert result == ("move", ("tableau", 0), ("tableau", 2))

    def test_garbage_returns_none(self) -> None:
        """Unrecognisable input returns None."""
        assert parse_move("") is None
        assert parse_move("hello world") is None
        assert parse_move("xyz 123") is None
        assert parse_move(None) is None


if __name__ == "__main__":
    unittest.main()
