#!/bin/bash
# UserPromptSubmit hook — blocks prompts when context is at/above threshold.
# Reads context_window.used_percentage directly from stdin JSON.
# Exit 0 = allow, Exit 2 = block (stderr shown to user).

INPUT=$(cat)
PCT=$(echo "$INPUT" | jq -r '.context_window.used_percentage // 0' 2>/dev/null)

[ -z "$PCT" ] || [ "$PCT" = "null" ] && exit 0

PCT_INT=${PCT%.*}
PCT_INT=${PCT_INT:-0}

if [ "$PCT_INT" -ge 55 ]; then
  echo "Context at ${PCT_INT}% — run /compact before continuing." >&2
  exit 2
fi

exit 0
