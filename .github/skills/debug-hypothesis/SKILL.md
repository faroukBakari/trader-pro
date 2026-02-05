---
name: debug-hypothesis
description: Hypothesis-driven debugging methodology. Use when investigating root cause, diagnosing failures, issues or problems.
---

# Hypothesis-Driven Debugging

Systematic investigation approach: form hypotheses, gather evidence, eliminate possibilities.

## Methodology

### Phase 1: Understand & Clarify

1. Parse the issue for: symptoms, expected vs actual behavior, environment, steps to reproduce
2. If critical information missing, gather using interactive questions
3. Form initial mental model of the problem space

### Phase 2: Hypothesize

List 2-5 possible causes ranked by likelihood:

| # | Hypothesis | Likelihood | Key Evidence Needed |
|---|------------|------------|---------------------|
| 1 | [cause] | High/Med/Low | [what would confirm/refute] |

### Phase 3: Investigate

For each hypothesis (highest likelihood first):

1. **Predict**: "If this hypothesis is correct, I expect to see..."
2. **Test**: Run targeted diagnostic (grep, read file, run specific test)
3. **Evaluate**: Does evidence support or refute? Update likelihood.
4. **Pivot or Drill**: Move to next hypothesis OR dig deeper

### Phase 4: Conclude

- State root cause with confidence level (Confirmed / Likely / Suspected)
- Link to specific code locations
- Explain the causal chain: trigger → fault → symptom

### Phase 5: Recommend

- Propose 1-3 fix approaches WITHOUT implementing
- Note trade-offs if applicable

## Output Format

Structure findings as:

```markdown
## Summary
[1-2 sentence synopsis of the issue and finding]

## Root Cause
**Confidence:** [Confirmed | Likely | Suspected]

[Specific explanation with file references]

**Location:** `path/to/file.py:123-145`

**Causal Chain:**
[trigger] → [fault in code] → [observable symptom]

## Evidence
| Finding | Source | Supports |
|---------|--------|----------|
| [observation] | [file/command] | Hypothesis # |

## Hypotheses Considered
| Hypothesis | Status | Reason |
|------------|--------|--------|
| [cause 1] | ✅ Confirmed / ❌ Refuted / ⏸️ Inconclusive | [brief reason] |

## Recommended Fixes
1. **[Approach name]**: [brief description]
   - Trade-off: [if any]
```

## Anti-Patterns

- ❌ Jumping to fix without confirming root cause
- ❌ Testing multiple hypotheses simultaneously (confounds evidence)
- ❌ Ignoring evidence that contradicts favorite hypothesis
- ❌ Not documenting eliminated possibilities
