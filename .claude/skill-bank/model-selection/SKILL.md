---
name: model-selection
description: FinOps-aware model selection for Claude Haiku 4.5, Sonnet 4.5, and Opus 4.6 with verified benchmarks
keywords: [model-selection, finops, benchmarks, opus, sonnet, haiku, pricing, context-window]
category: reasoning
disable-model-invocation: true
last-updated: 2026-02-12
data-sources: [anthropic.com/news, anthropic.com/pricing, artificialanalysis.ai, llm-stats.com]
---

# Model Selection Guide — Claude 4.x Family

FinOps-aware guidance for selecting between Haiku 4.5, Sonnet 4.5, and Opus 4.6.
All benchmarks from official Anthropic publications and verified third-party sources.

> **Last verified**: 2026-02-12. If >90 days old, re-verify pricing and benchmarks before relying on this data.

---

## Model Specs

| Attribute | Haiku 4.5 | Sonnet 4.5 | Opus 4.6 |
|-----------|-----------|------------|----------|
| **Model ID** | `claude-haiku-4-5-20251001` | `claude-sonnet-4-5-20250929` | `claude-opus-4-6` |
| **Released** | 2025-10-15 | 2025-09-29 | 2026-02-05 |
| **Context window** | 200K | 200K (1M beta) | 200K (1M beta) |
| **Max output** | 64K tokens | 64K tokens | 128K tokens |
| **Extended thinking** | Yes | Yes | Yes + adaptive effort controls |
| **Computer use** | Yes | Yes | Yes |
| **Context compaction** | No | No | Yes (beta) |

---

## Pricing (per 1M tokens, standard <=200K context)

| Tier | Haiku 4.5 | Sonnet 4.5 | Opus 4.6 |
|------|-----------|------------|----------|
| **Input** | $1.00 | $3.00 | $5.00 |
| **Output** | $5.00 | $15.00 | $25.00 |
| **Cache write** | $1.25 | $3.75 | $6.25 |
| **Cache read** | $0.10 | $0.30 | $0.50 |
| **Batch input** | $0.50 | $1.50 | $2.50 |
| **Batch output** | $2.50 | $7.50 | $12.50 |

**Cost ratios**: Haiku = 0.33x Sonnet. Opus = 1.67x Sonnet (input) / 1.67x (output).

> For >200K context: Sonnet $6/$22.50, Opus $10/$37.50 per 1M tokens.

---

## Verified Benchmarks

### Coding & Agentic

| Benchmark | Haiku 4.5 | Sonnet 4.5 | Opus 4.6 | What it measures |
|-----------|-----------|------------|----------|------------------|
| **SWE-bench Verified** | 73.3% | 77.2% | 80.8% | Real GitHub bug fixes (500 issues) |
| **Terminal-Bench 2.0** | 41.0% | 50.0% | **65.0%** | Command-line agentic coding (SOTA) |
| **tau2-Bench (Retail)** | — | 86.2% | **91.9%** | Multi-step tool use |
| **tau2-Bench (Telecom)** | — | 98.0% | **99.3%** | Multi-step tool use |
| **MCP Atlas** | — | 43.8% | **67.3%** | Multi-tool orchestration via MCP |
| **OSWorld** | 50.7% | 61.4% | **~66%+** | Desktop/computer use automation |

### Reasoning & Knowledge

| Benchmark | Haiku 4.5 | Sonnet 4.5 | Opus 4.6 | What it measures |
|-----------|-----------|------------|----------|------------------|
| **GPQA Diamond** | 73.0% | 83.4% | **91.3%** | PhD-level science Q&A |
| **MMMLU** | 83.0% | 89.1% | **91.1%** | Broad academic knowledge |
| **AIME 2025** | 80.7% | 87.0% | **93%+** | Competition math |
| **ARC-AGI-2** | — | 13.6% | **68.8%** | Abstract reasoning |
| **Humanity's Last Exam** | — | ~20% | **53.1%** | Expert-level questions (with tools) |

### Long-Context (1M window)

| Benchmark | Sonnet 4.5 | Opus 4.6 | Notes |
|-----------|------------|----------|-------|
| **MRCR v2 (8-needle, 1M)** | 18.5% | **76.0%** | Qualitative shift in context utilization |
| **MRCR v2 (256K)** | — | **93.0%** | Near-perfect at 256K |

