---
name: ux-design
description: UX design thinking for friction reduction, cognitive load management, and flow preservation. Use when building interactive UI, auditing user flows, designing feedback patterns, optimizing layouts, reducing decision fatigue, or reviewing component ergonomics.
---

# UX Design Patterns

Actionable UX design patterns grounded in cognitive psychology — Gestalt perception, Fitts' & Hick's Laws, cognitive load theory, flow state engineering, and ADHD-friendly design. Apply these while writing code to build interfaces that feel effortless.

---

## When to Use This Skill

- Building interactive components (forms, modals, menus, dashboards)
- Reviewing UI code for friction points
- Designing loading, error, and empty states
- Laying out controls, buttons, and navigation
- Optimizing data-dense interfaces (tables, charts, panels)
- Deciding progressive disclosure vs. upfront display

---

## Methodology

### Phase 1: Cognitive Load Assessment

Three types of mental load — eliminate the one you control:

| Type | Definition | Your Job |
|------|------------|----------|
| **Intrinsic** | Task complexity itself | Can't eliminate — acknowledge it |
| **Extraneous** | Poor design adding effort | **ELIMINATE THIS** |
| **Germane** | Learning/understanding | Minimize for repeat users |

**Working memory limits (Miller's Law):**
- 7 ± 2 items maximum in working memory
- 4 chunks optimal for complex tasks
- Group related controls; never show >7 options without categorization

**Reduction strategies:**
- Use **recognition over recall** — show options, don't expect users to remember them
- Provide **smart defaults** — pre-fill the most common choice
- Apply **progressive disclosure** — show one level of complexity at a time, reveal more on demand
- Remove **decorative noise** — every element that doesn't inform competes with those that do

### Phase 2: Gestalt Perception Principles

How humans perceive visual grouping — use these to communicate structure without labels:

**Proximity** — elements close together are perceived as related:
```
┌─────────┐  ┌─────────┐     ┌─────────┐  ┌─────────┐
│ Related │  │ Related │     │ Other   │  │ Other   │
│ Item A  │  │ Item B  │     │ Group A │  │ Group B │
└─────────┘  └─────────┘     └─────────┘  └─────────┘
     ↑ CLOSE = grouped            ↑ SEPARATE = distinct
```
- Group related form fields with shared whitespace boundaries
- Separate unrelated sections with meaningful gaps (not lines)

**Similarity** — same color/shape/size = perceived as same function:
```
┌──────┐  ┌──────┐  ┌──────┐     ┌──────┐  ┌──────┐
│ BLUE │  │ BLUE │  │ BLUE │     │ RED  │  │ RED  │
│ Save │  │ Copy │  │ Edit │     │ Del  │  │ Clear│
└──────┘  └──────┘  └──────┘     └──────┘  └──────┘
     ↑ Same style = safe actions       ↑ Different = destructive
```
- Use consistent styling for actions of the same class
- Visually differentiate destructive actions from safe ones

**Continuity** — the eye follows lines and paths naturally:
```
Step 1 ──→ Step 2 ──→ Step 3 ──→ Complete
   ●──────────●──────────●──────────●
```
- Align multi-step flows horizontally or vertically — never zigzag
- Use visual connectors (lines, arrows, progress bars) between steps

**Closure** — the brain completes incomplete shapes:
```
[ ████████░░░░░░░░ ] 50% — brain "sees" the end
```
- Progress bars leverage closure — users mentally project completion
- Partially visible cards imply more content beyond the fold

### Phase 3: Interaction Sizing (Fitts' Law)

Time to reach a target = f(Distance / Size). Larger + closer = faster.

**Minimum touch/click target sizes:**

| Platform | Minimum | Preferred |
|----------|---------|-----------|
| iOS | 44 × 44 px | 48 × 48 px |
| Android | 48 × 48 px | 56 × 56 px |
| Desktop | 32 × 32 px | 44 × 44 px |

**Layout rules:**
- **Primary action** → largest button, most prominent position
- **Destructive actions** → smaller, separated from primary path (never adjacent to confirm)
- **Icon + label > icon alone** → larger target area + reduced ambiguity
- **Edge targets are infinite** — place critical actions at screen edges/corners (can't overshoot)
- **Context menus** appear at cursor → zero travel distance

```
❌  [ Delete ]  [ Confirm ]     ← Adjacent destructive + primary
✅  [ Confirm ]          [ Delete ]  ← Separated, different size
```

### Phase 4: Decision Reduction (Hick's Law)

Decision time increases logarithmically with the number of choices.

**Rules:**
- ≤ 5 primary actions visible at once — hide rest behind "More" or progressive disclosure
- Highlight the **recommended option** to short-circuit decision time
- Use **categorized groups** for long lists (tabs, sections, filters)
- Provide **search** for any list > 15 items
- **Smart defaults** eliminate decisions entirely — pre-select the 80% case

**Decision hierarchy pattern:**
```
Primary:    [ Place Order ]          ← One clear CTA
Secondary:  [ Save Draft ] [ Cancel ] ← Supporting actions
Tertiary:   More options ▾            ← Everything else hidden
```

### Phase 5: Feedback & State Communication

Every user action needs acknowledgment. Silence breeds uncertainty.

**Response time thresholds:**

| Delay | User Perception | Required Feedback |
|-------|----------------|-------------------|
| < 100ms | Instant | None needed |
| 100ms – 1s | Noticeable | Subtle indicator (spinner, pulse) |
| 1s – 10s | Waiting | Progress bar, skeleton screen |
| > 10s | Leaving | Progress %, background processing with notification |

**State coverage checklist — every async component needs all five:**
- **Loading** — skeleton screens preferred over spinners (preserves layout)
- **Empty** — guide toward first action ("No orders yet. Place your first order →")
- **Error** — actionable message + recovery action ("Connection lost. [Retry]")
- **Partial** — some data loaded, some still pending (show what you have)
- **Success** — confirm completion briefly (toast, checkmark animation)

**Optimistic UI:**
- Execute visually before server confirms — rollback on error
- Creates perception of instant response
- Use for: toggles, list reordering, simple CRUD
- Avoid for: financial transactions, irreversible actions

### Phase 6: Flow State Preservation

Flow requires: clear goals, immediate feedback, challenge-skill balance, no failure anxiety.

**Rules to preserve flow:**
- **Never block UI** for operations > 1 second — process in background
- **Auto-save** everything — eliminate "save anxiety"
- **Undo everything** — confidence to experiment requires reversibility
- **Keyboard shortcuts** for power users — `Ctrl+Enter` for primary action, `Escape` for cancel
- **Re-orientation after interruption** — "Welcome back" panel showing last state and next action
- **Minimize mode switches** — every context switch costs 23 minutes of focus recovery

**Interruption cost matrix:**

| Interruption Type | Recovery Time | Mitigation |
|-------------------|--------------|------------|
| Modal dialog (blocks flow) | 15-30s | Use inline messages or toasts instead |
| Full page navigation | 5-15s | Use panels, drawers, or inline expansion |
| Confirmation dialog | 3-10s | Use undo pattern instead ("3 items deleted. [Undo]") |
| Toast notification | 1-2s | Minimal cost — preferred for non-critical feedback |

### Phase 7: ADHD-Friendly Design

Patterns that benefit neurodivergent users — and improve experience for everyone:

| Principle | Implementation |
|-----------|----------------|
| **Progressive disclosure** | Show one task at a time; hide future steps |
| **Context preservation** | Auto-save every keystroke; never lose work |
| **Gentle feedback** | Status updates, not alarms; no aggressive red urgency |
| **Pause & resume** | Session state persists across days/weeks |
| **Minimal distractions** | Single focus area; dim non-active panels |
| **Chunked progress** | Visual cards/steps, not endless scrolling |
| **Predictable layout** | Same layout always; no layout shifts or surprises |
| **Calm mode option** | Reduced animations, muted colors on demand |

---

## Friction Audit Checklist

Run this against any component or flow before shipping:

### Cognitive Load
- [ ] User can complete the task with ≤ 4 things in working memory
- [ ] No unnecessary choices — defaults handle the 80% case
- [ ] Recognition over recall — options are visible, not memorized
- [ ] Information hierarchy is clear — primary content dominates

### Interaction Design
- [ ] Primary buttons ≥ 44px tall with sufficient padding
- [ ] Destructive actions are visually distinct and separated from primary path
- [ ] Labels on buttons, not just icons (icon-only acceptable only with tooltip)
- [ ] Related controls are grouped with proximity, not with borders

### Feedback
- [ ] Every async action has loading, error, empty, and success states
- [ ] No action blocks the UI for > 2 seconds without progress indication
- [ ] Error messages are actionable — they say what went wrong AND what to do
- [ ] Success confirmation is brief and non-blocking (toast or inline)

### Flow
- [ ] Auto-save prevents data loss
- [ ] Every destructive action is undoable (prefer undo over confirmation dialogs)
- [ ] Keyboard shortcuts exist for frequent actions
- [ ] No unnecessary page reloads or full navigations

### Decision Architecture
- [ ] ≤ 5 primary options visible at once
- [ ] Recommended option is visually highlighted
- [ ] Long lists have search/filter (> 15 items)
- [ ] Steps show progress ("Step 2 of 4")

---

## Anti-Patterns

- ❌ **Confirmation fatigue** — "Are you sure?" dialogs for every action. Use undo instead.
- ❌ **Mystery meat navigation** — Icon-only buttons without labels or tooltips
- ❌ **Error tombstones** — "Something went wrong" with no recovery action
- ❌ **Layout thrashing** — Content shifting as async data loads (use skeleton screens)
- ❌ **Choice overload** — Showing 20+ options without grouping or search
- ❌ **Split attention** — Error messages far from the field that caused them
- ❌ **Modal abuse** — Using modals for information that could be inline
- ❌ **Silent failures** — Operations that fail without any visible feedback
- ✅ **Calm confidence** — Clear state, immediate feedback, easy reversal, predictable layout
