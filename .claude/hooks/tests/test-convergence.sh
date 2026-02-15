#!/bin/bash
# Tests for convergence counter in routing-enforcer.sh
# Usage: bash .claude/hooks/tests/test-convergence.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK="$SCRIPT_DIR/../routing-enforcer.sh"
TMPDIR=$(mktemp -d)
trap "rm -rf '$TMPDIR'" EXIT

PASS=0
FAIL=0
SESSION="test-convergence-$$"
STATE="/tmp/claude-routing-${SESSION}"

pass() { PASS=$((PASS + 1)); echo "  PASS: $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  FAIL: $1 — $2"; }

# Simulate a hook call
send_event() {
  local event="$1" tool_name="${2:-}"
  local input
  if [ -n "$tool_name" ]; then
    input=$(jq -n --arg ev "$event" --arg sid "$SESSION" --arg tn "$tool_name" \
      '{hook_event_name: $ev, session_id: $sid, tool_name: $tn}')
  else
    input=$(jq -n --arg ev "$event" --arg sid "$SESSION" \
      '{hook_event_name: $ev, session_id: $sid}')
  fi
  echo "$input" | bash "$HOOK" 2>"$TMPDIR/stderr"
}

# Reset state for a clean test
reset_state() {
  rm -f "$STATE"
}

get_total() {
  [ -f "$STATE" ] && source "$STATE" && echo "${total:-0}" || echo "0"
}

get_warned8() {
  [ -f "$STATE" ] && source "$STATE" && echo "${warned8:-0}" || echo "0"
}

get_warned12() {
  [ -f "$STATE" ] && source "$STATE" && echo "${warned12:-0}" || echo "0"
}

get_calls() {
  [ -f "$STATE" ] && source "$STATE" && echo "${calls:-0}" || echo "0"
}

# ── T3.1: 7 calls — no warning ──
echo "T3.1: 7 substantive calls — no warning"
reset_state
send_event "UserPromptSubmit"
# Mark skills=1 to suppress routing reminders (not testing that here)
sed -i 's/skills=0/skills=1/' "$STATE"

for i in $(seq 1 7); do
  send_event "PreToolUse" "Edit"
done
total=$(get_total)
stderr=$(cat "$TMPDIR/stderr")
[ "$total" -eq 7 ] && pass "T3.1a total=7" || fail "T3.1a" "expected total=7, got $total"
echo "$stderr" | grep -q "FinOps" && fail "T3.1b" "should not warn at 7" || pass "T3.1b no warning"

# ── T3.2: 8th call — checkpoint warning ──
echo "T3.2: 8th call — checkpoint warning"
send_event "PreToolUse" "Edit"
stderr=$(cat "$TMPDIR/stderr")
total=$(get_total)
[ "$total" -eq 8 ] && pass "T3.2a total=8" || fail "T3.2a" "expected total=8, got $total"
echo "$stderr" | grep -q "FinOps checkpoint" && pass "T3.2b checkpoint warning" || fail "T3.2b" "expected checkpoint, got: $stderr"

# ── T3.3: 9th call — no repeated warning ──
echo "T3.3: 9th call — no repeated warning"
send_event "PreToolUse" "Edit"
stderr=$(cat "$TMPDIR/stderr")
echo "$stderr" | grep -q "FinOps" && fail "T3.3" "should not re-warn at 9" || pass "T3.3 no repeated warning"

# ── T3.4: 12th call — hard warning ──
echo "T3.4: 12th call — hard stop warning"
send_event "PreToolUse" "Edit"  # 10
send_event "PreToolUse" "Edit"  # 11
send_event "PreToolUse" "Bash"  # 12
stderr=$(cat "$TMPDIR/stderr")
total=$(get_total)
[ "$total" -eq 12 ] && pass "T3.4a total=12" || fail "T3.4a" "expected total=12, got $total"
echo "$stderr" | grep -q "FinOps hard stop" && pass "T3.4b hard stop warning" || fail "T3.4b" "expected hard stop, got: $stderr"

