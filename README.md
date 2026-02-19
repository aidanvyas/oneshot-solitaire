# One-Pass Solitaire

A challenging Klondike variant with one pass through the stock and 4 FreeCell-style storage slots, plus an LLM benchmark suite.

## Overview

One-Pass Solitaire follows standard Klondike rules with two twists: you only get **one pass** through the stock pile (no recycling), and you have **4 storage slots** where any single card can be temporarily stashed. The storage slots add strategic depth while the single pass makes the game significantly harder than standard Klondike.

Three ways to play:
- **CLI** — text-based terminal interface
- **GUI** — pygame with drag-and-drop, hints, and a rules viewer
- **Benchmark** — watch LLMs play via the OpenAI Responses API

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

## Installation

```bash
pip install -r requirements.txt
```

`pygame` is needed for the GUI and `openai` for the benchmark. The CLI and engine have no dependencies beyond the standard library.

## Usage

### CLI

```bash
python one_shot_solitaire.py
```

Commands: `d` draw, `f` foundation, `t <col>` tableau, `s <slot>` storage, `m <src> <dst>` move between tableau/storage, `q` quit, `r` reset, `h` help.

### GUI

```bash
python one_shot_solitaire_gui.py
```

Drag-and-drop cards, click the stock to draw, and use the hint and rules buttons.

### Benchmark

```bash
python -m benchmark --model gpt-4o-mini --games 10 --seed 42 --verbose
```

Key flags:

| Flag | Default | Description |
|------|---------|-------------|
| `--model` | `gpt-4o-mini` | OpenAI model name |
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
python -m pytest tests/ -v
make test    # runs unittest
make check   # py_compile syntax check
```

## Game Rules

See [rules.md](rules.md) for the full rulebook.

**Quick summary:** 7 tableau columns with cards built down in alternating colors. 4 foundation piles built up by suit from Ace to King. 4 storage slots that each hold any single card. One pass through the stock — no recycling.
