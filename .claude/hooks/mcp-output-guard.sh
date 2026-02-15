#!/bin/bash
# PostToolUse — intercepts oversized MCP tool responses.
# Dumps full response to file, replaces context with a structure-aware preview.
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

# Structure-aware preview: try JSON shape first, fall back to head/tail
PREVIEW=$(echo "$RESPONSE" | jq '
  # For objects: show keys and truncate long string values / arrays
  if type == "object" then
    to_entries | map(
      if (.value | type) == "array" then
        .value = "[\(.value | length) items]"
      elif (.value | type) == "string" and (.value | length) > 120 then
        .value = .value[:120] + "..."
      elif (.value | type) == "object" then
        .value = "{\(.value | keys | join(", "))}"
      else . end
    ) | from_entries
  # For arrays: show first 3 items and count
  elif type == "array" then
    { "total_items": length, "first_items": .[:3] }
  else .
  end
' 2>/dev/null)

if [ $? -eq 0 ] && [ -n "$PREVIEW" ]; then
  # JSON structure preview succeeded
  MESSAGE=$(printf "Response from %s too large (%d chars, %d lines). Full output: %s\n\nStructure:\n%s" \
    "$TOOL" "$SIZE" "$LINE_COUNT" "$FILENAME" "$PREVIEW")
else
  # Non-JSON fallback: head + tail lines
  PREVIEW_HEAD=$(head -c 600 <<< "$RESPONSE")
  PREVIEW_TAIL=$(tail -c 300 <<< "$RESPONSE")
  MESSAGE=$(printf "Response from %s too large (%d chars, %d lines). Full output: %s\n\nHead:\n%s\n\n...[truncated]...\n\nTail:\n%s" \
    "$TOOL" "$SIZE" "$LINE_COUNT" "$FILENAME" "$PREVIEW_HEAD" "$PREVIEW_TAIL")
fi

# Output replacement via updatedMCPToolOutput
jq -n --arg msg "$MESSAGE" '{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "updatedMCPToolOutput": $msg
  }
}'

exit 0
