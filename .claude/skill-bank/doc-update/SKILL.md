---
name: doc-update
description: Documentation update planning and gap analysis. Load when updating docs after code changes or auditing doc accuracy
keywords: [documentation, update-planning, gap-analysis, accuracy]
category: review
disable-model-invocation: true
---

# Documentation Update Planning

Generate comprehensive, self-sufficient documentation update plans without making edits.

## Scope

Applies when:
- Code changes require documentation updates
- Auditing existing docs for accuracy
- Planning a documentation refresh
- Mapping implementation changes to doc hierarchy

## Critical Constraints

CRITICAL:

- DO NOT create, edit, or delete any files — planning only
- NEVER paste full source files in the plan
- ALWAYS read referenced files before planning updates

IMPORTANT:

- Use absolute paths for all file references
- Exclude `**/tmp/**/*.md` files (out of scope)
- Include rationale for every proposed change
- Cross-reference related docs (implementation → sub-system → root)

## Documentation Hierarchy

Plans address three levels:

| Level | Scope | Examples |
|-------|-------|----------|
| **Implementation** | Module-specific | `modules/*/README.md`, inline docs |
| **Sub-system** | Integration/architecture | `docs/TWS.md`, `docs/REDIS.md` |
| **Root** | Project-wide | `docs/ARCHITECTURE.md`, guides |

Use `docs/DOCUMENTATION-GUIDE.md` as the documentation map when available.

## Workflow Phases

### Phase 1: Context Analysis

1. Read ALL user-provided reference files (implementation, specs, architecture)
2. Use git commands to discover change scope if commits/branches referenced
3. Extract key details: function signatures, class names, endpoints, patterns
4. Filter noise — identify only documentation-relevant changes

### Phase 2: Documentation Mapping

1. Explore existing documentation structure
2. Map identified changes to specific documentation files
3. Determine: updates to existing docs vs. new docs needed
4. Build file list organized by hierarchy level

### Phase 3: Gap Analysis

For each identified doc file:

1. Read current content
2. Cross-reference against code changes
3. Identify: gaps, outdated content, inconsistencies
4. Note specific sections requiring updates

### Phase 4: Plan Generation

For each update, capture:

| Field | Content |
|-------|---------|
| **File path** | Absolute path |
| **Section** | Target heading/section |
| **Current** | Summary of existing content |
| **Changes** | Required updates with formatting guidance |
| **Source** | File references for execution context |
| **Rationale** | Why change reflects implementation |

## Output Format

```markdown
## Documentation Update Plan

**Summary:** [One-sentence description of changes]

---

### Phase 1: Implementation-Level Updates

#### [/absolute/path/to/module/README.md]
| Field | Content |
|-------|---------|
| **Section** | "Section Name" |
| **Current** | Summary of existing content... |
| **Changes** | Summary of updates with formatting. Reference: `path/to/source.py` |
| **Rationale** | Why this change reflects implementation |

---

### Phase 2: Sub-System Updates

#### [/absolute/path/to/docs/SUBSYSTEM.md]
| Field | Content |
|-------|---------|
| **Section** | "Architecture Overview" |
| **Current** | Existing description... |
| **Changes** | Updated content with diagram instructions. See: `path/to/file.py` |
| **Rationale** | Reflects new integration pattern |

---

### Phase 3: Root-Level Updates

#### [/absolute/path/to/docs/GUIDE.md]
| Field | Content |
|-------|---------|
| **Section** | "Cross-Cutting Pattern" _(new)_ |
| **Current** | — |
| **Changes** | New section covering [topic]. Reference: `docs/ARCHITECTURE.md` |
| **Rationale** | Documents new project-wide pattern |

---

## Execution Notes
Apply updates in phase order. Each "Changes" field requires reading referenced source files.
```

## Quality Checklist

Before finalizing, verify:

- [ ] All user-provided files were read and analyzed
- [ ] Every doc file in the plan was read (current state captured)
- [ ] Absolute paths used for all file references
- [ ] Each update has: section, current state, changes, rationale
- [ ] Source file references included for execution context
- [ ] No `**/tmp/**` files included
- [ ] Changes organized: implementation → sub-system → root

## Guidelines

- Consider UML diagrams when architecture changes
- When possible, quote existing content with surrounding context
- Use relative links for internal doc references within the plan content
