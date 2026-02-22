"""FastAPI backend for One-Shot Solitaire web UI."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine import (
    NUM_TABLEAU_COLS,
    Card,
    OneShotSolitaire,
)

app = FastAPI()

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# In-memory game sessions
games: dict[str, OneShotSolitaire] = {}


# --- Request / response models ---


class NewGameRequest(BaseModel):
    """Request body for creating a new game."""

    game_id: int | None = None


class MoveRequest(BaseModel):
    """Request body for making a move."""

    type: str
    col: int | None = None
    slot: int | None = None
    src: list | None = None
    dest: list | None = None
    src_col: int | None = None
    dest_col: int | None = None
    count: int | None = None
    foundation_idx: int | None = None


# --- Helpers ---


def _serialize_card(card: Card, *, hide: bool = False) -> dict[str, Any]:
    """Serialize a card to JSON, hiding face-down info."""
    if hide or not card.face_up:
        return {"face_up": False}
    return {
        "suit": card.suit,
        "value": card.value,
        "face_up": True,
    }


def _serialize_state(game: OneShotSolitaire) -> dict[str, Any]:
    """Serialize full game state to JSON."""
    tableau = [[_serialize_card(c) for c in col] for col in game.tableau]

    foundations = []
    for pile in game.foundations:
        if pile:
            foundations.append(
                [{"suit": c.suit, "value": c.value, "face_up": True} for c in pile],
            )
        else:
            foundations.append([])

    storage = []
    for card in game.storage:
        if card:
            storage.append({"suit": card.suit, "value": card.value, "face_up": True})
        else:
            storage.append(None)

    waste_top = None
    if game.waste:
        c = game.waste[-1]
        waste_top = {"suit": c.suit, "value": c.value, "face_up": True}

    return {
        "tableau": tableau,
        "foundations": foundations,
        "storage": storage,
        "waste_top": waste_top,
        "waste_count": len(game.waste),
        "stock_count": len(game.stock),
        "foundation_count": game.foundation_count(),
        "is_won": game.is_game_won(),
        "is_over": game.is_game_over(),
        "is_repetition_draw": game.is_repetition_draw(),
        "is_endgame": game.is_endgame(),
    }


def _get_game(game_id: str) -> OneShotSolitaire:
    """Look up a game by ID or raise 404."""
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    return games[game_id]


def _translate_move(payload: MoveRequest) -> str | tuple:
    """Translate a JSON move payload into the engine's move format."""
    if payload.type == "draw":
        return "draw"
    if payload.type == "foundation":
        return "foundation"
    if payload.type == "tableau":
        return ("tableau", payload.col)
    if payload.type == "storage":
        return ("storage", payload.slot)
    if payload.type == "move":
        src = tuple(payload.src)
        dest = tuple(payload.dest)
        return ("move", src, dest)
    if payload.type == "foundation_to_tableau":
        return (
            "move",
            ("foundation", payload.foundation_idx),
            ("tableau", payload.col),
        )
    msg = f"Unknown move type: {payload.type}"
    raise HTTPException(status_code=400, detail=msg)


def _validate_stack_bounds(
    src_col: int,
    dest_col: int,
    count: int,
    col_len: int,
) -> str | None:
    """Validate column indices and count for a stack move."""
    if not (0 <= src_col < NUM_TABLEAU_COLS and 0 <= dest_col < NUM_TABLEAU_COLS):
        return "Invalid column index"
    if src_col == dest_col:
        return "Source and destination are the same"
    if count < 1 or count > col_len:
        return "Invalid card count"
    return None


def _validate_stack_sequence(
    game: OneShotSolitaire,
    src_col: int,
    dest_col: int,
    count: int,
) -> str | None:
    """Validate that the sub-pile forms a legal stack and can be placed."""
    column = game.tableau[src_col]
    start_idx = len(column) - count

    if any(not column[i].face_up for i in range(start_idx, len(column))):
        return "Cannot move face-down cards"

    for i in range(start_idx, len(column) - 1):
        a, b = column[i], column[i + 1]
        if a.get_color() == b.get_color():
            return "Stack is not alternating colors"
        if a.get_value_index() != b.get_value_index() + 1:
            return "Stack is not in descending order"

    if not game.is_valid_tableau_move(column[start_idx], dest_col):
        return "Invalid tableau move"

    return None


def _execute_stack_move(
    game: OneShotSolitaire,
    src_col: int,
    dest_col: int,
    count: int,
) -> tuple[bool, str | None]:
    """Execute a multi-card tableau-to-tableau stack move.

    The engine doesn't support this natively, so we splice directly
    (same approach as the Pygame GUI).
    """
    error = _validate_stack_bounds(src_col, dest_col, count, len(game.tableau[src_col]))
    if not error:
        error = _validate_stack_sequence(game, src_col, dest_col, count)
    if error:
        return False, error

    column = game.tableau[src_col]
    start_idx = len(column) - count

    game.tableau[dest_col].extend(column[start_idx:])
    del column[start_idx:]

    if column and not column[-1].face_up:
        column[-1].flip()

    return True, None


