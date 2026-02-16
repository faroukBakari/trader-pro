---
name: frontend-design
description: Distinctive, production-grade visual design for frontend interfaces. Load when building UI needing polished aesthetics
user-invocable: false
---

# Frontend Design — Distinctive Visual Interfaces

Create production-grade frontend interfaces that avoid generic "AI slop" aesthetics. Generate creative, polished code with exceptional attention to visual details and bold creative choices.

> **Source**: Adapted from Anthropic's official `frontend-design` Claude Code plugin.

---

## When to Use This Skill

- Building new pages, components, or full applications from scratch
- Reskinning or visually refreshing existing UI
- Creating landing pages, dashboards, or marketing surfaces
- Any frontend task where visual quality matters beyond functional correctness

**Complementary skills**: Pair with `ux-design` (interaction/cognition), `accessibility` (WCAG), `vue-frontend` (framework patterns).

---

## Methodology

### Phase 1: Design Thinking (Before Code)

Understand context and commit to a **bold** aesthetic direction:

| Question | Purpose |
|----------|---------|
| **Purpose** | What problem does this interface solve? Who uses it? |
| **Tone** | Pick a direction: brutally minimal, maximalist, retro-futuristic, organic/natural, luxury/refined, playful, editorial/magazine, brutalist/raw, art deco, soft/pastel, industrial/utilitarian |
| **Constraints** | Framework, performance budget, accessibility requirements |
| **Differentiator** | What's the one thing someone will remember about this? |

Choose a clear conceptual direction and execute with precision. Bold maximalism and refined minimalism both work — the key is **intentionality**, not intensity.

### Phase 2: Typography

Typography is the highest-leverage design decision.

**Rules:**
- Choose fonts that are beautiful, unique, and characterful
- Pair a distinctive **display font** with a refined **body font**
- Use variable font weights for nuance (not just 400/700)
- Set line-height, letter-spacing, and measure (line length) deliberately

**Banned (generic/overused):**
- Inter, Roboto, Arial, system-ui defaults, Space Grotesk
- Any font that reads as "default AI output"

**Approach:**
- Google Fonts has hundreds of distinctive options — explore beyond page 1
- Consider the emotional tone: geometric = modern/cold, humanist = warm/approachable, slab = bold/confident, serif = editorial/refined

### Phase 3: Color & Theme

**Rules:**
- Commit to a cohesive palette using CSS custom properties
- Dominant color + sharp accent outperforms timid, evenly-distributed palettes
- Vary between light and dark themes across designs — never default to the same one
- Background is part of the design — never leave it as plain white/gray

**Banned:**
- Purple gradients on white backgrounds (the AI cliche)
- Safe corporate blue + gray
- Any palette that reads as "template default"

### Phase 4: Motion & Interaction

Animations create delight but must be purposeful.

**Priority order:**
1. **Page-load orchestration** — staggered reveals with `animation-delay` (highest impact)
2. **Scroll-triggered effects** — elements animate into view
3. **Hover states that surprise** — scale, color shift, shadow elevation
4. **Micro-interactions** — button feedback, toggle transitions

**Implementation:**
- CSS-only solutions for HTML/vanilla JS
- Motion library (Framer Motion) for React when available
- One well-orchestrated entrance creates more delight than scattered micro-interactions
- Respect `prefers-reduced-motion`

### Phase 5: Spatial Composition

Break out of predictable grid layouts:

- **Asymmetry** — intentional imbalance creates visual interest
- **Overlap** — elements breaking containment boundaries
- **Diagonal flow** — angled sections, skewed containers
- **Grid-breaking elements** — one element that defies the grid draws the eye
- **Generous negative space** OR **controlled density** — both work, middle ground doesn't

### Phase 6: Backgrounds & Visual Details

Create atmosphere and depth:

- Gradient meshes and multi-stop gradients
- Noise/grain textures (CSS or SVG filters)
- Geometric patterns (repeating SVG, CSS patterns)
- Layered transparencies and glassmorphism
- Dramatic shadows (large offsets, colored shadows)
- Decorative borders and dividers
- Custom cursors where appropriate

---

## Anti-Patterns

- **Convergence** — using the same font/palette/layout across designs. Every generation must be distinct
- **Template aesthetic** — cookie-cutter card grids, hero-section-with-gradient, feature-columns
- **Decoration without intention** — effects that don't serve the design direction
- **Complexity mismatch** — maximalist vision with minimal code, or minimalist vision with excessive effects
- **Safe choices** — when in doubt, the bolder option is usually the right one

---

## Quality Checklist

- [ ] Aesthetic direction is intentional and clearly identifiable
- [ ] Typography is distinctive (not Inter/Roboto/Arial/Space Grotesk)
- [ ] Color palette is cohesive with CSS custom properties
- [ ] At least one animation/transition adds delight
- [ ] Layout has at least one unexpected/creative element
- [ ] Background contributes to atmosphere (not plain white/gray)
- [ ] `prefers-reduced-motion` and `prefers-color-scheme` respected
- [ ] Code is production-grade and functional, not just a visual mockup
