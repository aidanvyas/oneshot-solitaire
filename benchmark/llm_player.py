"""LLM player that uses text-based responses to play solitaire."""

from __future__ import annotations

import openai

_SYSTEM_PROMPT_RULES = (
    "You are playing One-Shot Solitaire. Here are the rules:\n"
    "\n"
    "GAME LAYOUT:\n"
    "- 7 tableau columns: build DOWN in ALTERNATING colors "
    "(red on black, black on red). "
    "Only Kings on empty columns.\n"
    "- 4 foundations: build UP by suit from Ace to King "
    "(SA, S2, S3... SK for Spades, etc.)\n"
    "- 4 storage spaces: each holds exactly one card. "
    "Any card can go in an empty space.\n"
    "- Stock pile: draw one card at a time to waste. "
    "ONE SHOT ONLY - no recycling.\n"
    "- Waste pile: top card can be played to tableau, "
    "foundation, or storage.\n"
)

_SYSTEM_PROMPT_CARDS = (
    "CARD FORMAT: Suit letter + value. "
    "S=Spades(black), C=Clubs(black), "
    "H=Hearts(red), D=Diamonds(red).\n"
    "Values: A, 2, 3, 4, 5, 6, 7, 8, 9, 10, J, Q, K\n"
)

_SYSTEM_PROMPT_COMMANDS = (
    "COMMANDS (respond with ONLY the command, nothing else):\n"
    "  d           - Draw a card from stock to waste\n"
    "  f           - Move waste card to its foundation\n"
    "  t N         - Move waste card to tableau column N (1-7)\n"
    "  s N         - Move waste card to storage space N (1-4)\n"
    "  m tN tM     - Move top card from tableau col N "
    "to tableau col M\n"
    "  m sN tM     - Move card from storage N to tableau col M\n"
    "  m tN f      - Move top card from tableau col N "
    "to foundation\n"
    "  m sN f      - Move card from storage N to foundation\n"
    "  m tN sM     - Move top card from tableau col N "
    "to storage M\n"
    "  m sN sM     - Move card from storage N to storage M\n"
)

_SYSTEM_PROMPT_STRATEGY = (
    "\nSTRATEGY TIPS:\n"
    "- Expose face-down cards in tableau when possible\n"
    "- Keep storage spaces open for critical cards\n"
    "- Think ahead - you only get one shot through the stock\n"
    "- Building foundations too eagerly can block tableau moves\n"
    "\n"
    "Respond with EXACTLY ONE command. "
    "No explanation, no extra text."
)

_SYSTEM_PROMPT = (
    _SYSTEM_PROMPT_RULES
    + "\n"
    + _SYSTEM_PROMPT_CARDS
    + "\n"
    + _SYSTEM_PROMPT_COMMANDS
    + _SYSTEM_PROMPT_STRATEGY
)


def _extract_token_usage(
    usage: object,
) -> dict[str, int]:
    """Extract token counts from an OpenAI response usage object."""
    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0

    input_details = getattr(usage, "input_tokens_details", None)
    cached_input_tokens = (
        getattr(input_details, "cached_tokens", 0) or 0 if input_details else 0
    )

    output_details = getattr(usage, "output_tokens_details", None)
    reasoning_tokens = (
        getattr(output_details, "reasoning_tokens", 0) or 0 if output_details else 0
    )

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_input_tokens": cached_input_tokens,
        "reasoning_tokens": reasoning_tokens,
    }


class LLMPlayer:
    """Text-mode LLM player using the OpenAI Responses API."""

    SYSTEM_PROMPT = _SYSTEM_PROMPT

    def __init__(
        self,
        model: str = "gpt-5-nano",
        max_retries: int = 3,
        reasoning_effort: str = "low",
    ) -> None:
        """Initialize the player with model configuration."""
        self.client = openai.OpenAI()
        self.model = model
        self.max_retries = max_retries
        self.reasoning_effort = reasoning_effort
        self.previous_response_id: str | None = None

    def get_move(
        self,
        game_state_text: str,
        error_feedback: str | None = None,
    ) -> tuple[str, dict[str, int]]:
        """Request a move from the LLM given the current game state."""
        if error_feedback:
            user_input = f"Invalid move. {error_feedback}\n\n{game_state_text}"
        else:
            user_input = game_state_text

        kwargs: dict[str, object] = {
            "model": self.model,
            "instructions": self.SYSTEM_PROMPT,
            "input": user_input,
            "previous_response_id": self.previous_response_id,
        }
        if self.reasoning_effort:
            kwargs["reasoning"] = {"effort": self.reasoning_effort}

        response = self.client.responses.create(**kwargs)

        reply = response.output_text.strip()
        self.previous_response_id = response.id

        token_usage = _extract_token_usage(response.usage)
        return reply, token_usage

    def reset(self) -> None:
        """Clear conversation history for a new game."""
        self.previous_response_id = None
