---
name: stack-stability
description: Change impact analysis and incremental modification protocol for interconnected agentic design stacks. Use when modifying, renaming, restructuring, or removing existing IA assets (agents, skills, subagents, prompts, templates). Prevents big-bang changes that destabilize learned system behaviors.
---

# Stack Stability

Change-control methodology for mature agentic design stacks where assets form an interconnected dependency graph. Treats every asset as a weighted node — modifications propagate through connections. Controls the **rate** and **direction** of change to prevent systemic destabilization while allowing continuous improvement.

Inspired by ML training dynamics: stability tiers act as frozen layers, impact scores estimate gradient magnitude, change budgets clip excessive updates, and ecosystem alignment ensures the direction of change follows vendor and community trajectory.

---

## When to Use This Skill

- Modifying an existing asset (agent, skill, subagent, prompt, template)
- Renaming, merging, splitting, or removing any asset
- Changing an interface contract (caller protocol, output format)
- Restructuring the asset catalog or registry
- Responding to vendor API changes, new model releases, or community pattern shifts
- Reviewing whether a proposed change is safe to proceed

**Do NOT use for**:
- Creating brand-new leaf assets with zero existing dependents (additive changes are inherently safe)
- Cosmetic-only edits (typos, formatting, comment clarification) — these are unbounded
- Reading or analyzing assets without modification intent

---

## Methodology

### Phase 1: Stability Tier Classification

Every asset in the stack occupies a stability tier based on its **downstream dependency count** — not perceived importance.

| Tier | Label | Dependency Count | Change Protocol |
|------|-------|-----------------|-----------------|
| **T4** | Foundational | 8+ dependents | Explicit user request + full impact analysis + incremental migration plan |
| **T3** | Structural | 5-7 dependents | Impact analysis + downstream verification |
| **T2** | Shared | 2-4 dependents | Downstream notification scan |
| **T1** | Leaf | 0-1 dependents | Standard quality gates only |

**To classify an asset**:
1. Count direct dependents — assets that reference, import, or invoke this asset
2. Include: skill references, subagent invocations, template inheritance, registry listings, handoff targets
3. Exclude: indirect dependents (A depends on B depends on C — C is not a direct dependent of A)

**Tier boundary rule**: When in doubt, classify **one tier higher**. Over-protecting is cheaper than under-protecting.

### Phase 2: Change Impact Analysis

Before modifying any T2+ asset, compute the effective impact score.

#### Step 1: Base Impact

```
Base Impact = downstream_dependents × change_magnitude
```

**Change magnitude scale:**

| Magnitude | Value | Definition | Examples |
|-----------|-------|------------|---------|
| Cosmetic | 0.1 | No behavioral change | Typo fix, comment improvement, formatting |
| Additive | 0.3 | New content, nothing existing changes | New phase, new gate, new section |
| Modification | 0.6 | Existing behavior changes | Constraint level change, threshold adjustment, methodology reorder |
| Structural | 0.9 | Interface or identity changes | Rename, output format change, caller protocol change |
| Systemic | 1.0 | Foundational schema or topology change | Template restructure, registry reorganization, layer model change |

#### Step 2: Direction Multiplier (Ecosystem Alignment)

Every non-cosmetic change has a **direction** relative to the vendor and community ecosystem. The direction modulates the effective impact.

```
Effective Impact = Base Impact × Direction Multiplier
```

| Direction | Multiplier | Definition | Signal Source |
|-----------|-----------|------------|---------------|
| **Vendor-aligned** | 0.7 | Change follows explicit vendor guidance or adopts a new vendor feature | Official docs, changelogs, migration guides |
| **Community-validated** | 0.8 | Change follows patterns proven by the practitioner community | Blog posts, conference talks, open-source projects, postmortems |
| **Neutral** | 1.0 | Internal optimization with no external signal | Refactoring, performance improvement, internal consistency |
| **Divergent** | 1.5 | Change goes in a direction vendors haven't addressed | Novel pattern, untested approach |
| **Contradictory** | 2.0 | Change conflicts with explicit vendor or community guidance | Doing the opposite of documented best practice |

