---
name: accessibility
description: Web accessibility patterns following WCAG 2.1 AA. Use when building UI components, auditing accessibility, implementing keyboard navigation, adding ARIA attributes, managing focus, or ensuring color contrast compliance.
---

# Web Accessibility (a11y)

Actionable WCAG 2.1 AA patterns for building inclusive UI — semantic HTML, keyboard navigation, ARIA, focus management, color contrast, and testing checklists.

---

## When to Use This Skill

- Building or reviewing interactive UI components (forms, modals, menus, tabs)
- Auditing existing markup for accessibility compliance
- Implementing keyboard navigation or focus management
- Adding ARIA attributes to custom widgets
- Checking color contrast ratios
- Writing accessible error handling and live announcements

---

## WCAG Principles: POUR

| Principle | Description |
|-----------|-------------|
| **P**erceivable | Content can be perceived through different senses |
| **O**perable | Interface can be operated by all users |
| **U**nderstandable | Content and interface are understandable |
| **R**obust | Content works with assistive technologies |

---

## Methodology

### Phase 1: Semantic Structure

Use native HTML elements before reaching for ARIA:

```html
<!-- ❌ ARIA role on div -->
<div role="button" tabindex="0">Click me</div>

<!-- ✅ Native button -->
<button>Click me</button>
```

**Landmark regions:**
```html
<header><!-- site header --></header>
<nav aria-label="Main"><!-- primary nav --></nav>
<main id="main-content"><!-- page content --></main>
<aside><!-- sidebar --></aside>
<footer><!-- site footer --></footer>
```

**Skip link (first focusable element):**
```html
<a href="#main-content" class="skip-link">Skip to main content</a>
```

```css
.skip-link {
  position: absolute;
  top: -40px;
  left: 0;
  background: #000;
  color: #fff;
  padding: 8px 16px;
  z-index: 100;
}
.skip-link:focus { top: 0; }
```

### Phase 2: Keyboard Navigation

All interactive elements must be keyboard-operable:

| Key | Action |
|-----|--------|
| `Tab` | Move to next interactive element |
| `Shift+Tab` | Move to previous interactive element |
| `Enter` / `Space` | Activate focused control |
| `Arrow` | Navigate within composite widgets (tabs, menus, grids) |
| `Escape` | Close dialogs, menus, popovers |

**Rules:**
- Non-interactive elements must NOT have `tabindex` (except `tabindex="-1"` for programmatic focus targets like headings)
- Hidden elements must not be focusable
- Focus must never get trapped without an escape mechanism

**Focus visibility:**
```css
/* Never remove focus outlines globally */
:focus-visible {
  outline: 2px solid var(--color-focus, #005fcc);
  outline-offset: 2px;
}
```

**Roving tabindex for composite widgets (tabs, grids):**
- Active child: `tabindex="0"`
- All other children: `tabindex="-1"`
- Arrow keys move focus and update tabindex values

### Phase 3: ARIA & Labeling

**Text alternatives:**
```html
<!-- Images: descriptive alt -->
<img src="chart.png" alt="Bar chart showing 40% increase in Q3 sales">

<!-- Decorative images: empty alt -->
<img src="border.png" alt="" role="presentation">

<!-- Icon buttons: accessible name -->
<button aria-label="Close dialog">
  <svg aria-hidden="true"><!-- icon --></svg>
</button>
```

**ARIA states for interactive widgets:**
```html
<!-- Expandable sections -->
<button aria-expanded="false" aria-controls="panel-1">Details</button>
<div id="panel-1" hidden>Content</div>

<!-- Invalid form fields -->
<input aria-invalid="true" aria-describedby="email-error">
<p id="email-error" role="alert">Please enter a valid email</p>

<!-- Loading states -->
<button aria-busy="true" aria-live="polite" disabled>Loading...</button>
```

