#!/usr/bin/env bash
# Profile the solver using macOS `sample` (no extra installs needed).
#
# Usage:
#   cd solver && bash profile.sh
#
# Output: profile.txt in the solver/ directory — a call tree with CPU %.
# If cargo-flamegraph is installed, also generates flamegraph.svg.

set -euo pipefail
cd "$(dirname "$0")"

INPUT="/tmp/oneshot_bench_input.jsonl"
OUTPUT="profile.txt"

# Generate a hard mid-game position for the solver to chew on.
echo "Generating bench input..."
cd .. && uv run python solver/generate_bench_input.py > "$INPUT" && cd solver

# Benchmark mode: run 3 timed iterations with the release binary.
if [[ "${1:-}" == "--bench" ]]; then
    echo "Building release binary..."
    cargo build --release 2>&1 | tail -1
    BINARY="target/release/oneshot-solver"
    echo ""
    echo "Benchmark (3 runs):"
    for i in 1 2 3; do
        echo "--- Run $i ---"
        time "$BINARY" < "$INPUT"
        echo ""
    done
    exit 0
fi

BINARY="target/profiling/oneshot-solver"

# Build with profiling profile (release optimizations + debug symbols).
echo "Building with profiling profile..."
cargo build --profile profiling 2>&1 | tail -1

# Launch the solver in the background, feeding it the bench input.
echo "Running solver for ~10s while sampling..."
"$BINARY" < "$INPUT" &
SOLVER_PID=$!

# Give it a moment to start the search, then sample for 9 seconds.
sleep 0.5
sample "$SOLVER_PID" 9 -f "$OUTPUT" 2>/dev/null || true

# Wait for the solver to finish.
wait "$SOLVER_PID" 2>/dev/null || true

echo ""
echo "Profile saved to: solver/$OUTPUT"
echo "Open it in a text editor — look for the heaviest call stacks."
echo ""
echo "Tip: search for 'max_node', 'chance_node', 'legal_moves', 'clone'"
echo "to find the hot functions."

# If cargo-flamegraph is available, also generate an SVG.
if command -v cargo-flamegraph &>/dev/null; then
    echo ""
    echo "cargo-flamegraph detected — generating flamegraph.svg..."
    cargo flamegraph \
        --profile profiling \
        --output flamegraph.svg \
        -- < "$INPUT"
    echo "Open solver/flamegraph.svg in a browser."
fi
