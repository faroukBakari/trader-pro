#!/bin/bash
# Delivery gate — Stop hook enforcing CLAUDE.md §1 "No Unverified Output"
# Checks that source code changes were followed by verification (diagnostics/tests)
# Mode: DELIVERY_GATE_MODE=warn (default) or block
# Fail-open: any parse error, missing transcript, jq failure → allow exit

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Read input from stdin
INPUT=$(cat)
TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path // ""' 2>/dev/null) || exit 0
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"' 2>/dev/null) || true

# Fail-open: missing or empty transcript
[ -z "$TRANSCRIPT" ] && exit 0
[ ! -f "$TRANSCRIPT" ] && exit 0
[ ! -s "$TRANSCRIPT" ] && exit 0

# Source transcript library
LIB="$SCRIPT_DIR/lib/transcript.sh"
[ ! -f "$LIB" ] && exit 0
# shellcheck source=lib/transcript.sh
source "$LIB" || exit 0

# Get modified files
MODIFIED=$(transcript_modified_files "$TRANSCRIPT" 2>/dev/null) || exit 0
[ -z "$MODIFIED" ] && exit 0

# Filter to SOURCE files only (exclude docs, config, IA stack)
SOURCE_EXTS='\.py$\|\.ts$\|\.tsx$\|\.js$\|\.jsx$\|\.vue$'
EXCLUDE_PATHS='\.claude/'
SOURCE_FILES=$(echo "$MODIFIED" | grep -E '\.(py|ts|tsx|js|jsx|vue)$' | grep -v '\.claude/' 2>/dev/null) || true

# No source files modified → allow exit
[ -z "$SOURCE_FILES" ] && exit 0

# Find the last line number where a source file was modified
last_change_line=0
while IFS= read -r fpath; do
  # Check Edit tool for this file
  grep -n "\"file_path\":\"${fpath}\"\|\"file_path\": \"${fpath}\"\|\"path\":\"${fpath}\"\|\"path\": \"${fpath}\"" "$TRANSCRIPT" 2>/dev/null | \
    grep '"Edit"\|"Write"\|"create_file_code"\|"replace_lines_code"' | \
    tail -1 | cut -d: -f1 | while read -r ln; do
      [ -n "$ln" ] && [ "$ln" -gt "$last_change_line" ] && echo "$ln"
    done
done <<< "$SOURCE_FILES" | sort -n | tail -1 | read -r max_line || true

[ -n "$max_line" ] && last_change_line="$max_line"

# Fallback: if we couldn't determine line, use the last Edit/Write/MCP write line
if [ "$last_change_line" -eq 0 ]; then
  for tool in "Edit" "Write" "mcp__vscode-mcp-server__create_file_code" "mcp__vscode-mcp-server__replace_lines_code"; do
    ln=$(transcript_last_tool_line "$tool" "$TRANSCRIPT")
    [ "$ln" -gt "$last_change_line" ] && last_change_line="$ln"
  done
fi

[ "$last_change_line" -eq 0 ] && exit 0

# Check for verification after last change
verification_found=0

# Check 1: get_diagnostics_code after last change
if transcript_has_tool_after_line "get_diagnostics_code" "$last_change_line" "$TRANSCRIPT" 2>/dev/null; then
  verification_found=1
fi

# Check 2: Bash commands containing test runners after last change
if [ "$verification_found" -eq 0 ]; then
  # Get all Bash tool lines after last_change_line
  bash_lines=$(transcript_tool_lines "Bash" "$TRANSCRIPT" 2>/dev/null) || true
  while IFS= read -r bash_line; do
    [ -z "$bash_line" ] && continue
    [ "$bash_line" -le "$last_change_line" ] && continue
    # Extract the command from this line and check for test patterns
    cmd=$(sed -n "${bash_line}p" "$TRANSCRIPT" 2>/dev/null | jq -r '
      .message.content[]? // empty |
      select(.type == "tool_use" and .name == "Bash") |
      .input.command // empty
    ' 2>/dev/null) || true
    if echo "$cmd" | grep -qE 'pytest|test|make test|make check|npm test|vitest|jest'; then
      verification_found=1
      break
    fi
  done <<< "$bash_lines"
fi

# Verification found → allow exit
[ "$verification_found" -eq 1 ] && exit 0

# No verification found — check mode
MODE="${DELIVERY_GATE_MODE:-warn}"
STATE_FILE="/tmp/claude-delivery-gate-${SESSION_ID}"

# Safety valve: max 2 blocks per session
block_count=0
if [ -f "$STATE_FILE" ]; then
  block_count=$(cat "$STATE_FILE" 2>/dev/null) || block_count=0
fi

if [ "$MODE" = "block" ] && [ "$block_count" -lt 2 ]; then
  # Increment block counter
  echo "$((block_count + 1))" > "$STATE_FILE"
  # Output JSON to block exit and inject verification prompt
  cat <<EOF
{
  "decision": "block",
  "reason": "You modified source files but haven't verified changes. Please run diagnostics (get_diagnostics_code) and/or relevant tests before exiting.",
  "systemMessage": "Delivery gate: verification required (block $((block_count + 1))/2)"
}
EOF
  exit 0
else
  # Warn mode (default) or safety valve exceeded
  if [ "$block_count" -ge 2 ]; then
    echo "Delivery gate: verification skipped (safety valve — blocked $block_count times already)." >&2
  else
    echo "Delivery gate: source files modified without verification. Consider running diagnostics or tests." >&2
  fi
  exit 0
fi
