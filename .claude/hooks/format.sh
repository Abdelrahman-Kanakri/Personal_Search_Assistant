#!/usr/bin/env bash
# PostToolUse hook: auto-format Python after Claude writes/edits a file.
# Fails soft — never break the session if ruff isn't installed.
set -euo pipefail
if command -v ruff >/dev/null 2>&1; then
  ruff format . 2>/dev/null || true
  ruff check --fix . 2>/dev/null || true
fi
exit 0
