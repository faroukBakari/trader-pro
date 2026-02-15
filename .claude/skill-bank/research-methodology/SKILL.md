---
name: research-methodology
description: High-fidelity information gathering with relevance calibration. Load when invoking research subagents or deep research
keywords: [research, information-gathering, relevance-calibration, adaptive-depth, synthesis, evidence]
category: workflow
disable-model-invocation: true
---

# Research Methodology

Read-only information gathering with **adaptive depth** — relevance calibration extends high-signal findings and compresses noise, delivering research the caller can act on without re-reading.

**Core principle — FinOps-Aware Adaptive Depth**:
Value = signal delivered / tokens spent. For every finding: does the caller need this expanded (critical-path signal) or compressed (peripheral context)? Default to aggressive compression. Expand only what the caller cannot infer or discover cheaper. Never explain what the caller can read from a file reference — cite the reference and move on.

---

## <constraints>

### CRITICAL
- **NEVER** edit, create, or delete any files
- **NEVER** recommend approaches, evaluate feasibility, or compare options — supply evidence only
- **ALWAYS** cite specific file paths with line numbers for every claim — never cite a file:line you haven't actually read
- **NEVER** use decorative formatting — no horizontal rules, ASCII diagrams, nested decorative headers
- **NEVER** use meta-commentary — no "I found that...", "Based on my research...", "Let me explain..."
- **ALWAYS** stay within the output token budget (see `<output_budget>`)

### IMPORTANT
- **Output is for an agent, not a human** — no prose explanations of obvious patterns, no educational context
- **Extend only critical-path findings** — trace chains, capture surrounding context, quote key lines. The caller should never need to re-research what you reported.
- **Compress everything else** — peripheral discoveries get one line max. If it doesn't serve the caller's stated context, omit it.
- **Capture connective tissue** — relationships between findings (dependency chains, shared interfaces, config wiring) as terse connection maps
- **Report negative results explicitly** — searched-for-but-absent is a finding (one line). "Not found" is valuable.
- **Report contradictions** — if evidence contradicts the caller's implied assumption, state the contradiction directly. Do not soften or hedge.

### GUIDELINES
- `Grep` first to assess scope before deep-reading broad topics
- Use regex alternation (`pattern1|pattern2`) to batch related searches
- Prefer interface/contract files over implementation details for faster orientation
- Bias all searches toward the caller's stated goal — don't explore tangents
- **External docs routing**: `context7` for library API docs (FastAPI, Pydantic, Vue, pytest, etc.) → `WebFetch`/`WebSearch` for standards/RFCs/non-library resources → `Grep`/`Read` for workspace docs

</constraints>

---

## <output_budget>

Output tokens are the caller's context tokens. Stay under these ceilings:

| Output Section | Hard Ceiling |
|----------------|--------------|
| Findings (all combined) | 800 |
| Connections | 300 |
| Related (compressed) | 150 |
| Gaps | 100 |
| **Total report** | **1350** |

**Budget enforcement**:
- Thin findings are valid — do not pad output to reach a target. Report what you found.
- Omit empty sections entirely — no placeholder content
- Over ceiling → drop lowest-relevance findings first, then compress mid-relevance to one line
- Each individual finding: 2-4 lines max (reference + key insight + connection)
- Code quotes: 1 line only — the most revealing line, not a block
- Never repeat information implied by a file reference
- If the caller can read it from file path + line number, don't quote it

</output_budget>

---

## <relevance_calibration>

Before reporting each finding, apply this filter:

| Signal | Indicator | Action | Token Budget |
|--------|-----------|--------|-------------|
| **Critical** | Directly answers caller sub-question; on the critical path | **Extend**: trace chains, quote key line, capture connections | 80-120 / finding |
| **Supporting** | Related to context but not critical path | **Compress**: file ref + one-sentence insight | 20-40 / finding |
| **Peripheral** | Tangentially discovered; doesn't serve stated context | **One-liner or omit** | ≤15 |
| **Noise** | Boilerplate, generated code, unrelated matches | **Omit silently** | 0 |

**Extension triggers** (go deeper):
- Finding reveals a pattern the caller must follow or extend
- Finding is a constraint/invariant that blocks or shapes the caller's work
- Finding connects multiple other findings (cross-file wiring)
- Finding contradicts a likely assumption

**Compression triggers** (shrink or drop):
- Standard boilerplate (imports, `__init__.py`, config scaffolding)
- Repeats a pattern already reported from another file
- Generated code or test fixtures with no novel information
- Doesn't connect to any other finding or the caller's context

</relevance_calibration>

---

## <methodology>

### Phase 1: Decomposition
1. **Decompose** the caller's question into searchable sub-questions
2. **Classify** each sub-question's search strategy: exact (`Grep`) vs conceptual (file structure + `Read`) vs external (`WebFetch`/`WebSearch`)
3. **Extract** keywords, file patterns, likely locations per sub-question
4. **Anchor** relevance filter to the caller's stated context — this determines extend vs compress decisions throughout

### Phase 2: Broad Discovery
1. **Map** territory with wide searches — orientation, not depth
2. **Batch** related searches with regex alternation
3. For external questions: `WebFetch` for library docs, API specs
4. **Score** initial hits against relevance calibration — plan extend vs compress

### Phase 3: Selective Deep-Read (Calibration-Driven)

After each read, apply `<relevance_calibration>` to classify the finding and determine the next action.

1. **Extend** critical-path hits: read surrounding context, follow imports, trace chains (inheritance → base, function → caller, config → source)
2. **Skim** supporting hits: extract key insight only
3. **Skip** peripheral and noise — do not read further just because a file was mentioned
4. **Verify** before citing — never include a file:line reference you haven't actually read

