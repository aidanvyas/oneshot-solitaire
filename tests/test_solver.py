"""Integration tests for the Rust expectimax solver subprocess."""

from __future__ import annotations

from pathlib import Path

import pytest

from engine import SUITS, VALUES, Card, OneShotSolitaire
from solver.solver import SolverProcess, _serialize_game_state

SOLVER_BINARY = (
    Path(__file__).parent.parent / "solver" / "target" / "release" / "oneshot-solver"
)

# Tolerance for floating-point win-probability comparisons.
WIN_PROB_TOL = 1e-5


def _solver_available() -> bool:
    return SOLVER_BINARY.exists()


solver_required = pytest.mark.skipif(
    not _solver_available(),
    reason="Solver binary not built. Run: cd solver && cargo build --release",
)


@solver_required
def test_solver_binary_exists() -> None:
    """Solver binary must exist after build."""
    assert SOLVER_BINARY.exists()


@solver_required
def test_query_returns_valid_response() -> None:
    """SolverProcess.query returns a well-formed dict for a fresh game."""
    game = OneShotSolitaire(game_id=42)
    with SolverProcess(timeout_ms=3000) as solver:
        resp = solver.query(game)

    assert "win_probability" in resp
    assert "nodes_visited" in resp
    assert "depth_reached" in resp
    assert "timed_out" in resp
    assert "error" in resp
    assert resp["error"] is None
    assert 0.0 <= resp["win_probability"] <= 1.0


@solver_required
def test_best_move_is_legal() -> None:
    """The solver's best_move_engine must always be in game.legal_moves()."""
    game = OneShotSolitaire(game_id=42)
    with SolverProcess(timeout_ms=3000) as solver:
        resp = solver.query(game)

    move = resp["best_move_engine"]
    assert move is not None
    legal = game.legal_moves()
    assert move in legal, f"Solver returned illegal move {move!r}. Legal: {legal}"


@solver_required
def test_best_move_is_legal_multiple_games() -> None:
    """Solver returns legal moves across several different game IDs."""
    with SolverProcess(timeout_ms=2000) as solver:
        for game_id in [1, 42, 100, 999, 12345]:
            game = OneShotSolitaire(game_id=game_id)
            resp = solver.query(game)
            move = resp["best_move_engine"]
            assert move is not None, f"No move for game_id={game_id}"
            legal = game.legal_moves()
            assert move in legal, (
                f"game_id={game_id}: illegal move {move!r}. Legal: {legal}"
            )


@solver_required
def test_trivially_won_state() -> None:
    """A state where all foundations are complete returns win_prob=1.0 and no move."""
    game = OneShotSolitaire(game_id=1)
    game.tableau = [[] for _ in range(7)]
    game.storage = [None] * 4
    game.stock = []
    game.waste = []
    game.foundations = []
    for suit in SUITS:
        pile = [Card(suit, v, face_up=True) for v in VALUES]
        game.foundations.append(pile)

    with SolverProcess(timeout_ms=1000) as solver:
        resp = solver.query(game)

    assert resp["best_move_engine"] is None
    assert abs(resp["win_probability"] - 1.0) < WIN_PROB_TOL


@solver_required
def test_dead_state_no_moves() -> None:
    """A state with no legal moves (and not won) returns win_prob=0.0."""
    game = OneShotSolitaire(game_id=1)
    game.tableau = [[] for _ in range(7)]
    game.storage = [None] * 4
    game.stock = []
    game.waste = []
    game.foundations = [[] for _ in range(4)]

    assert game.legal_moves() == []

    with SolverProcess(timeout_ms=1000) as solver:
        resp = solver.query(game)

    assert resp["best_move_engine"] is None
    assert abs(resp["win_probability"] - 0.0) < WIN_PROB_TOL


@solver_required
def test_one_move_to_win() -> None:
    """State with exactly one foundation move to win returns that move with prob=1.0."""
    game = OneShotSolitaire(game_id=1)
    game.tableau = [[] for _ in range(7)]
    game.storage = [None] * 4
    game.stock = []
    game.waste = []

    # Fill all foundations except Spades King.
    game.foundations = []
    for suit in SUITS:
        if suit == "♠":
            pile = [Card(suit, v, face_up=True) for v in VALUES[:-1]]
        else:
            pile = [Card(suit, v, face_up=True) for v in VALUES]
        game.foundations.append(pile)

    game.waste = [Card("♠", "K", face_up=True)]

    with SolverProcess(timeout_ms=3000) as solver:
        resp = solver.query(game)

    assert resp["best_move_engine"] == "foundation"
    assert abs(resp["win_probability"] - 1.0) < WIN_PROB_TOL


@solver_required
def test_timeout_returns_move() -> None:
    """Even with a 1ms timeout, the solver returns a valid move (fallback)."""
    game = OneShotSolitaire(game_id=42)
    with SolverProcess(timeout_ms=1) as solver:
        resp = solver.query(game, timeout_ms=1)

    move = resp["best_move_engine"]
    legal = game.legal_moves()
    assert move in legal


@solver_required
def test_context_manager() -> None:
    """SolverProcess works as a context manager."""
    with SolverProcess(timeout_ms=2000) as solver:
        game = OneShotSolitaire(game_id=7)
        resp = solver.query(game)
        assert resp["best_move_engine"] is not None


@solver_required
def test_multiple_sequential_queries() -> None:
    """Solver handles multiple sequential queries without restarting."""
    with SolverProcess(timeout_ms=2000) as solver:
        game = OneShotSolitaire(game_id=42)
        for _ in range(5):
            if game.is_game_over() or game.is_game_won():
                break
            resp = solver.query(game)
            move = resp["best_move_engine"]
            assert move is not None
            legal = game.legal_moves()
            assert move in legal
            game.step(move)


@solver_required
def test_serialize_then_query_matches_legal_moves() -> None:
    """Serialised game state round-trips correctly through the solver protocol."""
    game = OneShotSolitaire(game_id=123)
    state = _serialize_game_state(game)

    assert state["stock_count"] == len(game.stock)
    assert len(state["waste"]) == 1
    assert all(v is None for v in state["foundations"].values())

    with SolverProcess(timeout_ms=2000) as solver:
        resp = solver.query(game)

    assert resp["error"] is None
    assert resp["best_move_engine"] in game.legal_moves()
