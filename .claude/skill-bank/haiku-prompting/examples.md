# Haiku-Prompting Examples

Concrete guard and workaround patterns organized by flaw. Each example shows a Haiku failure scenario and the prompt pattern that prevents it.

---

## Anti-Hallucination Guards (H7)

### Problem: Haiku invents file paths when target not found

```xml
<!-- ❌ Asked to find a config file, Haiku fabricates a plausible path -->
<task>Find the database configuration file for the broker module</task>

<!-- Haiku without guard:
"The database configuration is at backend/src/trading_api/modules/broker/db_config.py"
(file does not exist — Haiku constructed a plausible path from conventions)
-->
```

### Guard: Mandatory NOT FOUND protocol

```xml
<constraints>
CRITICAL:
- If target not found after searching, respond "NOT FOUND: {what was searched}".
- NEVER fabricate file paths, function names, or parameter values.
</constraints>

<!-- Haiku with guard:
"NOT FOUND: database configuration file for broker module.
Searched: file_search('**/broker/*config*'), grep_search('database', 'modules/broker/')
No matches found."
-->
```

### Problem: Haiku guesses function signatures

```xml
<!-- ❌ Asked to find a method's parameters, Haiku invents them -->
<task>What parameters does the create_order method accept?</task>

<!-- Haiku without guard:
"create_order accepts: symbol: str, quantity: int, order_type: str, price: float"
(actual signature differs — Haiku inferred from domain knowledge, not from code)
-->
```

### Guard: Evidence-only responses

```xml
<constraints>
CRITICAL:
- Cite file path and line number for EVERY factual claim.
- If you cannot find the source, say "NOT FOUND" — do not infer from domain knowledge.
</constraints>

<output_format>
| Finding | Source | Line |
|---------|--------|------|
| {fact} | {file_path} | {line_number} |
</output_format>
```

---

## Instruction Fragility Guards (H2)

### Problem: Haiku drops constraints after 4 tool calls

```xml
<!-- ❌ Initial constraint: "Only report .py files" -->
<!-- Tool calls 1-3: correctly filters to .py files -->
<!-- Tool call 4+: starts including .ts, .md files in results -->
```

### Guard: Constraint compression + mid-session anchor

```xml
<constraints>
CRITICAL:
- ONLY report .py files — exclude all other extensions.
- Cite file:line for every finding.
- NOT FOUND if target absent — never guess.
</constraints>

<!-- After Phase 1 (approx. tool call 3): -->
<constraint-anchor>
⚠️ Re-read CRITICAL constraints. Verify: Am I still filtering to .py files only?
</constraint-anchor>
```

### Problem: Too many CRITICAL items overwhelm Haiku

```xml
<!-- ❌ 6 CRITICAL constraints — Haiku follows first 2-3, ignores rest -->
<constraints>
CRITICAL:
- Only .py files
- Cite line numbers
- Use grep before read
- Report NOT FOUND for missing
- Include import statements
- Skip test files
</constraints>
```

### Guard: Compress to ≤3 CRITICAL, overflow to IMPORTANT

```xml
<constraints>
CRITICAL:
- Only .py files (skip tests) — cite file:line for every finding.
- NOT FOUND if target absent — never guess or fabricate.
- Use grep to locate, then read targeted ranges.

IMPORTANT:
- Include import statements when relevant.
</constraints>
```

---

## Synthesis Fence Guards (H3)

### Problem: Haiku produces wrong conclusions when connecting findings

```xml
<!-- ❌ Asked to find related patterns across files, Haiku fabricates connections -->
<task>Find how the auth token flows from login to WebSocket connection</task>

<!-- Haiku without guard:
"The auth token is created in auth/service.py, stored in a session cookie,
and passed to the WebSocket via the handshake headers."
(partially wrong — Haiku connected dots that don't exist in the code)
-->
```

### Guard: Extract-only, no analysis

```xml
<synthesis-fence>
Report findings as extracted data only — quote or cite, do not interpret.
Do NOT draw conclusions about how components connect.
If analysis is needed, flag: "ANALYSIS NEEDED: {what should be analyzed}"
</synthesis-fence>

<output_format>
## Findings

### File: {path}
- Line {N}: `{relevant code snippet}`
- Line {M}: `{relevant code snippet}`

### File: {path2}
- Line {N}: `{relevant code snippet}`

## ANALYSIS NEEDED
- How token flows from auth/service.py to ws/v1/__init__.py
</output_format>

<!-- Haiku with guard:
Reports raw findings per file with line citations,
flags "ANALYSIS NEEDED" for the connection question,
parent (Sonnet/Opus) performs the actual analysis
-->
```

---

## Tool Chain Breakdown Guards (H4)

### Problem: Haiku loses track in multi-tool sequences

```xml
<!-- ❌ Task: grep for pattern → read matching files → extract specific data -->
<!-- Haiku: grep succeeds (step 1), reads file (step 2),
     but then summarizes wrong section or skips the extraction (step 3) -->
```

### Guard: Single-tool focus per invocation OR parallel independence

```xml
<!-- Option A: Single-tool caller protocol (preferred) -->
<caller_protocol>
Each invocation should focus on ONE tool operation:
- Invocation 1: "grep for X in Y" → return matching files + lines
- Invocation 2: "read lines N-M of file Z" → return content
Parent agent handles sequencing between invocations.
</caller_protocol>

<!-- Option B: Parallel independent reads (no sequencing needed) -->
<task>
Read these 3 files and extract {specific data} from each:
1. {file1} — extract {what}
2. {file2} — extract {what}
3. {file3} — extract {what}
</task>
<!-- Works because each read is independent — no chain dependency -->
```

