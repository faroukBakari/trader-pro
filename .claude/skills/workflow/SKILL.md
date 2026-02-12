---
name: workflow
description: Category glossary for workflow. Contains 12 skills: `claude-history-traces`, `command-execution`, `context-persistenc...
keywords: [adaptive-depth, analytics, auto-approve, batch, batching, blockers, clarification, command, commands, context-sharing, convergence, daemon, decision-making, delegation, deviation, diagnostics, docker, drift, environment, escalation, evidence, execution, extensions, filesystem, gpu, guards, history, ide, information-gathering, interactive, investigation, large-data, mcp, move, multi-invocation, non-destructive, parallel, persistence, platform, readonly, recovery, refactoring, relevance-calibration, rename, research, routing, runtime, runtime-efficiency, safety-checks, scope-change, sessions, subagent, synthesis, terminal, timeout, token-efficiency, tooling, tools, traces, user-input, vscode, workspace, wsl]
auto-generated: true
---

# Workflow

Load any skill below: `Read .claude/skill-bank/{skill-name}/SKILL.md`

## Skills

| Skill | Description |
|-------|-------------|
| `claude-history-traces` | Session history search, file recovery, and trace analytics. Load when recovering files or searching past conversations |
| `command-execution` | Guarded terminal execution with pre-flight validation and timeouts. Load when delegating commands to Bash subagents |
| `context-persistence` | Filesystem-based context sharing across subagent invocations. Load when coordinating multi-step subagent workflows |
| `drift-guard` | Mid-flight deviation detection and response protocol. Load when encountering blockers or scope changes during work |
| `mode-interactive` | Structured decision-making for open-ended requests. Load when facing vague instructions or multiple viable approaches |
| `mode-readonly` | Non-destructive investigation constraints. Load when analyzing, debugging, reviewing, or performing RCA without edits |
| `research-methodology` | High-fidelity information gathering with relevance calibration. Load when invoking research subagents or deep research |
| `runtime-awareness` | Full runtime environment inventory — platform, tools, services, paths. Load when checking tooling or capabilities |
| `runtime-efficiency` | Runtime volume handling, convergence gates, and operation batching. Load when processing big files, diffs, bulk results, or long investigations |
| `terminal-usage` | Terminal command safety checks and delegation routing. Load when running shell commands or delegating execution |
| `vscode-integration` | VS Code IDE runtime tool selection and usage patterns. Load when using VS Code sub-tools or IDE integration features |
| `vscode-mcp-routing` | VS Code MCP tool routing and diagnostics-driven edit loops. Load when choosing between native and MCP workspace tools |

## Keyword Index

| Keyword | Skills |
|---------|--------|
| adaptive-depth | `research-methodology` |
| analytics | `claude-history-traces` |
| auto-approve | `command-execution` |
| batch | `command-execution` |
| batching | `runtime-efficiency` |
| blockers | `drift-guard` |
| clarification | `mode-interactive` |
| command | `command-execution` |
| commands | `terminal-usage` |
| context-sharing | `context-persistence` |
| convergence | `runtime-efficiency` |
| daemon | `command-execution` |
| decision-making | `mode-interactive` |
| delegation | `runtime-efficiency`, `terminal-usage` |
| deviation | `drift-guard` |
| diagnostics | `mode-readonly`, `vscode-mcp-routing` |
| docker | `runtime-awareness` |
| drift | `drift-guard` |
| environment | `runtime-awareness` |
| escalation | `drift-guard` |
| evidence | `research-methodology` |
| execution | `command-execution`, `terminal-usage` |
| extensions | `vscode-integration` |
| filesystem | `context-persistence` |
| gpu | `runtime-awareness` |
| guards | `command-execution` |
| history | `claude-history-traces` |
| ide | `vscode-integration` |
| information-gathering | `research-methodology` |
| interactive | `mode-interactive` |
| investigation | `mode-readonly` |
| large-data | `runtime-efficiency` |
| mcp | `vscode-mcp-routing` |
| move | `vscode-mcp-routing` |
| multi-invocation | `context-persistence` |
| non-destructive | `mode-readonly` |
| parallel | `command-execution` |
| persistence | `context-persistence` |
| platform | `runtime-awareness` |
| readonly | `mode-readonly` |
| recovery | `claude-history-traces` |
| refactoring | `vscode-mcp-routing` |
| relevance-calibration | `research-methodology` |
| rename | `vscode-mcp-routing` |
| research | `research-methodology` |
| routing | `vscode-mcp-routing` |
| runtime | `runtime-awareness` |
| runtime-efficiency | `runtime-efficiency` |
| safety-checks | `terminal-usage` |
| scope-change | `drift-guard` |
| sessions | `claude-history-traces` |
| subagent | `context-persistence` |
| synthesis | `research-methodology` |
| terminal | `command-execution`, `terminal-usage` |
| timeout | `command-execution` |
| token-efficiency | `runtime-efficiency` |
| tooling | `runtime-awareness` |
| tools | `vscode-integration` |
| traces | `claude-history-traces` |
| user-input | `mode-interactive` |
| vscode | `vscode-integration`, `vscode-mcp-routing` |
| workspace | `vscode-integration` |
| wsl | `runtime-awareness` |
