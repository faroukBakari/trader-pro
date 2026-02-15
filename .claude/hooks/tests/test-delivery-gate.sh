#!/bin/bash
# Tests for .claude/hooks/delivery-gate.sh
# Usage: bash .claude/hooks/tests/test-delivery-gate.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK="$SCRIPT_DIR/../delivery-gate.sh"
TMPDIR=$(mktemp -d)
trap "rm -rf '$TMPDIR'" EXIT

PASS=0
FAIL=0

pass() { PASS=$((PASS + 1)); echo "  PASS: $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  FAIL: $1 — $2"; }

# Run hook with given transcript, return stdout + check stderr
run_hook() {
  local transcript="$1" mode="${2:-warn}" session="${3:-test-session}"
  local input
  input=$(jq -n --arg tp "$transcript" --arg sid "$session" '{transcript_path: $tp, session_id: $sid}')
  # Clean state file for this session
  rm -f "/tmp/claude-delivery-gate-${session}"
  DELIVERY_GATE_MODE="$mode" echo "$input" | bash "$HOOK" 2>"$TMPDIR/stderr"
}

# ── Nominal: should allow exit ──

echo "T2.1: No code changes (only Read/Grep)"
cat > "$TMPDIR/t2-1.jsonl" <<'JSONL'
{"message":{"content":[{"type":"tool_use","name":"Read","input":{"file_path":"/tmp/foo.py"}}]}}
{"message":{"content":[{"type":"tool_use","name":"Grep","input":{"pattern":"test"}}]}}
JSONL
out=$(run_hook "$TMPDIR/t2-1.jsonl")
[ -z "$out" ] && pass "T2.1 no output" || fail "T2.1" "unexpected output: $out"

echo "T2.2: Only .md edits"
cat > "$TMPDIR/t2-2.jsonl" <<'JSONL'
{"message":{"content":[{"type":"tool_use","name":"Edit","input":{"file_path":"/tmp/README.md","old_string":"a","new_string":"b"}}]}}
JSONL
out=$(run_hook "$TMPDIR/t2-2.jsonl")
[ -z "$out" ] && pass "T2.2 no output" || fail "T2.2" "unexpected output: $out"

echo "T2.3: Only .json edits"
cat > "$TMPDIR/t2-3.jsonl" <<'JSONL'
{"message":{"content":[{"type":"tool_use","name":"Write","input":{"file_path":"/tmp/package.json","content":"{}"}}]}}
JSONL
out=$(run_hook "$TMPDIR/t2-3.jsonl")
[ -z "$out" ] && pass "T2.3 no output" || fail "T2.3" "unexpected output: $out"

echo "T2.4: Only .claude/ edits"
cat > "$TMPDIR/t2-4.jsonl" <<'JSONL'
{"message":{"content":[{"type":"tool_use","name":"Edit","input":{"file_path":"/home/farouk/trader-pro/.claude/CLAUDE.md","old_string":"a","new_string":"b"}}]}}
JSONL
out=$(run_hook "$TMPDIR/t2-4.jsonl")
[ -z "$out" ] && pass "T2.4 no output" || fail "T2.4" "unexpected output: $out"

echo "T2.5: Source edit + diagnostics after"
cat > "$TMPDIR/t2-5.jsonl" <<'JSONL'
{"message":{"content":[{"type":"tool_use","name":"Read","input":{"file_path":"/tmp/foo.py"}}]}}
{"message":{"content":[{"type":"tool_use","name":"Edit","input":{"file_path":"/tmp/foo.py","old_string":"a","new_string":"b"}}]}}
{"message":{"content":[{"type":"tool_use","name":"Read","input":{"file_path":"/tmp/foo.py"}}]}}
{"message":{"content":[{"type":"tool_use","name":"mcp__vscode-mcp-server__get_diagnostics_code","input":{"path":"/tmp/foo.py"}}]}}
JSONL
out=$(run_hook "$TMPDIR/t2-5.jsonl")
stderr=$(cat "$TMPDIR/stderr")
[ -z "$out" ] && [ -z "$stderr" ] && pass "T2.5 allowed" || fail "T2.5" "out='$out' stderr='$stderr'"

echo "T2.6: Source edit + pytest after"
cat > "$TMPDIR/t2-6.jsonl" <<'JSONL'
{"message":{"content":[{"type":"tool_use","name":"Edit","input":{"file_path":"/tmp/foo.py","old_string":"a","new_string":"b"}}]}}
{"message":{"content":[{"type":"tool_use","name":"Read","input":{"file_path":"/tmp/foo.py"}}]}}
{"message":{"content":[{"type":"tool_use","name":"Bash","input":{"command":"pytest tests/"}}]}}
JSONL
out=$(run_hook "$TMPDIR/t2-6.jsonl")
stderr=$(cat "$TMPDIR/stderr")
[ -z "$out" ] && [ -z "$stderr" ] && pass "T2.6 allowed" || fail "T2.6" "out='$out' stderr='$stderr'"

