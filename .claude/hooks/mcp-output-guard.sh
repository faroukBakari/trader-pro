#!/bin/bash
# PostToolUse — intercepts oversized MCP tool responses.
# Dumps full response to file, replaces context via updatedMCPToolOutput.
# Exit 0 = allow (with optional JSON output for replacement).

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // ""')

# Only intercept MCP tools — updatedMCPToolOutput doesn't work for built-ins
echo "$TOOL" | grep -q '^mcp__' || exit 0

RESPONSE=$(echo "$INPUT" | jq -c '.tool_response // {}')
SIZE=${#RESPONSE}
THRESHOLD=20000

[ "$SIZE" -le "$THRESHOLD" ] && exit 0

# Dump full response to temp file
FILENAME="/tmp/claude-mcp-$(date +%s)-$$.json"
echo "$RESPONSE" | jq '.' > "$FILENAME" 2>/dev/null || echo "$RESPONSE" > "$FILENAME"
LINE_COUNT=$(wc -l < "$FILENAME")

# Preview: first 300 chars + last 200 chars
PREVIEW_HEAD=$(echo "$RESPONSE" | head -c 300)
PREVIEW_TAIL=$(echo "$RESPONSE" | tail -c 200)

# Build replacement message
MESSAGE=$(printf "Response from %s too large (%d chars, %d lines). Full output saved to: %s\n\nHead:\n%s\n\n...[truncated]...\n\nTail:\n%s" \
  "$TOOL" "$SIZE" "$LINE_COUNT" "$FILENAME" "$PREVIEW_HEAD" "$PREVIEW_TAIL")

# Output replacement via updatedMCPToolOutput — use jq to safely encode
jq -n --arg msg "$MESSAGE" '{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "updatedMCPToolOutput": $msg
  }
}'

exit 0