---

## Output Truncation Guards (H6)

### Problem: Haiku silently drops output tail

```xml
<!-- ❌ Task produces 30 findings, Haiku returns 12 without acknowledging the rest -->
<task>List all TODO comments in the backend codebase</task>

<!-- Haiku without guard:
Lists 12 TODOs, ends with "These are the TODO comments found."
(18 more exist but were silently dropped)
-->
```

### Guard: Explicit truncation protocol

```xml
<output-scope-lock>
If more than 20 findings, list first 20, then:
"[TRUNCATED: {N} additional items found but not listed]"
Never end with a summary that implies completeness if items were omitted.
</output-scope-lock>
```

### Alternative: File redirection for large output (command subagent)

```xml
<constraints>
IMPORTANT:
- For commands expected to produce >50KB output, redirect to temp file:
  command > /tmp/cmd-{label}.log 2>&1
- Then read only the relevant sections from the file.
</constraints>
```

---

## Literal Interpretation Guards (H9)

### Problem: Haiku misses intent, follows words literally

```xml
<!-- ❌ "Find test files for the broker module" -->
<!-- Haiku: searches for "broker/test*" only -->
<!-- Misses: "tests/broker/", "test_broker_*.py", "broker.test.ts" -->
```

### Guard: Explicit search strategy with fallbacks

```xml
<search-strategy>
When searching for test files related to a module:
1. EXACT: file_search("**/modules/{name}/tests/**")
2. PATTERN: file_search("**/test*{name}*")
3. CONVENTION: file_search("**/tests/{name}/**")
4. BROAD: grep_search("import.*{name}", includePattern="**/test*")
Report which strategies matched. Try all before reporting NOT FOUND.
</search-strategy>
```

### Problem: Haiku returns only exact string matches

```xml
<!-- ❌ "Find where orders are validated" -->
<!-- Haiku: grep_search("orders are validated") — finds nothing -->
<!-- Should have searched: "validate_order", "order_validation", "OrderValidator" -->
```

### Guard: Semantic search fallback

```xml
<search-strategy>
- Start with likely code identifiers: function names, class names, variable names.
- Try variations: validate_order, order_validation, OrderValidator, validateOrder.
- If exact searches fail, use semantic_search for concept discovery.
- Cite which search strategy found each result.
</search-strategy>
```

---

## Format Compliance Guards (H8)

### Problem: Haiku output drifts from specified format mid-task

```xml
<!-- ❌ Output format specifies table, Haiku starts with table then switches to prose -->
<output_format>
| File | Finding | Line |
|------|---------|------|
| {path} | {what} | {N} |
</output_format>

<!-- Haiku: first 5 findings in table format,
     then switches to: "Also found in src/utils.ts on line 34..."
-->
```

### Guard: Format re-anchor before output

```xml
<!-- Place just before the output section in methodology -->
<format-re-anchor>
⚠️ Before writing your response, re-read <output_format> above.
Every finding MUST use the table format. No prose summaries between rows.
</format-re-anchor>
```

---

## Verification Rubber-Stamp (H5)

### Problem: Haiku confirms everything the caller expects

```xml
<!-- ❌ DO NOT GUARD — REDESIGN INSTEAD -->
<!-- Parent: "Verify the auth fix works" -->
<!-- Haiku: "The auth fix correctly handles token expiry ✅" -->
<!-- (Haiku didn't actually check — H5 makes it agree with the premise) -->
```

### Solution: Never assign verification to Haiku

```xml
<!-- ❌ WRONG: Using Haiku for verification -->
<task>Verify that the WebSocket reconnection logic handles token refresh.</task>

<!-- ✅ CORRECT: Use Haiku for extraction, Sonnet for verification -->
<!-- Haiku invocation: -->
<task>
Extract the WebSocket reconnection logic from {file}.
Return: function names, line ranges, and any token-related calls.
</task>

<!-- Sonnet invocation (separate, downstream): -->
<task>
Given these extracted code sections, verify the reconnection logic
correctly handles token refresh. Use expected-vs-found evidence pattern.
</task>
```

---

## Combined Example: Haiku Subagent Prompt

A complete prompt for a Haiku subagent (file extraction task):

```xml
<task>
Extract all Pydantic model class definitions from {file_paths}.
Return: class name, parent class, field names with types.
</task>

<constraints>
CRITICAL:
- Cite file path and line number for every finding.
- NOT FOUND if no Pydantic models exist — never fabricate.
- Report extracted data only — no analysis or recommendations.
</constraints>

<search-strategy>
Search for "class.*BaseModel" pattern in each file.
If no matches, try "class.*Model" as fallback.
</search-strategy>

<output-scope-lock>
If more than 15 models found, list first 15, then:
"[TRUNCATED: {N} additional models not listed]"
</output-scope-lock>

<output_format>
| Class | Parent | Fields | File | Line |
|-------|--------|--------|------|------|
| Order | BaseModel | symbol: str, qty: int | models/broker.py | 45 |

Example for no results:
"NOT FOUND: No Pydantic model classes in {file_path}"
</output_format>
```
