from dataclasses import dataclass, field
from typing import Optional
import json

from engine import OnePassSolitaire
from benchmark.text_protocol import render_game_state, parse_move
from benchmark.llm_player import LLMPlayer
from benchmark.llm_player_tools import ToolCallPlayer


@dataclass
class GameResult:
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
    error: Optional[str] = None


@dataclass
class BenchmarkResults:
    results: list  # list of GameResult
    model: str

    @property
    def win_rate(self):
        return sum(1 for r in self.results if r.won) / len(self.results) if self.results else 0

    @property
    def avg_foundation_cards(self):
        return sum(r.foundation_cards for r in self.results) / len(self.results) if self.results else 0

    @property
    def avg_total_moves(self):
        return sum(r.total_moves for r in self.results) / len(self.results) if self.results else 0

    @property
    def avg_invalid_moves(self):
        return sum(r.invalid_moves for r in self.results) / len(self.results) if self.results else 0

    @property
    def legal_move_rate(self):
        total = sum(r.total_moves + r.invalid_moves for r in self.results)
        legal = sum(r.total_moves for r in self.results)
        return legal / total if total > 0 else 0

    @property
    def total_api_calls(self):
        return sum(r.total_moves + r.invalid_moves for r in self.results)

    @property
    def total_input_tokens(self):
        return sum(r.input_tokens for r in self.results)

    @property
    def total_cached_input_tokens(self):
        return sum(r.cached_input_tokens for r in self.results)

    @property
    def total_reasoning_tokens(self):
        return sum(r.reasoning_tokens for r in self.results)

    @property
    def total_output_tokens(self):
        return sum(r.output_tokens for r in self.results)

    @property
    def total_tokens(self):
        return self.total_input_tokens + self.total_output_tokens

    def to_dict(self):
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


class BenchmarkRunner:
    def __init__(self, model="gpt-4o-mini", games=10, start_seed=42,
                 max_moves=200, max_retries=3, reasoning_effort="low",
                 mode="text", verbose=False):
        self.model = model
        self.games = games
        self.start_seed = start_seed
        self.max_moves = max_moves
        self.max_retries = max_retries
        self.reasoning_effort = reasoning_effort
        self.mode = mode
        self.verbose = verbose

    def play_one_game(self, seed):
        game = OnePassSolitaire(seed=seed)
        if self.mode == "tools":
            player = ToolCallPlayer(model=self.model, max_retries=self.max_retries, reasoning_effort=self.reasoning_effort)
        else:
            player = LLMPlayer(model=self.model, max_retries=self.max_retries, reasoning_effort=self.reasoning_effort)

        total_moves = 0
        invalid_moves = 0
        draw_count = 0
        turn_number = 0
        input_tokens = 0
        cached_input_tokens = 0
        reasoning_tokens = 0
        output_tokens = 0

        try:
            while total_moves < self.max_moves:
                if game.is_game_won() or game.is_game_over():
                    break

                turn_number += 1
                state_text = render_game_state(game, turn_number)

                # Try to get a valid move from the LLM
                error_feedback = None
                retries = 0
                move_made = False

                while retries <= self.max_retries:
                    raw_response, token_usage = player.get_move(
                        state_text if retries == 0 else state_text,
                        error_feedback=error_feedback if retries > 0 else None,
                    )

                    # Accumulate tokens
                    input_tokens += token_usage["input_tokens"]
                    cached_input_tokens += token_usage["cached_input_tokens"]
                    reasoning_tokens += token_usage["reasoning_tokens"]
                    output_tokens += token_usage["output_tokens"]

                    if self.verbose:
                        print(f"  Turn {turn_number} (retry {retries}): LLM says '{raw_response}'", flush=True)

                    move = parse_move(raw_response)

                    if move is None:
                        invalid_moves += 1
                        retries += 1
                        error_feedback = f"Could not parse your response '{raw_response}'. Use exact command format: d, f, t N, s N, m tN tM, etc."
                        continue

                    success, err_msg = game.step(move)

                    if success:
                        total_moves += 1
                        if move == 'draw':
                            draw_count += 1
                        move_made = True
                        break
                    else:
                        invalid_moves += 1
                        retries += 1
                        error_feedback = err_msg

                if not move_made:
                    # Max retries exhausted -- force draw if possible, else end
                    if game.stock:
                        game.step('draw')
                        total_moves += 1
                        draw_count += 1
                        if self.verbose:
                            print(f"  Turn {turn_number}: Forced draw after max retries", flush=True)
                    else:
                        if self.verbose:
                            print(f"  Turn {turn_number}: No valid move found, ending game", flush=True)
                        break

            return GameResult(
                seed=seed,
                won=game.is_game_won(),
                foundation_cards=game.foundation_count(),
                total_moves=total_moves,
                invalid_moves=invalid_moves,
                draw_count=draw_count,
                input_tokens=input_tokens,
                cached_input_tokens=cached_input_tokens,
                reasoning_tokens=reasoning_tokens,
                output_tokens=output_tokens,
            )
        except Exception as e:
            return GameResult(
                seed=seed,
                won=False,
                foundation_cards=game.foundation_count(),
                total_moves=total_moves,
                invalid_moves=invalid_moves,
                draw_count=draw_count,
                input_tokens=input_tokens,
                cached_input_tokens=cached_input_tokens,
                reasoning_tokens=reasoning_tokens,
                output_tokens=output_tokens,
                error=str(e),
            )

    def run(self):
        results = []
        for i in range(self.games):
            seed = self.start_seed + i
            print(f"Game {i+1}/{self.games} (seed={seed})...", end=" ", flush=True)
            result = self.play_one_game(seed)
            status = "WON" if result.won else f"{result.foundation_cards}/52"
            tokens_str = f"tokens={result.input_tokens + result.output_tokens}"
            print(f"{status} | moves={result.total_moves} invalid={result.invalid_moves} draws={result.draw_count} | {tokens_str}" +
                  (f" | error: {result.error}" if result.error else ""))
            results.append(result)

        return BenchmarkResults(results=results, model=self.model)
