"""LLM player that uses OpenAI function-calling (tools) to play solitaire."""

from __future__ import annotations

import json

import openai

from benchmark.llm_player import _extract_token_usage

TOOLS: list[dict[str, object]] = [
    {
        "type": "function",
        "function": {
            "name": "draw",
            "description": "Draw a card from stock to waste",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "waste_to_foundation",
            "description": ("Move waste card to its foundation pile"),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "waste_to_tableau",
            "description": ("Move waste card to a tableau column"),
            "parameters": {
                "type": "object",
                "properties": {
                    "column": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 7,
                        "description": ("Tableau column number (1-7)"),
                    },
                },
                "required": ["column"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "waste_to_storage",
            "description": ("Move waste card to a storage slot"),
            "parameters": {
                "type": "object",
                "properties": {
                    "slot": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 4,
                        "description": ("Storage slot number (1-4)"),
                    },
                },
                "required": ["slot"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_card",
            "description": (
                "Move a card between tableau columns, storage slots, and foundations"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "from_location": {
                        "type": "string",
                        "enum": [
                            "t1",
                            "t2",
                            "t3",
                            "t4",
                            "t5",
                            "t6",
                            "t7",
                            "s1",
                            "s2",
                            "s3",
                            "s4",
                        ],
                        "description": ("Source: t1-t7 for tableau, s1-s4 for storage"),
                    },
                    "to_location": {
                        "type": "string",
                        "enum": [
                            "t1",
                            "t2",
                            "t3",
                            "t4",
                            "t5",
                            "t6",
                            "t7",
                            "s1",
                            "s2",
                            "s3",
                            "s4",
                            "f",
                        ],
                        "description": (
                            "Destination: t1-t7 for tableau,"
                            " s1-s4 for storage,"
                            " f for foundation"
                        ),
                    },
                },
                "required": ["from_location", "to_location"],
            },
        },
    },
]


def tool_call_to_text(
    name: str,
    args: dict[str, object],
) -> str | None:
    """Convert a tool call into the text command format the engine expects."""
    if name == "draw":
        return "d"
    if name == "waste_to_foundation":
        return "f"
    if name == "waste_to_tableau":
        return f"t {args['column']}"
    if name == "waste_to_storage":
        return f"s {args['slot']}"
    if name == "move_card":
        return f"m {args['from_location']} {args['to_location']}"
    return None


_SYSTEM_PROMPT = (
    "You are playing One-Shot Solitaire.\n"
    "\n"
    "RULES:\n"
    "- 7 tableau columns: build DOWN in ALTERNATING colors "
    "(red on black, black on red). "
    "Only Kings on empty columns.\n"
    "- 4 foundations: build UP by suit from Ace to King.\n"
    "- 4 storage spaces: each holds exactly one card.\n"
    "- Stock pile: draw one card at a time to waste. "
    "ONE SHOT ONLY.\n"
    "\n"
    "CARD FORMAT: Suit letter + value. "
    "S=Spades(black), C=Clubs(black), "
    "H=Hearts(red), D=Diamonds(red).\n"
    "Values: A, 2, 3, 4, 5, 6, 7, 8, 9, 10, J, Q, K\n"
    "\n"
    "Use the provided tools to make your move. "
    "Call exactly one tool per turn."
)


class ToolCallPlayer:
    """Function-calling LLM player using the OpenAI Responses API."""

    SYSTEM_PROMPT = _SYSTEM_PROMPT

    def __init__(
        self,
        model: str = "gpt-5-nano",
        max_retries: int = 3,
        reasoning_effort: str = "high",
        service_tier: str = "flex",
        max_output_tokens: int = 128_000,
    ) -> None:
        """Initialize the tool-calling player with model configuration."""
        self.client = openai.OpenAI()
        self.model = model
        self.max_retries = max_retries
        self.reasoning_effort = reasoning_effort
        self.service_tier = service_tier
        self.max_output_tokens = max_output_tokens
        self.previous_response_id: str | None = None

    def get_move(
        self,
        game_state_text: str,
        error_feedback: str | None = None,
    ) -> tuple[str | None, dict[str, int]]:
        """Request a move via function calling given the game state."""
        if error_feedback:
            user_input = f"Invalid move. {error_feedback}\n\n{game_state_text}"
        else:
            user_input = game_state_text

        kwargs: dict[str, object] = {
            "model": self.model,
            "instructions": self.SYSTEM_PROMPT,
            "input": user_input,
            "tools": TOOLS,
            "tool_choice": "required",
            "previous_response_id": self.previous_response_id,
            "max_output_tokens": self.max_output_tokens,
        }
        if self.service_tier:
            kwargs["service_tier"] = self.service_tier
        if self.reasoning_effort:
            kwargs["reasoning"] = {"effort": self.reasoning_effort}

        response = self.client.responses.create(**kwargs)
        self.previous_response_id = response.id

        token_usage = _extract_token_usage(response.usage)

        for item in response.output:
            if item.type == "function_call":
                args = json.loads(item.arguments) if item.arguments else {}
                text_cmd = tool_call_to_text(item.name, args)
                if text_cmd:
                    return text_cmd, token_usage

        return None, token_usage

    def reset(self) -> None:
        """Clear conversation history for a new game."""
        self.previous_response_id = None