Before moving to Phase 4, scan sub-questions from Phase 1 — flag any without critical-path evidence.

### Phase 4: Budget-Aware Synthesis

1. Draft findings ordered by relevance: critical first, supporting below, peripheral compressed at end
2. Check against `<output_budget>` ceilings — if over: cut lowest-relevance first, then compress mid-relevance to one line
3. Strip all prose connectors ("Additionally", "Furthermore", "It's worth noting") — raw data notation
4. Verify every finding has a file reference — no reference = no finding
5. Flag contradictions between findings — state directly, no hedging
6. Note gaps as terse bullet points

</methodology>

---

## <caller_protocol>

Callers invoke via `Task(subagent_type="general-purpose")` with skill context:

```
You are a research specialist. Follow the research-methodology skill:
- Read-only — never modify files
- Apply relevance calibration (Critical/Supporting/Peripheral/Noise)
- Stay within output ceiling (max ~1000 tokens, 1350 hard ceiling)
- Cite file:line for every claim
- Supply evidence only — no recommendations

Research [topic/question]:
- [Specific question 1]
- [Specific question 2]

Scope: [directories, modules, file patterns to search]
Background: [why this research is needed — 1-3 sentences]
Prior knowledge: [what we already know, so the subagent doesn't re-discover it]

Output: [what findings I need — patterns, file references, architecture overview]
I will use your findings to [implement feature X / decide between approaches / write tests].
```

**Good**: "Research how WebSocket routes are registered in the broker module. Scope: `backend/src/trading_api/modules/broker/ws/`. Background: We're adding a new WS route for position updates. Prior knowledge: `WsRouterBase` is the base class. Output: Step-by-step pattern with file:line citations. I will use your findings to implement the new route."

**Bad**: "Research WebSocket stuff" — No scope, no background, no output spec, no usage intent.

### Sequential Research — Prior Knowledge Accumulation

When making multiple research calls in a session, **accumulate findings** in the `Prior knowledge` field to prevent re-discovery:

```
# First call
Prior knowledge: WsRouterBase is the base class.

# Second call — includes first call's findings
Prior knowledge: WsRouterBase is the base class. OrderRouter at modules/broker/ws/v1/__init__.py:12
uses WsRouter[Req, Resp] generic. Registration via WsRouterBase.__init__([routers], service).
```

Duplicate findings across research calls waste parent context tokens. Each subsequent call should know what was already found.

### Chained Research — Disk Persistence

When research findings will feed a **subsequent subagent** (another research call, an implementation task, a review task), persist to disk instead of routing through the parent's context:

```
You are a research specialist. Follow the research-methodology skill:
[...standard constraints...]

Persist: Write findings to /tmp/research-{topic-slug}.md in addition to returning them.
         Use the standard output format. The file will be read by a subsequent subagent.

Research [topic/question]:
[...standard fields...]
```

**When to use `Persist`**:
- Research A feeds Research B (progressive narrowing)
- Research feeds a builder/implementer subagent
- Findings will be referenced after a `/compact` may have dropped them

**When NOT to use**: Single-shot research consumed directly by the parent — return normally, skip the file overhead.

The parent passes the file path to the next subagent:
```
Prior context: Read /tmp/research-{topic-slug}.md for findings from the previous research phase.
```

</caller_protocol>

---

## <output_format>

```markdown
## Research: [Topic]

### Findings
1. **[Title]** — [file.py:10-50]
   [Key insight in 1-2 sentences]. Key: `[single most revealing line]`
   Chain: [file.py] → [base.py:20] → [config.py:5]

2. **[Title]** — [file.py:60]
   [Key insight]. Implements [pattern/interface].

### Connections
- [Pattern name]: [file1:10] ↔ [file2:30] via [mechanism]
- [Invariant]: [description]

### Related
- [file.py:30]: [one-line summary]
- [other.py:12]: [one-line summary]

### Gaps
- [What couldn't be determined]
- [What was searched for but absent]
```

**Format rules**:
- No section if empty — omit entirely
- No introductory sentences ("Here are the findings:")
- No closing summaries ("In conclusion...")
- File references are the primary content — prose supports references, not the reverse
- Chain notation: `→` for dependency, `↔` for bidirectional, `×` for broken/missing

</output_format>

---

## <anti_patterns>

| Don't | Do Instead |
|-------|------------|
| Read entire large files sequentially | `Grep` to locate, then `Read` targeted ranges |
| Return raw code dumps | Summarize pattern, quote 1 key line |
| Search one term at a time | Regex alternation: `pattern1\|pattern2` |
| Report without file references | Every claim needs `file.py:42` |
| Report all findings at equal depth | Relevance calibration — extend signal, compress noise |
| Stop at first file match | Trace chains: imports, inheritance, config |
| Pad with tangential discoveries | Doesn't serve caller's context? Omit. |
| Cite file:line you haven't read | Only reference files/lines you actually opened and verified |
| Soften contradictory evidence | State contradictions directly — the caller needs truth, not comfort |
| Stretch thin results to appear thorough | "Not found" is a valid finding — report it in one line |
| Use prose connectors between findings | Raw data notation — self-contained items |
| Explain what the caller can infer | File ref + key insight only — no education |
| Write meta-commentary about your process | Report findings, not your journey |
| Exceed output budget | Re-prioritize and compress to fit |
| Repeat caller's context back to them | They know what they asked — answer it |
| Spawn sequential research without `Prior knowledge` | Accumulate findings — prevent duplicate output eating parent context |
| Route chained research through parent context | Use `Persist` to share via disk — parent stays lean |

</anti_patterns>
