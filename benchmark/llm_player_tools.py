import json
import openai


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "draw",
            "description": "Draw a card from stock to waste",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "waste_to_foundation",
            "description": "Move waste card to its foundation pile",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "waste_to_tableau",
            "description": "Move waste card to a tableau column",
            "parameters": {
                "type": "object",
                "properties": {
                    "column": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 7,
                        "description": "Tableau column number (1-7)",
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
            "description": "Move waste card to a storage slot",
            "parameters": {
                "type": "object",
                "properties": {
                    "slot": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 4,
                        "description": "Storage slot number (1-4)",
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
            "description": "Move a card between tableau columns, storage slots, and foundations",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_location": {
                        "type": "string",
                        "enum": ["t1", "t2", "t3", "t4", "t5", "t6", "t7",
                                 "s1", "s2", "s3", "s4"],
                        "description": "Source: t1-t7 for tableau, s1-s4 for storage",
                    },
                    "to_location": {
                        "type": "string",
                        "enum": ["t1", "t2", "t3", "t4", "t5", "t6", "t7",
                                 "s1", "s2", "s3", "s4", "f"],
                        "description": "Destination: t1-t7 for tableau, s1-s4 for storage, f for foundation",
                    },
                },
                "required": ["from_location", "to_location"],
            },
        },
    },
]


def tool_call_to_text(name, args):
    """Convert a tool call into the text command format the game engine expects."""
    if name == "draw":
        return "d"
    elif name == "waste_to_foundation":
        return "f"
    elif name == "waste_to_tableau":
        return f"t {args['column']}"
    elif name == "waste_to_storage":
        return f"s {args['slot']}"
    elif name == "move_card":
        return f"m {args['from_location']} {args['to_location']}"
    return None


class ToolCallPlayer:
    SYSTEM_PROMPT = """You are playing One-Pass Solitaire.

RULES:
- 7 tableau columns: build DOWN in ALTERNATING colors (red on black, black on red). Only Kings on empty columns.
- 4 foundations: build UP by suit from Ace to King.
- 4 storage spaces: each holds exactly one card.
- Stock pile: draw one card at a time to waste. ONE PASS ONLY.

CARD FORMAT: Suit letter + value. S=Spades(black), C=Clubs(black), H=Hearts(red), D=Diamonds(red).
Values: A, 2, 3, 4, 5, 6, 7, 8, 9, 10, J, Q, K

Use the provided tools to make your move. Call exactly one tool per turn."""

    def __init__(self, model="gpt-4o-mini", max_retries=3, reasoning_effort="low"):
        self.client = openai.OpenAI()
        self.model = model
        self.max_retries = max_retries
        self.reasoning_effort = reasoning_effort
        self.previous_response_id = None

    def get_move(self, game_state_text, error_feedback=None):
        if error_feedback:
            user_input = f"Invalid move. {error_feedback}\n\n{game_state_text}"
        else:
            user_input = game_state_text

        kwargs = dict(
            model=self.model,
            instructions=self.SYSTEM_PROMPT,
            input=user_input,
            tools=TOOLS,
            tool_choice="required",
            previous_response_id=self.previous_response_id,
        )
        if self.reasoning_effort:
            kwargs["reasoning"] = {"effort": self.reasoning_effort}

        response = self.client.responses.create(**kwargs)
        self.previous_response_id = response.id

        # Extract token usage
        usage = response.usage
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0

        input_details = getattr(usage, "input_tokens_details", None)
        cached_input_tokens = getattr(input_details, "cached_tokens", 0) or 0 if input_details else 0

        output_details = getattr(usage, "output_tokens_details", None)
        reasoning_tokens = getattr(output_details, "reasoning_tokens", 0) or 0 if output_details else 0

        token_usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cached_input_tokens": cached_input_tokens,
            "reasoning_tokens": reasoning_tokens,
        }

        # Find the function call in the response output
        for item in response.output:
            if item.type == "function_call":
                args = json.loads(item.arguments) if item.arguments else {}
                text_cmd = tool_call_to_text(item.name, args)
                if text_cmd:
                    return text_cmd, token_usage

        # Fallback: no tool call found
        return None, token_usage

    def reset(self):
        self.previous_response_id = None
