"""Benchmark runner that plays multiple games using an LLM player."""

from __future__ import annotations

from dataclasses import dataclass, field

import openai
from rich.console import Console

from benchmark.llm_player import LLMPlayer
from benchmark.llm_player_tools import ToolCallPlayer
from benchmark.text_protocol import parse_move, render_game_state
from engine import OneShotSolitaire

console = Console()


@dataclass
class GameResult:
    """Result of a single benchmark game."""

    seed: int
    won: bool
    foundation_cards: int
    total_moves: int
    invalid_moves: int
    draw_count: int
    input_tokens: int = 0
    cached_input_tokens: int = 0
    reasoning_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None


@dataclass
class BenchmarkResults:
    """Aggregated results across all benchmark games."""

    results: list[GameResult]
    model: str

    @property
    def win_rate(self) -> float:
        """Return the fraction of games won."""
        return (
            sum(1 for r in self.results if r.won) / len(self.results)
            if self.results
            else 0
        )

    @property
    def avg_foundation_cards(self) -> float:
        """Return the average number of foundation cards across games."""
        return (
            sum(r.foundation_cards for r in self.results) / len(self.results)
            if self.results
            else 0
        )

    @property
    def avg_total_moves(self) -> float:
        """Return the average total moves per game."""
        return (
            sum(r.total_moves for r in self.results) / len(self.results)
            if self.results
            else 0
        )

    @property
    def avg_invalid_moves(self) -> float:
        """Return the average invalid moves per game."""
        return (
            sum(r.invalid_moves for r in self.results) / len(self.results)
            if self.results
            else 0
        )

    @property
    def legal_move_rate(self) -> float:
        """Return the fraction of moves that were legal."""
        total = sum(r.total_moves + r.invalid_moves for r in self.results)
        legal = sum(r.total_moves for r in self.results)
        return legal / total if total > 0 else 0

    @property
    def total_api_calls(self) -> int:
        """Return the total number of API calls across all games."""
        return sum(r.total_moves + r.invalid_moves for r in self.results)

    @property
    def total_input_tokens(self) -> int:
        """Return the total input tokens across all games."""
        return sum(r.input_tokens for r in self.results)

    @property
    def total_cached_input_tokens(self) -> int:
        """Return the total cached input tokens across all games."""
        return sum(r.cached_input_tokens for r in self.results)

    @property
    def total_reasoning_tokens(self) -> int:
        """Return the total reasoning tokens across all games."""
        return sum(r.reasoning_tokens for r in self.results)

    @property
    def total_output_tokens(self) -> int:
        """Return the total output tokens across all games."""
        return sum(r.output_tokens for r in self.results)

    @property
    def total_tokens(self) -> int:
        """Return the total tokens (input + output) across all games."""
        return self.total_input_tokens + self.total_output_tokens

    def to_dict(self) -> dict[str, object]:
        """Serialize results to a JSON-compatible dictionary."""
        return {
            "model": self.model,
            "num_games": len(self.results),
            "win_rate": self.win_rate,
            "avg_foundation_cards": self.avg_foundation_cards,
            "avg_total_moves": self.avg_total_moves,
            "avg_invalid_moves": self.avg_invalid_moves,
            "legal_move_rate": self.legal_move_rate,
            "total_api_calls": self.total_api_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_cached_input_tokens": self.total_cached_input_tokens,
            "total_reasoning_tokens": self.total_reasoning_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "games": [
                {
                    "seed": r.seed,
                    "won": r.won,
                    "foundation_cards": r.foundation_cards,
                    "total_moves": r.total_moves,
                    "invalid_moves": r.invalid_moves,
                    "draw_count": r.draw_count,
                    "input_tokens": r.input_tokens,
                    "cached_input_tokens": r.cached_input_tokens,
                    "reasoning_tokens": r.reasoning_tokens,
                    "output_tokens": r.output_tokens,
                    "error": r.error,
                }
                for r in self.results
            ],
        }


@dataclass
class BenchmarkConfig:
    """Configuration for a benchmark run."""

    model: str = "gpt-5-nano"
    games: int = 10
    start_seed: int = 42
    max_moves: int = 200
    max_retries: int = 3
    reasoning_effort: str = "low"
    mode: str = "text"
    verbose: bool = field(default=False, kw_only=True)


@dataclass
class _TokenAccumulator:
    """Mutable accumulator for token usage during a game."""

    input_tokens: int = 0
    cached_input_tokens: int = 0
    reasoning_tokens: int = 0
    output_tokens: int = 0

    def add(self, usage: dict[str, int]) -> None:
        """Add token counts from a single API call."""
        self.input_tokens += usage["input_tokens"]
        self.cached_input_tokens += usage["cached_input_tokens"]
        self.reasoning_tokens += usage["reasoning_tokens"]
        self.output_tokens += usage["output_tokens"]


