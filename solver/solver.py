"""Python wrapper for the Rust expectimax solver subprocess.

Usage::

    from solver.solver import get_solver

    solver = get_solver()
    result = solver.query(game)
    best_move = result["best_move_engine"]  # Python engine move format
    win_prob  = result["win_probability"]
"""

from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    from engine import OneShotSolitaire

from engine import SUITS

SOLVER_BINARY = Path(__file__).parent / "target" / "release" / "oneshot-solver"

# Card suit translations: Python unicode ↔ Rust letter.
SUIT_TO_LETTER: dict[str, str] = {"♠": "S", "♥": "H", "♦": "D", "♣": "C"}


# ── Card serialisation ────────────────────────────────────────────────────────


def _card_to_str(card: Any) -> str:  # noqa: ANN401
    """Convert a Python Card to solver string format, e.g. '♠A' → 'SA'."""
    return SUIT_TO_LETTER[card.suit] + card.value


# ── Move serialisation (Python engine format → solver JSON) ───────────────────


def _move_to_dict(move: str | tuple) -> dict[str, Any]:
    """Translate a Python engine move to solver JSON move format."""
    if move == "draw":
        return {"type": "draw"}
    if move == "foundation":
        return {"type": "foundation"}
    if isinstance(move, tuple):
        tag = move[0]
        if tag == "tableau":
            return {"type": "tableau", "col": move[1]}
        if tag == "storage":
            return {"type": "storage", "slot": move[1]}
        if tag == "move":
            src = move[1]
            dst = move[2]
            return {
                "type": "move",
                "src": [src[0], src[1]],
                "dest": [dst[0], dst[1]],
            }
    msg = f"Unknown move format: {move!r}"
    raise ValueError(msg)


# ── Move deserialisation (solver JSON → Python engine format) ─────────────────


def _move_from_dict(d: dict[str, Any]) -> str | tuple:
    """Translate a solver JSON move dict back to a Python engine move."""
    t = d.get("type")
    if t == "draw":
        return "draw"
    if t == "foundation":
        return "foundation"
    if t == "tableau":
        return ("tableau", int(d["col"]))
    if t == "storage":
        return ("storage", int(d["slot"]))
    if t == "move":
        src_zone, src_idx = d["src"]
        dest_zone, dest_idx = d["dest"]
        src = (str(src_zone), int(src_idx))
        dst = (str(dest_zone), int(dest_idx))
        return ("move", src, dst)
    msg = f"Unknown move type in solver response: {d!r}"
    raise ValueError(msg)


# ── Game state serialisation ──────────────────────────────────────────────────


def _serialize_game_state(game: OneShotSolitaire) -> dict[str, Any]:
    """Serialize the visible game state for the solver."""
    # Tableau: one entry per column with hidden_count and face-up top.
    tableau = []
    for col in game.tableau:
        face_up_cards = [c for c in col if c.face_up]
        hidden_count = sum(1 for c in col if not c.face_up)
        top = _card_to_str(face_up_cards[-1]) if face_up_cards else None
        tableau.append({"hidden_count": hidden_count, "top": top})

    # Foundations: suit letter → top card string or None.
    foundations: dict[str, str | None] = {}
    for i, suit in enumerate(SUITS):
        letter = SUIT_TO_LETTER[suit]
        pile = game.foundations[i]
        foundations[letter] = _card_to_str(pile[-1]) if pile else None

    # Storage slots.
    storage: list[str | None] = [
        _card_to_str(c) if c is not None else None for c in game.storage
    ]

    # Waste pile: full pile bottom→top (all face-up).
    waste = [_card_to_str(c) for c in game.waste]

    return {
        "tableau": tableau,
        "foundations": foundations,
        "storage": storage,
        "waste": waste,
        "stock_count": len(game.stock),
    }


# ── SolverProcess ─────────────────────────────────────────────────────────────


class SolverProcess:
    """Manages the Rust solver subprocess with a persistent stdin/stdout pipe."""

    def __init__(self, timeout_ms: int = 5000) -> None:
        """Initialise and launch the solver subprocess."""
        self.default_timeout_ms = timeout_ms
        self._lock = threading.Lock()
        if not SOLVER_BINARY.exists():
            msg = (
                f"Solver binary not found at {SOLVER_BINARY}.\n"
                "Run: cd solver && cargo build --release"
            )
            raise FileNotFoundError(msg)
        self._proc = subprocess.Popen(  # noqa: S603
            [str(SOLVER_BINARY)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    def query(
        self,
        game: OneShotSolitaire,
        timeout_ms: int | None = None,
    ) -> dict[str, Any]:
        """Query the solver for the best move in the given game state.

        Returns a dict with keys:
            best_move_engine: Python engine move format (or None)
            win_probability: float in [0.0, 1.0]
            nodes_visited: int
            depth_reached: int
            timed_out: bool
            error: str | None
        """
        t_ms = timeout_ms if timeout_ms is not None else self.default_timeout_ms
        request = {
            "game_state": _serialize_game_state(game),
            "timeout_ms": t_ms,
        }
        line = json.dumps(request) + "\n"

        with self._lock:
            if self._proc.poll() is not None:
                msg = "Solver process has died"
                raise RuntimeError(msg)
            assert self._proc.stdin is not None
            assert self._proc.stdout is not None
            self._proc.stdin.write(line)
            self._proc.stdin.flush()
            response_line = self._proc.stdout.readline()

        if not response_line:
            msg = "Solver process closed stdout unexpectedly"
            raise RuntimeError(msg)

        resp: dict[str, Any] = json.loads(response_line)

        # Translate best_move back to Python engine format.
        raw_move = resp.get("best_move")
        if raw_move is not None:
            try:
                resp["best_move_engine"] = _move_from_dict(raw_move)
            except ValueError as e:
                resp["best_move_engine"] = None
                resp["error"] = str(e)
        else:
            resp["best_move_engine"] = None

        return resp

    def clear_cache(self) -> None:
        """Tell the solver to clear its transposition table."""
        with self._lock:
            assert self._proc.stdin is not None
            assert self._proc.stdout is not None
            self._proc.stdin.write('{"type":"clear_cache"}\n')
            self._proc.stdin.flush()
            self._proc.stdout.readline()

    def close(self) -> None:
        """Terminate the solver process gracefully."""
        try:
            self._proc.terminate()
            self._proc.wait(timeout=2)
        except OSError:
            self._proc.kill()

    def __enter__(self) -> Self:
        """Return self for use as a context manager."""
        return self

    def __exit__(self, *_: object) -> None:
        """Close the solver process on context exit."""
        self.close()


# ── Module-level singleton ────────────────────────────────────────────────────

_default_solver: SolverProcess | None = None
_solver_lock = threading.Lock()


def get_solver(timeout_ms: int = 5000) -> SolverProcess:
    """Get or create the default solver singleton."""
    global _default_solver  # noqa: PLW0603
    with _solver_lock:
        if _default_solver is None:
            _default_solver = SolverProcess(timeout_ms=timeout_ms)
    return _default_solver


def close_solver() -> None:
    """Shut down the default solver singleton if it exists."""
    global _default_solver  # noqa: PLW0603
    with _solver_lock:
        if _default_solver is not None:
            _default_solver.close()
            _default_solver = None
