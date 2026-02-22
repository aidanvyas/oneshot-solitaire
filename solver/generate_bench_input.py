"""Generate a challenging mid-game solver request for profiling.

Plays a few moves into game_id=42, then emits a single JSON request
with a long timeout so the search dominates the profile.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow importing from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import OneShotSolitaire
from solver.solver import _serialize_game_state

GAME_ID = 42
SETUP_DRAWS = 5
TIMEOUT_MS = 10_000


def main() -> None:
    """Generate and print a single solver request JSON line."""
    game = OneShotSolitaire(game_id=GAME_ID)

    # Draw a few cards so the solver faces a non-trivial mid-game state.
    for _ in range(SETUP_DRAWS):
        success, _ = game.step("draw")
        if not success:
            break

    request = {
        "game_state": _serialize_game_state(game),
        "timeout_ms": TIMEOUT_MS,
    }
    sys.stdout.write(json.dumps(request) + "\n")


if __name__ == "__main__":
    main()