class BenchmarkRunner:
    """Runs multiple solitaire games using an LLM player."""

    def __init__(self, config: BenchmarkConfig) -> None:
        """Initialize the runner from a config dataclass."""
        self.model = config.model
        self.games = config.games
        self.start_seed = config.start_seed
        self.max_moves = config.max_moves
        self.max_retries = config.max_retries
        self.reasoning_effort = config.reasoning_effort
        self.mode = config.mode
        self.verbose = config.verbose

    def _create_player(self) -> LLMPlayer | ToolCallPlayer:
        """Create the appropriate LLM player for the configured mode."""
        if self.mode == "tools":
            return ToolCallPlayer(
                model=self.model,
                max_retries=self.max_retries,
                reasoning_effort=self.reasoning_effort,
            )
        return LLMPlayer(
            model=self.model,
            max_retries=self.max_retries,
            reasoning_effort=self.reasoning_effort,
        )

    def _try_get_valid_move(
        self,
        player: LLMPlayer | ToolCallPlayer,
        game: OneShotSolitaire,
        state_text: str,
        turn_number: int,
        tokens: _TokenAccumulator,
    ) -> tuple[bool, int, int]:
        """Attempt to get and execute a valid move from the LLM.

        Returns (move_made, invalid_count, draw_increment).
        """
        error_feedback = None
        retries = 0
        invalid_count = 0

        while retries <= self.max_retries:
            raw_response, token_usage = player.get_move(
                state_text,
                error_feedback=(error_feedback if retries > 0 else None),
            )
            tokens.add(token_usage)

            if self.verbose:
                console.print(
                    f"  Turn {turn_number} (retry {retries}):"
                    f" LLM says '{raw_response}'",
                )

            move = parse_move(raw_response)

            if move is None:
                invalid_count += 1
                retries += 1
                error_feedback = (
                    f"Could not parse your response"
                    f" '{raw_response}'."
                    " Use exact command format:"
                    " d, f, t N, s N, m tN tM, etc."
                )
                continue

            success, err_msg = game.step(move)
            if success:
                draw_inc = 1 if move == "draw" else 0
                return True, invalid_count, draw_inc

            invalid_count += 1
            retries += 1
            error_feedback = err_msg

        return False, invalid_count, 0

    def _handle_max_retries(
        self,
        game: OneShotSolitaire,
        turn_number: int,
    ) -> tuple[bool, int, int]:
        """Handle the case when max retries are exhausted.

        Returns (should_continue, move_increment, draw_increment).
        """
        if game.stock:
            game.step("draw")
            if self.verbose:
                console.print(
                    f"  Turn {turn_number}: Forced draw after max retries",
                )
            return True, 1, 1

        if self.verbose:
            console.print(
                f"  Turn {turn_number}: No valid move found, ending game",
            )
        return False, 0, 0

    def play_one_game(self, seed: int) -> GameResult:
        """Play a single game and return the result."""
        game = OneShotSolitaire(seed=seed)
        player = self._create_player()

        total_moves = 0
        invalid_moves = 0
        draw_count = 0
        turn_number = 0
        tokens = _TokenAccumulator()

        try:
            while total_moves < self.max_moves:
                if game.is_game_won() or game.is_game_over():
                    break

                turn_number += 1
                state_text = render_game_state(game, turn_number)

                made, inv, drw = self._try_get_valid_move(
                    player,
                    game,
                    state_text,
                    turn_number,
                    tokens,
                )
                invalid_moves += inv

                if made:
                    total_moves += 1
                    draw_count += drw
                else:
                    cont, m_inc, d_inc = self._handle_max_retries(
                        game,
                        turn_number,
                    )
                    total_moves += m_inc
                    draw_count += d_inc
                    if not cont:
                        break
        except (openai.OpenAIError, KeyError, ValueError) as e:
            return GameResult(
                seed=seed,
                won=False,
                foundation_cards=game.foundation_count(),
                total_moves=total_moves,
                invalid_moves=invalid_moves,
                draw_count=draw_count,
                input_tokens=tokens.input_tokens,
                cached_input_tokens=tokens.cached_input_tokens,
                reasoning_tokens=tokens.reasoning_tokens,
                output_tokens=tokens.output_tokens,
                error=str(e),
            )

        return GameResult(
            seed=seed,
            won=game.is_game_won(),
            foundation_cards=game.foundation_count(),
            total_moves=total_moves,
            invalid_moves=invalid_moves,
            draw_count=draw_count,
            input_tokens=tokens.input_tokens,
            cached_input_tokens=tokens.cached_input_tokens,
            reasoning_tokens=tokens.reasoning_tokens,
            output_tokens=tokens.output_tokens,
        )

    def run(self) -> BenchmarkResults:
        """Run all benchmark games and return aggregated results."""
        results: list[GameResult] = []
        for i in range(self.games):
            seed = self.start_seed + i
            console.print(
                f"Game {i + 1}/{self.games} (seed={seed})...",
                end=" ",
            )
            result = self.play_one_game(seed)
            status = "WON" if result.won else f"{result.foundation_cards}/52"
            total_tok = result.input_tokens + result.output_tokens
            msg = (
                f"{status}"
                f" | moves={result.total_moves}"
                f" invalid={result.invalid_moves}"
                f" draws={result.draw_count}"
                f" | tokens={total_tok}"
            )
            if result.error:
                msg += f" | error: {result.error}"
            console.print(msg)
            results.append(result)

        return BenchmarkResults(results=results, model=self.model)