echo "T2.7: Source edit + make test after"
cat > "$TMPDIR/t2-7.jsonl" <<'JSONL'
{"message":{"content":[{"type":"tool_use","name":"Edit","input":{"file_path":"/tmp/foo.py","old_string":"a","new_string":"b"}}]}}
{"message":{"content":[{"type":"tool_use","name":"Bash","input":{"command":"make test"}}]}}
JSONL
out=$(run_hook "$TMPDIR/t2-7.jsonl")
stderr=$(cat "$TMPDIR/stderr")
[ -z "$out" ] && [ -z "$stderr" ] && pass "T2.7 allowed" || fail "T2.7" "out='$out' stderr='$stderr'"

echo "T2.8: Empty transcript"
touch "$TMPDIR/t2-8.jsonl"
out=$(run_hook "$TMPDIR/t2-8.jsonl")
[ -z "$out" ] && pass "T2.8 fail-open" || fail "T2.8" "unexpected output: $out"

echo "T2.9: Missing transcript"
out=$(run_hook "$TMPDIR/nonexistent.jsonl")
[ -z "$out" ] && pass "T2.9 fail-open" || fail "T2.9" "unexpected output: $out"

# ── Should warn (default mode) ──

echo "T2.10: Source edit, no verification (warn)"
cat > "$TMPDIR/t2-10.jsonl" <<'JSONL'
{"message":{"content":[{"type":"tool_use","name":"Edit","input":{"file_path":"/tmp/foo.py","old_string":"a","new_string":"b"}}]}}
{"message":{"content":[{"type":"tool_use","name":"Read","input":{"file_path":"/tmp/foo.py"}}]}}
JSONL
out=$(run_hook "$TMPDIR/t2-10.jsonl" "warn")
stderr=$(cat "$TMPDIR/stderr")
[ -z "$out" ] && pass "T2.10a no stdout" || fail "T2.10a" "unexpected stdout: $out"
echo "$stderr" | grep -q "Delivery gate" && pass "T2.10b stderr warning" || fail "T2.10b" "expected stderr warning, got: $stderr"

echo "T2.11: Source edit, diagnostics BEFORE edit (warn)"
cat > "$TMPDIR/t2-11.jsonl" <<'JSONL'
{"message":{"content":[{"type":"tool_use","name":"mcp__vscode-mcp-server__get_diagnostics_code","input":{"path":"/tmp/x.py"}}]}}
{"message":{"content":[{"type":"tool_use","name":"Edit","input":{"file_path":"/tmp/foo.py","old_string":"a","new_string":"b"}}]}}
JSONL
out=$(run_hook "$TMPDIR/t2-11.jsonl" "warn")
stderr=$(cat "$TMPDIR/stderr")
[ -z "$out" ] && pass "T2.11a no stdout" || fail "T2.11a" "unexpected stdout: $out"
echo "$stderr" | grep -q "Delivery gate" && pass "T2.11b stderr warning" || fail "T2.11b" "expected stderr warning, got: $stderr"

echo "T2.12: create_file_code for .py (warn)"
cat > "$TMPDIR/t2-12.jsonl" <<'JSONL'
{"message":{"content":[{"type":"tool_use","name":"mcp__vscode-mcp-server__create_file_code","input":{"path":"/tmp/new_module.py","content":"pass"}}]}}
JSONL
out=$(run_hook "$TMPDIR/t2-12.jsonl" "warn")
stderr=$(cat "$TMPDIR/stderr")
[ -z "$out" ] && pass "T2.12a no stdout" || fail "T2.12a" "unexpected stdout: $out"
echo "$stderr" | grep -q "Delivery gate" && pass "T2.12b stderr warning" || fail "T2.12b" "expected stderr warning, got: $stderr"

echo "T2.13: replace_lines_code for .ts (warn)"
cat > "$TMPDIR/t2-13.jsonl" <<'JSONL'
{"message":{"content":[{"type":"tool_use","name":"mcp__vscode-mcp-server__replace_lines_code","input":{"path":"/tmp/component.ts","startLine":1,"endLine":2,"content":"const x = 1","originalCode":"const x = 0"}}]}}
JSONL
out=$(run_hook "$TMPDIR/t2-13.jsonl" "warn")
stderr=$(cat "$TMPDIR/stderr")
[ -z "$out" ] && pass "T2.13a no stdout" || fail "T2.13a" "unexpected stdout: $out"
echo "$stderr" | grep -q "Delivery gate" && pass "T2.13b stderr warning" || fail "T2.13b" "expected stderr warning, got: $stderr"