# ── T3.5: 13th call — no repeated hard warning ──
echo "T3.5: 13th call — no repeated warning"
send_event "PreToolUse" "Edit"
stderr=$(cat "$TMPDIR/stderr")
echo "$stderr" | grep -q "FinOps" && fail "T3.5" "should not re-warn at 13" || pass "T3.5 no repeated warning"

# ── T3.6: Turn boundary — total persists, calls reset ──
echo "T3.6: Turn boundary — total persists, calls reset"
reset_state
send_event "UserPromptSubmit"
sed -i 's/skills=0/skills=1/' "$STATE"

for i in $(seq 1 5); do
  send_event "PreToolUse" "Edit"
done
total_before=$(get_total)
calls_before=$(get_calls)
[ "$total_before" -eq 5 ] && pass "T3.6a total=5 before turn" || fail "T3.6a" "expected total=5, got $total_before"
[ "$calls_before" -eq 5 ] && pass "T3.6b calls=5 before turn" || fail "T3.6b" "expected calls=5, got $calls_before"

# New turn
send_event "UserPromptSubmit"
sed -i 's/skills=0/skills=1/' "$STATE"
calls_after_reset=$(get_calls)
total_after_reset=$(get_total)
[ "$calls_after_reset" -eq 0 ] && pass "T3.6c calls reset to 0" || fail "T3.6c" "expected calls=0, got $calls_after_reset"
[ "$total_after_reset" -eq 5 ] && pass "T3.6d total preserved at 5" || fail "T3.6d" "expected total=5, got $total_after_reset"

for i in $(seq 1 4); do
  send_event "PreToolUse" "Edit"
done
total_final=$(get_total)
warned8=$(get_warned8)
calls_final=$(get_calls)
[ "$total_final" -eq 9 ] && pass "T3.6e total=9 after 4 more" || fail "T3.6e" "expected total=9, got $total_final"
[ "$calls_final" -eq 4 ] && pass "T3.6f calls=4 this turn" || fail "T3.6f" "expected calls=4, got $calls_final"
[ "$warned8" -eq 1 ] && pass "T3.6g warned8 fired" || fail "T3.6g" "expected warned8=1, got $warned8"

# ── T3.7: Old state format (backward compatibility) ──
echo "T3.7: Old state format (no total field)"
reset_state
echo "skills=1 calls=3" > "$STATE"
send_event "PreToolUse" "Edit"
total=$(get_total)
# total should be 1 (0 default + 1 new call)
[ "$total" -eq 1 ] && pass "T3.7 total defaults to 0+1=1" || fail "T3.7" "expected total=1, got $total"

# ── T3.8: Missing state file ──
echo "T3.8: Missing state file mid-session"
reset_state
# Don't send UserPromptSubmit — file doesn't exist
send_event "PreToolUse" "Edit"
# Should not crash — [ ! -f "$STATE" ] && exit 0
pass "T3.8 no crash on missing state"

# ── T3.9: Existing routing logic — 1st call reminder ──
echo "T3.9: Existing routing logic — 1st call reminder"
reset_state
send_event "UserPromptSubmit"
# skills=0 (default), calls will be 1
send_event "PreToolUse" "Edit"
stderr=$(cat "$TMPDIR/stderr")
echo "$stderr" | grep -q "Routing check" && pass "T3.9 routing reminder at call 1" || fail "T3.9" "expected routing reminder, got: $stderr"

# ── T3.10: Existing routing logic — 3rd call reminder ──
echo "T3.10: Existing routing logic — 3rd call reminder"
send_event "PreToolUse" "Bash"  # call 2
send_event "PreToolUse" "Write" # call 3
stderr=$(cat "$TMPDIR/stderr")
echo "$stderr" | grep -q "Routing check" && pass "T3.10 routing reminder at call 3" || fail "T3.10" "expected routing reminder, got: $stderr"

# ── Cleanup ──
rm -f "$STATE"

# ── Summary ──
echo ""
echo "═══════════════════════════════════"
echo "  RESULTS: $PASS passed, $FAIL failed"
echo "═══════════════════════════════════"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