---

## Decision Framework

### Task → Model Mapping

| Task Type | Model | Why |
|-----------|-------|-----|
| File reading, grep, simple search | **Haiku** | Routine tool use; 0.33x cost |
| Code editing, focused implementation | **Sonnet** | 77% SWE-bench at 1x cost; sweet spot |
| Single-file refactoring | **Sonnet** | Code editing is its core strength |
| Multi-step orchestration, planning | **Opus** | 65% Terminal-Bench, 67% MCP Atlas |
| Deep research with synthesis | **Sonnet** | Intelligence gap rarely matters for research |
| Long-context analysis (>200K) | **Opus** | 76% vs 18.5% at 1M context — no contest |
| Novel architectural decisions | **Opus** | 91.3% GPQA, abstract reasoning dominance |
| Repetitive data transformation | **Haiku** | Cost efficiency on bulk operations |

### Agent Pattern → Model Mapping

| Agent Pattern | Model | Justification |
|---------------|-------|---------------|
| **Read-only / exploration** | Haiku | No creative reasoning needed |
| **Implementation (single-file)** | Sonnet | Best cost/performance for code edits |
| **Implementation (multi-file)** | Sonnet | Builder pattern with Sonnet works well |
| **Review / analysis** | Sonnet | Analysis doesn't need Opus overhead |
| **Orchestrator (multi-agent)** | Opus | Coordination complexity justifies cost |
| **Complex planning** | Opus | Multi-step reasoning is Opus strength |
| **Doc updates** | Sonnet | Structured writing, doesn't need Opus |

---

## When to Upgrade from Sonnet → Opus

Reserve Opus for tasks where the performance gap is **material** (not marginal):

| Upgrade Signal | Gap Size | Verdict |
|----------------|----------|---------|
| SWE-bench (77→81%) | +4pt | Marginal — stay on Sonnet |
| Terminal-Bench (50→65%) | +15pt | **Upgrade** — agentic coding |
| GPQA (83→91%) | +8pt | **Upgrade** — complex reasoning |
| MCP Atlas (44→67%) | +23pt | **Upgrade** — multi-tool orchestration |
| Long-context 1M (18→76%) | +58pt | **Always upgrade** — Sonnet can't do this |
| ARC-AGI-2 (14→69%) | +55pt | **Always upgrade** — abstract reasoning |

**Heuristic**: If the task is well-scoped and describable in <50 words with clear inputs/outputs → Sonnet. If ambiguous, multi-step, or requires 200K+ context → Opus.

---

## When to Downgrade from Sonnet → Haiku

Haiku at 0.33x cost is viable when the task doesn't need creative reasoning:

| Haiku Succeeds | Haiku Struggles |
|----------------|-----------------|
| CLI tool invocation | Creative code generation |
| File reading / summarization | Complex refactoring |
| Search + filter operations | Architectural decisions |
| Repetitive transformations | Novel problem solving |
| Sub-agent workers in parallel | Long-horizon autonomous tasks |

**Key data**: Haiku's 73.3% SWE-bench is within 4 points of Sonnet at 1/3 the price. For parallelized sub-agents doing bounded tasks, Haiku is the FinOps winner.

---

## Overthinking Tax

Anthropic's own research shows thinking **can hurt** on simple tasks:
- Up to **36% degradation** when overthinking simple/intuitive problems
- Opus `max` effort used **58M output tokens** on one benchmark run

**Rule**: Match effort to complexity. Don't default to Opus + max thinking for everything.

| Task Complexity | Model + Effort |
|-----------------|----------------|
| Trivial (grep, read) | Haiku, low effort |
| Moderate (edit, implement) | Sonnet, high effort |
| Complex (plan, orchestrate) | Opus, high effort |
| Frontier (novel reasoning) | Opus, max effort |

---

## Quick Reference

| Question | Answer |
|----------|--------|
| Default for most work? | **Sonnet 4.5** |
| Read-only / bulk ops? | **Haiku 4.5** (0.33x) |
| Orchestrators / planners? | **Opus 4.6** |
| Long-context (>200K)? | **Opus 4.6** (mandatory) |
| When unsure? | Start Sonnet, upgrade if it struggles |
| FinOps rule | Use the cheapest model that succeeds reliably |
