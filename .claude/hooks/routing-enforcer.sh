#!/bin/bash
# Multi-event routing enforcement hook
# Events: UserPromptSubmit, PreToolUse, PostToolUse
# Soft enforcement — reminds, never blocks

INPUT=$(cat)
SESSION=$(echo "$INPUT" | jq -r '.session_id // "unknown"')
STATE="/tmp/claude-routing-${SESSION}"

# ── Detect event type ──
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""')
HAS_RESPONSE=$(echo "$INPUT" | jq 'has("tool_response")' 2>/dev/null)
USER_MSG=$(echo "$INPUT" | jq -r '.message.content // ""' 2>/dev/null)

# ── UserPromptSubmit: reset state ──
if [ -z "$TOOL_NAME" ] && [ -n "$USER_MSG" ]; then
  # Skip slash commands
  echo "$USER_MSG" | grep -q '^\s*/' && exit 0
  echo "turn=$(date +%s)|skills=0|calls=0" > "$STATE"
  exit 0
fi

# ── PostToolUse: track skill reads ──
if [ -n "$TOOL_NAME" ] && [ "$HAS_RESPONSE" = "true" ]; then
  if [ "$TOOL_NAME" = "Read" ]; then
    FPATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""')
    if echo "$FPATH" | grep -qE '\.claude/(skills|skill-bank)/'; then
      [ -f "$STATE" ] && sed -i 's/skills=[0-9]*/skills=1/' "$STATE"
    fi
  fi
  exit 0
fi

# ── PreToolUse: check routing compliance ──
if [ -n "$TOOL_NAME" ] && [ "$HAS_RESPONSE" != "true" ]; then
  # Only gate substantive tools
  case "$TOOL_NAME" in
    Edit|Write|Bash|Task|NotebookEdit) ;;
    mcp__vscode-mcp-server__create_file_code) ;;
    mcp__vscode-mcp-server__replace_lines_code) ;;
    *) exit 0 ;;  # Read/Glob/Grep/Explore = routing actions, allow
  esac

  # Read state
  [ ! -f "$STATE" ] && exit 0  # No state = continuation turn, skip
  SKILLS=$(grep -oP 'skills=\K[0-9]+' "$STATE" 2>/dev/null || echo "0")
  CALLS=$(grep -oP 'calls=\K[0-9]+' "$STATE" 2>/dev/null || echo "0")

  # Increment call counter
  NEW_CALLS=$((CALLS + 1))
  sed -i "s/calls=[0-9]*/calls=${NEW_CALLS}/" "$STATE"

  # Only remind on first substantive call (not every call)
  [ "$CALLS" -gt 0 ] && exit 0

  # Check compliance
  if [ "$SKILLS" -eq 0 ]; then
    echo "Routing check: no skill file read this turn. CLAUDE.md requires: scan glossary descriptions -> match category -> Read glossary -> load skill (or confirm no match) before substantive actions." >&2
  fi
  exit 0  # Always allow — soft enforcement only
fi

exit 0
