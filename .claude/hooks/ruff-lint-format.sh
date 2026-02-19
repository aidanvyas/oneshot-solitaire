#!/bin/bash
# .claude/hooks/ruff-lint-format.sh
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))")

# Only lint Python files
if [[ "$FILE_PATH" != *.py ]]; then
  exit 0
fi

# Auto-fix what ruff can
ruff check --fix "$FILE_PATH" 2>/dev/null

# Format
ruff format "$FILE_PATH" 2>/dev/null

# Check for remaining unfixable issues
RESULT=$(ruff check "$FILE_PATH" 2>&1)
if [ $? -ne 0 ]; then
  echo "$RESULT" >&2
  exit 2  # Claude sees the remaining violations and tries to fix them
fi

exit 0
