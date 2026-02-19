"""CLI entry point for the One-Pass Solitaire LLM benchmark."""

import argparse
import json
from pathlib import Path

from rich.console import Console

from benchmark.runner import BenchmarkConfig, BenchmarkResults, BenchmarkRunner

console = Console()


def _print_header(args: argparse.Namespace) -> None:
    """Print the benchmark header before running games."""
    console.print("=== One-Pass Solitaire LLM Benchmark ===")
    console.print(
        f"Model: {args.model} | Games: {args.games} | Start seed: {args.seed}",
    )
    console.print(
        f"Max moves: {args.max_moves} | Max retries: {args.max_retries}"
        f" | Mode: {args.mode}",
    )
    console.print()


def _print_results(results: BenchmarkResults) -> None:
    """Print the benchmark results summary."""
    console.print()
    console.print("=== RESULTS ===")
    console.print(f"Model:                {results.model}")
    console.print(f"Games played:         {len(results.results)}")
    console.print(f"Win rate:             {results.win_rate:.1%}")
    console.print(
        f"Avg foundation cards: {results.avg_foundation_cards:.1f}/52",
    )
    console.print(f"Avg total moves:      {results.avg_total_moves:.1f}")
    console.print(f"Avg invalid moves:    {results.avg_invalid_moves:.1f}")
    console.print(f"Legal move rate:      {results.legal_move_rate:.1%}")
    console.print(f"Total API calls:      {results.total_api_calls}")
    console.print()
    console.print("=== TOKEN USAGE ===")
    console.print(f"Input tokens:         {results.total_input_tokens:,}")
    console.print(
        f"Cached input tokens:  {results.total_cached_input_tokens:,}",
    )
    console.print(
        f"Reasoning tokens:     {results.total_reasoning_tokens:,}",
    )
    console.print(f"Output tokens:        {results.total_output_tokens:,}")
    console.print(f"Total tokens:         {results.total_tokens:,}")


def main() -> None:
    """Parse arguments and run the LLM benchmark."""
    parser = argparse.ArgumentParser(
        description="One-Pass Solitaire LLM Benchmark",
    )
    parser.add_argument(
        "--model",
        default="gpt-5-nano",
        help="OpenAI model to use",
    )
    parser.add_argument(
        "--games",
        type=int,
        default=10,
        help="Number of games to play",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Starting seed",
    )
    parser.add_argument(
        "--max-moves",
        type=int,
        default=200,
        help="Max moves per game",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Max retries per move",
    )
    parser.add_argument(
        "--reasoning-effort",
        default="low",
        help="Reasoning effort: low, medium, high",
    )
    parser.add_argument(
        "--mode",
        default="text",
        choices=["text", "tools"],
        help="text or tools (function calling)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed output",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Save results to JSON file",
    )

    args = parser.parse_args()

    config = BenchmarkConfig(
        model=args.model,
        games=args.games,
        start_seed=args.seed,
        max_moves=args.max_moves,
        max_retries=args.max_retries,
        reasoning_effort=args.reasoning_effort,
        mode=args.mode,
        verbose=args.verbose,
    )
    runner = BenchmarkRunner(config)

    _print_header(args)

    results = runner.run()

    _print_results(results)

    if args.output:
        with Path(args.output).open("w") as f:
            json.dump(results.to_dict(), f, indent=2)
        console.print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
