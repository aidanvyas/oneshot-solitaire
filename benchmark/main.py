import argparse
import json

from benchmark.runner import BenchmarkRunner


def main():
    parser = argparse.ArgumentParser(description="One-Pass Solitaire LLM Benchmark")
    parser.add_argument("--model", default="gpt-4o-mini", help="OpenAI model to use")
    parser.add_argument("--games", type=int, default=10, help="Number of games to play")
    parser.add_argument("--seed", type=int, default=42, help="Starting seed")
    parser.add_argument("--max-moves", type=int, default=200, help="Max moves per game")
    parser.add_argument("--max-retries", type=int, default=3, help="Max retries per move")
    parser.add_argument("--reasoning-effort", default="low", help="Reasoning effort: low, medium, high")
    parser.add_argument("--mode", default="text", choices=["text", "tools"], help="text or tools (function calling)")
    parser.add_argument("--verbose", action="store_true", help="Print detailed output")
    parser.add_argument("--output", type=str, help="Save results to JSON file")

    args = parser.parse_args()

    runner = BenchmarkRunner(
        model=args.model,
        games=args.games,
        start_seed=args.seed,
        max_moves=args.max_moves,
        max_retries=args.max_retries,
        reasoning_effort=args.reasoning_effort,
        mode=args.mode,
        verbose=args.verbose,
    )

    print(f"=== One-Pass Solitaire LLM Benchmark ===")
    print(f"Model: {args.model} | Games: {args.games} | Start seed: {args.seed}")
    print(f"Max moves: {args.max_moves} | Max retries: {args.max_retries} | Mode: {args.mode}")
    print()

    results = runner.run()

    print()
    print("=== RESULTS ===")
    print(f"Model:                {results.model}")
    print(f"Games played:         {len(results.results)}")
    print(f"Win rate:             {results.win_rate:.1%}")
    print(f"Avg foundation cards: {results.avg_foundation_cards:.1f}/52")
    print(f"Avg total moves:      {results.avg_total_moves:.1f}")
    print(f"Avg invalid moves:    {results.avg_invalid_moves:.1f}")
    print(f"Legal move rate:      {results.legal_move_rate:.1%}")
    print(f"Total API calls:      {results.total_api_calls}")
    print()
    print("=== TOKEN USAGE ===")
    print(f"Input tokens:         {results.total_input_tokens:,}")
    print(f"Cached input tokens:  {results.total_cached_input_tokens:,}")
    print(f"Reasoning tokens:     {results.total_reasoning_tokens:,}")
    print(f"Output tokens:        {results.total_output_tokens:,}")
    print(f"Total tokens:         {results.total_tokens:,}")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results.to_dict(), f, indent=2)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
