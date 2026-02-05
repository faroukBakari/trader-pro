---
name: model-selection
description: FinOps-aware model selection guidance with benchmark-backed recommendations. Use when choosing between Opus, Sonnet, Haiku, or comparing Claude to GPT/Gemini for agents and prompts.
---

# Model Selection Guide

Apply this knowledge when selecting models for agents, prompts, or API integrations. Recommendations are based on GitHub Copilot premium request multipliers and independent benchmarks (Artificial Analysis, Aider leaderboards).

---

## Cost Multipliers (GitHub Copilot Premium Requests)

| Model | Multiplier | Relative Cost |
|-------|------------|---------------|
| Claude Haiku 4.5 | 0.33x | Budget-friendly |
| Claude Sonnet 4.5 | 1.0x | Baseline |
| Claude Opus 4.5 | 3.0x | Premium |
| GPT-5.x (heavy thinking) | 8.0x | Very expensive |

**Key insight**: Haiku costs 1/3 of Sonnet. Opus costs 3x Sonnet. Choose the cheapest model that succeeds reliably.

---

## Independent Benchmark Summary

| Model | Intelligence Index | Code Editing (Aider) | Speed (t/s) |
|-------|-------------------|----------------------|-------------|
| Claude Opus 4.5 | 50 | — | 92 |
| Claude Sonnet 4.5 | 43 | 84.2% (tied #1 with o1) | 71 |
| Gemini 3 Flash | 46 | — | 199 |
| GPT-5.2 | 51 | — | — |

**Key finding**: Sonnet 4.5 matches o1 on code editing benchmarks (84.2%) while costing 1/3 of Opus.

---

## Decision Framework

### Match Model to Task Complexity

| Task Type | Recommended Model | Reasoning |
|-----------|-------------------|-----------|
| **File reading, grep, simple search** | Haiku 4.5 | Routine tool use; 0.33x cost justified |
| **Code editing, focused implementation** | Sonnet 4.5 | Matches top-tier benchmarks |
| **Multi-step orchestration, planning** | Opus 4.5 | Complex reasoning worth 3x premium |
| **Deep research with synthesis** | Sonnet 4.5 | Intelligence gap (14%) rarely matters |

### Agent Type → Model Mapping

| Agent Pattern | Model | Cost | Justification |
|---------------|-------|------|---------------|
| **Research/read-only** | Haiku 4.5 | 0.33x | No creative reasoning needed |
| **Implementation** | Sonnet 4.5 | 1.0x | Code editing is core strength |
| **Review/test** | Sonnet 4.5 | 1.0x | Analysis doesn't need Opus overhead |
| **Orchestrator (multi-agent)** | Opus 4.5 | 3.0x | Coordination complexity justifies cost |
| **Complex planning** | Opus 4.5 | 3.0x | Multi-step reasoning is Opus strength |

---

## When to Use Opus (3x Cost)

Reserve Opus for tasks where the 14% intelligence gap matters:

| ✅ Use Opus | ❌ Don't Need Opus |
|-------------|-------------------|
| Orchestrating 3+ sub-agents | Single-agent code editing |
| Novel architectural decisions | Following established patterns |
| Ambiguous, underspecified problems | Clear, well-scoped tasks |
| Long-horizon multi-step planning | Short, focused operations |

**Heuristic**: If you can describe the task in <50 words with clear inputs/outputs, Sonnet suffices.

---

## When to Use Haiku (0.33x Cost)

Haiku excels at routine operations:

| ✅ Use Haiku | When It Fails |
|--------------|---------------|
| CLI tool invocation | Creative code generation |
| File reading and summarization | Complex refactoring |
| Search result synthesis | Architectural decisions |
| Repetitive data transformation | Novel problem solving |

**Practitioner evidence**: "Using the CLI lowers the bar so cheap, fast models can reliably succeed." — Jeremy Daer, 37signals

---

## Cross-Vendor Comparison

When comparing across providers (useful for tool selection):

| Need | Best Option | Notes |
|------|-------------|-------|
| **Fastest response** | Gemini 3 Flash (199 t/s) | Good for interactive use |
| **Best code editing** | Claude Sonnet 4.5 / o1 (tied) | Aider benchmark leaders |
| **Cheapest per token** | DeepSeek V3.2 ($0.30/MTok) | 20x cheaper than Sonnet |
| **Highest intelligence** | GPT-5.2 (51) / Opus 4.5 (50) | Near-equivalent at top |

---

## Quick Reference

| Question | Answer |
|----------|--------|
| Default for most agents? | **Sonnet 4.5** |
| Read-only research? | **Haiku 4.5** (0.33x) |
| Orchestrators/planners? | **Opus 4.5** (3x) |
| When unsure? | Start with Sonnet, upgrade if it struggles |
| FinOps rule | Use cheapest model that succeeds reliably |
