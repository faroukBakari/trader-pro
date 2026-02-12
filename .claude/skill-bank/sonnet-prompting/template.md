# Sonnet-Specific Calibrations

Sonnet-specific adjustments to apply on top of the generic prompt sections defined in the `prompting-guide` skill. This file does NOT redefine sections — it calibrates them for Sonnet 4.5's behavioral characteristics.

---

## Sonnet Calibration Rules

Apply these adjustments when the target model is Sonnet 4.5:

| Generic Section          | Sonnet Calibration                                                                                                                        |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `<role>`                 | Keep to 1-3 lines. Line 1 = identity. Lines 2-3 = convention anchoring (for F9 mitigation). Omit filler adjectives — Sonnet ignores them. |
| `<task>`                 | Use imperative sentences. "Implement X" not "You might want to consider implementing X."                                                  |
| `<constraints>` CRITICAL | Cap at **≤5 items**. Adherence drops sharply beyond 5. Move overflow to IMPORTANT.                                                        |
| `<constraints>` language | Use direct commands. Eliminate "you should", "consider", "try to".                                                                        |
| `<output_format>`        | Prefer tables → near-100% compliance. JSON with example → reliable schema compliance.                                                     |
| `<anti-sycophancy>`      | Always include for evaluation/review. Sonnet F1 (sycophancy) is HIGH severity.                                                            |
| `<completeness>`         | Always include for code generation. Sonnet F2 (lazy output) is the #1 reported flaw.                                                      |
| `<constraint-anchor>`    | Include for sessions >10 tool calls. Sonnet F4 (constraint drift) is HIGH severity.                                                       |

---

## Minimal Template (Sonnet Speed Optimization)

For focused, single-step tasks where the full template adds unnecessary tokens. Exploits Sonnet's fast processing with minimal prompt overhead:

```xml
<task>
{Direct verb} {target} {to achieve what}.
</task>

<constraints>
CRITICAL:
- {1-3 non-negotiable rules}
</constraints>

<completeness>
Output ALL code completely. No placeholders or abbreviations.
</completeness>
```

---

## Flaw-to-Section Mapping Reference

| Sonnet Flaw               | Primary Guard Section           | Secondary Guard                          |
| ------------------------- | ------------------------------- | ---------------------------------------- |
| F1: Sycophancy            | `<anti-sycophancy>`             | `<constraints>` CRITICAL tier            |
| F2: Lazy output           | `<completeness>`                | `<output_format>` with examples          |
| F3: Premature completion  | `<completeness>`                | `<task>` numbered requirements           |
| F4: Constraint drift      | `<constraint-anchor>`           | Constraint sandwiching                   |
| F5: Bold changes          | `<scope-fence>`                 | `<constraints>` CRITICAL tier            |
| F6: Reasoning ceiling     | Escalate to Opus                | `<task>` decomposition into ≤3-hop steps |
| F7: Tool hallucination    | `<output_format>` with examples | Provide concrete path/param examples     |
| F8: Confirmation bias     | `<anti-sycophancy>`             | "expected vs found" output pattern       |
| F9: Code slop             | `<role>` convention anchoring   | `<scope-fence>` preserve style           |
| F10: Negative suppression | `<anti-sycophancy>`             | "Report what you did NOT find"           |
