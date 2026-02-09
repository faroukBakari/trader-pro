---
name: frontend-visual-verification
description: Decision logic and verification protocol for automatic Playwright-based visual validation of frontend UI changes. Use when a task creates, modifies, or analyzes frontend components, styles, or layouts — determines whether visual verification is warranted and provides the delegation template for invoking browser automation.
---

# Frontend Visual Verification

Automatic detection and visual validation of frontend UI changes via browser automation. This skill answers two questions: (1) does this task warrant visual verification? and (2) what exactly should be verified?

**Core invariant**: Frontend UI changes that affect what the user sees should be visually verified — not just tested in isolation.

---

## When to Use This Skill

- After implementing frontend component changes (template, styles, layout)
- After a study/analysis recommends frontend UI modifications
- When reviewing code that touches visual presentation
- After refactoring CSS, component structure, or layout hierarchy
- When co-working across agents (study → plan → implement) on frontend features

---

## Methodology

### Phase 1: Detect Frontend Relevance

Scan the task context for frontend signals. A task is frontend-relevant if **any** of these indicators match:

| Signal | Detection Pattern | Weight |
|--------|-------------------|--------|
| Component files changed/analyzed | Paths matching `frontend/src/components/**/*.vue` or `frontend/src/views/**/*.vue` | High |
| Style changes | CSS/SCSS modifications, `<style>` block edits, class name changes | High |
| Layout/template changes | `<template>` block modifications, DOM structure changes | High |
| Visual design discussion | Study mentions "UI", "layout", "theme", "overlay", "animation", "responsive" | Medium |
| Generated client changes | Files in `frontend/src/clients_generated/` that affect displayed data shapes | Low |
| Only logic/service changes | `frontend/src/services/`, `frontend/src/composables/` without template impact | Skip |

