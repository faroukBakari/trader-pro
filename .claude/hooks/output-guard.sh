#!/bin/bash
# PreToolUse — blocks Bash commands likely to produce unbounded output.
# Exit 0 = allow, Exit 2 = deny (stderr guidance to Claude).

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // ""')
[ "$TOOL" != "Bash" ] && exit 0

CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""')
[ -z "$CMD" ] && exit 0

# ── Universal mitigating patterns: if present, allow through ──
if echo "$CMD" | grep -qE '\| head|\| tail|\| wc|> /tmp/|>> /tmp/|tee /tmp/|\| grep|timeout '; then
  exit 0
fi

# ── Risky pattern checks ──

# grep -r / -R / --recursive (unbounded recursive search)
if echo "$CMD" | grep -qE '\bgrep\s+(-[a-zA-Z]*[rR]|--recursive)\b'; then
  echo "Unbounded recursive grep. Add '| head -50' or use the Grep tool instead." >&2
  exit 2
fi

# bare ripgrep without file scope (rg <pattern> with no path/glob constraint)
if echo "$CMD" | grep -qE '^\s*rg\s'; then
  echo "Bare ripgrep may produce unbounded output. Add '| head -50' or use the Grep tool instead." >&2
  exit 2
fi

# cat <file> (dumps entire file)
if echo "$CMD" | grep -qE '^\s*cat\s'; then
  echo "cat dumps entire file into context. Use the Read tool with line ranges instead." >&2
  exit 2
fi

# docker logs without --tail
if echo "$CMD" | grep -qE '\bdocker\s+(logs|compose\s+logs)\b'; then
  echo "$CMD" | grep -q -- '--tail' && : || {
    echo "docker logs without --tail is unbounded. Add '--tail 100'." >&2
    exit 2
  }
fi

# git log without -n or --oneline
if echo "$CMD" | grep -qE '\bgit\s+log\b'; then
  if ! echo "$CMD" | grep -qE -- '\s-n\s*[0-9]|--oneline|-[0-9]+\b'; then
    echo "git log without -n limit. Add '-n 20' or '--oneline'." >&2
    exit 2
  fi
fi

# git diff (bare, no --stat/--name-only/--name-status and no path scope after --)
if echo "$CMD" | grep -qE '^\s*git\s+diff\b'; then
  if ! echo "$CMD" | grep -qE -- '--stat|--name-only|--name-status|--cached|-- '; then
    echo "Bare git diff can produce large output. Add '--stat' first, then targeted diff." >&2
    exit 2
  fi
fi

exit 0
