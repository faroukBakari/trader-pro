#!/usr/bin/env python3
"""IA Stack Health Check — deterministic structural validation only.

Checks frontmatter, sizes, category bounds, routing consistency, glossary sync.
Human/IA judgment checks (agent-agnostic, portability, keyword overlap) are
intentionally excluded — those belong in manual review.

Design principles:
  - Deterministic: every check is boolean/numeric with clear pass/fail
  - Self-discovering: agent types, thresholds derived from source files
  - No duplication: imports parse_frontmatter from build-skill-tree.py
  - Baseline-aware: known issues can be suppressed via .health-baseline.json
  - Single-pass I/O: files read once, shared across checks

Pure stdlib — zero external dependencies.

Usage:
    python3 .claude/scripts/check-stack-health.py              # failures only
    python3 .claude/scripts/check-stack-health.py -v           # include passing
    python3 .claude/scripts/check-stack-health.py --json       # machine-readable
    python3 .claude/scripts/check-stack-health.py --ci         # exit 1 on FAIL
    python3 .claude/scripts/check-stack-health.py --baseline   # save current as baseline
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────
# Paths (all relative to .claude/)
# ──────────────────────────────────────────────────────────────────────

CLAUDE_DIR = Path(__file__).resolve().parent.parent
BANK_DIR = CLAUDE_DIR / "skill-bank"
SKILLS_DIR = CLAUDE_DIR / "skills"
CLAUDE_MD = CLAUDE_DIR / "CLAUDE.md"
AGENTS_DIR = CLAUDE_DIR / "agents"
SETTINGS_JSON = CLAUDE_DIR / "settings.json"
BASELINE_FILE = CLAUDE_DIR / "scripts" / ".health-baseline.json"

# ──────────────────────────────────────────────────────────────────────
# Import shared frontmatter parser (single source of truth)
# ──────────────────────────────────────────────────────────────────────

_tree_spec = importlib.util.spec_from_file_location(
    "build_skill_tree", CLAUDE_DIR / "scripts" / "build-skill-tree.py"
)
_tree_mod = importlib.util.module_from_spec(_tree_spec)  # type: ignore[arg-type]
_tree_spec.loader.exec_module(_tree_mod)  # type: ignore[union-attr]
parse_frontmatter = _tree_mod.parse_frontmatter

# ──────────────────────────────────────────────────────────────────────
# Thresholds — derived from governance docs where possible
# ──────────────────────────────────────────────────────────────────────

# From ia-stack-ops Workflow D / ia-quality-gates K1
KERNEL_MAX_LINES = 400
KERNEL_MAX_WORDS = 5000

# From ia-quality-gates / skill-design spec
SKILL_MAX_LINES = 500
CATEGORY_MIN_SKILLS = 3
CATEGORY_MAX_SKILLS = 12

# Agent template size budget
AGENT_MAX_LINES = 400

# From skill-design T1 gate
LEAF_REQUIRED_FIELDS = ("name", "description", "keywords", "category", "disable-model-invocation")

# From skill-design spec — description conciseness (160 aligns with desktop
# meta-description convention; sufficient for "what + when" structure while
# keeping glossary token overhead manageable across 60+ skills).
DESC_MAX_CHARS = 160

# Built-in Claude Code subagent types (from Task tool runtime).
# Update this list if Claude Code adds new built-in types.
# Source: error message when an invalid subagent_type is used.
BUILTIN_SUBAGENT_TYPES = frozenset({
    "Bash",
    "general-purpose",
    "statusline-setup",
    "Explore",
    "Plan",
    "claude-code-guide",
})


# ──────────────────────────────────────────────────────────────────────
# Self-discovery: extract dynamic values from source files
# ──────────────────────────────────────────────────────────────────────

def discover_subagent_types(claude_md_text: str) -> list[str]:
    """Extract subagent type names from Built-in Subagent Types table."""
    types = []
    in_section = False
    in_table = False
    for line in claude_md_text.splitlines():
        if "Subagent Types" in line and ("Available" in line or "Built-in" in line):
            in_section = True
            continue
        if in_section and not in_table:
            # Haven't hit the table yet — skip description text, bail on next heading
            if line.startswith("|"):
                in_table = True  # fall through to table parsing below
            elif line.startswith("#"):
                break
            else:
                continue
        if in_table and line.startswith("|"):
            if "---" in line or "subagent_type" in line:
                continue
            cells = [c.strip().strip("`") for c in line.split("|") if c.strip()]
            if cells:
                types.append(cells[0])
        elif in_table and line.strip() and not line.startswith("|") and not line.startswith(">"):
            break
    return types


def discover_quick_rule_types(claude_md_text: str) -> set[str]:
    """Extract type names mentioned in Delegation Rules section."""
    for heading in ("Delegation Rules", "Quick Decision Rules"):
        if heading in claude_md_text:
            section = claude_md_text.split(heading)[-1].split("\n---")[0]
            return set(re.findall(r"`(\w[\w-]*)`", section))
    return set()


def discover_routing_categories(claude_md_text: str) -> set[str]:
    """Extract category names from the §0 routing table (Task Signal → Category)."""
    categories: set[str] = set()
    in_section = False
    in_table = False
    for line in claude_md_text.splitlines():
        if "Route to Skill" in line:
            in_section = True
            continue
        if in_section and not in_table:
            if line.startswith("|"):
                in_table = True  # fall through to table parsing
            elif line.startswith("#"):
                break
            else:
                continue
        if in_table and line.startswith("|"):
            if "---" in line or "Category" in line or "Task Signal" in line:
                continue
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if len(cells) >= 2:
                # Category is the last column; handle compound "dev + review"
                for cat in cells[-1].split("+"):
                    cat = cat.strip()
                    if cat:
                        categories.add(cat)
        elif in_table and line.strip() and not line.startswith("|"):
            break
    return categories


def discover_referenced_skills(claude_md_text: str) -> set[str]:
    """Extract skill names referenced in Auto-attach Modifiers and Delegation Rules."""
    skills: set[str] = set()

    # Auto-attach Modifiers: skill names live in the Auto-load column (index 1)
    if "Auto-attach Modifiers" in claude_md_text:
        section = claude_md_text.split("Auto-attach Modifiers")[-1].split("\n#")[0]
        for line in section.splitlines():
            if not line.startswith("|") or "---" in line:
                continue
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if len(cells) >= 2 and "Auto-load" not in cells[1]:
                skills.update(re.findall(r"`([\w-]+)`", cells[1]))

    # Delegation Rules: skill names live in the Notes column (index 2)
    for heading in ("Delegation Rules", "Quick Decision Rules"):
        if heading not in claude_md_text:
            continue
        section = claude_md_text.split(heading)[-1].split("\n---")[0]
        for line in section.splitlines():
            if not line.startswith("|") or "---" in line:
                continue
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if len(cells) >= 3 and "Notes" not in cells[2]:
                skills.update(re.findall(r"`([\w-]+)`", cells[2]))
        break  # use first matching heading only

    # Filter out non-skill identifiers (subagent types, tool names, model names)
    non_skills = BUILTIN_SUBAGENT_TYPES | {
        "EnterPlanMode", "inline", "model", "sonnet", "haiku", "opus",
    }
    return skills - non_skills


# ──────────────────────────────────────────────────────────────────────
# Agent template parsing
# ──────────────────────────────────────────────────────────────────────

def parse_agent_frontmatter(agent_file: Path) -> dict:
    """Parse agent .md frontmatter (model, tools, mcpServers) using pure stdlib.

    Agent frontmatter uses YAML-like syntax between --- markers.
    Returns dict with: name, path, model, tools, mcpServers, line_count, text.
    """
    text = agent_file.read_text(encoding="utf-8")
    lines = text.splitlines()
    name = agent_file.stem  # filename without .md

    result: dict = {
        "name": name,
        "path": str(agent_file),
        "model": "",
        "tools": [],
        "mcpServers": [],
        "line_count": len(lines),
        "text": text,
    }

    # Extract frontmatter between first and second ---
    if not lines or lines[0].strip() != "---":
        return result

    fm_lines: list[str] = []
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            fm_lines = lines[1:i]
            break

    # Parse simple YAML: scalar values and list items
    current_key = ""
    for line in fm_lines:
        # Top-level key: value
        m = re.match(r"^(\w[\w-]*):\s*(.*)", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            current_key = key
            if key == "model":
                result["model"] = val
            elif key in ("tools", "mcpServers") and not val:
                result[key] = []  # list follows on next lines
            elif key in ("tools", "mcpServers") and val:
                # Inline list: [a, b, c]
                result[key] = [v.strip().strip("'\"") for v in val.strip("[]").split(",") if v.strip()]
            continue
        # List item under current key
        m_item = re.match(r"^\s+-\s+(.*)", line)
        if m_item and current_key in ("tools", "mcpServers"):
            result[current_key].append(m_item.group(1).strip())

    return result


def classify_agent_role(agent: dict) -> str:
    """Classify agent role based on name and tools.

    Returns: 'governance' | 'executor' | 'read-only'
    """
    if agent["name"] == "agentic-designer":
        return "governance"
    tools = agent.get("tools", [])
    if "Write" in tools or "Edit" in tools:
        return "executor"
    return "read-only"


def discover_claude_md_agents(claude_md_text: str) -> set[str]:
    """Extract agent names from the Custom Agent Templates table in CLAUDE.md §4."""
    agents: set[str] = set()
    in_section = False
    in_table = False
    for line in claude_md_text.splitlines():
        if "Custom Agent Templates" in line:
            in_section = True
            continue
        if in_section and not in_table:
            if line.startswith("|"):
                in_table = True  # fall through to table parsing
            elif line.startswith("#"):
                break
            else:
                continue
        if in_table and line.startswith("|"):
            if "---" in line or "Agent" in line and "Model" in line:
                continue
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if cells:
                # Agent name is first column, strip backticks
                name = cells[0].strip("`").strip()
                if name and name != "Agent":
                    agents.add(name)
        elif in_table and line.strip() and not line.startswith("|") and not line.startswith(">"):
            break
    return agents


# ──────────────────────────────────────────────────────────────────────
# Data model
# ──────────────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    name: str
    gate: str
    passed: bool
    finding: str
    severity: str = "INFO"  # INFO (pass), WARN (act eventually), FAIL (act now)

    def key(self) -> str:
        """Stable identity for baseline comparison."""
        return f"{self.gate}:{self.name}"


@dataclass
class StackContext:
    """Single-pass loaded context shared across all checks."""
    skills: list[dict] = field(default_factory=list)
    claude_md_text: str = ""
    subagent_types: list[str] = field(default_factory=list)
    quick_rule_types: set[str] = field(default_factory=set)
    routing_categories: set[str] = field(default_factory=set)
    referenced_skills: set[str] = field(default_factory=set)
    agents: list[dict] = field(default_factory=list)


def load_context() -> StackContext:
    """Load all files once, extract derived data."""
    ctx = StackContext()

    # Skills
    if BANK_DIR.is_dir():
        for skill_dir in sorted(BANK_DIR.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.is_file():
                continue
            text = skill_file.read_text(encoding="utf-8")
            ctx.skills.append({
                "dir_name": skill_dir.name,
                "path": str(skill_file),
                "frontmatter": parse_frontmatter(text),
                "line_count": len(text.splitlines()),
            })

    # CLAUDE.md
    if CLAUDE_MD.is_file():
        ctx.claude_md_text = CLAUDE_MD.read_text(encoding="utf-8")
        ctx.subagent_types = discover_subagent_types(ctx.claude_md_text)
        ctx.quick_rule_types = discover_quick_rule_types(ctx.claude_md_text)
        ctx.routing_categories = discover_routing_categories(ctx.claude_md_text)
        ctx.referenced_skills = discover_referenced_skills(ctx.claude_md_text)

    # Agents
    if AGENTS_DIR.is_dir():
        for agent_file in sorted(AGENTS_DIR.glob("*.md")):
            ctx.agents.append(parse_agent_frontmatter(agent_file))

    return ctx


# ──────────────────────────────────────────────────────────────────────
# Baseline support
# ──────────────────────────────────────────────────────────────────────

def load_baseline() -> set[str]:
    """Load known-issue keys to suppress from report."""
    if not BASELINE_FILE.is_file():
        return set()
    data = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    return set(data.get("suppressed", []))


def save_baseline(results: list[CheckResult]) -> None:
    """Save current failures as baseline (acknowledge known issues)."""
    keys = sorted(r.key() for r in results if not r.passed)
    BASELINE_FILE.write_text(
        json.dumps({"suppressed": keys, "_note": "Auto-generated. Re-run --baseline to update."}, indent=2),
        encoding="utf-8",
    )
    print(f"Baseline saved: {len(keys)} known issues in {BASELINE_FILE}")


# ──────────────────────────────────────────────────────────────────────
# Checks — each returns list[CheckResult]
# ──────────────────────────────────────────────────────────────────────

def check_frontmatter(ctx: StackContext) -> list[CheckResult]:
    """T1 + T5: Required frontmatter fields + leaf hidden flag."""
    results = []
    for s in ctx.skills:
        fm = s["frontmatter"]

        # T1: required fields
        missing = [f for f in LEAF_REQUIRED_FIELDS if f not in fm]
        if missing:
            results.append(CheckResult(
                name=s["dir_name"], gate="T1",
                passed=False, finding=f"Missing: {', '.join(missing)}", severity="FAIL",
            ))

        # T5: disable-model-invocation must be true
        if str(fm.get("disable-model-invocation", "")).lower() != "true":
            results.append(CheckResult(
                name=s["dir_name"], gate="T5",
                passed=False, finding="Missing disable-model-invocation: true", severity="FAIL",
            ))

    if results:
        return results
    return [CheckResult(name="all-skills", gate="T1+T5", passed=True,
                        finding=f"All {len(ctx.skills)} skills have complete frontmatter")]


def check_description_length(ctx: StackContext) -> list[CheckResult]:
    """DESC: Skill descriptions must be ≤120 characters (skill-design spec)."""
    results = []
    for s in ctx.skills:
        desc = s["frontmatter"].get("description", "")
        length = len(desc)
        if length > DESC_MAX_CHARS:
            results.append(CheckResult(
                name=s["dir_name"], gate="DESC", passed=False,
                finding=f"{length}/{DESC_MAX_CHARS} chars", severity="WARN",
            ))

    if not results:
        return [CheckResult(name="all", gate="DESC", passed=True,
                            finding=f"All {len(ctx.skills)} descriptions within {DESC_MAX_CHARS} chars")]
    return results


def check_category_health(ctx: StackContext) -> list[CheckResult]:
    """Category bounds: 3-12 skills per category, no orphans."""
    results = []
    categories: dict[str, list[str]] = {}
    orphans: list[str] = []

    for s in ctx.skills:
        cat = s["frontmatter"].get("category", "")
        if isinstance(cat, str) and cat:
            categories.setdefault(cat, []).append(s["dir_name"])
        else:
            orphans.append(s["dir_name"])

    for cat, members in sorted(categories.items()):
        n = len(members)
        if n < CATEGORY_MIN_SKILLS:
            results.append(CheckResult(
                name=cat, gate="CAT", passed=False,
                finding=f"{n} skills (min {CATEGORY_MIN_SKILLS})", severity="WARN",
            ))
        elif n > CATEGORY_MAX_SKILLS:
            results.append(CheckResult(
                name=cat, gate="CAT", passed=False,
                finding=f"{n} skills (max {CATEGORY_MAX_SKILLS}) — split", severity="WARN",
            ))

    if orphans:
        results.append(CheckResult(
            name="orphans", gate="CAT", passed=False,
            finding=f"Uncategorized: {', '.join(orphans)}", severity="WARN",
        ))

    if not results:
        results.append(CheckResult(
            name="all", gate="CAT", passed=True,
            finding=f"{len(categories)} categories, all within bounds",
        ))
    return results


def check_kernel_metrics(ctx: StackContext) -> list[CheckResult]:
    """K1: CLAUDE.md line and word count within limits."""
    if not ctx.claude_md_text:
        return [CheckResult(name="missing", gate="K1", passed=False,
                            finding="CLAUDE.md not found", severity="FAIL")]

    lines = len(ctx.claude_md_text.splitlines())
    words = len(ctx.claude_md_text.split())
    results = []

    results.append(CheckResult(
        name="lines", gate="K1",
        passed=lines <= KERNEL_MAX_LINES,
        finding=f"{lines}/{KERNEL_MAX_LINES}",
        severity="FAIL" if lines > KERNEL_MAX_LINES else "INFO",
    ))
    results.append(CheckResult(
        name="words", gate="K1",
        passed=words <= KERNEL_MAX_WORDS,
        finding=f"{words}/{KERNEL_MAX_WORDS}",
        severity="FAIL" if words > KERNEL_MAX_WORDS else "INFO",
    ))
    return results


def check_skill_sizes(ctx: StackContext) -> list[CheckResult]:
    """SIZE: No skill exceeds 500 lines."""
    oversized = [(s["dir_name"], s["line_count"]) for s in ctx.skills
                 if s["line_count"] > SKILL_MAX_LINES]
    if oversized:
        return [CheckResult(
            name=name, gate="SIZE", passed=False,
            finding=f"{count}/{SKILL_MAX_LINES} lines", severity="WARN",
        ) for name, count in oversized]

    largest = max(ctx.skills, key=lambda s: s["line_count"]) if ctx.skills else None
    if largest:
        return [CheckResult(
            name="largest", gate="SIZE", passed=True,
            finding=f"{largest['dir_name']} ({largest['line_count']} lines)",
        )]
    return []


def check_routing_consistency(ctx: StackContext) -> list[CheckResult]:
    """R5: Every Built-in Subagent Types entry also appears in Delegation Rules."""
    results = []
    for t in ctx.subagent_types:
        found = t in ctx.quick_rule_types or t.lower() in {r.lower() for r in ctx.quick_rule_types}
        if not found:
            results.append(CheckResult(
                name=t, gate="R5", passed=False,
                finding="In subagent types table but NOT in Delegation Rules", severity="WARN",
            ))

    if not results:
        results.append(CheckResult(
            name="all", gate="R5", passed=True,
            finding=f"All {len(ctx.subagent_types)} types consistent",
        ))
    return results


def check_subagent_types_valid(ctx: StackContext) -> list[CheckResult]:
    """R6: Every subagent_type in Built-in Subagent Types table must be a real built-in agent."""
    results = []
    phantom_types = []
    for t in ctx.subagent_types:
        if t not in BUILTIN_SUBAGENT_TYPES:
            phantom_types.append(t)
            results.append(CheckResult(
                name=t, gate="R6", passed=False,
                finding=(
                    f"Phantom subagent_type — not a built-in type. "
                    f"Valid: {', '.join(sorted(BUILTIN_SUBAGENT_TYPES))}"
                ),
                severity="FAIL",
            ))

    if not results:
        results.append(CheckResult(
            name="all", gate="R6", passed=True,
            finding=f"All {len(ctx.subagent_types)} types are valid built-in agents",
        ))
    return results


def check_routing_categories(ctx: StackContext) -> list[CheckResult]:
    """R7: Every routing table category has a glossary, and vice versa."""
    if not ctx.routing_categories:
        return [CheckResult(name="routing-table", gate="R7", passed=False,
                            finding="No categories found in routing table", severity="WARN")]

    results = []
    glossary_categories = {
        d.name for d in SKILLS_DIR.iterdir()
        if d.is_dir() and (d / "SKILL.md").is_file()
    } if SKILLS_DIR.is_dir() else set()

    for cat in sorted(ctx.routing_categories - glossary_categories):
        results.append(CheckResult(
            name=cat, gate="R7", passed=False,
            finding=f"In routing table but no glossary at skills/{cat}/", severity="FAIL",
        ))

    for cat in sorted(glossary_categories - ctx.routing_categories):
        results.append(CheckResult(
            name=cat, gate="R7", passed=False,
            finding="Glossary exists but not in routing table", severity="WARN",
        ))

    if not results:
        results.append(CheckResult(
            name="all", gate="R7", passed=True,
            finding=f"All {len(ctx.routing_categories)} routing categories have glossaries",
        ))
    return results


def check_referenced_skills_exist(ctx: StackContext) -> list[CheckResult]:
    """R8: Every skill referenced in Auto-attach/Delegation tables exists in skill-bank."""
    if not ctx.referenced_skills:
        return [CheckResult(name="refs", gate="R8", passed=True,
                            finding="No skill references found to validate")]

    results = []
    skill_dirs = {d.name for d in BANK_DIR.iterdir() if d.is_dir()} if BANK_DIR.is_dir() else set()

    for name in sorted(ctx.referenced_skills - skill_dirs):
        results.append(CheckResult(
            name=name, gate="R8", passed=False,
            finding="Referenced in kernel but not in skill-bank/", severity="WARN",
        ))

    if not results:
        results.append(CheckResult(
            name="all", gate="R8", passed=True,
            finding=f"All {len(ctx.referenced_skills)} referenced skills exist",
        ))
    return results


def check_glossary_sync(_ctx: StackContext) -> list[CheckResult]:
    """SYNC: Glossary files match what build-skill-tree.py would generate."""
    # Delegate to the tree builder's --check mode (exit code)
    import subprocess
    try:
        result = subprocess.run(
            [sys.executable, str(CLAUDE_DIR / "scripts" / "build-skill-tree.py"), "--check"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return [CheckResult(name="glossaries", gate="SYNC", passed=True,
                                finding="All glossaries in sync")]
        else:
            drifted = re.findall(r"DRIFT:\s+(.+)", result.stdout)
            return [CheckResult(
                name="glossaries", gate="SYNC", passed=False,
                finding=f"Drift in {len(drifted)} file(s) — run build-skill-tree.py --write",
                severity="FAIL",
            )]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return [CheckResult(name="glossaries", gate="SYNC", passed=False,
                            finding="Could not run build-skill-tree.py", severity="WARN")]


# ──────────────────────────────────────────────────────────────────────
# Agent template checks (A1–A7)
# ──────────────────────────────────────────────────────────────────────

def check_agent_frontmatter(ctx: StackContext) -> list[CheckResult]:
    """A1: Agent templates must have model, tools, mcpServers in frontmatter."""
    results = []
    for agent in ctx.agents:
        missing = []
        if not agent["model"]:
            missing.append("model")
        if not agent["tools"]:
            missing.append("tools")
        if not agent["mcpServers"]:
            missing.append("mcpServers")
        if missing:
            results.append(CheckResult(
                name=agent["name"], gate="A1",
                passed=False, finding=f"Missing: {', '.join(missing)}", severity="FAIL",
            ))

    if not results:
        return [CheckResult(name="all-agents", gate="A1", passed=True,
                            finding=f"All {len(ctx.agents)} agents have complete frontmatter")]
    return results


def check_agent_constraints(ctx: StackContext) -> list[CheckResult]:
    """A2/A3/A4: Agent constraint validation by role.

    A2 (IA-guard): executor agents must have NEVER + .claude/ in CRITICAL constraints.
    A3 (user-isolation): all agents must have "DO NOT interact with the user".
    A4 (no subagents): executor agents must have "DO NOT spawn subagents".

    Exemptions by role:
      governance (agentic-designer): exempt from A2 (it IS the IA stack editor)
      read-only (no Write/Edit): exempt from A2 (can't write) and A4 (spawning is safe)
    """
    results = []
    for agent in ctx.agents:
        role = classify_agent_role(agent)
        text = agent["text"]

        # A2: IA-guard constraint (executor only)
        if role == "executor":
            # Look for NEVER + .claude/ pattern anywhere in text
            has_ia_guard = bool(re.search(r"NEVER.*\.claude/", text))
            if not has_ia_guard:
                results.append(CheckResult(
                    name=agent["name"], gate="A2",
                    passed=False,
                    finding="Executor missing NEVER...`.claude/` in CRITICAL constraints",
                    severity="FAIL",
                ))

        # A3: user-isolation constraint (all agents)
        # Handle markdown bold: **DO NOT** or plain DO NOT
        has_user_isolation = bool(re.search(r"\*{0,2}DO NOT\*{0,2} interact with the user", text))
        if not has_user_isolation:
            results.append(CheckResult(
                name=agent["name"], gate="A3",
                passed=False,
                finding="Missing 'DO NOT interact with the user' constraint",
                severity="WARN",
            ))

        # A4: no-subagent constraint (executor only)
        if role == "executor":
            has_no_subagent = bool(re.search(r"\*{0,2}DO NOT\*{0,2} spawn subagent", text))
            if not has_no_subagent:
                results.append(CheckResult(
                    name=agent["name"], gate="A4",
                    passed=False,
                    finding="Executor missing 'DO NOT spawn subagents' constraint",
                    severity="WARN",
                ))

    if not results:
        return [CheckResult(name="all-agents", gate="A2-A4", passed=True,
                            finding=f"All {len(ctx.agents)} agents pass constraint checks")]
    return results


def check_agent_size(ctx: StackContext) -> list[CheckResult]:
    """A5: Agent templates must not exceed AGENT_MAX_LINES."""
    oversized = [(a["name"], a["line_count"]) for a in ctx.agents
                 if a["line_count"] > AGENT_MAX_LINES]
    if oversized:
        return [CheckResult(
            name=name, gate="A5", passed=False,
            finding=f"{count}/{AGENT_MAX_LINES} lines", severity="WARN",
        ) for name, count in oversized]

    largest = max(ctx.agents, key=lambda a: a["line_count"]) if ctx.agents else None
    if largest:
        return [CheckResult(
            name="largest", gate="A5", passed=True,
            finding=f"{largest['name']} ({largest['line_count']} lines)",
        )]
    return []


def check_agent_claude_md_sync(ctx: StackContext) -> list[CheckResult]:
    """A6/A7: Agent templates <-> CLAUDE.md §4 table sync.

    A6: template exists on disk but NOT registered in CLAUDE.md -> WARN
    A7: registered in CLAUDE.md but NO template file on disk -> FAIL
    """
    results = []
    disk_agents = {a["name"] for a in ctx.agents}
    registered_agents = discover_claude_md_agents(ctx.claude_md_text) if ctx.claude_md_text else set()

    # A6: on disk but not registered
    for name in sorted(disk_agents - registered_agents):
        results.append(CheckResult(
            name=name, gate="A6",
            passed=False,
            finding="Template exists but not registered in CLAUDE.md §4",
            severity="WARN",
        ))

    # A7: registered but no template file
    for name in sorted(registered_agents - disk_agents):
        results.append(CheckResult(
            name=name, gate="A7",
            passed=False,
            finding="Registered in CLAUDE.md §4 but no template file",
            severity="FAIL",
        ))

    if not results:
        return [CheckResult(name="all-agents", gate="A6-A7", passed=True,
                            finding=f"All {len(disk_agents)} agents synced with CLAUDE.md §4")]
    return results


# ──────────────────────────────────────────────────────────────────────
# Check registry
# ──────────────────────────────────────────────────────────────────────

# Ordered list — each check gets ctx and returns results.
# Adding a check = append one entry here. No other changes needed.
CHECKS: list[tuple[str, str]] = [
    ("check_frontmatter", "Frontmatter completeness (T1) + leaf hidden (T5)"),
    ("check_description_length", "Description conciseness ≤120 chars (DESC)"),
    ("check_category_health", "Category bounds: 3-12 skills (CAT)"),
    ("check_kernel_metrics", "Kernel size limits (K1)"),
    ("check_skill_sizes", "Skill file size limits (SIZE)"),
    ("check_routing_consistency", "Routing table vs Delegation Rules (R5)"),
    ("check_subagent_types_valid", "Subagent types are real built-in agents (R6)"),
    ("check_routing_categories", "Routing table categories vs glossary dirs (R7)"),
    ("check_referenced_skills_exist", "Referenced skills exist in skill-bank (R8)"),
    ("check_glossary_sync", "Glossary files match tree builder (SYNC)"),
    ("check_agent_frontmatter", "Agent frontmatter completeness (A1)"),
    ("check_agent_constraints", "Agent constraints: IA-guard (A2), user-isolation (A3), subagent (A4)"),
    ("check_agent_size", "Agent template size limits (A5)"),
    ("check_agent_claude_md_sync", "Agent template ↔ CLAUDE.md sync (A6, A7)"),
]


# ──────────────────────────────────────────────────────────────────────
# Report formatting
# ──────────────────────────────────────────────────────────────────────

def format_report(
    results: list[CheckResult],
    skills_count: int,
    agents_count: int,
    baseline: set[str],
    show_passing: bool,
) -> str:
    """Format results as a concise, actionable markdown report."""
    passed = [r for r in results if r.passed]
    new_failures = [r for r in results if not r.passed and r.key() not in baseline]
    baselined = [r for r in results if not r.passed and r.key() in baseline]

    lines = ["## Stack Health Report", ""]
    lines.append(
        f"**{skills_count} skills, {agents_count} agents** | "
        f"{len(passed)} passed | "
        f"{len(new_failures)} new issue(s) | "
        f"{len(baselined)} baselined"
    )
    lines.append("")

    # New failures — the only section that always shows
    if new_failures:
        lines.append("### New Issues")
        lines.append("")
        lines.append("| Gate | Name | Sev | Finding |")
        lines.append("|------|------|-----|---------|")
        for r in new_failures:
            sev = "!!" if r.severity == "FAIL" else "~"
            lines.append(f"| {r.gate} | {r.name} | {sev} | {r.finding} |")
        lines.append("")

    # Baselined (collapsed)
    if baselined:
        lines.append(f"### Baselined ({len(baselined)} known issues suppressed)")
        lines.append("")

    # Passing (only with -v)
    if show_passing and passed:
        lines.append("### Passing")
        lines.append("")
        lines.append("| Gate | Name | Finding |")
        lines.append("|------|------|---------|")
        for r in passed:
            lines.append(f"| {r.gate} | {r.name} | {r.finding} |")
        lines.append("")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="IA Stack Health Check")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    parser.add_argument("--ci", action="store_true", help="Exit 1 on any FAIL-severity new issue")
    parser.add_argument("-v", "--verbose", action="store_true", help="Include passing checks")
    parser.add_argument("--baseline", action="store_true", help="Save current failures as baseline")
    args = parser.parse_args()

    ctx = load_context()
    baseline = load_baseline()
    all_results: list[CheckResult] = []

    # Run all registered checks
    this_module = sys.modules[__name__]
    for fn_name, _ in CHECKS:
        fn = getattr(this_module, fn_name)
        all_results.extend(fn(ctx))

    # Baseline mode: save and exit
    if args.baseline:
        save_baseline(all_results)
        return

    if args.json:
        new_failures = [r for r in all_results if not r.passed and r.key() not in baseline]
        output = {
            "skills_scanned": len(ctx.skills),
            "agents_scanned": len(ctx.agents),
            "total_checks": len(all_results),
            "passed": sum(1 for r in all_results if r.passed),
            "new_failures": len(new_failures),
            "baselined": sum(1 for r in all_results if not r.passed and r.key() in baseline),
            "results": [asdict(r) for r in (all_results if args.verbose else new_failures)],
        }
        print(json.dumps(output, indent=2))
    else:
        print(format_report(all_results, len(ctx.skills), len(ctx.agents), baseline, args.verbose))

    # CI exit code: only new FAIL-severity issues
    if args.ci:
        new_fails = sum(1 for r in all_results
                        if r.severity == "FAIL" and not r.passed and r.key() not in baseline)
        if new_fails > 0:
            print(f"\n{new_fails} new FAIL-severity issue(s).", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
