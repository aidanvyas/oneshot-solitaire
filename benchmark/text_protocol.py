"""Text protocol for rendering game state and parsing LLM move commands."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine import Card, OnePassSolitaire

SUIT_TO_ASCII: dict[str, str] = {
    "\u2660": "S",
    "\u2665": "H",
    "\u2666": "D",
    "\u2663": "C",
}
SUIT_NAMES: list[str] = ["Spades", "Hearts", "Diamonds", "Clubs"]

# Move type aliases used by the engine
type _Move = str | tuple[str, int] | tuple[str, tuple[str, int], tuple[str, int]]


def card_to_ascii(card: Card) -> str:
    """Convert a Card to ASCII format, e.g. Card('\u2660', 'A') -> 'SA'."""
    return SUIT_TO_ASCII[card.suit] + card.value


def _render_foundations(game: OnePassSolitaire) -> list[str]:
    """Render the foundation piles as text lines."""
    lines: list[str] = ["", "Foundations:"]
    for i, name in enumerate(SUIT_NAMES):
        pile = game.foundations[i]
        if pile:
            cards_str = " ".join(card.value for card in pile)
            lines.append(f"  {name + ':':10s} {cards_str}")
        else:
            lines.append(f"  {name + ':':10s} empty")
    return lines


def _render_storage(game: OnePassSolitaire) -> list[str]:
    """Render the storage slots as text lines."""
    parts: list[str] = []
    for slot in game.storage:
        if slot is None:
            parts.append("[empty]")
        else:
            parts.append(f"[{card_to_ascii(slot)}]")
    return ["", "Storage: " + " ".join(parts)]


def _render_tableau(game: OnePassSolitaire) -> list[str]:
    """Render the tableau columns as text lines."""
    lines: list[str] = ["", "Tableau:"]
    for col_idx, column in enumerate(game.tableau):
        if not column:
            lines.append(f"  Col {col_idx + 1}: [empty]")
        else:
            parts: list[str] = []
            for card in column:
                if card.face_up:
                    parts.append(card_to_ascii(card))
                else:
                    parts.append("??")
            lines.append(
                f"  Col {col_idx + 1}: {' '.join(parts)}",
            )
    return lines


def render_game_state(
    game: OnePassSolitaire,
    turn_number: int = 0,
) -> str:
    """Produce a text representation of the game state for an LLM."""
    lines: list[str] = []

    lines.append(f"=== GAME STATE (Turn {turn_number}) ===")
    lines.append(f"Stock: {len(game.stock)} cards remaining")

    if game.waste:
        lines.append(f"Waste: {card_to_ascii(game.waste[-1])}")
    else:
        lines.append("Waste: empty")

    lines.extend(_render_foundations(game))
    lines.extend(_render_storage(game))
    lines.extend(_render_tableau(game))

    lines.append("")
    lines.append("Your move:")

    return "\n".join(lines)


def _parse_move_command(
    cleaned: str,
) -> _Move | None:
    """Parse an 'm' (move) command from cleaned text."""
    m_match = re.search(
        r"\bm\s+([ts])(\d+)\s+([tsf])(\d*)\b",
        cleaned,
        re.IGNORECASE,
    )
    if not m_match:
        return None

    src_type = m_match.group(1).lower()
    src_num = int(m_match.group(2))
    dst_type = m_match.group(3).lower()
    dst_num_str = m_match.group(4)

    source: tuple[str, int] = (
        ("tableau", src_num - 1) if src_type == "t" else ("storage", src_num - 1)
    )

    dest: tuple[str, int]
    if dst_type == "f":
        dest = ("foundation", -1)
    elif dst_type == "t":
        dest = ("tableau", int(dst_num_str) - 1)
    else:
        dest = ("storage", int(dst_num_str) - 1)

    return ("move", source, dest)


def _pick_simple_command(
    cleaned: str,
) -> _Move | None:
    """Pick the best simple command (d/f/t/s) from the text."""
    t_match = re.search(r"\bt\s*(\d+)\b", cleaned, re.IGNORECASE)
    s_match = re.search(r"\bs\s*(\d+)\b", cleaned, re.IGNORECASE)
    f_match = re.search(r"\bf\b", cleaned, re.IGNORECASE)
    d_match = re.search(r"\bd\b", cleaned, re.IGNORECASE)

    candidates: list[tuple[str, int, re.Match[str]]] = []
    if t_match:
        candidates.append(("t", t_match.start(), t_match))
    if s_match:
        candidates.append(("s", s_match.start(), s_match))
    if f_match:
        candidates.append(("f", f_match.start(), f_match))
    if d_match:
        candidates.append(("d", d_match.start(), d_match))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[1], reverse=True)
    best = candidates[0]

    if best[0] == "t":
        return ("tableau", int(best[2].group(1)) - 1)
    if best[0] == "s":
        return ("storage", int(best[2].group(1)) - 1)
    if best[0] == "f":
        return "foundation"
    return "draw"


def parse_move(text: str | None) -> _Move | None:
    """Parse a move command from LLM text output.

    Returns a move tuple or None.
    """
    if text is None:
        return None

    text = text.strip()
    if not text:
        return None

    cleaned = " ".join(text.split())

    move_cmd = _parse_move_command(cleaned)
    if move_cmd is not None:
        return move_cmd

    return _pick_simple_command(cleaned)