**Determining direction:**
1. State which ecosystem signal (if any) motivated this change
2. If no signal → Neutral (1.0)
3. If signal exists → cite the source (URL, doc reference, or community pattern name)
4. Internal inventions are valid (Neutral) but flagged — they don't get the direction discount
5. When unsure → default to Neutral (1.0), never assume alignment without a source

#### Step 3: Threshold Response

| Effective Impact | Protocol | Analogy |
|-----------------|----------|---------|
| < 1.0 | **Proceed normally** — standard quality gates | Small gradient, normal step |
| 1.0 – 3.0 | **Document and proceed carefully** — note impact in change record, verify direct dependents | Moderate gradient, reduced step |
| 3.1 – 6.0 | **Decompose** — break into smaller independent changes, execute incrementally | Large gradient, clip and accumulate |
| > 6.0 | **Halt** — present full impact map and migration plan, get explicit approval | Gradient explosion, stop training |

### Phase 3: Change Budget Enforcement

Maximum assets modifiable in a single session, scaled by change type:

| Change Type | Max Assets Per Session | Rationale |
|------------|----------------------|-----------|
| Cosmetic-only | Unbounded | No behavioral change |
| Additive | 3 assets | New content is safer than modifications |
| Modification | 2 assets | Changed behavior needs verification |
| Structural | 1 asset + its direct dependents | Focused change, verifiable blast radius |
| Systemic | 1 asset only, with migration plan for dependents | Maximum caution for maximum impact |

**Budget exceeded?** → Decompose into a **multi-session migration plan**:
1. List all changes needed
2. Order by dependency (modify leaves first, foundations last)
3. Define per-session scope (respecting budget)
4. Define verification checkpoints between sessions

### Phase 4: Interface Contract Protection

High-centrality assets have two surfaces:

| Surface | Definition | Protection Level |
|---------|-----------|-----------------|
| **Interface** | How callers invoke the asset and what they receive back | Frozen — changes require dependent migration |
| **Internals** | How the asset accomplishes its work | Free — optimize without restriction |

**Interface elements (frozen by default):**
- Caller/invocation protocol (parameters, expected input format)
- Output contract (response structure, field names, semantics)
- Asset identity (name, file path, extension)
- Capability scope (what the asset can/cannot do)

**Internal elements (free to modify):**
- Methodology phases and steps
- Decision heuristics and thresholds
- Examples and anti-patterns
- Performance optimizations

**Interface change protocol**: When an interface change is necessary:
1. Compute impact score (interface change = Structural magnitude, 0.9)
2. If score > 6.0 → multi-session migration required
3. If score 3.1–6.0 → decompose: create new interface alongside old, migrate dependents one by one, remove old
4. If score < 3.0 → update interface and all dependents atomically in one session

### Phase 5: Deprecation-First Protocol

Never remove, rename, or fundamentally restructure a T2+ asset in one step.

**Five-step deprecation sequence:**

| Step | Action | Verification |
|------|--------|-------------|
| 1. **MARK** | Add deprecation notice + successor reference to the old asset | Old asset still functional |
| 2. **BRIDGE** | Create successor alongside deprecated asset | Both old and new work |
| 3. **MIGRATE** | Update dependents one at a time (respecting change budget) | Each migrated dependent passes its quality gates |
| 4. **VERIFY** | All dependents now reference successor, zero references to deprecated asset | Search confirms zero remaining references |
| 5. **REMOVE** | Delete deprecated asset | Clean asset graph, no orphaned references |

**Never skip to REMOVE** — even if "it's obviously safe." The sequence exists to catch assumptions that are wrong.

### Phase 6: Coherence Validation

After any T2+ change, verify system-wide coherence:

1. **Dependent health** — Each direct dependent of the modified asset still passes its own quality gates
2. **Interface satisfaction** — All callers still conform to the (potentially updated) interface contract
3. **Reference integrity** — No orphaned references (skill refs pointing to renamed assets, subagent invocations targeting removed assets)
4. **Catalog consistency** — Asset registry accurately reflects current state

**Coherence check scope scales with tier:**

| Tier | Coherence Check Scope |
|------|----------------------|
| T1 | Skip (no dependents to check) |
| T2 | Direct dependents only |
| T3 | Direct dependents + spot-check indirect dependents |
| T4 | Full stack scan |

---

## Ecosystem Alignment

### Reference Anchors

Agentic design stacks are built on vendor platforms and community patterns. These are the canonical truth sources for directional alignment:

