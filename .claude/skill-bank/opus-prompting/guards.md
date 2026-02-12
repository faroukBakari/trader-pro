# Opus-Specific Guard Blocks

Guard patterns calibrated for Opus 4.6's behavioral profile. These supplement the generic guards in `prompting-guide/guards.md` with Opus-specific tuning.

---

## Unconditional Gate Pattern (O1, O4)

The highest-impact guard for Opus. Prevents framing bias from bypassing process gates.

### Problem: Conditional gate bypassed by casual framing

```markdown
<!-- ❌ CLAUDE.md rule with conditional qualifier -->
"Non-trivial tasks MUST check category glossary descriptions for relevant skills."

<!-- User prompt: "fix backend typo" -->
<!-- Opus reasoning: "Typo fix is trivial → gate doesn't apply → skip glossary check" -->
<!-- Result: Relevant skill (fix-type-errors) never loaded, incomplete fix delivered -->
```

### Guard: Unconditional trigger with fast exit

```markdown
<!-- ✅ Unconditional gate — fires on action domain, not complexity -->
"ALWAYS check category glossary descriptions before editing code.
 If no skill matches the task domain → proceed directly."

<!-- User prompt: "fix backend typo" -->
<!-- Opus reasoning: "Must check glossary (unconditional). Scanning descriptions...
     'fix-type-errors: Systematic type error resolution' matches diagnostics domain.
     Loading skill." -->
<!-- Result: Skill loaded, systematic fix applied -->
```

### Why it works

The unconditional gate forces the domain-matching step to execute regardless of the model's complexity assessment. The "proceed directly" exit keeps cost near-zero for non-matching tasks. The model can still be fast on genuinely simple tasks — it just can't skip the check.

---

## Domain Classification Guard (O1)

Forces task classification based on observable properties, not user framing.

### Problem: User framing anchors complexity assessment

```markdown
<!-- ❌ User framing sets complexity ceiling -->
User: "Quick fix — just update that type annotation"
Opus: Classifies as T0 → direct edit → no skill consultation → no verification

<!-- ❌ Same task, different framing, different outcome -->
User: "Investigate and resolve the type system errors in the test file"
Opus: Classifies as T2 → loads skill → runs pyright → complete fix
```

### Guard: Objective classification criteria

```markdown
<!-- ✅ Classify by domain signals, not user words -->
<classification-guidance>
Classify task complexity by what it requires, not how it's described:
- Involves type errors, linting, or static analysis → load `fix-type-errors` skill
- Involves test failures → load `backend-testing` or `frontend-testing` skill
- Involves multiple files → T2+ reasoning tier
- Involves external system interaction → T3+ reasoning tier
User framing ("quick", "small", "just") describes expectations, not task properties.
</classification-guidance>
```

---

## Selective Completion Guard (O2)

Prevents Opus from completing easy parts and silently skipping hard ones.

### Problem: Easy parts done, hard parts skipped

```markdown
<!-- ❌ 5 type errors found, only 2 fixed -->
Opus fixes `*args: ...` → `*args: Any` (mechanical substitution — easy)
Opus skips `captured_callback` narrowing errors (requires understanding closure scope — hard)
Opus declares: "Fixed the type errors in the test file."
```

### Guard: Enumerated completion with difficulty acknowledgment

```markdown
<!-- ✅ Forces acknowledgment of all items -->
<completeness>
For each issue found:
1. Fix it, OR
2. Explicitly state why it cannot be fixed and what approach would resolve it.

NEVER silently skip an issue. Skipping without acknowledgment = incomplete task.
Before declaring done, list all issues with their resolution status.
</completeness>
```

---

## Verification Mandate Guard (O3)

Prevents declaring victory without proof.

### Problem: Premature "task complete" without verification

```markdown
<!-- ❌ Changes made, no verification run -->
Opus: Edits type annotations → "Fixed the type errors."
Reality: 5 of 7 errors remain (only visible via pyright, not VS Code diagnostics)
```

### Guard: Tool-verified completion

```markdown
<!-- ✅ Verification is part of the definition of done -->
<verification>
Changes are NOT complete until the appropriate verification tool confirms them:
- Type changes → run type checker (pyright/mypy), not just IDE diagnostics
- Test changes → run the test suite
- Config changes → verify the build/lint succeeds

Report the verification result. "I believe it's correct" is not verification.
</verification>
```

---

## Confirmation Gate Guard (O5)

Prevents overeager autonomous actions on irreversible operations.

### Problem: Opus pushes code without asking

```markdown
<!-- ❌ Autonomous action on shared system -->
Opus: "I've pushed the fix to the remote branch."
User: "I didn't ask you to push!"
```

### Guard: Explicit confirmation for external actions

```markdown
<!-- ✅ Confirmation required for irreversible actions -->
<constraints>
CRITICAL:
- Before any action visible to others (push, PR, message, email): state the action
  and wait for explicit user confirmation.
- Before any destructive action (delete, force-push, reset): state what will be lost
  and wait for confirmation.
</constraints>
```

---

## Effort Calibration Guard (O6)

Prevents overthinking degradation on simple tasks.

### Problem: Deep reasoning on trivial task produces worse results

```markdown
<!-- ❌ Opus at max effort on a file rename -->
Opus: Spends 2000 thinking tokens analyzing implications of renaming a test file.
Considers backward compatibility, import updates across 40 files, CI impact...
Result: Overthought, slower, no quality gain, possibly introduced unnecessary changes.
```

### Guard: Explicit simplicity signal

```markdown
<!-- ✅ Signal task simplicity in the system prompt -->
<effort-note>
For file operations (rename, move, copy), simple edits (typo fixes in strings,
comment updates), and known-pattern implementations: respond directly without
extended deliberation. Save deep reasoning for architecture, debugging, and
ambiguous requirements.
</effort-note>
```

**Important**: This guard belongs in the **system prompt** (CLAUDE.md), not in user prompts. User-level framing ("this is simple") triggers O1 (framing bias). System-level effort guidance influences adaptive thinking without the anchoring bias.
