#!/usr/bin/env bash
# SessionStart hook: print persistent notes so they enter context each session.
# This is what makes the (non-native) agent-memory/ folder actually do something.
set -euo pipefail
MEM="${CLAUDE_PROJECT_DIR:-.}/.claude/agent-memory/notes.md"
if [ -f "$MEM" ]; then
  echo "## Persistent project notes (agent-memory)"
  cat "$MEM"
fi
exit 0
