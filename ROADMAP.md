# Roadmap

## Phase 1: Web UI
- Port the Pygame GUI to a web app (HTML/CSS/JS + Python backend)
- Serve on localhost for local development
- Full human-playable game with drag-and-drop or click-to-move

## Phase 2: Polish the human game
- Smooth animations, undo, seed selection, win/loss stats
- Eventually deploy to aidanvyas.github.io

## Phase 3: Solver and move grading
- Exact solver (DFS with full card knowledge via seed)
- Per-move EV scoring — rank every legal move by best achievable outcome
- Human baseline metrics from real play sessions

## Phase 4: LLM benchmarking
- Scaffold LLM play through the web UI (observation panel showing prompts, responses, tool calls)
- Benchmark suite: move-level grading (EV-optimal move rate, blunder rate)
- Multi-model comparison (varying reasoning effort, text vs tool-calling modes)
