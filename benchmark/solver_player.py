"""Benchmark player backed by the Rust expectimax solver."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from solver.solver import SolverProcess

if TYPE_CHECKING:
    from engine import OneShotSolitaire

# Default per-move time budget for the solver.
DEFAULT_TIMEOUT_MS = 5000


class SolverPlayer:
    """Wraps SolverProcess to implement the same interface as LLMPlayer.

    Compatible with BenchmarkRunner — drop-in replacement for the LLM players
    used in text/tools modes.
    """

    def __init__(self, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> None:
        """Initialise the solver player with a per-move timeout."""
        self.timeout_ms = timeout_ms
        self._solver = SolverProcess(timeout_ms=timeout_ms)
        self.last_win_probability: float = 0.0
        self.last_nodes_visited: int = 0
        self.last_depth_reached: int = 0
        self.last_timed_out: bool = False

    def get_move(
        self,
        game: OneShotSolitaire,
    ) -> tuple[str | tuple | None, dict[str, int]]:
        """Query the solver for the best move.

        Returns:
            (move, token_usage) — token_usage is always zero for the solver
            (it has no API cost), but the dict shape matches LLMPlayer.

        """
        resp = self._solver.query(game, timeout_ms=self.timeout_ms)
        self.last_win_probability = resp.get("win_probability", 0.0)
        self.last_nodes_visited = resp.get("nodes_visited", 0)
        self.last_depth_reached = resp.get("depth_reached", 0)
        self.last_timed_out = resp.get("timed_out", False)

        move = resp.get("best_move_engine")

        # Zero token usage — solver has no API cost.
        token_usage: dict[str, int] = {
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "reasoning_tokens": 0,
            "output_tokens": 0,
        }
        return move, token_usage

    def reset(self) -> None:
        """Reset per-game state (solver is stateless between moves)."""

    def close(self) -> None:
        """Shut down the solver subprocess."""
        self._solver.close()

    def __enter__(self) -> Self:
        """Return self for use as a context manager."""
        return self

    def __exit__(self, *_: object) -> None:
        """Close the solver on context exit."""
        self.close()
