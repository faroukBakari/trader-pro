# Sonnet-Prompting Examples

Concrete guard and workaround patterns organized by template section. Each example shows a Sonnet failure scenario and the prompt pattern that prevents it.

---

## Anti-Sycophancy Guards (F1, F8, F10)

### Problem: Sonnet validates suboptimal approaches

```xml
<!-- ❌ User proposes bad design, Sonnet agrees -->
<task>Review my implementation of a global state manager using window.__state</task>

<!-- Sonnet response without guard: "This is a creative approach! Here's how to improve it..." -->
```

### Guard: Force honest evaluation

```xml
<anti-sycophancy>
- If the proposed approach has design flaws, state them before suggesting improvements.
- Rank alternatives: if a better pattern exists, present it alongside the user's approach.
- "This won't work because..." is more valuable than polishing a broken design.
</anti-sycophancy>

<!-- Sonnet response with guard: "Using window.__state creates XSS vulnerability 
     and breaks SSR. Recommended alternative: Pinia store with typed state..." -->
```

### Problem: Verification confirms caller expectations

```xml
<!-- ❌ Parent agent says "verify the fix works", Sonnet confirms without checking -->
<task>Verify that the authentication fix in auth.ts resolves the token expiry issue.</task>

<!-- Sonnet response without guard: "The fix correctly handles token expiry ✅" -->
```

### Guard: Force evidence-based verdicts

```xml
<anti-sycophancy>
- For every claim, cite file path + line number as evidence.
- Use "expected vs found" pattern: state what SHOULD be true, then what IS true.
- If you cannot find evidence confirming the fix, say so explicitly.
</anti-sycophancy>

<output_format>
| Check | Expected | Found | Verdict |
|-------|----------|-------|---------|
| Token refresh logic | Refreshes before expiry | {actual finding} | PASS/FAIL |
</output_format>
```

---

## Completeness Guards (F2, F3)

### Problem: Lazy output with placeholders

```xml
<!-- ❌ Sonnet generates partial implementation -->
<task>Implement CRUD endpoints for the User model</task>

<!-- Sonnet without guard:
def create_user(...): ...
def get_user(...): ...
# Similar for update and delete
-->
```

### Guard: Explicit anti-placeholder directive

```xml
<completeness>
- Output ALL endpoint implementations completely.
- NEVER use: "# Similar for...", "// ... rest of code", "etc."
- Each endpoint must include: route decorator, type hints, error handling, return type.
</completeness>

<!-- Sonnet with guard: outputs all 4 endpoints fully implemented -->
```

### Problem: Premature task completion

```xml
<!-- ❌ Multi-step task, Sonnet stops after step 2 of 5 -->
<task>
Implement the broker WebSocket module:
1. Create models in models/broker/
2. Create WS router in modules/broker/ws/v1/
3. Create service layer
4. Add tests
5. Generate OpenAPI spec
</task>

<!-- Sonnet without guard: completes steps 1-2, says "Implementation complete!" -->
```

### Guard: Enumerated completion check

```xml
<completeness>
- This task has 5 numbered steps. ALL must be completed.
- Before declaring done, output this checklist:
  □ Step 1: Models created
  □ Step 2: WS router created
  □ Step 3: Service layer created
  □ Step 4: Tests added
  □ Step 5: OpenAPI spec generated
- If ANY step is incomplete, continue working. Do not summarize partial progress as done.
</completeness>
```

### Alternative: Progressive completion tracking

```xml
<!-- For very long multi-step work, track progress inline -->
<completeness>
After completing each major step, output:
Progress: [X/N] — {step just completed}
Remaining: {list of remaining steps}

ONLY use "Task complete" when Progress shows [N/N].
</completeness>
```

---

## Scope Fence Guards (F5)

### Problem: Bold unauthorized changes

```xml
<!-- ❌ Asked to fix a type error, Sonnet refactors the whole file -->
<task>Fix the TypeScript error on line 45 of UserService.ts</task>

<!-- Sonnet without guard: fixes line 45, also renames variables, extracts a class,
     updates imports in 3 other files, adds a utility function -->
```

