import openai


class LLMPlayer:
    SYSTEM_PROMPT = """You are playing One-Pass Solitaire. Here are the rules:

GAME LAYOUT:
- 7 tableau columns: build DOWN in ALTERNATING colors (red on black, black on red). Only Kings on empty columns.
- 4 foundations: build UP by suit from Ace to King (SA, S2, S3... SK for Spades, etc.)
- 4 storage spaces: each holds exactly one card. Any card can go in an empty space.
- Stock pile: draw one card at a time to waste. ONE PASS ONLY - no recycling.
- Waste pile: top card can be played to tableau, foundation, or storage.

CARD FORMAT: Suit letter + value. S=Spades(black), C=Clubs(black), H=Hearts(red), D=Diamonds(red).
Values: A, 2, 3, 4, 5, 6, 7, 8, 9, 10, J, Q, K

COMMANDS (respond with ONLY the command, nothing else):
  d           - Draw a card from stock to waste
  f           - Move waste card to its foundation
  t N         - Move waste card to tableau column N (1-7)
  s N         - Move waste card to storage space N (1-4)
  m tN tM     - Move top card from tableau col N to tableau col M
  m sN tM     - Move card from storage N to tableau col M
  m tN f      - Move top card from tableau col N to foundation
  m sN f      - Move card from storage N to foundation
  m tN sM     - Move top card from tableau col N to storage M
  m sN sM     - Move card from storage N to storage M

STRATEGY TIPS:
- Expose face-down cards in tableau when possible
- Keep storage spaces open for critical cards
- Think ahead - you only get one pass through the stock
- Building foundations too eagerly can block tableau moves

Respond with EXACTLY ONE command. No explanation, no extra text."""

    def __init__(self, model="gpt-5-nano", max_retries=3, reasoning_effort="low"):
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
            previous_response_id=self.previous_response_id,
        )
        if self.reasoning_effort:
            kwargs["reasoning"] = {"effort": self.reasoning_effort}

        response = self.client.responses.create(**kwargs)

        reply = response.output_text.strip()
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

        return reply, token_usage

    def reset(self):
        self.previous_response_id = None
