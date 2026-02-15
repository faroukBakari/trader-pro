#!/bin/bash
# Tests for .claude/hooks/lib/transcript.sh
# Usage: bash .claude/hooks/tests/test-transcript-lib.sh

set -uo pipefail
# Note: NOT using set -e — tests deliberately call functions that return non-zero

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LIB_DIR="$(cd "$SCRIPT_DIR/../lib" && pwd)"
source "$LIB_DIR/transcript.sh"

PASS=0
FAIL=0
TMPDIR=$(mktemp -d)
trap "rm -rf '$TMPDIR'" EXIT

pass() { PASS=$((PASS + 1)); echo "  PASS: $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  FAIL: $1 — $2"; }

# ── Mock transcript helpers ──

# Direct assistant message with tool_use
mock_tool_line() {
  local name="$1" input="$2"
  printf '{"message":{"content":[{"type":"tool_use","name":"%s","input":%s}]}}\n' "$name" "$input"
}

# ── T1.1: Empty transcript ──
echo "T1.1: Empty transcript"
touch "$TMPDIR/empty.jsonl"

transcript_has_tool "Edit" "$TMPDIR/empty.jsonl" && fail "T1.1a" "has_tool should return 1" || pass "T1.1a has_tool returns 1"

out=$(transcript_tool_lines "Edit" "$TMPDIR/empty.jsonl" 2>/dev/null) || true
[ -z "$out" ] && pass "T1.1b tool_lines empty" || fail "T1.1b" "expected empty, got: $out"

out=$(transcript_last_tool_line "Edit" "$TMPDIR/empty.jsonl")
[ "$out" = "0" ] && pass "T1.1c last_tool_line=0" || fail "T1.1c" "expected 0, got: $out"

transcript_has_tool_after_line "Edit" 0 "$TMPDIR/empty.jsonl" && fail "T1.1d" "should return 1" || pass "T1.1d has_tool_after_line returns 1"

out=$(transcript_modified_files "$TMPDIR/empty.jsonl" 2>/dev/null) || true
[ -z "$out" ] && pass "T1.1e modified_files empty" || fail "T1.1e" "expected empty, got: $out"

# ── T1.2: Has Edit tool ──
echo "T1.2: Has Edit tool"
cat > "$TMPDIR/has-edit.jsonl" <<'JSONL'
{"message":{"content":[{"type":"tool_use","name":"Read","input":{"file_path":"/tmp/foo.py"}}]}}
{"message":{"content":[{"type":"tool_use","name":"Edit","input":{"file_path":"/tmp/foo.py","old_string":"x","new_string":"y"}}]}}
{"message":{"content":[{"type":"tool_use","name":"Read","input":{"file_path":"/tmp/bar.py"}}]}}
JSONL

transcript_has_tool "Edit" "$TMPDIR/has-edit.jsonl" && pass "T1.2 has_tool Edit" || fail "T1.2" "should find Edit"

# ── T1.3: No Edit tool ──
echo "T1.3: No Edit tool"
cat > "$TMPDIR/no-edit.jsonl" <<'JSONL'
{"message":{"content":[{"type":"tool_use","name":"Read","input":{"file_path":"/tmp/foo.py"}}]}}
{"message":{"content":[{"type":"tool_use","name":"Bash","input":{"command":"ls"}}]}}
{"message":{"content":[{"type":"tool_use","name":"Grep","input":{"pattern":"test"}}]}}
JSONL

transcript_has_tool "Edit" "$TMPDIR/no-edit.jsonl" && fail "T1.3" "should not find Edit" || pass "T1.3 no Edit found"

# ── T1.4: Line ordering — Edit at line 2, diagnostics at line 4 ──
echo "T1.4: Line ordering (tool after edit)"
cat > "$TMPDIR/ordering.jsonl" <<'JSONL'
{"message":{"content":[{"type":"tool_use","name":"Read","input":{"file_path":"/tmp/x.py"}}]}}
{"message":{"content":[{"type":"tool_use","name":"Edit","input":{"file_path":"/tmp/x.py","old_string":"a","new_string":"b"}}]}}
{"message":{"content":[{"type":"tool_use","name":"Read","input":{"file_path":"/tmp/x.py"}}]}}
{"message":{"content":[{"type":"tool_use","name":"mcp__vscode-mcp-server__get_diagnostics_code","input":{"path":"/tmp/x.py"}}]}}
JSONL

transcript_has_tool_after_line "mcp__vscode-mcp-server__get_diagnostics_code" 2 "$TMPDIR/ordering.jsonl" \
  && pass "T1.4 diagnostics after line 2" || fail "T1.4" "should find diagnostics after edit line"

# ── T1.5: Reverse ordering — diagnostics before edit ──
echo "T1.5: Reverse ordering (diagnostics before edit)"
cat > "$TMPDIR/reverse.jsonl" <<'JSONL'
{"message":{"content":[{"type":"tool_use","name":"Read","input":{"file_path":"/tmp/x.py"}}]}}
{"message":{"content":[{"type":"tool_use","name":"mcp__vscode-mcp-server__get_diagnostics_code","input":{"path":"/tmp/x.py"}}]}}
{"message":{"content":[{"type":"tool_use","name":"Read","input":{"file_path":"/tmp/x.py"}}]}}
{"message":{"content":[{"type":"tool_use","name":"Edit","input":{"file_path":"/tmp/x.py","old_string":"a","new_string":"b"}}]}}
JSONL