### Guard: Explicit scope boundary

```xml
<scope-fence>
- ONLY modify the specific line/function causing the error.
- Do not rename, refactor, or reorganize surrounding code.
- Do not modify other files unless the fix requires import changes.
- If you notice other issues, list them in a "Noticed but not fixed" section.
</scope-fence>

<output_format>
## Fix Applied
{minimal change description}

## Noticed But Not Fixed
- {issue 1} — {why it should be addressed separately}
</output_format>
```

---

## Constraint Drift Guards (F4)

### Problem: Mid-session instruction amnesia

```xml
<!-- ❌ 20 tool calls into a session, Sonnet forgets initial constraints -->
<!-- Initial constraint: "Use repository pattern, no direct DB access" -->
<!-- By tool call 15: Sonnet writes raw SQL queries directly in route handlers -->
```

### Guard: Constraint sandwiching

```xml
<!-- Place at TOP of prompt -->
<constraints>
CRITICAL:
- ALL database access MUST go through Repository classes
- No raw SQL in route handlers
</constraints>

<!-- ... methodology phases 1-3 ... -->

<!-- Place at MIDPOINT of methodology -->
<constraint-anchor>
⚠️ CHECKPOINT: Before proceeding to the next phase, verify:
- Am I using Repository classes for ALL data access?
- Have I introduced any raw SQL outside Repository classes?
If violations found → fix before continuing.
</constraint-anchor>

<!-- ... methodology phases 4-6 ... -->

<!-- Place at END / output phase -->
<final-check>
Before submitting output, scan for CRITICAL constraint violations:
□ All DB access uses Repository pattern
□ No raw SQL in route handlers
</final-check>
```

### Alternative: Key constraint repetition

```xml
<!-- Repeat the single most important constraint in 3 locations -->

<!-- In <constraints> -->
CRITICAL:
- NEVER import from other modules directly (use provider callbacks)

<!-- In methodology Phase 2 -->
**Remember**: No cross-module imports. Use provider callbacks only.

<!-- In output section -->
**Self-check**: Verify zero cross-module imports in your output.
```

---

## Reasoning Depth Guards (F6)

### Problem: Multi-hop reasoning fails beyond 3 steps

```xml
<!-- ❌ Complex debugging chain, Sonnet loses the thread -->
<task>
Trace why the WebSocket reconnection fails:
1. Find where the connection drops
2. Check if the retry logic fires
3. Determine if the token refresh happens before retry
4. Verify the refreshed token reaches the reconnect handler
5. Check if the server validates the new token correctly
</task>

<!-- Sonnet: accurately traces steps 1-3, then makes incorrect leap on step 4,
     produces plausible-sounding but wrong conclusion at step 5 -->
```

### Guard: Decompose into ≤3-hop chains

```xml
<!-- Break into sequential sub-tasks with intermediate checkpoints -->
<task>
## Phase A: Connection lifecycle (steps 1-2)
1. Find where the WebSocket connection drops — cite file:line
2. Check if retry logic fires after the drop — cite evidence

## Phase B: Token flow (steps 3-4)  
3. Does token refresh trigger before retry? — cite the sequence
4. Does the refreshed token reach the reconnect handler? — cite the handoff

## Phase C: Server validation (step 5)
5. Does the server accept the new token? — cite the validation logic

Complete Phase A fully before starting Phase B.
Report findings per phase before proceeding.
</task>
```

### Alternative: Escalation marker

```xml
<!-- When a task MIGHT exceed Sonnet's reasoning depth -->
<reasoning-check>
If at any point you realize this requires reasoning across more than 3 causal
steps simultaneously, state: "⚠️ REASONING DEPTH: This chain exceeds 3 hops.
Consider delegating to Opus for this sub-problem." Then provide what you've
determined so far as evidence for the next agent.
</reasoning-check>
```

---

## Tool Parameter Guards (F7)

### Problem: Hallucinated file paths or parameters