**Decision rule:**
- **Any High signal** → visual verification warranted
- **2+ Medium signals** → visual verification warranted
- **Only Low signals** → visual verification optional (offer but don't auto-trigger)
- **No signals** → skip entirely

### Phase 2: Select Verification Tier

Based on change scope, select the verification tier that balances thoroughness with speed:

| Tier | When to Use | Tool Calls | Typical Duration |
|------|-------------|------------|------------------|
| **Quick** | CSS-only tweaks, single-property changes, auto-triggered checks | 1-2 | ~5s |
| **Standard** | New components, layout changes, theme modifications | 3-5 | ~15s |
| **Full** | Cross-cutting redesigns, multi-route changes, design system updates | 6+ | ~30s+ |

**Tier selection rules:**

| Change Type | Tier | Rationale |
|-------------|------|-----------|
| Single CSS property change (color, spacing, opacity) | Quick | One screenshot confirms correctness |
| Style/theme change across a component | Standard | Need component + adjacent context |
| New component or layout restructure | Standard | Render check + positioning + regression |
| Animation/transition addition | Standard | Trigger + visual smoothness |
| State-dependent UI (multi-state component) | Standard | Each state needs verification |
| Multi-component or multi-route visual change | Full | Cross-cutting regression risk |
| Design system / global theme change | Full | Broad blast radius |
| Accessibility audit (focus, contrast, ARIA) | Full | Multiple interaction patterns |

**Auto-triggered default**: When verification is triggered automatically (not explicitly requested), use **Quick** tier unless change signals clearly indicate Standard or Full. This prevents slow feedback loops for routine changes.

**Escalation**: If Quick tier reveals anomalies → escalate to Standard. If Standard reveals cross-cutting issues → escalate to Full.

### Phase 3: Compose Verification Delegation

Build the Playwright subagent invocation using the tier-appropriate template:

#### Quick Tier Template

```
Playwright task:
- URL: {dev server URL, typically http://localhost:5173 + route}
- Action: screenshot and check
- Details:
  1. Navigate to the page containing the changed component
  2. Take a screenshot — does the component render correctly?
- Return:
  - Screenshot of the component in context
  - Any console errors on the page
  - Pass/fail: does it match the expected visual outcome?

Context: {What changed and what it should look like}
```

#### Standard Tier Template

```
Playwright task:
- URL: {dev server URL, typically http://localhost:5173 + route}
- Action: verify
- Details:
  1. {Primary verification — does the changed component render?}
  2. {Visual consistency — do colors/spacing/layout match the design spec?}
  3. {No regression — are adjacent components unaffected?}
  4. {State check — test relevant states if applicable}
- Return:
  - Screenshot of the component in context
  - Any console errors on the page
  - Whether the component matches the design specification
  - Any visual anomalies or regressions detected

Context: {Brief description of what was changed and what the expected visual outcome is}
```

#### Full Tier Template

```
Playwright task:
- URL: {dev server URL, typically http://localhost:5173 + route}
- Action: comprehensive verify
- Details:
  1. {Primary verification — render check per route/component}
  2. {Visual consistency — colors, spacing, layout vs design spec}
  3. {All states — loading, error, empty, populated, hover, expanded, collapsed}
  4. {Regression — adjacent components, sibling routes, global layout}
  5. {Responsive — viewport adaptation if applicable}
  6. {Accessibility — focus indicators, contrast, ARIA structure}
- Return:
  - Screenshots of each verified state and route
  - Console errors/warnings
  - Per-criterion pass/fail with evidence
  - Visual anomalies or regressions detected

Context: {Detailed description of changes, design spec, and expected outcomes across all states}
```

**Adaptation rules:**
- If the dev server isn't running → note that visual verification requires `make -f project.mk dev-frontend` first
- If changes span multiple routes → use Full tier (or escalate)
- If the component has interactive states → use Standard tier minimum

### Phase 4: Interpret Results

After receiving the Playwright report, assess against these criteria:

| Criterion | Pass | Fail |
|-----------|------|------|
| Component renders | Visible in expected position | Missing, misplaced, or invisible |
| Visual consistency | Colors/spacing match design spec or surrounding context | Clashing theme, wrong colors, broken spacing |
| No regression | Adjacent elements unchanged | Layout shift, overlap, or style bleed |
| No console errors | Zero errors (warnings acceptable) | JS errors, failed network requests |
| Responsive | Adapts to viewport (if applicable) | Overflow, truncation, or collapse |

---

## Pre-Requisites

Visual verification requires:
1. **Dev server running** — `make -f project.mk dev-frontend` (or `dev-fullstack` if backend needed)
2. **Playwright MCP available** — browser automation tools accessible in the tool set
3. **Changes applied** — code modifications must be saved and hot-reloaded

If pre-requisites aren't met, **report what's missing** rather than silently skipping verification.

---

## Anti-Patterns

- ❌ **Skipping verification for "small" CSS changes** — A single color or z-index change can break visual hierarchy. Use Quick tier — it's fast enough for any High signal.
- ❌ **Always running Full tier** — Full verification is slow (~30s+). Reserve it for cross-cutting changes. Auto-triggered checks should default to Quick.
- ❌ **Verifying only the changed component** — At Standard/Full tiers, always check adjacent context. Overlay changes can affect chart visibility; layout changes can shift siblings.
- ❌ **Treating test-passing as visual-passing** — Unit tests validate DOM structure and logic; they don't catch visual regressions (wrong color, broken blur, z-index clash).
- ❌ **Running verification without design context** — Always include the design spec or expected visual outcome in the delegation prompt so the Playwright subagent knows what "correct" looks like.
- ✅ **Auto-detect + auto-delegate at Quick tier** — When the skill's detection rules match, invoke Quick verification without being asked. Escalate only if anomalies found.
- ✅ **Tier escalation on anomaly** — Quick reveals something off? Escalate to Standard. Standard reveals cross-cutting issues? Escalate to Full.
