import re

SUIT_TO_ASCII = {'♠': 'S', '♥': 'H', '♦': 'D', '♣': 'C'}
SUIT_NAMES = ['Spades', 'Hearts', 'Diamonds', 'Clubs']


def card_to_ascii(card):
    """Convert a Card to ASCII format, e.g. Card('♠', 'A') -> 'SA'."""
    return SUIT_TO_ASCII[card.suit] + card.value


def render_game_state(game, turn_number=0):
    """Produce a text representation of the game state for an LLM."""
    lines = []

    lines.append(f"=== GAME STATE (Turn {turn_number}) ===")

    # Stock
    lines.append(f"Stock: {len(game.stock)} cards remaining")

    # Waste
    if game.waste:
        lines.append(f"Waste: {card_to_ascii(game.waste[-1])}")
    else:
        lines.append("Waste: empty")

    # Foundations
    lines.append("")
    lines.append("Foundations:")
    for i, name in enumerate(SUIT_NAMES):
        pile = game.foundations[i]
        if pile:
            cards_str = " ".join(card.value for card in pile)
            lines.append(f"  {name + ':':10s} {cards_str}")
        else:
            lines.append(f"  {name + ':':10s} empty")

    # Storage
    lines.append("")
    storage_parts = []
    for slot in game.storage:
        if slot is None:
            storage_parts.append("[empty]")
        else:
            storage_parts.append(f"[{card_to_ascii(slot)}]")
    lines.append("Storage: " + " ".join(storage_parts))

    # Tableau
    lines.append("")
    lines.append("Tableau:")
    for col_idx, column in enumerate(game.tableau):
        if not column:
            lines.append(f"  Col {col_idx + 1}: [empty]")
        else:
            parts = []
            for card in column:
                if card.face_up:
                    parts.append(card_to_ascii(card))
                else:
                    parts.append("??")
            lines.append(f"  Col {col_idx + 1}: {' '.join(parts)}")

    lines.append("")
    lines.append("Your move:")

    return "\n".join(lines)


def parse_move(text):
    """Parse a move command from LLM text output. Returns a move tuple or None."""
    if text is None:
        return None

    text = text.strip()
    if not text:
        return None

    # Normalize whitespace
    cleaned = " ".join(text.split())

    # Try 'm' (move) commands first — most complex
    m_match = re.search(
        r'\bm\s+([ts])(\d+)\s+([tsf])(\d*)\b',
        cleaned,
        re.IGNORECASE,
    )
    if m_match:
        src_type = m_match.group(1).lower()
        src_num = int(m_match.group(2))
        dst_type = m_match.group(3).lower()
        dst_num_str = m_match.group(4)

        if src_type == 't':
            source = ('tableau', src_num - 1)
        else:
            source = ('storage', src_num - 1)

        if dst_type == 'f':
            dest = ('foundation', -1)
        elif dst_type == 't':
            dest = ('tableau', int(dst_num_str) - 1)
        else:
            dest = ('storage', int(dst_num_str) - 1)

        return ('move', source, dest)

    # Try 't N' (tableau) command
    t_match = re.search(r'\bt\s*(\d+)\b', cleaned, re.IGNORECASE)
    # Try 's N' (storage) command
    s_match = re.search(r'\bs\s*(\d+)\b', cleaned, re.IGNORECASE)

    # Try 'f' (foundation) command
    f_match = re.search(r'\bf\b', cleaned, re.IGNORECASE)

    # Try 'd' (draw) command
    d_match = re.search(r'\bd\b', cleaned, re.IGNORECASE)

    # Decide among t, s, f, d — prefer the one that appears latest in the text
    # (the actual command is usually at the end for LLM responses)
    candidates = []
    if t_match:
        candidates.append(('t', t_match.start(), t_match))
    if s_match:
        candidates.append(('s', s_match.start(), s_match))
    if f_match:
        candidates.append(('f', f_match.start(), f_match))
    if d_match:
        candidates.append(('d', d_match.start(), d_match))

    if not candidates:
        return None

    # Pick the last match in the string (most likely to be the actual command)
    candidates.sort(key=lambda x: x[1], reverse=True)
    best = candidates[0]

    if best[0] == 't':
        col = int(best[2].group(1))
        return ('tableau', col - 1)
    elif best[0] == 's':
        space = int(best[2].group(1))
        return ('storage', space - 1)
    elif best[0] == 'f':
        return 'foundation'
    elif best[0] == 'd':
        return 'draw'

    return None