```xml
<!-- ❌ Sonnet invents plausible but wrong file paths -->
<!-- Calls: read_file("/src/services/UserService.ts") -->
<!-- Actual path: "/src/plugins/user-service.ts" -->
```

### Guard: Provide concrete examples in output format

```xml
<output_format>
When referencing files, use ONLY paths verified via file_search or grep_search.
Never construct paths from memory — always verify first.

Example tool call:
- ✅ Search first: file_search("**/user*service*")
- ✅ Then read: read_file("/verified/path/from/search")
- ❌ Never: read_file("/guessed/path/UserService.ts")
</output_format>
```

---

## Code Convention Guards (F9)

### Problem: Over-engineered output ignoring project style

```xml
<!-- ❌ Project uses simple functions, Sonnet creates class hierarchy -->
<!-- Existing code: export function mapOrder(raw: RawOrder): Order { ... } -->
<!-- Sonnet output: class OrderMapper implements IMapper<RawOrder, Order> { ... } -->
```

### Guard: Convention anchoring in role

```xml
<role>
You write code that matches the existing codebase style exactly.
Before generating code, examine 2-3 nearby files for patterns:
- Function vs class style
- Naming conventions (camelCase, snake_case, etc.)
- Import patterns
- Error handling style
Match these patterns. Do NOT introduce abstractions absent from the codebase.
</role>
```

---

## Sonnet Speed Exploitation Patterns

### Pattern: Concise, direct prompts

Sonnet's speed advantage (71 t/s vs Opus 92 t/s) peaks with focused prompts. Avoid verbose preambles.

```xml
<!-- ❌ Verbose prompt (wastes Sonnet's speed advantage) -->
<role>
You are an experienced software engineer with deep expertise in Python
development, particularly in the area of web services and API design.
You have extensive knowledge of FastAPI, Pydantic, SQLAlchemy, and
modern Python best practices including type annotations, async/await
patterns, and comprehensive testing strategies...
</role>

<!-- ✅ Concise prompt (exploits Sonnet's fast processing) -->
<role>
Senior Python/FastAPI developer. Clean, typed, tested code.
Matches existing project patterns.
</role>
```

### Pattern: Structured output for reliable extraction

Sonnet produces highly reliable structured output when given explicit format:

```xml
<!-- ✅ Table format gets near-100% compliance -->
<output_format>
| File | Change | Reason |
|------|--------|--------|
| {path} | {what changed} | {why} |
</output_format>

<!-- ✅ JSON schema gets reliable compliance -->
<output_format>
Return a JSON object:
{
  "status": "pass" | "fail",
  "findings": [{"file": "...", "line": N, "issue": "..."}],
  "summary": "one-line verdict"
}
</output_format>
```

---

## Combined Example: Full Guard Stack

A complete prompt using multiple guards for a complex Sonnet task:

```xml
<role>
Senior TypeScript/Vue developer. Clean, typed code matching project conventions.
</role>

<task>
Implement the order history component:
1. Create OrderHistory.vue with table display
2. Add order filtering by status and date range
3. Integrate with the broker API client
4. Add loading and error states
</task>

<constraints>
CRITICAL:
- Use ONLY types from @public/trading_terminal — never use backend types directly
- All props and emits must be typed — no `any`
- Use composables for API calls, not inline fetch

IMPORTANT:
- Follow existing component patterns in src/components/
- Use the project's existing date formatting utilities
</constraints>

<anti-sycophancy>
If the existing API client doesn't support order history queries,
say so instead of fabricating an implementation.
</anti-sycophancy>

<completeness>
All 4 requirements must be implemented. Before finishing:
□ OrderHistory.vue created with full template + script + style
□ Filtering logic implemented (not stubbed)
□ API integration using actual client methods
□ Loading spinner + error display included
</completeness>

<scope-fence>
- Create new files only: OrderHistory.vue, useOrderHistory.ts
- Do NOT modify existing components or API clients
- Note needed API changes in a "Requires" section instead
</scope-fence>

<output_format>
## Files Created
{file path and complete contents for each}

## Requires (changes needed in other files)
- {file}: {what change is needed and why}
</output_format>
```
