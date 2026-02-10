---
name: code-review
description: Post-implementation code review methodology with severity framework and project-specific rules. Use when reviewing code changes, auditing pull requests, analyzing code quality, or performing security review.
---

# Code Review

Structured methodology for reviewing code changes — security, correctness, quality, and project convention adherence. Produces actionable findings with severity classification and a clear verdict.

---

## When to Use This Skill

- Reviewing code after implementation (post-build audit)
- Analyzing pull requests or staged changes
- Security-focused code audit
- Checking adherence to project conventions
- Validating that generated code wasn't manually edited

---

## Methodology

### Phase 1: Scope & Context

1. **Identify the change set** — files modified, lines changed, modules affected
2. **Read surrounding code** — understand the context before judging the change
3. **Check module boundaries** — are changes confined to one module or cross-cutting?

### Phase 2: Review Checklist

Apply each category systematically. Skip categories that don't apply to the change.

#### Security

| Check | Look For |
|-------|----------|
| Injection | SQL, command, XSS vulnerabilities |
| Auth | Missing auth checks, token handling |
| Secrets | Hardcoded credentials, exposed keys |
| Validation | Missing input validation |

#### Correctness

| Check | Look For |
|-------|----------|
| Logic | Off-by-one, null checks, edge cases |
| Types | Type safety, proper generics usage |
| Error handling | Unhandled exceptions, error propagation |
| Tests | Missing tests for new behavior |

#### Quality

| Check | Look For |
|-------|----------|
| Patterns | Consistency with codebase conventions |
| Complexity | Overly complex solutions, unnecessary abstractions |
| Documentation | Missing docstrings, outdated comments |
| Dead code | Unreachable or unused code |

#### Project Rules

| Check | Look For |
|-------|----------|
| Generated code | Manual edits to `*_generated/` directories |
| Types | Use of `any` (TS) or `Any` (Python) |
| Commands | Direct npm/poetry usage instead of make targets |
| Module boundaries | Cross-module imports violating isolation |
| Statelessness | Instance variables storing request-scoped data |

### Phase 3: Severity Classification

Classify each finding:

| Severity | Criteria | Action |
|----------|----------|--------|
| **Critical** | Security vulnerability, data loss risk, production crash | Must fix before merge |
| **High** | Type safety violation, missing error handling, broken contract | Should fix before merge |
| **Medium** | Missing tests, inconsistent patterns, minor quality issue | Fix recommended |
| **Low** | Style suggestions, minor improvements, nice-to-haves | Optional |

### Phase 4: Verdict

| Verdict | When |
|---------|------|
| ✅ Approve | No Critical/High findings |
| ⚠️ Approve with comments | Only Medium/Low findings |
| ❌ Request changes | Any Critical or High findings |

---

## Output Format

```markdown
## Code Review: [Scope]

### Summary
[1-2 sentence overview of changes reviewed]

### Findings

#### 🔴 Critical
| Location | Issue | Recommendation |
|----------|-------|----------------|

#### 🟠 High
| Location | Issue | Recommendation |
|----------|-------|----------------|

#### 🟡 Medium
| Location | Issue | Recommendation |
|----------|-------|----------------|

#### 🔵 Low / Suggestions
| Location | Issue | Recommendation |
|----------|-------|----------------|

### Positive Observations
- [Good patterns observed]

### Statistics
- Files reviewed: X
- Critical: X | High: X | Medium: X | Low: X

### Verdict: [✅ | ⚠️ | ❌]
```

---

## Anti-Patterns

- ❌ Reviewing without reading surrounding code — leads to false positives
- ❌ Style-only feedback disguised as High severity — undermines trust
- ❌ Asserting "no tests exist" without searching — verify before claiming absence
- ✅ Every finding has a specific file:line reference and actionable recommendation
