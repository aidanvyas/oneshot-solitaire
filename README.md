# One-Pass Solitaire

A challenging Klondike variant with one pass through the stock and 4 FreeCell-style storage slots, plus an LLM benchmark suite.

## Quick Start

### 1. Clone and Install

```bash
gh repo clone aidanvyas/oneshot-solitaire
cd oneshot-solitaire
uv sync  # Install dependencies with uv
```

### 2. Play

```bash
# Terminal
uv run python one_shot_solitaire.py

# GUI
uv run python one_shot_solitaire_gui.py
```

### 3. Benchmark an LLM

```bash
# Set your OpenAI API key
export OPENAI_API_KEY=your_api_key_here

# Quick test (10 games, gpt-5-nano)
uv run python -m benchmark --games 10 --seed 42 --verbose

# Compare models
uv run python -m benchmark --model o4-mini --games 10 --seed 42 --verbose
```

## Game Mechanics

Standard Klondike with two key differences:

1. **One pass** — you get a single pass through the stock pile. No recycling.
2. **4 storage slots** — FreeCell-style slots where any single card can be temporarily stashed, adding strategic depth.

See [rules.md](rules.md) for the full rulebook.

## Project Structure

```
engine.py                 # Game logic (Card, OnePassSolitaire)
one_shot_solitaire.py     # CLI player
one_shot_solitaire_gui.py # Pygame GUI
rules.md                  # Full rulebook
benchmark/                # LLM benchmark suite
  main.py                 # CLI entry point + argument parsing
  runner.py               # Game loop + result tracking
  llm_player.py           # Text-mode LLM player (OpenAI Responses API)
  llm_player_tools.py     # Tool-calling mode LLM player
  text_protocol.py        # Game state renderer + move parser
tests/                    # 89 unit tests
```

## Benchmark

Run LLMs against the game via the OpenAI Responses API:

```bash
uv run python -m benchmark --games 10 --seed 42 --verbose
```

| Flag | Default | Description |
|------|---------|-------------|
| `--model` | `gpt-5-nano` | OpenAI model name |
| `--games` | `10` | Number of games to play |
| `--seed` | `42` | Starting seed (increments per game) |
| `--reasoning-effort` | `low` | `low`, `medium`, or `high` |
| `--mode` | `text` | `text` or `tools` (function calling) |
| `--max-moves` | `200` | Max moves per game |
| `--max-retries` | `3` | Max retries on illegal moves |
| `--output` | — | Save results to JSON file |
| `--verbose` | off | Print detailed output |

## Testing

```bash
uv run pytest -v     # 89 unit tests
make test            # same thing via Makefile
make check           # py_compile syntax check
```

## Dependencies

| Component | Dependencies |
|-----------|-------------|
| Engine + CLI | None (stdlib only) |
| GUI | `pygame` |
| Benchmark | `openai` |
| Dev | `pytest` |

## License

[MIT](LICENSE)
