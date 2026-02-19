"""Pygame GUI for One-Shot Solitaire."""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pygame

from engine import SUITS, Card, OneShotSolitaire

# Initialize pygame
pygame.init()

# Constants
SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 700
CARD_WIDTH = 80
CARD_HEIGHT = 120
CARD_SPACING = 30
MARGIN = 20
FONT_SIZE = 20

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 128, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
LIGHT_GRAY = (220, 220, 220)
DARKER_GRAY = (180, 180, 180)

FELT_GREEN = (4, 102, 36)
CARD_BORDER_R = 8
SHADOW_COLOR = (0, 0, 0, 90)
SHADOW_OFFSET = (4, 4)
TITLE_FONT = pygame.font.SysFont("Arial", 24, bold=True)

# Rules + hint button constants
RULE_BUTTON_RECT = pygame.Rect(SCREEN_WIDTH - 110, SCREEN_HEIGHT - 50, 100, 35)
HINT_BUTTON_RECT = pygame.Rect(SCREEN_WIDTH - 220, SCREEN_HEIGHT - 50, 100, 35)
BUTTON_COLOR = (255, 255, 255)
_ANTIALIAS = True
MIN_NUMBERED_ITEM_LEN = 3
WASTE_BADGE_THRESHOLD = 3
RULE_BUTTON_TEXT = TITLE_FONT.render("Rules", _ANTIALIAS, BLACK)
HINT_BUTTON_TEXT = TITLE_FONT.render("Hint", _ANTIALIAS, BLACK)

# Rules panel constants
RULE_BOX_W = SCREEN_WIDTH - 220
RULE_BOX_H = SCREEN_HEIGHT - 180
RULE_TITLE_FONT = pygame.font.SysFont("Arial", 30, bold=True)
RULE_H1_FONT = pygame.font.SysFont("Arial", 24, bold=True)
RULE_H2_FONT = pygame.font.SysFont("Arial", 21, bold=True)
RULE_FONT = pygame.font.SysFont("Arial", 19)
RULE_SCROLL_STEP = 30
RULE_PANEL_BG = (250, 250, 250)
RULE_PANEL_BORDER = (40, 40, 40)
RULE_PANEL_ACCENT = (18, 84, 46)
RULE_TEXT = (20, 20, 20)
RULE_MUTED = (90, 90, 90)
AUTO_FINISH_STEP_FRAMES = 12

# Suit render colors (pygame color tuples for rendering)
SUIT_RENDER_COLORS = {"\u2660": BLACK, "\u2663": BLACK, "\u2665": RED, "\u2666": RED}

# Set up the display
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("One-Shot Solitaire")
clock = pygame.time.Clock()

font = pygame.font.SysFont("Arial", FONT_SIZE)

# ---- Card rendering (cached surfaces) ----

# Card back surface
card_back = pygame.Surface((CARD_WIDTH, CARD_HEIGHT), pygame.SRCALPHA)
card_back.fill((0, 0, 0, 0))
pygame.draw.rect(card_back, BLUE, card_back.get_rect(), border_radius=CARD_BORDER_R)
pygame.draw.rect(
    card_back,
    WHITE,
    card_back.get_rect(),
    2,
    border_radius=CARD_BORDER_R,
)
for x in range(-CARD_HEIGHT, CARD_WIDTH, 10):
    pygame.draw.line(
        card_back,
        (255, 255, 255, 30),
        (x, 0),
        (x + CARD_HEIGHT, CARD_HEIGHT),
        2,
    )

_card_surface_cache: dict[tuple[str, str], pygame.Surface] = {}


def _make_face_surface(suit: str, value: str) -> pygame.Surface:
    """Create the surface for a face-up card."""
    surf = pygame.Surface((CARD_WIDTH, CARD_HEIGHT), pygame.SRCALPHA)
    # Subtle shadow (clips to surface bounds)
    shadow_rect = surf.get_rect().move(*SHADOW_OFFSET)
    pygame.draw.rect(surf, SHADOW_COLOR, shadow_rect, border_radius=CARD_BORDER_R)
    # Card face
    pygame.draw.rect(surf, WHITE, surf.get_rect(), border_radius=CARD_BORDER_R)
    pygame.draw.rect(surf, BLACK, surf.get_rect(), 2, border_radius=CARD_BORDER_R)

    color = SUIT_RENDER_COLORS[suit]
    val_txt = font.render(value, _ANTIALIAS, color)
    suit_txt = font.render(suit, _ANTIALIAS, color)
    surf.blit(val_txt, (6, 4))
    surf.blit(suit_txt, (6, 22))

    # Upside-down corners
    surf.blit(
        pygame.transform.rotate(val_txt, 180),
        (
            CARD_WIDTH - 6 - val_txt.get_width(),
            CARD_HEIGHT - 4 - val_txt.get_height(),
        ),
    )
    surf.blit(
        pygame.transform.rotate(suit_txt, 180),
        (
            CARD_WIDTH - 6 - suit_txt.get_width(),
            CARD_HEIGHT - 22 - suit_txt.get_height(),
        ),
    )

    # Large center glyph
    big = pygame.font.SysFont("Arial", FONT_SIZE * 2, bold=True)
    center = big.render(suit, _ANTIALIAS, color)
    surf.blit(center, center.get_rect(center=surf.get_rect().center))
    return surf


def get_card_surface(card: Card) -> pygame.Surface:
    """Get the cached surface for a card."""
    if not card.face_up:
        return card_back
    key = (card.suit, card.value)
    if key not in _card_surface_cache:
        _card_surface_cache[key] = _make_face_surface(card.suit, card.value)
    return _card_surface_cache[key]


def draw_card(
    surface: pygame.Surface,
    card: Card,
    pos: tuple[int, int],
) -> None:
    """Draw a card at the given position."""
    surface.blit(get_card_surface(card), pos)


