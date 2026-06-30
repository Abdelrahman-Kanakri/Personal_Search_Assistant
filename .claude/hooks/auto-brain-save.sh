#!/usr/bin/env bash
# Auto brain-save (SessionEnd hook).
# On session end, resume the just-ended session headlessly and run /brain-save
# so its durable knowledge is distilled into the Claude-Brain vault and the
# graphify graph is refreshed. Works alongside the MANUAL /brain-save command —
# both stay available; this is just the automatic safety net.
#
# Hook payload (JSON) arrives on stdin: { session_id, transcript_path, cwd, reason }

# --- Loop guard --------------------------------------------------------------
# The headless brain-save we launch below is itself a Claude session that will
# fire this same SessionEnd hook. We set CLAUDE_BRAIN_AUTOSAVE=1 when launching
# it; this check makes that nested run exit immediately, so we never recurse.
if [ -n "${CLAUDE_BRAIN_AUTOSAVE:-}" ]; then
  exit 0
fi

# --- Read hook payload -------------------------------------------------------
input="$(cat)"

field() { # field <name>  -> value or empty (needs jq)
  command -v jq >/dev/null 2>&1 || return 0
  printf '%s' "$input" | jq -r ".$1 // empty" 2>/dev/null
}

session_id="$(field session_id)"
transcript="$(field transcript_path)"
cwd="$(field cwd)"

# Need a session id to resume and a transcript to judge activity.
[ -z "$session_id" ] && exit 0
{ [ -z "$transcript" ] || [ ! -f "$transcript" ]; } && exit 0

# --- Activity guard ----------------------------------------------------------
# Skip trivially short sessions (nothing worth saving). Tune MIN_LINES to taste.
MIN_LINES="${CLAUDE_BRAIN_MIN_LINES:-15}"
lines="$(wc -l < "$transcript" 2>/dev/null || echo 0)"
[ "${lines:-0}" -lt "$MIN_LINES" ] && exit 0

workdir="${cwd:-$HOME}"

# --- Dry run (for testing): print intent, don't launch ----------------------
if [ -n "${CLAUDE_BRAIN_DRYRUN:-}" ]; then
  echo "[auto-brain-save] would resume session '$session_id' in '$workdir' ($lines transcript lines)"
  exit 0
fi

# --- Launch headless brain-save, fully detached ------------------------------
# setsid + nohup + </dev/null so it survives the parent session exiting.
# CLAUDE_BRAIN_AUTOSAVE=1 trips the loop guard in the nested session.
setsid nohup env CLAUDE_BRAIN_AUTOSAVE=1 \
  bash -c "cd \"$workdir\" 2>/dev/null || cd \"$HOME\"; claude -p --resume \"$session_id\" \"/brain-save\"" \
  >/dev/null 2>&1 </dev/null &

exit 0