| Pillar | What to Monitor | Drift Signal |
|--------|----------------|--------------|
| **LLM vendor** (model provider) | Agent patterns docs, model capabilities, ACI principles | Stack patterns contradict vendor's documented best practices |
| **IDE platform** (runtime host) | Agent API, tool schema, YAML frontmatter spec, deployment modes | Stack uses deprecated features or ignores new capabilities |
| **Skill standard** (portability layer) | Standard spec updates, community adoption patterns | Skills drift from portability standard |
| **Community** (practitioner ecosystem) | Postmortems, pattern catalogs, conference talks, open-source agent repos | Stack invents solutions for problems the community has already solved better |

### Periodic Review Triggers

| Event | Review Scope | Priority |
|-------|-------------|----------|
| New model release | Model assignments across all agents, capability changes | HIGH |
| Platform agent API update | Tool aliases, YAML schema, deployment mode changes | HIGH |
| Skill standard revision | Skill structure, portability compliance | MEDIUM |
| Community postmortem surfaces failure mode | Check if stack has the same vulnerability | MEDIUM |
| Quarterly (no events) | General alignment scan — are we drifting? | LOW |

### Alignment Assessment Protocol

When a review trigger fires:

1. **Identify the signal** — What changed in the ecosystem?
2. **Assess relevance** — Does this change affect our stack's domain?
3. **Map impact** — Which assets would need modification to align?
4. **Apply change protocol** — Use Phase 2-5 of this skill (the change is vendor-aligned, so gets 0.7 multiplier)
5. **Document** — Record the ecosystem event and stack response (or explicit decision not to respond)

---

## Change Record Template

For T2+ changes, document the decision:

```
CHANGE: {what was modified}
ASSET:  {asset name} (Tier {N})
BASE:   {dependents} × {magnitude} = {base impact}
DIR:    {direction} ({multiplier}) — {source citation or "internal"}
EFF:    {effective impact}
GATE:   {proceed | document | decompose | halt}
SCOPE:  {what dependents were checked/updated}
```

---

## Anti-Patterns

- ❌ **Big-bang refactor** — Modifying 5+ assets simultaneously because "they're all related." Decompose into sessions respecting change budget. Each session should be independently verifiable.
- ❌ **Importance-based tiers** — Classifying by perceived importance instead of dependency count. A "minor" utility skill referenced by 9 agents is T4, not T1.
- ❌ **Silent interface changes** — Modifying an output contract or caller protocol without updating dependents. Interface changes require migration.
- ❌ **Ecosystem ignorance** — Making significant changes without checking if the vendor/community has guidance on the topic. Internal inventions are fine but should be conscious, not accidental.
- ❌ **Cosmetic creep** — Starting with a "cosmetic fix" and gradually expanding scope to modifications. Re-classify if scope grows beyond original magnitude.
- ❌ **Deprecation skip** — Removing an asset and "fixing dependents later." The deprecation sequence exists to prevent broken references.
- ❌ **Direction inflating** — Claiming vendor alignment without citing a specific source. No source = Neutral (1.0), never assumed alignment.
- ❌ **Stability theater** — Running the protocol but ignoring its recommendations. If the score says "halt," halt.
- ✅ **Incremental evolution** — Small, verified, directionally-aligned changes that accumulate into significant improvement without destabilizing the system.

---

## Quick Reference

```
CLASSIFY: Count dependents → T1 (0-1) | T2 (2-4) | T3 (5-7) | T4 (8+)
   │
   ▼
ANALYZE: Impact = dependents × magnitude × direction_multiplier
   │
   ├── < 1.0  → Proceed normally
   ├── 1-3    → Document, proceed carefully
   ├── 3.1-6  → Decompose into smaller changes
   └── > 6.0  → HALT, present impact map, get approval
   │
   ▼
BUDGET: Cosmetic=∞ | Additive≤3 | Modify≤2 | Structural≤1+deps | Systemic≤1
   │
   ▼
PROTECT: Interface frozen, internals free
   │
   ▼
DEPRECATE: Mark → Bridge → Migrate → Verify → Remove (never skip steps)
   │
   ▼
VERIFY: Dependent health + interface satisfaction + reference integrity
```

## End of file — no trailing content
