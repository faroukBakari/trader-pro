#!/bin/bash
# Multi-event routing enforcement hook
# Events: UserPromptSubmit, PreToolUse, PostToolUse
# Soft enforcement — reminds, never blocks

INPUT=$(cat)
SESSION=$(echo "$INPUT" | jq -r '.session_id // "unknown"')
EVENT=$(echo "$INPUT" | jq -r '.hook_event_name // ""')
STATE="/tmp/claude-routing-${SESSION}"

# ── UserPromptSubmit: reset per-turn state, preserve convergence counters ──
if [ "$EVENT" = "UserPromptSubmit" ]; then
  if [ -f "$STATE" ]; then
    # shellcheck source=/dev/null
    source "$STATE"
    echo "skills=0 calls=0 total=${total:-0} warned8=${warned8:-0} warned12=${warned12:-0}" > "$STATE"
  else
    echo "skills=0 calls=0 total=0 warned8=0 warned12=0" > "$STATE"
  fi
  exit 0
fi

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""')

# ── PostToolUse: track skill reads ──
if [ "$EVENT" = "PostToolUse" ]; then
  if [ "$TOOL_NAME" = "Read" ]; then
    FPATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""')
    if echo "$FPATH" | grep -qE '\.claude/(skills|skill-bank)/'; then
      [ -f "$STATE" ] && sed -i 's/skills=0/skills=1/' "$STATE"
    fi
  elif [ "$TOOL_NAME" = "Skill" ]; then
    # User-invoked skill — counts as routed
    [ -f "$STATE" ] && sed -i 's/skills=0/skills=1/' "$STATE"
  fi
  exit 0
fi

# ── PreToolUse: check routing compliance ──
if [ "$EVENT" = "PreToolUse" ]; then
  # Only gate substantive tools
  case "$TOOL_NAME" in
    Edit|Write|Bash|Task|NotebookEdit) ;;
    mcp__vscode-mcp-server__create_file_code) ;;
    mcp__vscode-mcp-server__replace_lines_code) ;;
    *) exit 0 ;;  # Read/Glob/Grep/Explore = routing actions, allow
  esac

  # No state = continuation turn, skip
  [ ! -f "$STATE" ] && exit 0

  # shellcheck source=/dev/null
  source "$STATE"

  # Increment call counters
  calls=$((calls + 1))
  total=$((${total:-0} + 1))
  echo "skills=${skills} calls=${calls} total=${total} warned8=${warned8:-0} warned12=${warned12:-0}" > "$STATE"

  # Check compliance: remind on 1st and 3rd substantive call
  if [ "$skills" -eq 0 ] && { [ "$calls" -eq 1 ] || [ "$calls" -eq 3 ]; }; then
    echo "Routing check: no skill file read this turn. CLAUDE.md requires: scan glossary descriptions -> match category -> Read glossary -> load skill (or confirm no match) before substantive actions." >&2
  fi

  # Convergence warnings (non-blocking, fire once each per session)
  if [ "$total" -ge 12 ] && [ "${warned12:-0}" -eq 0 ]; then
    echo "FinOps hard stop: ${total} substantive calls. Surface status to user or delegate." >&2
    sed -i 's/warned12=0/warned12=1/' "$STATE"
  elif [ "$total" -ge 8 ] && [ "${warned8:-0}" -eq 0 ]; then
    echo "FinOps checkpoint: ${total} substantive calls without deliverable. Reassess approach." >&2
    sed -i 's/warned8=0/warned8=1/' "$STATE"
  fi
  exit 0
fi

exit 0
