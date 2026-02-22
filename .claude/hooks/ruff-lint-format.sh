#!/bin/bash
# .claude/hooks/ruff-lint-format.sh
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))")

# Only lint Python files
if [[ "$FILE_PATH" != *.py ]]; then
  exit 0
fi

# Find ruff: prefer ~/.local/bin, then PATH
RUFF=$(command -v ruff 2>/dev/null || echo "$HOME/.local/bin/ruff")
if [ ! -x "$RUFF" ]; then
  exit 0  # ruff not available; skip silently
fi

# Auto-fix what ruff can
"$RUFF" check --fix "$FILE_PATH" 2>/dev/null

# Format
"$RUFF" format "$FILE_PATH" 2>/dev/null

# Check for remaining unfixable issues
RESULT=$("$RUFF" check "$FILE_PATH" 2>&1)
if [ $? -ne 0 ]; then
  echo "$RESULT" >&2
  exit 2  # Claude sees the remaining violations and tries to fix them
fi

exit 0