# ── Should block (block mode) ──

echo "T2.14: Block mode, no verification"
cat > "$TMPDIR/t2-14.jsonl" <<'JSONL'
{"message":{"content":[{"type":"tool_use","name":"Edit","input":{"file_path":"/tmp/foo.py","old_string":"a","new_string":"b"}}]}}
JSONL
out=$(run_hook "$TMPDIR/t2-14.jsonl" "block" "test-block-14")
echo "$out" | jq -e '.decision == "block"' >/dev/null 2>&1 && pass "T2.14 block JSON" || fail "T2.14" "expected block JSON, got: $out"

echo "T2.15: Block mode, 3rd attempt (safety valve)"
cat > "$TMPDIR/t2-15.jsonl" <<'JSONL'
{"message":{"content":[{"type":"tool_use","name":"Edit","input":{"file_path":"/tmp/foo.py","old_string":"a","new_string":"b"}}]}}
JSONL
# Pre-set block count to 2
echo "2" > "/tmp/claude-delivery-gate-test-block-15"
input=$(jq -n --arg tp "$TMPDIR/t2-15.jsonl" --arg sid "test-block-15" '{transcript_path: $tp, session_id: $sid}')
out=$(DELIVERY_GATE_MODE=block echo "$input" | bash "$HOOK" 2>"$TMPDIR/stderr")
stderr=$(cat "$TMPDIR/stderr")
# Should allow (safety valve) not block
echo "$out" | grep -q "block" && fail "T2.15a" "should not block after 2" || pass "T2.15a no block"
echo "$stderr" | grep -q "safety valve" && pass "T2.15b safety valve msg" || fail "T2.15b" "expected safety valve, got: $stderr"
rm -f "/tmp/claude-delivery-gate-test-block-15"

# ── Edge cases ──

echo "T2.16: Mixed source + docs, diagnostics present"
cat > "$TMPDIR/t2-16.jsonl" <<'JSONL'
{"message":{"content":[{"type":"tool_use","name":"Edit","input":{"file_path":"/tmp/foo.py","old_string":"a","new_string":"b"}}]}}
{"message":{"content":[{"type":"tool_use","name":"Edit","input":{"file_path":"/tmp/README.md","old_string":"x","new_string":"y"}}]}}
{"message":{"content":[{"type":"tool_use","name":"mcp__vscode-mcp-server__get_diagnostics_code","input":{"path":"/tmp/foo.py"}}]}}
JSONL
out=$(run_hook "$TMPDIR/t2-16.jsonl")
stderr=$(cat "$TMPDIR/stderr")
[ -z "$out" ] && [ -z "$stderr" ] && pass "T2.16 allowed" || fail "T2.16" "out='$out' stderr='$stderr'"

echo "T2.17: Malformed transcript JSON"
cat > "$TMPDIR/t2-17.jsonl" <<'JSONL'
not valid json
{broken
JSONL
out=$(run_hook "$TMPDIR/t2-17.jsonl")
[ -z "$out" ] && pass "T2.17 fail-open" || fail "T2.17" "unexpected output: $out"

echo "T2.18: Long transcript (500+ lines)"
{
  for i in $(seq 1 500); do
    echo '{"message":{"content":[{"type":"tool_use","name":"Read","input":{"file_path":"/tmp/file'$i'.py"}}]}}'
  done
  echo '{"message":{"content":[{"type":"tool_use","name":"Edit","input":{"file_path":"/tmp/final.py","old_string":"a","new_string":"b"}}]}}'
  echo '{"message":{"content":[{"type":"tool_use","name":"mcp__vscode-mcp-server__get_diagnostics_code","input":{"path":"/tmp/final.py"}}]}}'
} > "$TMPDIR/t2-18.jsonl"
start_time=$(date +%s)
out=$(run_hook "$TMPDIR/t2-18.jsonl")
end_time=$(date +%s)
elapsed=$((end_time - start_time))
stderr=$(cat "$TMPDIR/stderr")
[ -z "$out" ] && [ -z "$stderr" ] && pass "T2.18a allowed" || fail "T2.18a" "out='$out' stderr='$stderr'"
[ "$elapsed" -lt 10 ] && pass "T2.18b completed in ${elapsed}s" || fail "T2.18b" "took ${elapsed}s (>10s)"

# ── Summary ──
echo ""
echo "═══════════════════════════════════"
echo "  RESULTS: $PASS passed, $FAIL failed"
echo "═══════════════════════════════════"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