def _load_rules() -> list[str]:
    """Load the rules text from rules.md."""
    try:
        return Path("rules.md").read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return ["Rules file not found."]


class OneShotSolitaireGUI:
    """Pygame-based graphical interface for One-Shot Solitaire."""

    def __init__(self) -> None:
        """Initialize the GUI and start a new game."""
        self.game = OneShotSolitaire()
        self.card_being_dragged: Card | None = None
        self.drag_pile: list[Card] = []
        self.drag_from: tuple[str, int] | None = None
        self.drag_offset = (0, 0)
        self.calculate_positions()
        self.message = ""
        self.message_timer = 0
        self.game_over = False
        self.game_won = False
        self.auto_finish_active = False
        self.auto_finish_timer = 0
        self.confetti: list[dict] = []
        self.confetti_started = False

        self.rules_text = _load_rules()
        self.show_rules = False
        self.show_hint = False
        self.hint_text: list[str] = []
        self.hint_scroll = 0
        self.max_hint_scroll = 0
        self.rule_scroll = 0
        self.max_rule_scroll = 0

    def reset_game(self) -> None:
        """Reset the game and all GUI state."""
        self.game.reset_game()
        self.card_being_dragged = None
        self.drag_pile = []
        self.drag_from = None
        self.message = ""
        self.game_over = False
        self.game_won = False
        self.auto_finish_active = False
        self.auto_finish_timer = 0
        self.confetti = []
        self.confetti_started = False

        self.rules_text = _load_rules()
        self.show_rules = False
        self.show_hint = False
        self.hint_text = []
        self.hint_scroll = 0
        self.max_hint_scroll = 0
        self.rule_scroll = 0
        self.max_rule_scroll = 0

    def _wrap_text(
        self,
        text: str,
        f: pygame.font.Font,
        max_w: int,
    ) -> list[str]:
        """Wrap text to fit within a given pixel width."""
        if not text:
            return [""]
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            if f.size(test)[0] <= max_w:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def _parse_rule_line(self, raw: str) -> tuple:
        """Parse a single markdown rule line into a tagged tuple."""
        raw = raw.rstrip()
        if raw.startswith("### "):
            return ("h2", raw[4:])
        if raw.startswith("## "):
            return ("h1", raw[3:])
        if raw.startswith("# "):
            return ("h1", raw[2:])
        stripped = raw.lstrip()
        if stripped.startswith("- "):
            return ("bullet", stripped[2:])
        if (
            len(stripped) >= MIN_NUMBERED_ITEM_LEN
            and stripped[0].isdigit()
            and stripped[1:3] == ". "
        ):
            return ("number", stripped[0], stripped[3:])
        return ("text", raw)

    def _render_rule_line(
        self,
        kind: str,
        payload: str | tuple[str, str],
        max_w: int,
    ) -> list[tuple]:
        """Render a parsed rule line into font/text/color/gap tuples."""
        lines: list[tuple] = []
        if kind == "h1":
            lines.append((RULE_H1_FONT, payload, RULE_TEXT, 10))
        elif kind == "h2":
            lines.append((RULE_H2_FONT, payload, RULE_TEXT, 8))
        elif kind == "bullet":
            bullet = "\u2022"
            body_lines = self._wrap_text(str(payload), RULE_FONT, max_w - 18)
            for i, line in enumerate(body_lines):
                prefix = f"{bullet} " if i == 0 else "  "
                lines.append((RULE_FONT, prefix + line, RULE_TEXT, 4))
        elif kind == "number":
            num, text = payload
            body_lines = self._wrap_text(text, RULE_FONT, max_w - 26)
            for i, line in enumerate(body_lines):
                prefix = f"{num}. " if i == 0 else "   "
                lines.append((RULE_FONT, prefix + line, RULE_TEXT, 4))
        else:
            lines.extend(
                (RULE_FONT, line, RULE_TEXT, 4)
                for line in self._wrap_text(str(payload), RULE_FONT, max_w)
            )
        return lines

    def calculate_positions(self) -> None:
        """Calculate screen positions for all card areas."""
        self.stock_pos = (MARGIN, MARGIN)
        self.waste_pos = (MARGIN + CARD_WIDTH + 20, MARGIN)

        self.foundation_pos = [
            (SCREEN_WIDTH - (4 - i) * (CARD_WIDTH + 10), MARGIN) for i in range(4)
        ]

        tableau_y = MARGIN + CARD_HEIGHT + 40
        col_w = (SCREEN_WIDTH - 2 * MARGIN) / 7
        self.tableau_pos = [(MARGIN + i * col_w, tableau_y) for i in range(7)]

        storage_y = SCREEN_HEIGHT - CARD_HEIGHT - 60
        self.storage_pos = [
            (MARGIN + i * (CARD_WIDTH + 10), storage_y) for i in range(4)
        ]

    def _is_valid_stack(self, column: list[Card], start_idx: int) -> bool:
        """Validate descending alternating colors within a tableau sub-pile."""
        for i in range(start_idx, len(column) - 1):
            a, b = column[i], column[i + 1]
            if not a.face_up or not b.face_up:
                return False
            if a.get_color() == b.get_color():
                return False
            if a.get_value_index() != b.get_value_index() + 1:
                return False
        return True

    def _can_drop_on_tableau(self, card: Card, dest_col: int) -> bool:
        """Check if a card (or pile) can be dropped on a tableau column."""
        if (
            self.drag_from
            and self.drag_from[0] == "tableau"
            and self.drag_from[1] == dest_col
        ):
            return False
        if self.drag_pile:
            source, idx = self.drag_from
            if source == "tableau":
                start_idx = len(self.game.tableau[idx]) - len(self.drag_pile)
                if not self._is_valid_stack(
                    self.game.tableau[idx],
                    start_idx,
                ):
                    return False
        return self.game.is_valid_tableau_move(card, dest_col)

    def _can_drop_on_foundation(self, card: Card, foundation_idx: int) -> bool:
        """Check if a single card can be dropped on a foundation pile."""
        if self.drag_pile and len(self.drag_pile) > 1:
            return False
        return self.game.is_valid_foundation_move(card, foundation_idx)

    def _format_legal_moves(self) -> list[str]:
        """Convert engine legal_moves() to human-readable hint strings."""
        hints: list[str] = []
        for move in self.game.legal_moves():
            hint = self._format_single_move(move)
            if hint:
                hints.append(hint)
        return hints

    def _format_single_move(self, move: str | tuple) -> str:
        """Format a single move into a human-readable hint string."""
        if move == "draw":
            return "Draw a card from stock"
        if move == "foundation":
            card = self.game.waste[-1]
            return f"Move {card.suit}{card.value} from waste (discard) to foundation"
        if isinstance(move, tuple) and move[0] == "tableau":
            card = self.game.waste[-1]
            return (
                f"Move {card.suit}{card.value}"
                f" from waste (discard) to tableau {move[1] + 1}"
            )
        if isinstance(move, tuple) and move[0] == "storage":
            card = self.game.waste[-1]
            return (
                f"Move {card.suit}{card.value}"
                f" from waste (discard) to storage {move[1] + 1}"
            )
        if isinstance(move, tuple) and move[0] == "move":
            return self._format_compound_move(move)
        return ""

    def _format_compound_move(self, move: tuple) -> str:
        """Format a compound move (source -> destination) as a hint string."""
        src, dst = move[1], move[2]
        if src[0] == "tableau":
            card = self.game.tableau[src[1]][-1]
            src_name = f"tableau {src[1] + 1}"
        else:
            card = self.game.storage[src[1]]
            src_name = f"storage {src[1] + 1}"
        if dst[0] == "tableau":
            dst_name = f"tableau {dst[1] + 1}"
        elif dst[0] == "foundation":
            dst_name = "foundation"
        elif dst[0] == "storage":
            dst_name = f"storage {dst[1] + 1}"
        else:
            dst_name = str(dst)
        return f"Move {card.suit}{card.value} from {src_name} to {dst_name}"

    def _draw_shadow(self, dest: tuple[int, int]) -> None:
        """Draw a card shadow at the given position."""
        shadow = pygame.Surface(
            (CARD_WIDTH, CARD_HEIGHT),
            pygame.SRCALPHA,
        )
        pygame.draw.rect(
            shadow,
            SHADOW_COLOR,
            shadow.get_rect(),
            border_radius=CARD_BORDER_R,
        )
        screen.blit(
            shadow,
            (dest[0] + SHADOW_OFFSET[0], dest[1] + SHADOW_OFFSET[1]),
        )

    def _draw_stock(self) -> None:
        """Draw the stock pile area."""
        if self.game.stock:
            for i in range(min(5, len(self.game.stock))):
                offset = i * 2
                pygame.draw.rect(
                    screen,
                    DARKER_GRAY,
                    (
                        self.stock_pos[0] - offset,
                        self.stock_pos[1] - offset,
                        CARD_WIDTH,
                        CARD_HEIGHT,
                    ),
                    border_radius=CARD_BORDER_R,
                )
            self._draw_shadow(self.stock_pos)
            draw_card(screen, self.game.stock[0], self.stock_pos)
            self._draw_count_badge(self.stock_pos, len(self.game.stock))
        else:
            pygame.draw.rect(
                screen,
                DARKER_GRAY,
                (
                    self.stock_pos[0],
                    self.stock_pos[1],
                    CARD_WIDTH,
                    CARD_HEIGHT,
                ),
                2,
                border_radius=CARD_BORDER_R,
            )

    def _draw_count_badge(self, pos: tuple, count: int) -> None:
        """Draw a count badge at the bottom-right of a card position."""
        count_circle = pygame.Surface((30, 30), pygame.SRCALPHA)
        pygame.draw.circle(count_circle, (0, 0, 0, 180), (15, 15), 15)
        screen.blit(
            count_circle,
            (pos[0] + CARD_WIDTH - 20, pos[1] + CARD_HEIGHT - 20),
        )
        count_text = font.render(str(count), _ANTIALIAS, WHITE)
        screen.blit(
            count_text,
            (pos[0] + CARD_WIDTH - 15, pos[1] + CARD_HEIGHT - 20),
        )

    def _draw_waste(self) -> None:
        """Draw the waste pile area."""
        if self.game.waste:
            for i in range(min(3, len(self.game.waste) - 1)):
                offset = (i + 1) * 5
                waste_idx = len(self.game.waste) - i - 2
                if waste_idx >= 0:
                    waste_card_pos = (
                        self.waste_pos[0] - offset,
                        self.waste_pos[1] - offset,
                    )
                    pygame.draw.rect(
                        screen,
                        LIGHT_GRAY,
                        (
                            waste_card_pos[0],
                            waste_card_pos[1],
                            CARD_WIDTH,
                            CARD_HEIGHT,
                        ),
                        border_radius=CARD_BORDER_R,
                    )
            self._draw_shadow(self.waste_pos)
            draw_card(screen, self.game.waste[-1], self.waste_pos)

            if len(self.game.waste) > WASTE_BADGE_THRESHOLD:
                self._draw_count_badge(
                    self.waste_pos,
                    len(self.game.waste),
                )
        else:
            pygame.draw.rect(
                screen,
                DARKER_GRAY,
                (
                    self.waste_pos[0],
                    self.waste_pos[1],
                    CARD_WIDTH,
                    CARD_HEIGHT,
                ),
                2,
                border_radius=CARD_BORDER_R,
            )

    def _draw_storage(self) -> None:
        """Draw the storage spaces."""
        for i, card in enumerate(self.game.storage):
            if card:
                self._draw_shadow(self.storage_pos[i])
                draw_card(screen, card, self.storage_pos[i])
            else:
                pygame.draw.rect(
                    screen,
                    WHITE,
                    (
                        self.storage_pos[i][0],
                        self.storage_pos[i][1],
                        CARD_WIDTH,
                        CARD_HEIGHT,
                    ),
                    2,
                    border_radius=CARD_BORDER_R,
                )
                plus = TITLE_FONT.render("+", _ANTIALIAS, (180, 180, 180))
                screen.blit(
                    plus,
                    plus.get_rect(
                        center=(
                            self.storage_pos[i][0] + CARD_WIDTH // 2,
                            self.storage_pos[i][1] + CARD_HEIGHT // 2,
                        ),
                    ),
                )

    def _draw_foundations(self) -> None:
        """Draw the foundation piles."""
        for i, pile in enumerate(self.game.foundations):
            if pile:
                if len(pile) > 1:
                    for j in range(min(3, len(pile) - 1)):
                        offset = (j + 1) * 2
                        pygame.draw.rect(
                            screen,
                            LIGHT_GRAY,
                            (
                                self.foundation_pos[i][0] - offset,
                                self.foundation_pos[i][1] - offset,
                                CARD_WIDTH,
                                CARD_HEIGHT,
                            ),
                            border_radius=CARD_BORDER_R,
                        )
                self._draw_shadow(self.foundation_pos[i])
                draw_card(screen, pile[-1], self.foundation_pos[i])
            else:
                pygame.draw.rect(
                    screen,
                    WHITE,
                    (
                        self.foundation_pos[i][0],
                        self.foundation_pos[i][1],
                        CARD_WIDTH,
                        CARD_HEIGHT,
                    ),
                    2,
                    border_radius=CARD_BORDER_R,
                )
                big_suit = TITLE_FONT.render(
                    SUITS[i],
                    _ANTIALIAS,
                    (160, 160, 160),
                )
                screen.blit(
                    big_suit,
                    big_suit.get_rect(
                        center=(
                            self.foundation_pos[i][0] + CARD_WIDTH // 2,
                            self.foundation_pos[i][1] + CARD_HEIGHT // 2,
                        ),
                    ),
                )

    def _draw_tableau(self) -> None:
        """Draw the tableau columns."""
        for col_idx, column in enumerate(self.game.tableau):
            if not column:
                self._draw_empty_tableau_col(col_idx)
                continue
            self._draw_tableau_shadows(col_idx, column)
            self._draw_tableau_cards(col_idx, column)

    def _draw_empty_tableau_col(self, col_idx: int) -> None:
        """Draw an empty tableau column placeholder."""
        pygame.draw.rect(
            screen,
            LIGHT_GRAY,
            (
                self.tableau_pos[col_idx][0],
                self.tableau_pos[col_idx][1],
                CARD_WIDTH,
                CARD_HEIGHT,
            ),
            2,
            border_radius=CARD_BORDER_R,
        )
        empty_text = font.render("Empty", _ANTIALIAS, BLACK)
        empty_pos = (
            self.tableau_pos[col_idx][0] + (CARD_WIDTH - empty_text.get_width()) // 2,
            self.tableau_pos[col_idx][1] + (CARD_HEIGHT - empty_text.get_height()) // 2,
        )
        screen.blit(empty_text, empty_pos)

    def _draw_tableau_shadows(
        self,
        col_idx: int,
        column: list[Card],
    ) -> None:
        """Draw shadow layers under a tableau column."""
        for i in range(min(3, len(column))):
            shadow_offset = i * 2
            pygame.draw.rect(
                screen,
                (50, 50, 50),
                (
                    self.tableau_pos[col_idx][0] - shadow_offset,
                    self.tableau_pos[col_idx][1] - shadow_offset,
                    CARD_WIDTH,
                    CARD_HEIGHT,
                ),
                1,
                border_radius=CARD_BORDER_R,
            )

    def _draw_tableau_cards(
        self,
        col_idx: int,
        column: list[Card],
    ) -> None:
        """Draw the cards in a tableau column."""
        for row_idx, card in enumerate(column):
            if card is self.card_being_dragged or card in self.drag_pile:
                continue
            if row_idx == len(column) - 1 and not card.face_up:
                card.face_up = True
            card_pos = (
                self.tableau_pos[col_idx][0],
                self.tableau_pos[col_idx][1] + row_idx * CARD_SPACING,
            )
            draw_card(screen, card, card_pos)

    def _draw_dragged_cards(self) -> None:
        """Draw cards currently being dragged by the mouse."""
        if not self.card_being_dragged:
            return
        mouse_pos = pygame.mouse.get_pos()
        pos = (
            mouse_pos[0] - self.drag_offset[0],
            mouse_pos[1] - self.drag_offset[1],
        )
        if self.drag_pile:
            for i, card in enumerate(self.drag_pile):
                card_pos = (pos[0], pos[1] + i * CARD_SPACING)
                draw_card(screen, card, card_pos)
        else:
            draw_card(screen, self.card_being_dragged, pos)

    def _draw_message(self) -> None:
        """Draw the status message at the bottom of the screen."""
        if self.message and self.message_timer > 0:
            message_text = TITLE_FONT.render(
                self.message,
                _ANTIALIAS,
                WHITE,
            )
            screen.blit(
                message_text,
                (
                    SCREEN_WIDTH / 2 - message_text.get_width() / 2,
                    SCREEN_HEIGHT - 30,
                ),
            )

    def _draw_buttons(self) -> None:
        """Draw the hint and rules buttons."""
        pygame.draw.rect(
            screen,
            BUTTON_COLOR,
            HINT_BUTTON_RECT,
            border_radius=6,
        )
        screen.blit(
            HINT_BUTTON_TEXT,
            HINT_BUTTON_TEXT.get_rect(center=HINT_BUTTON_RECT.center),
        )
        pygame.draw.rect(
            screen,
            BUTTON_COLOR,
            RULE_BUTTON_RECT,
            border_radius=6,
        )
        screen.blit(
            RULE_BUTTON_TEXT,
            RULE_BUTTON_TEXT.get_rect(center=RULE_BUTTON_RECT.center),
        )

    def _draw_panel_overlay(self) -> pygame.Rect:
        """Draw a dark overlay and return the centered panel box rect."""
        overlay = pygame.Surface(
            (SCREEN_WIDTH, SCREEN_HEIGHT),
            pygame.SRCALPHA,
        )
        overlay.fill((0, 0, 0, 200))
        screen.blit(overlay, (0, 0))
        return pygame.Rect(0, 0, 0, 0)

    def _draw_panel_box(
        self,
        width: int,
        height: int,
    ) -> pygame.Rect:
        """Draw a centered panel box with shadow and border."""
        overlay = pygame.Surface(
            (SCREEN_WIDTH, SCREEN_HEIGHT),
            pygame.SRCALPHA,
        )
        overlay.fill((0, 0, 0, 200))
        screen.blit(overlay, (0, 0))

        box = pygame.Rect(0, 0, width, height)
        box.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        shadow = pygame.Rect(
            box.left + 6,
            box.top + 6,
            box.width,
            box.height,
        )
        pygame.draw.rect(
            screen,
            (0, 0, 0, 100),
            shadow,
            border_radius=12,
        )
        pygame.draw.rect(
            screen,
            RULE_PANEL_BG,
            box,
            border_radius=12,
        )
        pygame.draw.rect(
            screen,
            RULE_PANEL_BORDER,
            box,
            2,
            border_radius=12,
        )
        pygame.draw.line(
            screen,
            RULE_PANEL_ACCENT,
            (box.left + 18, box.top + 52),
            (box.right - 18, box.top + 52),
            2,
        )
        return box

    def _draw_rules_popup(self) -> None:
        """Draw the rules overlay panel."""
        box = self._draw_panel_box(RULE_BOX_W, RULE_BOX_H)

        title = RULE_TITLE_FONT.render(
            "RULES",
            _ANTIALIAS,
            RULE_PANEL_ACCENT,
        )
        screen.blit(title, (box.left + 20, box.top + 16))

        content_top = box.top + 64
        x, y = box.left + 24, content_top - self.rule_scroll
        wrap_w = RULE_BOX_W - 48
        total_h = 0

        for raw in self.rules_text:
            parsed = self._parse_rule_line(raw)
            if parsed[0] == "number":
                render_lines = self._render_rule_line(
                    parsed[0],
                    (parsed[1], parsed[2]),
                    wrap_w,
                )
            else:
                render_lines = self._render_rule_line(
                    parsed[0],
                    parsed[-1],
                    wrap_w,
                )
            for font_obj, text, color, gap in render_lines:
                surf = font_obj.render(text, _ANTIALIAS, color)
                if content_top <= y + total_h <= box.bottom - 44:
                    screen.blit(surf, (x, y + total_h))
                total_h += surf.get_height() + gap

        self.max_rule_scroll = max(0, total_h - (RULE_BOX_H - 88))
        hint = RULE_FONT.render(
            (
                "\u2191 / \u2193 or mouse-wheel to scroll"
                " \u2022 Click Rules again to close"
            ),
            _ANTIALIAS,
            RULE_MUTED,
        )
        screen.blit(
            hint,
            hint.get_rect(center=(box.centerx, box.bottom - 25)),
        )

    def _draw_hint_popup(self) -> None:
        """Draw the hint overlay panel."""
        box = self._draw_panel_box(RULE_BOX_W, RULE_BOX_H - 60)

        title = RULE_TITLE_FONT.render(
            "POSSIBLE MOVES",
            _ANTIALIAS,
            RULE_PANEL_ACCENT,
        )
        screen.blit(title, (box.left + 20, box.top + 16))

        content_top = box.top + 64
        x, y = box.left + 24, content_top - self.hint_scroll
        wrap_w = box.width - 48
        total_h = 0

        if not self.hint_text:
            empty = RULE_FONT.render(
                "No legal moves.",
                _ANTIALIAS,
                RULE_TEXT,
            )
            screen.blit(empty, (x, content_top))
            total_h = empty.get_height()
        else:
            for raw in self.hint_text:
                for font_obj, text, color, gap in self._render_rule_line(
                    "bullet",
                    raw,
                    wrap_w,
                ):
                    surf = font_obj.render(text, _ANTIALIAS, color)
                    if content_top <= y + total_h <= box.bottom - 44:
                        screen.blit(surf, (x, y + total_h))
                    total_h += surf.get_height() + gap

        self.max_hint_scroll = max(0, total_h - (box.height - 88))
        hint = RULE_FONT.render(
            (
                "\u2191 / \u2193 or mouse-wheel to scroll"
                " \u2022 Click Hint again to close"
            ),
            _ANTIALIAS,
            RULE_MUTED,
        )
        screen.blit(
            hint,
            hint.get_rect(center=(box.centerx, box.bottom - 25)),
        )

    def _draw_game_over_overlay(self) -> None:
        """Draw the game-won or game-over overlay."""
        if self.game_won:
            self._start_confetti()
            overlay = pygame.Surface(
                (SCREEN_WIDTH, SCREEN_HEIGHT),
                pygame.SRCALPHA,
            )
            overlay.fill((0, 0, 0, 128))
            screen.blit(overlay, (0, 0))
            win_text = TITLE_FONT.render(
                "Congratulations! You've won! Press 'R' to play again.",
                _ANTIALIAS,
                BLUE,
            )
            screen.blit(
                win_text,
                (
                    SCREEN_WIDTH / 2 - win_text.get_width() / 2,
                    SCREEN_HEIGHT / 2,
                ),
            )
        elif self.game_over:
            overlay = pygame.Surface(
                (SCREEN_WIDTH, SCREEN_HEIGHT),
                pygame.SRCALPHA,
            )
            overlay.fill((0, 0, 0, 128))
            screen.blit(overlay, (0, 0))
            over_text = TITLE_FONT.render(
                "Game over! No more legal moves. Press 'R' to try again.",
                _ANTIALIAS,
                RED,
            )
            screen.blit(
                over_text,
                (
                    SCREEN_WIDTH / 2 - over_text.get_width() / 2,
                    SCREEN_HEIGHT / 2,
                ),
            )

    def _draw_confetti(self) -> None:
        """Draw confetti particles."""
        for p in self.confetti:
            pygame.draw.rect(
                screen,
                p["color"],
                (p["x"], p["y"], p["size"], p["size"]),
            )

    def draw_game(self) -> None:
        """Render the entire game screen."""
        screen.fill(FELT_GREEN)
        self._draw_stock()
        self._draw_waste()
        self._draw_storage()
        self._draw_foundations()
        self._draw_tableau()
        self._draw_dragged_cards()
        self._draw_message()
        self._draw_buttons()

        if self.show_rules:
            self._draw_rules_popup()
        if self.show_hint:
            self._draw_hint_popup()

        self._draw_game_over_overlay()
        self._draw_confetti()

    def show_message(self, message: str, time: int = 180) -> None:
        """Show a temporary message at the bottom of the screen."""
        self.message = message
        self.message_timer = time

    def update_message_timer(self) -> None:
        """Decrement the message timer and clear when expired."""
        if self.message_timer > 0:
            self.message_timer -= 1
            if self.message_timer == 0:
                self.message = ""

    def draw_card_from_stock(self) -> None:
        """Draw a card from the stock pile to the waste pile."""
        if not self.game.stock:
            self.show_message("No more cards in the stock!")
            return
        card = self.game.stock.pop()
        card.face_up = True
        self.game.waste.append(card)

    def _try_drag_waste(self, pos: tuple[int, int]) -> bool:
        """Try to start dragging from the waste pile."""
        if not self.game.waste:
            return False
        if not pygame.Rect(
            self.waste_pos[0],
            self.waste_pos[1],
            CARD_WIDTH,
            CARD_HEIGHT,
        ).collidepoint(pos):
            return False
        self.card_being_dragged = self.game.waste[-1]
        self.drag_from = ("waste", 0)
        self.drag_offset = (
            pos[0] - self.waste_pos[0],
            pos[1] - self.waste_pos[1],
        )
        return True

    def _try_drag_foundation(self, pos: tuple[int, int]) -> bool:
        """Try to start dragging from a foundation pile."""
        for i, pile in enumerate(self.game.foundations):
            if pile and pygame.Rect(
                self.foundation_pos[i][0],
                self.foundation_pos[i][1],
                CARD_WIDTH,
                CARD_HEIGHT,
            ).collidepoint(pos):
                self.card_being_dragged = pile[-1]
                self.drag_from = ("foundation", i)
                self.drag_offset = (
                    pos[0] - self.foundation_pos[i][0],
                    pos[1] - self.foundation_pos[i][1],
                )
                return True
        return False

    def _try_drag_storage(self, pos: tuple[int, int]) -> bool:
        """Try to start dragging from a storage space."""
        for i, card in enumerate(self.game.storage):
            if card:
                storage_rect = pygame.Rect(
                    self.storage_pos[i][0],
                    self.storage_pos[i][1],
                    CARD_WIDTH,
                    CARD_HEIGHT,
                )
                if storage_rect.collidepoint(pos):
                    self.card_being_dragged = card
                    self.drag_from = ("storage", i)
                    self.drag_offset = (
                        pos[0] - self.storage_pos[i][0],
                        pos[1] - self.storage_pos[i][1],
                    )
                    return True
        return False

    def _try_drag_tableau(self, pos: tuple[int, int]) -> bool:
        """Try to start dragging from a tableau column."""
        for col_idx, column in enumerate(self.game.tableau):
            if not column:
                continue
            for row_idx in range(len(column) - 1, -1, -1):
                card = column[row_idx]
                card_pos = (
                    self.tableau_pos[col_idx][0],
                    self.tableau_pos[col_idx][1] + row_idx * CARD_SPACING,
                )
                height = CARD_HEIGHT if row_idx == len(column) - 1 else CARD_SPACING
                card_rect = pygame.Rect(
                    card_pos[0],
                    card_pos[1],
                    CARD_WIDTH,
                    height,
                )
                if card_rect.collidepoint(pos) and card.face_up:
                    self.card_being_dragged = card
                    self.drag_from = ("tableau", col_idx)
                    self.drag_offset = (
                        pos[0] - card_pos[0],
                        pos[1] - card_pos[1],
                    )
                    if row_idx < len(column) - 1:
                        self.drag_pile = column[row_idx:]
                    return True
        return False

    def start_drag(self, pos: tuple[int, int]) -> bool:
        """Start dragging a card from any valid source."""
        return (
            self._try_drag_waste(pos)
            or self._try_drag_foundation(pos)
            or self._try_drag_storage(pos)
            or self._try_drag_tableau(pos)
        )

    def _try_drop_foundation(self, card: Card, pos: tuple[int, int]) -> bool:
        """Try to drop a card on a foundation pile."""
        for i, foundation_pos in enumerate(self.foundation_pos):
            if pygame.Rect(
                foundation_pos[0],
                foundation_pos[1],
                CARD_WIDTH,
                CARD_HEIGHT,
            ).collidepoint(pos):
                if self._can_drop_on_foundation(card, i):
                    self.move_card_to_foundation(i)
                    self.card_being_dragged = None
                    self.drag_pile = []
                    self.check_game_state()
                    return True
                self.show_message("Invalid move to foundation")
                return True
        return False

    def _try_drop_tableau(self, card: Card, pos: tuple[int, int]) -> bool:
        """Try to drop a card on a tableau column."""
        for i, (col_x, col_y) in enumerate(self.tableau_pos):
            column = self.game.tableau[i]
            top_y = col_y + max(0, len(column) - 1) * CARD_SPACING
            target_rect = pygame.Rect(
                col_x,
                top_y,
                CARD_WIDTH,
                CARD_HEIGHT,
            )
            if target_rect.collidepoint(pos):
                if self._can_drop_on_tableau(card, i):
                    self.move_card_to_tableau(i)
                    self.card_being_dragged = None
                    self.drag_pile = []
                    self.check_game_state()
                else:
                    self.show_message("Invalid move to tableau")
                return True
        return False

    def _try_drop_storage(self, pos: tuple[int, int]) -> bool:
        """Try to drop a card on a storage space."""
        for i, storage_pos in enumerate(self.storage_pos):
            if pygame.Rect(
                storage_pos[0],
                storage_pos[1],
                CARD_WIDTH,
                CARD_HEIGHT,
            ).collidepoint(pos):
                if self.game.storage[i] is None and not self.drag_pile:
                    self.move_card_to_storage(i)
                    self.card_being_dragged = None
                    self.drag_pile = []
                    self.check_game_state()
                    return True
                if self.drag_pile:
                    self.show_message(
                        "Cannot move multiple cards to storage",
                    )
                else:
                    self.show_message("Storage space is already occupied")
                return True
        return False

    def stop_drag(self, pos: tuple[int, int]) -> None:
        """Stop dragging and try to place the card at the drop position."""
        if not self.card_being_dragged:
            return

        card = self.card_being_dragged

        if self._try_drop_foundation(card, pos):
            return
        if self._try_drop_tableau(card, pos):
            return
        if self._try_drop_storage(pos):
            return

        # Return card to original position
        self.card_being_dragged = None
        self.drag_pile = []

    def move_card_to_foundation(self, foundation_idx: int) -> None:
        """Move a dragged card to a foundation pile."""
        source, idx = self.drag_from
        if source == "waste":
            self.game.foundations[foundation_idx].append(
                self.game.waste.pop(),
            )
        elif source == "storage":
            self.game.foundations[foundation_idx].append(
                self.game.storage[idx],
            )
            self.game.storage[idx] = None
        elif source == "tableau":
            if self.drag_pile:
                self.game.foundations[foundation_idx].append(
                    self.game.tableau[idx].pop(),
                )
                self.drag_pile = []
            else:
                self.game.foundations[foundation_idx].append(
                    self.game.tableau[idx].pop(),
                )
            if self.game.tableau[idx] and not self.game.tableau[idx][-1].face_up:
                self.game.tableau[idx][-1].flip()

    def move_card_to_tableau(self, tableau_idx: int) -> None:
        """Move a dragged card (or pile) to a tableau column."""
        source, idx = self.drag_from
        if source == "waste":
            self.game.tableau[tableau_idx].append(self.game.waste.pop())
        elif source == "storage":
            self.game.tableau[tableau_idx].append(self.game.storage[idx])
            self.game.storage[idx] = None
        elif source == "foundation":
            self.game.tableau[tableau_idx].append(
                self.game.foundations[idx].pop(),
            )
        elif source == "tableau":
            if self.drag_pile:
                start_idx = len(self.game.tableau[idx]) - len(self.drag_pile)
                self.game.tableau[tableau_idx].extend(
                    self.game.tableau[idx][start_idx:],
                )
                del self.game.tableau[idx][start_idx:]
            else:
                self.game.tableau[tableau_idx].append(
                    self.game.tableau[idx].pop(),
                )
            if self.game.tableau[idx] and not self.game.tableau[idx][-1].face_up:
                self.game.tableau[idx][-1].flip()

    def move_card_to_storage(self, storage_idx: int) -> None:
        """Move a dragged card to a storage space."""
        source, idx = self.drag_from
        if source == "waste":
            self.game.storage[storage_idx] = self.game.waste.pop()
        elif source == "storage":
            self.game.storage[storage_idx] = self.game.storage[idx]
            self.game.storage[idx] = None
        elif source == "tableau":
            self.game.storage[storage_idx] = self.game.tableau[idx].pop()
            if self.game.tableau[idx] and not self.game.tableau[idx][-1].face_up:
                self.game.tableau[idx][-1].flip()

    def _auto_finish_if_forced(self) -> None:
        """Start auto-finish when the endgame condition is met."""
        if self.auto_finish_active or self.game_won or self.game_over:
            return
        if not self.game.is_endgame():
            return
        if len(self.game.waste) > 1:
            return
        self.auto_finish_active = True
        self.auto_finish_timer = 0

    def _auto_finish_step(self) -> bool:
        """Move a single eligible card to foundations for visual auto-finish."""
        for _col_idx, column in enumerate(self.game.tableau):
            if column and column[-1].face_up:
                card = column[-1]
                foundation_idx = SUITS.index(card.suit)
                if self.game.is_valid_foundation_move(
                    card,
                    foundation_idx,
                ):
                    self.game.foundations[foundation_idx].append(
                        column.pop(),
                    )
                    if column and not column[-1].face_up:
                        column[-1].flip()
                    return True

        for storage_idx, card in enumerate(self.game.storage):
            if card:
                foundation_idx = SUITS.index(card.suit)
                if self.game.is_valid_foundation_move(
                    card,
                    foundation_idx,
                ):
                    self.game.foundations[foundation_idx].append(card)
                    self.game.storage[storage_idx] = None
                    return True

        if self.game.waste:
            card = self.game.waste[-1]
            foundation_idx = SUITS.index(card.suit)
            if self.game.is_valid_foundation_move(card, foundation_idx):
                self.game.foundations[foundation_idx].append(
                    self.game.waste.pop(),
                )
                return True

        return False

    def _update_auto_finish(self) -> None:
        """Advance the auto-finish animation by one tick."""
        if not self.auto_finish_active:
            return
        self.auto_finish_timer += 1
        if self.auto_finish_timer < AUTO_FINISH_STEP_FRAMES:
            return
        self.auto_finish_timer = 0
        if not self._auto_finish_step():
            self.auto_finish_active = False

    def _start_confetti(self) -> None:
        """Initialize confetti particles for the win animation."""
        if self.confetti_started:
            return
        self.confetti_started = True
        colors = [
            (214, 69, 65),
            (250, 201, 69),
            (62, 168, 91),
            (64, 128, 196),
            (243, 130, 50),
        ]
        for _ in range(120):
            self.confetti.append(
                {
                    "x": random.randint(0, SCREEN_WIDTH),
                    "y": random.randint(-SCREEN_HEIGHT, 0),
                    "vx": random.uniform(-1.5, 1.5),
                    "vy": random.uniform(2.0, 5.5),
                    "color": random.choice(colors),
                    "life": random.randint(120, 220),
                    "size": random.randint(3, 6),
                },
            )

    def _update_confetti(self) -> None:
        """Update confetti particle positions and remove dead ones."""
        if not self.confetti:
            return
        alive = []
        for p in self.confetti:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["life"] -= 1
            if p["y"] < SCREEN_HEIGHT + 20 and p["life"] > 0:
                alive.append(p)
        self.confetti = alive

    def check_game_state(self) -> None:
        """Check if the game has been won or is over."""
        self._auto_finish_if_forced()
        if self.game.is_game_won():
            self.game_won = True
        elif self.game.is_game_over():
            self.game_over = True

    def handle_stock_click(self, pos: tuple[int, int]) -> bool:
        """Handle a click on the stock pile area."""
        if pygame.Rect(
            self.stock_pos[0],
            self.stock_pos[1],
            CARD_WIDTH,
            CARD_HEIGHT,
        ).collidepoint(pos):
            self.draw_card_from_stock()
            return True
        return False

    def _handle_mouse_down(self, event: pygame.event.Event) -> None:
        """Handle left mouse button down events."""
        if event.button != 1:
            return
        if RULE_BUTTON_RECT.collidepoint(event.pos):
            self.show_rules = not self.show_rules
            if self.show_rules:
                self.show_hint = False
            return
        if HINT_BUTTON_RECT.collidepoint(event.pos):
            self.show_hint = not self.show_hint
            if self.show_hint:
                self.show_rules = False
                self.hint_text = self._format_legal_moves()
                self.hint_scroll = 0
            return
        if self.show_rules:
            self.show_rules = False
            return
        if self.show_hint:
            self.show_hint = False
            return
        if not self.handle_stock_click(event.pos) and (
            not self.game_over
            and not self.game_won
            and not self.show_rules
            and not self.show_hint
        ):
            self.start_drag(event.pos)

    def _handle_scroll(self, event: pygame.event.Event) -> None:
        """Handle mouse wheel scroll events for panels."""
        if not (self.show_rules or self.show_hint):
            return
        scroll_amount = -event.y * RULE_SCROLL_STEP
        if self.show_rules:
            self.rule_scroll = max(
                0,
                min(
                    self.max_rule_scroll,
                    self.rule_scroll + scroll_amount,
                ),
            )
        else:
            self.hint_scroll = max(
                0,
                min(
                    self.max_hint_scroll,
                    self.hint_scroll + scroll_amount,
                ),
            )

    def _handle_keydown(
        self,
        event: pygame.event.Event,
    ) -> bool:
        """Handle key press events. Return False to quit."""
        if event.key == pygame.K_r:
            self.reset_game()
        elif event.key == pygame.K_q:
            return False
        elif event.key == pygame.K_d:
            if not self.game_over and not self.game_won:
                self.draw_card_from_stock()
        elif self.show_rules or self.show_hint:
            self._handle_panel_key(event)
        return True

    def _handle_panel_key(self, event: pygame.event.Event) -> None:
        """Handle arrow key scrolling within an open panel."""
        if event.key == pygame.K_UP:
            if self.show_rules:
                self.rule_scroll = max(
                    0,
                    self.rule_scroll - RULE_SCROLL_STEP,
                )
            else:
                self.hint_scroll = max(
                    0,
                    self.hint_scroll - RULE_SCROLL_STEP,
                )
        elif event.key == pygame.K_DOWN:
            if self.show_rules:
                self.rule_scroll = min(
                    self.max_rule_scroll,
                    self.rule_scroll + RULE_SCROLL_STEP,
                )
            else:
                self.hint_scroll = min(
                    self.max_hint_scroll,
                    self.hint_scroll + RULE_SCROLL_STEP,
                )

    def run(self) -> None:
        """Run the main game loop."""
        running = True

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self._handle_mouse_down(event)
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1 and self.card_being_dragged:
                        self.stop_drag(event.pos)
                elif event.type == pygame.MOUSEWHEEL:
                    self._handle_scroll(event)
                elif event.type == pygame.KEYDOWN and not self._handle_keydown(event):
                    running = False

            self.update_message_timer()
            self._update_auto_finish()
            self._update_confetti()

            self.draw_game()
            pygame.display.flip()
            clock.tick(60)

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    game = OneShotSolitaireGUI()
    game.run()