**Custom tabs pattern:**
```html
<div role="tablist" aria-label="Product info">
  <button role="tab" id="tab-1" aria-selected="true" aria-controls="panel-1">Desc</button>
  <button role="tab" id="tab-2" aria-selected="false" aria-controls="panel-2" tabindex="-1">Reviews</button>
</div>
<div role="tabpanel" id="panel-1" aria-labelledby="tab-1">...</div>
<div role="tabpanel" id="panel-2" aria-labelledby="tab-2" hidden>...</div>
```

### Phase 4: Color & Contrast

| Element | AA Minimum Ratio |
|---------|-----------------|
| Normal text (< 18px / < 14px bold) | 4.5:1 |
| Large text (>= 18px / >= 14px bold) | 3:1 |
| UI components & graphics | 3:1 |

**Never rely on color alone to convey meaning:**
```html
<!-- ❌ Only color indicates error -->
<input style="border-color: red">

<!-- ✅ Color + icon + text -->
<input aria-invalid="true" aria-describedby="err">
<span id="err">
  <svg aria-hidden="true"><!-- error icon --></svg>
  Please enter a valid email
</span>
```

### Phase 5: Forms & Error Handling

```html
<!-- Explicit label association -->
<label for="email">Email address</label>
<input type="email" id="email" autocomplete="email" required
       aria-describedby="email-hint">
<p id="email-hint">We'll never share your email</p>
```

**On validation failure:**
1. Set `aria-invalid="true"` on the field
2. Associate error message via `aria-describedby`
3. Use `role="alert"` or `aria-live="assertive"` on the error container
4. Focus the first invalid field on form submit

### Phase 6: Dynamic Content & Live Regions

```html
<!-- Polite: announced after current speech -->
<div aria-live="polite" aria-atomic="true">
  3 items in your cart
</div>

<!-- Assertive: interrupts current speech (use sparingly) -->
<div role="alert" aria-live="assertive">
  Connection lost. Reconnecting...
</div>
```

### Phase 7: Motion & Timing

```css
/* Respect reduced motion preference */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

- Provide controls to pause/stop auto-updating content
- Allow users to extend time limits (session warnings)

---

## Focus Management Patterns

**Modal dialog focus trap:**
1. On open: save previously focused element, focus first focusable child
2. Tab/Shift+Tab cycles within modal (trap)
3. Escape closes the modal
4. On close: restore focus to the saved element

**Route transitions (SPA):**
- After navigation, move focus to the new page's heading or main content
- Announce route changes via a live region

---

## Audit Checklist

### Critical (fix immediately)
- [ ] All images have appropriate `alt` text
- [ ] All form fields have associated labels
- [ ] Color contrast meets AA ratios
- [ ] No keyboard traps
- [ ] Focus indicators visible on all interactive elements

### Serious (fix before release)
- [ ] Page has `lang` attribute on `<html>`
- [ ] Logical heading hierarchy (h1 > h2 > h3)
- [ ] Skip link present
- [ ] Link text is descriptive (no "click here")
- [ ] No auto-playing media

### Moderate (fix soon)
- [ ] ARIA labels on icon-only buttons
- [ ] Error messages associated with fields
- [ ] Landmark regions present (`main`, `nav`, `header`, `footer`)
- [ ] `aria-live` for dynamic content updates
- [ ] `prefers-reduced-motion` respected

---

## Anti-Patterns

- ❌ **Div soup** — Using `<div>` or `<span>` for interactive elements instead of `<button>`, `<a>`, `<input>`
- ❌ **Outline removal** — `*:focus { outline: none }` without replacement focus styles
- ❌ **Placeholder-as-label** — Using `placeholder` as the only label (disappears on input, poor contrast)
- ❌ **ARIA overuse** — Adding redundant roles to semantic elements (`<nav role="navigation">` is unnecessary)
- ❌ **tabindex > 0** — Positive tabindex values break natural tab order
- ✅ **Progressive enhancement** — Semantic HTML first, ARIA only for custom widgets