def _format_move_hint(move: str | tuple, game: OneShotSolitaire) -> dict[str, Any]:
    """Format a legal move as a JSON-friendly hint."""
    if move == "draw":
        return {"type": "draw", "description": "Draw a card from stock"}
    if move == "foundation":
        card = game.waste[-1]
        return {
            "type": "foundation",
            "description": f"Move {card.suit}{card.value} from waste to foundation",
        }
    if isinstance(move, tuple):
        if move[0] == "tableau":
            card = game.waste[-1]
            return {
                "type": "tableau",
                "col": move[1],
                "description": (
                    f"Move {card.suit}{card.value} from waste to tableau {move[1] + 1}"
                ),
            }
        if move[0] == "storage":
            card = game.waste[-1]
            return {
                "type": "storage",
                "slot": move[1],
                "description": (
                    f"Move {card.suit}{card.value} from waste to storage {move[1] + 1}"
                ),
            }
        if move[0] == "move":
            src, dest = move[1], move[2]
            if src[0] == "tableau":
                card = game.tableau[src[1]][-1]
            else:
                card = game.storage[src[1]]
            return {
                "type": "move",
                "src": list(src),
                "dest": list(dest),
                "description": (
                    f"Move {card.suit}{card.value}"
                    f" from {src[0]} {src[1] + 1}"
                    f" to {dest[0]} {dest[1] + 1}"
                ),
            }
    return {"type": "unknown", "description": str(move)}


# --- Routes ---


@app.get("/")
async def index() -> FileResponse:
    """Serve the main HTML page."""
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/rules")
async def rules() -> FileResponse:
    """Serve the rules markdown file."""
    rules_path = Path(__file__).parent.parent / "rules.md"
    if not rules_path.exists():
        raise HTTPException(status_code=404, detail="Rules file not found")
    return FileResponse(str(rules_path), media_type="text/plain")


@app.post("/api/new-game")
async def new_game(req: NewGameRequest | None = None) -> dict[str, Any]:
    """Create a new game session."""
    requested_id = req.game_id if req else None
    game = OneShotSolitaire(game_id=requested_id)
    session_id = str(uuid.uuid4())
    games[session_id] = game
    return {
        "game_id": session_id,
        "deal_id": game.game_id,
        "state": _serialize_state(game),
    }


@app.get("/api/state/{game_id}")
async def get_state(game_id: str) -> dict[str, Any]:
    """Get the current game state."""
    game = _get_game(game_id)
    return {"state": _serialize_state(game)}


@app.post("/api/move/{game_id}")
async def make_move(game_id: str, req: MoveRequest) -> dict[str, Any]:
    """Execute a move on the game."""
    game = _get_game(game_id)

    if req.type == "stack_move":
        success, error = _execute_stack_move(
            game,
            req.src_col,
            req.dest_col,
            req.count,
        )
    else:
        move = _translate_move(req)
        success, error = game.step(move)

    return {
        "success": success,
        "error": error,
        "state": _serialize_state(game),
    }


@app.post("/api/reset/{game_id}")
async def reset_game(game_id: str) -> dict[str, Any]:
    """Reset the game to its initial state (same deal)."""
    game = _get_game(game_id)
    game.reset_game()
    return {"state": _serialize_state(game)}


def _is_useful_hint(move: str | tuple, game: OneShotSolitaire) -> bool:
    """Filter out tableau-to-tableau moves that are provably pointless.

    Only filters the one case that never helps: moving a lone King to an
    empty column (the board state is identical afterward).  Other shuffles
    that don't reveal a face-down card *might* still enable future plays,
    so we keep them until the solver can grade moves properly.
    """
    if not isinstance(move, tuple) or move[0] != "move":
        return True
    src, dest = move[1], move[2]
    if src[0] != "tableau" or dest[0] != "tableau":
        return True
    src_col = game.tableau[src[1]]
    dest_col = game.tableau[dest[1]]
    # Lone King to empty column — pure shuffle, always pointless
    return not (len(src_col) == 1 and not dest_col)


@app.get("/api/hints/{game_id}")
async def get_hints(game_id: str) -> dict[str, Any]:
    """Get useful legal moves as hints (filters pointless shuffles)."""
    game = _get_game(game_id)
    moves = game.legal_moves()
    useful = [m for m in moves if _is_useful_hint(m, game)]
    # Fall back to all moves if filtering removed everything
    filtered = useful or moves
    hints = [_format_move_hint(m, game) for m in filtered]
    return {"hints": hints}