transcript_has_tool_after_line "mcp__vscode-mcp-server__get_diagnostics_code" 4 "$TMPDIR/reverse.jsonl" \
  && fail "T1.5" "should NOT find diagnostics after line 4" || pass "T1.5 no diagnostics after edit"

# ── T1.6: Missing file ──
echo "T1.6: Missing file"
transcript_has_tool "Edit" "$TMPDIR/nonexistent.jsonl" && fail "T1.6a" "should return 1" || pass "T1.6a has_tool returns 1"

out=$(transcript_last_tool_line "Edit" "$TMPDIR/nonexistent.jsonl")
[ "$out" = "0" ] && pass "T1.6b last_tool_line=0" || fail "T1.6b" "expected 0, got: $out"

out=$(transcript_modified_files "$TMPDIR/nonexistent.jsonl" 2>/dev/null) || true
[ -z "$out" ] && pass "T1.6c modified_files empty" || fail "T1.6c" "expected empty, got: $out"

# ── T1.7: Malformed lines ──
echo "T1.7: Malformed lines mixed with valid"
cat > "$TMPDIR/malformed.jsonl" <<'JSONL'
this is not json at all
{"message":{"content":[{"type":"tool_use","name":"Edit","input":{"file_path":"/tmp/good.py","old_string":"a","new_string":"b"}}]}}
{broken json
{"message":{"content":[{"type":"tool_use","name":"Read","input":{"file_path":"/tmp/other.py"}}]}}
JSONL

transcript_has_tool "Edit" "$TMPDIR/malformed.jsonl" && pass "T1.7a finds Edit in malformed file" || fail "T1.7a" "should find Edit"

out=$(transcript_last_tool_line "Edit" "$TMPDIR/malformed.jsonl")
[ "$out" = "2" ] && pass "T1.7b Edit on line 2" || fail "T1.7b" "expected line 2, got: $out"

# ── T1.8: MCP tool names (partial grep match) ──
echo "T1.8: MCP tool names"
cat > "$TMPDIR/mcp-tools.jsonl" <<'JSONL'
{"message":{"content":[{"type":"tool_use","name":"mcp__vscode-mcp-server__create_file_code","input":{"path":"/tmp/new.py","content":"print(1)"}}]}}
{"message":{"content":[{"type":"tool_use","name":"mcp__vscode-mcp-server__replace_lines_code","input":{"path":"/tmp/old.ts","startLine":1,"endLine":2,"content":"const x = 1"}}]}}
JSONL

transcript_has_tool "mcp__vscode-mcp-server__create_file_code" "$TMPDIR/mcp-tools.jsonl" \
  && pass "T1.8a create_file_code found" || fail "T1.8a" "should find MCP tool"
transcript_has_tool "create_file_code" "$TMPDIR/mcp-tools.jsonl" \
  && pass "T1.8b partial name found" || fail "T1.8b" "should find partial MCP tool name"

# ── T1.9: Modified files extraction ──
echo "T1.9: Modified files extraction"
cat > "$TMPDIR/modified.jsonl" <<'JSONL'
{"message":{"content":[{"type":"tool_use","name":"Read","input":{"file_path":"/tmp/readme.md"}}]}}
{"message":{"content":[{"type":"tool_use","name":"Edit","input":{"file_path":"/tmp/foo.py","old_string":"a","new_string":"b"}}]}}
{"message":{"content":[{"type":"tool_use","name":"Write","input":{"file_path":"/tmp/bar.md","content":"# Hi"}}]}}
{"message":{"content":[{"type":"tool_use","name":"mcp__vscode-mcp-server__create_file_code","input":{"path":"/tmp/new_module.py","content":"pass"}}]}}
{"message":{"content":[{"type":"tool_use","name":"Read","input":{"file_path":"/tmp/foo.py"}}]}}
JSONL

out=$(transcript_modified_files "$TMPDIR/modified.jsonl")
echo "$out" | grep -q "/tmp/foo.py" && pass "T1.9a foo.py found" || fail "T1.9a" "foo.py missing from: $out"
echo "$out" | grep -q "/tmp/bar.md" && pass "T1.9b bar.md found" || fail "T1.9b" "bar.md missing from: $out"
echo "$out" | grep -q "/tmp/new_module.py" && pass "T1.9c new_module.py found" || fail "T1.9c" "new_module.py missing from: $out"
echo "$out" | grep -q "/tmp/readme.md" && fail "T1.9d" "Read should not appear" || pass "T1.9d Read excluded"

# ── Summary ──
echo ""
echo "═══════════════════════════════════"
echo "  RESULTS: $PASS passed, $FAIL failed"
echo "═══════════════════════════════════"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
