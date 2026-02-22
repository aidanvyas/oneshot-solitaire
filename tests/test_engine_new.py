"""Tests for new engine methods: legal_moves, is_game_over, state_hash, is_endgame."""

import unittest

from engine import SUITS, Card, OneShotSolitaire


class TestLegalMoves(unittest.TestCase):
    """Tests for the legal_moves method."""

    def _empty_game(self) -> OneShotSolitaire:
        """Create an empty game state for testing."""
        game = OneShotSolitaire(game_id=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.stock = []
        game.waste = []
        return game

    def test_draw_available_when_stock_not_empty(self) -> None:
        """Draw should be available when stock has cards."""
        game = self._empty_game()
        game.stock = [Card("\u2660", "5")]
        moves = game.legal_moves()
        assert "draw" in moves

    def test_draw_not_available_when_stock_empty(self) -> None:
        """Draw should not be available when stock is empty."""
        game = self._empty_game()
        moves = game.legal_moves()
        assert "draw" not in moves

    def test_foundation_move_from_waste(self) -> None:
        """Foundation move should be available for ace on waste."""
        game = self._empty_game()
        game.waste = [Card("\u2660", "A", face_up=True)]
        moves = game.legal_moves()
        assert "foundation" in moves

    def test_waste_to_tableau(self) -> None:
        """Waste card should be movable to valid tableau column."""
        game = self._empty_game()
        game.waste = [Card("\u2665", "5", face_up=True)]
        game.tableau[0] = [Card("\u2660", "6", face_up=True)]
        moves = game.legal_moves()
        assert ("tableau", 0) in moves

    def test_waste_to_storage(self) -> None:
        """Waste card should be movable to first empty storage slot."""
        game = self._empty_game()
        game.waste = [Card("\u2660", "5", face_up=True)]
        moves = game.legal_moves()
        storage_moves = [m for m in moves if isinstance(m, tuple) and m[0] == "storage"]
        assert len(storage_moves) == 1
        assert storage_moves[0] == ("storage", 0)

    def test_tableau_to_tableau(self) -> None:
        """Tableau card should be movable to valid tableau column."""
        game = self._empty_game()
        game.tableau[0] = [Card("\u2665", "5", face_up=True)]
        game.tableau[1] = [Card("\u2660", "6", face_up=True)]
        moves = game.legal_moves()
        assert ("move", ("tableau", 0), ("tableau", 1)) in moves

    def test_tableau_to_foundation(self) -> None:
        """Tableau ace should be movable to foundation."""
        game = self._empty_game()
        game.tableau[0] = [Card("\u2660", "A", face_up=True)]
        moves = game.legal_moves()
        spade_idx = SUITS.index("\u2660")
        assert ("move", ("tableau", 0), ("foundation", spade_idx)) in moves

    def test_tableau_to_storage(self) -> None:
        """Tableau card should be movable to empty storage."""
        game = self._empty_game()
        game.tableau[0] = [Card("\u2660", "5", face_up=True)]
        moves = game.legal_moves()
        storage_moves = [
            m
            for m in moves
            if isinstance(m, tuple) and m[0] == "move" and m[2][0] == "storage"
        ]
        assert len(storage_moves) >= 1

    def test_storage_to_foundation(self) -> None:
        """Storage ace should be movable to foundation."""
        game = self._empty_game()
        game.storage[2] = Card("\u2665", "A", face_up=True)
        moves = game.legal_moves()
        heart_idx = SUITS.index("\u2665")
        assert ("move", ("storage", 2), ("foundation", heart_idx)) in moves

    def test_storage_to_tableau(self) -> None:
        """Storage card should be movable to valid tableau column."""
        game = self._empty_game()
        game.storage[1] = Card("\u2666", "5", face_up=True)
        game.tableau[0] = [Card("\u2663", "6", face_up=True)]
        moves = game.legal_moves()
        assert ("move", ("storage", 1), ("tableau", 0)) in moves

    def test_legal_moves_includes_storage_when_slots_empty(self) -> None:
        """Regression: is_game_over must not miss storage as a valid destination."""
        game = self._empty_game()
        game.tableau[0] = [Card("\u2665", "4", face_up=True)]
        game.tableau[1] = [Card("\u2665", "7", face_up=True)]
        game.storage = [None, None, None, None]
        moves = game.legal_moves()
        storage_moves = [
            m
            for m in moves
            if isinstance(m, tuple) and m[0] == "move" and m[2][0] == "storage"
        ]
        assert len(storage_moves) >= 1

    def test_no_moves_on_truly_dead_board(self) -> None:
        """Board with no valid moves should return empty list."""
        game = self._empty_game()
        red_cards = [
            Card("\u2665", "4", face_up=True),
            Card("\u2666", "7", face_up=True),
            Card("\u2665", "9", face_up=True),
            Card("\u2666", "J", face_up=True),
            Card("\u2665", "Q", face_up=True),
            Card("\u2666", "6", face_up=True),
            Card("\u2665", "8", face_up=True),
        ]
        for i in range(7):
            game.tableau[i] = [red_cards[i]]
        game.storage = [
            Card("\u2666", "5", face_up=True),
            Card("\u2665", "10", face_up=True),
            Card("\u2666", "K", face_up=True),
            Card("\u2665", "7", face_up=True),
        ]
        moves = game.legal_moves()
        assert len(moves) == 0

    def test_all_legal_moves_are_executable(self) -> None:
        """Every move from legal_moves() should succeed in step()."""
        game = OneShotSolitaire(game_id=42)
        for _ in range(5):
            game.step("draw")
        moves = game.legal_moves()
        for move in moves:
            test_game = OneShotSolitaire(game_id=42)
            for _ in range(5):
                test_game.step("draw")
            success, err = test_game.step(move)
            assert success, f"Move {move} should be legal but got error: {err}"


class TestIsGameOver(unittest.TestCase):
    """Tests for the is_game_over method."""

    def _empty_game(self) -> OneShotSolitaire:
        """Create an empty game state for testing."""
        game = OneShotSolitaire(game_id=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.stock = []
        game.waste = []
        return game

    def test_game_over_when_no_moves(self) -> None:
        """Game should be over when no legal moves exist."""
        game = self._empty_game()
        red_cards = [
            Card("\u2665", "4", face_up=True),
            Card("\u2666", "7", face_up=True),
            Card("\u2665", "9", face_up=True),
            Card("\u2666", "J", face_up=True),
            Card("\u2665", "Q", face_up=True),
            Card("\u2666", "6", face_up=True),
            Card("\u2665", "8", face_up=True),
        ]
        for i in range(7):
            game.tableau[i] = [red_cards[i]]
        game.storage = [
            Card("\u2666", "5", face_up=True),
            Card("\u2665", "10", face_up=True),
            Card("\u2666", "K", face_up=True),
            Card("\u2665", "7", face_up=True),
        ]
        assert game.is_game_over()

    def test_not_game_over_with_empty_storage(self) -> None:
        """Game is NOT over if storage has empty slots and cards exist."""
        game = self._empty_game()
        game.tableau[0] = [Card("\u2660", "9", face_up=True)]
        game.storage = [None, None, None, None]
        assert not game.is_game_over()

    def test_not_game_over_with_stock(self) -> None:
        """Game should not be over when stock has cards."""
        game = self._empty_game()
        game.stock = [Card("\u2660", "2")]
        assert not game.is_game_over()

    def test_game_over_on_empty_board(self) -> None:
        """Empty board with nothing to do is game over (also means game is won)."""
        game = self._empty_game()
        assert game.is_game_over()


class TestStateHash(unittest.TestCase):
    """Tests for the state_hash method."""

    def test_same_state_same_hash(self) -> None:
        """Same game_id should produce same hash."""
        game1 = OneShotSolitaire(game_id=42)
        game2 = OneShotSolitaire(game_id=42)
        assert game1.state_hash() == game2.state_hash()

    def test_different_state_different_hash(self) -> None:
        """Different states should produce different hashes."""
        game1 = OneShotSolitaire(game_id=42)
        game2 = OneShotSolitaire(game_id=42)
        game2.step("draw")
        assert game1.state_hash() != game2.state_hash()

    def test_hash_changes_after_move(self) -> None:
        """Hash should change after a move."""
        game = OneShotSolitaire(game_id=42)
        h1 = game.state_hash()
        game.step("draw")
        h2 = game.state_hash()
        assert h1 != h2

    def test_hash_is_int(self) -> None:
        """Hash should be an integer."""
        game = OneShotSolitaire(game_id=42)
        assert isinstance(game.state_hash(), int)


class TestIsEndgame(unittest.TestCase):
    """Tests for the is_endgame method."""

    def _empty_game(self) -> OneShotSolitaire:
        """Create an empty game state for testing."""
        game = OneShotSolitaire(game_id=1)
        game.tableau = [[] for _ in range(7)]
        game.foundations = [[] for _ in range(4)]
        game.storage = [None] * 4
        game.stock = []
        game.waste = []
        return game

    def test_endgame_when_stock_empty_all_face_up(self) -> None:
        """Endgame should be true when stock is empty and all cards face up."""
        game = self._empty_game()
        game.tableau[0] = [
            Card("\u2660", "K", face_up=True),
            Card("\u2665", "Q", face_up=True),
        ]
        assert game.is_endgame()

    def test_not_endgame_when_stock_has_cards(self) -> None:
        """Endgame should be false when stock has cards."""
        game = self._empty_game()
        game.stock = [Card("\u2660", "5")]
        game.tableau[0] = [Card("\u2660", "K", face_up=True)]
        assert not game.is_endgame()

    def test_not_endgame_when_face_down_cards(self) -> None:
        """Endgame should be false when face-down cards exist."""
        game = self._empty_game()
        game.tableau[0] = [
            Card("\u2660", "K", face_up=False),
            Card("\u2665", "Q", face_up=True),
        ]
        assert not game.is_endgame()

    def test_endgame_on_empty_tableau(self) -> None:
        """Endgame should be true on empty tableau with empty stock."""
        game = self._empty_game()
        assert game.is_endgame()


if __name__ == "__main__":
    unittest.main()
