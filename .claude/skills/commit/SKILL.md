---
name: commit
description: Run tests and create a git commit for all current changes
---

Run tests, then create a git commit for all current changes.

Steps:
1. Run `uv run pytest -v` and confirm all tests pass. If any fail, stop and report the failures — do not commit.
2. Run `git status` and `git diff` to review all changes (staged and unstaged).
3. Run `git log --oneline -5` to see recent commit message style.
4. Stage all relevant changed files by name (never use `git add .` or `git add -A`). Do not stage files that look like secrets (.env, credentials, etc.).
5. Write a concise commit message (1-2 sentences) that focuses on the "why" not the "what". Follow the style of recent commits.
6. Commit with the message, appending: `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`
7. Run `git status` to confirm the commit succeeded.

If there are no changes to commit, say so and stop.
