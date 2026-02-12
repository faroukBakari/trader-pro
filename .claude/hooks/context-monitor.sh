#!/bin/bash
# statusLine hook — persists context % to temp file for other hooks to read.
# Receives JSON on stdin with context_window.used_percentage.

INPUT=$(cat)
PCT=$(echo "$INPUT" | jq -r '.context_window.used_percentage // 0' 2>/dev/null)

[ -z "$PCT" ] || [ "$PCT" = "null" ] && exit 0

echo "$PCT" > /tmp/claude-context-pct

# Visual warning in statusLine when context is getting high
PCT_INT=${PCT%.*}
PCT_INT=${PCT_INT:-0}

if [ "$PCT_INT" -ge 50 ]; then
  echo "!! COMPACT SOON (${PCT_INT}%)"
elif [ "$PCT_INT" -ge 40 ]; then
  echo "ctx:${PCT_INT}%"
fi
