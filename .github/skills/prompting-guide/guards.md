# Quality Guard Sections

Model-agnostic guards that improve output quality across all LLMs. Apply based on the Section Decision Table in the main skill — not every task needs every guard.

---

## Anti-Sycophancy

Prevents agreement-bias in evaluation and verification tasks:

```xml
<anti-sycophancy>
- If the approach has risks or flaws, state them explicitly.
- "This won't work because..." is more valuable than silent compliance.
- Report what you did NOT find — absence of evidence is a finding.
- Challenge assumptions when evidence contradicts them.
</anti-sycophancy>
```

## Completeness

Prevents truncated, placeholder-filled, or prematurely concluded output:

```xml
<completeness>
- Output ALL code completely. No placeholders, no abbreviations.
- NEVER use: "// ... rest", "# similar for others", "<!-- etc -->".
- Before finishing, enumerate all requirements and confirm each is addressed.
- If unable to complete in one response, state what remains explicitly.
</completeness>
```

## Scope Fence

Prevents unauthorized changes beyond the stated task:

```xml
<scope-fence>
- ONLY modify files directly related to the stated task.
- If you notice unrelated issues, note them but do NOT fix them.
- Do not refactor, rename, or reorganize unless explicitly requested.
- Preserve existing code style and patterns.
</scope-fence>
```

## Constraint Anchor

Combats instruction drift in long-running sessions. Place at methodology midpoints:

```xml
<constraint-anchor>
⚠️ PAUSE — Re-read the CRITICAL constraints above.
Confirm you are still operating within scope-fence boundaries.
</constraint-anchor>
```
