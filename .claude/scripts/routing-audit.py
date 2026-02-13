#!/usr/bin/env python3
"""Post-session routing compliance audit.

Reads Claude Code JSONL transcripts and measures skill routing compliance
per user turn. A turn is "compliant" if at least one .claude/skills/ or
.claude/skill-bank/ file was Read before the first substantive tool call
(Edit, Write, Bash, Task, or VS Code MCP write tools).

Usage:
    python3 routing-audit.py <session_id_or_jsonl_path>
    python3 routing-audit.py --dir <projects_dir> --session <session_id>
"""

import json
import sys
import os
import glob
import argparse
from dataclasses import dataclass, field

# Tools that count as "substantive" (non-routing actions)
SUBSTANTIVE_TOOLS = {
    "Edit", "Write", "Bash", "Task", "NotebookEdit",
    "mcp__vscode-mcp-server__create_file_code",
    "mcp__vscode-mcp-server__replace_lines_code",
}

SKILL_PATH_PATTERN = ".claude/skills/"
SKILL_BANK_PATH_PATTERN = ".claude/skill-bank/"

# Slash commands that skip routing
SLASH_COMMAND_PREFIX = "/"


@dataclass
class TurnResult:
    """Result of compliance analysis for a single user turn."""
    turn_number: int
    user_message: str
    category_match: str = ""
    skill_loaded: bool = False
    skill_files_read: list = field(default_factory=list)
    first_substantive_tool: str = ""
    verdict: str = "UNKNOWN"
    is_slash_command: bool = False
    tool_calls_before_substantive: list = field(default_factory=list)


def _get_inner_message(entry: dict) -> dict:
    """Unwrap the JSONL envelope to get the inner message dict.

    Claude Code JSONL format: {type, message: {role, content, ...}, ...}
    """
    return entry.get("message", entry)


def extract_user_message(entry: dict) -> str | None:
    """Extract user message text from a JSONL entry."""
    msg = _get_inner_message(entry)
    # Claude Code format: message.role == "user"
    if msg.get("role") == "user" or entry.get("type") == "human":
        content = msg.get("content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    return block.get("text", "").strip()
    return None


def extract_tool_use(entry: dict) -> list[dict]:
    """Extract tool use blocks from an assistant message."""
    tools = []
    msg = _get_inner_message(entry)
    if msg.get("role") != "assistant" and entry.get("type") != "assistant":
        return tools
    content = msg.get("content", [])
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tools.append({
                    "name": block.get("name", ""),
                    "input": block.get("input", {}),
                })
    return tools


def is_skill_read(tool: dict) -> bool:
    """Check if a tool call is a Read of a skill file."""
    if tool["name"] != "Read":
        return False
    fpath = tool.get("input", {}).get("file_path", "")
    return SKILL_PATH_PATTERN in fpath or SKILL_BANK_PATH_PATTERN in fpath


def guess_category(user_msg: str) -> str:
    """Best-effort category guess based on keywords."""
    msg = user_msg.lower()
    category_signals = {
        "development": ["implement", "modify", "build", "debug", "diagnose", "fix", "websocket", "provider", "type error"],
        "review": ["review", "audit", "quality", "documentation", "retrospective"],
        "testing": ["test", "coverage", "verification"],
        "frontend": ["vue", "typescript", "ui", "ux", "a11y", "component", "css"],
        "workflow": ["research", "explain", "compare", "config", "runtime", "mcp", "session history"],
        "ia-design": ["ia stack", "skill", "agent", "glossary"],
        "prompting": ["prompt", "model-specific", "tuning"],
        "reasoning": ["reasoning", "calibration", "model selection", "effort"],
        "tradingview": ["tradingview", "charting", "chart"],
    }
    for category, signals in category_signals.items():
        for signal in signals:
            if signal in msg:
                return category
    return "(no match)"


def analyze_session(messages: list[dict]) -> list[TurnResult]:
    """Analyze a list of JSONL messages for routing compliance."""
    results = []
    turn_number = 0
    current_turn_tools: list[dict] = []
    current_user_msg = None
    in_turn = False

    for msg in messages:
        user_text = extract_user_message(msg)
        if user_text is not None:
            # Process previous turn if exists
            if in_turn and current_user_msg is not None:
                result = analyze_turn(turn_number, current_user_msg, current_turn_tools)
                results.append(result)

            # Start new turn
            turn_number += 1
            current_user_msg = user_text
            current_turn_tools = []
            in_turn = True
            continue

        # Collect tool uses from assistant messages
        if in_turn:
            tools = extract_tool_use(msg)
            current_turn_tools.extend(tools)

    # Process final turn
    if in_turn and current_user_msg is not None:
        result = analyze_turn(turn_number, current_user_msg, current_turn_tools)
        results.append(result)

    return results


def analyze_turn(turn_number: int, user_msg: str, tools: list[dict]) -> TurnResult:
    """Analyze a single turn for routing compliance."""
    result = TurnResult(
        turn_number=turn_number,
        user_message=user_msg[:80] + ("..." if len(user_msg) > 80 else ""),
    )

    # Slash command check
    if user_msg.startswith(SLASH_COMMAND_PREFIX):
        result.is_slash_command = True
        result.verdict = "SLASH_CMD"
        return result

    # Internal system messages (XML-tagged) — not real user turns
    if user_msg.startswith("<"):
        result.verdict = "SYSTEM"
        return result

    result.category_match = guess_category(user_msg)

    # Walk tools in order, looking for skill reads before first substantive call
    skill_reads = []
    for tool in tools:
        if is_skill_read(tool):
            fpath = tool.get("input", {}).get("file_path", "")
            skill_reads.append(fpath)

        if tool["name"] in SUBSTANTIVE_TOOLS:
            result.first_substantive_tool = tool["name"]
            result.skill_files_read = skill_reads
            result.skill_loaded = len(skill_reads) > 0
            result.verdict = "COMPLIANT" if result.skill_loaded else "SKIP"
            return result

        result.tool_calls_before_substantive.append(tool["name"])

    # No substantive tools called — informational turn
    result.skill_files_read = skill_reads
    result.skill_loaded = len(skill_reads) > 0
    result.verdict = "NO_ACTION"
    return result


def find_session_file(session_id: str, projects_dir: str | None = None) -> str | None:
    """Find a JSONL file for a given session ID."""
    if projects_dir:
        search_dir = projects_dir
    else:
        home = os.path.expanduser("~")
        search_dir = os.path.join(home, ".claude", "projects")

    pattern = os.path.join(search_dir, "**", f"{session_id}*.jsonl")
    matches = glob.glob(pattern, recursive=True)
    return matches[0] if matches else None


def print_report(results: list[TurnResult]) -> None:
    """Print a formatted compliance report."""
    compliant = 0
    skipped = 0
    no_action = 0
    slash_cmd = 0
    system_msg = 0
    total_actionable = 0

    for r in results:
        # Suppress internal system messages from output
        if r.verdict == "SYSTEM":
            system_msg += 1
            continue

        print(f"\nTurn {r.turn_number}: \"{r.user_message}\"")

        if r.is_slash_command:
            print("  Type: slash command (skipped)")
            slash_cmd += 1
            continue

        if r.verdict == "NO_ACTION":
            print(f"  Category match: {r.category_match}")
            print("  No substantive tools called (informational turn)")
            no_action += 1
            continue

        total_actionable += 1
        print(f"  Category match: {r.category_match}")

        if r.skill_loaded:
            for sf in r.skill_files_read:
                print(f"  Skill loaded: \u2705 ({os.path.basename(sf)})")
            compliant += 1
        else:
            print(f"  Skill loaded: \u274c (0 skill reads before first {r.first_substantive_tool})")
            skipped += 1

        print(f"  Verdict: {r.verdict}")

    print("\n" + "=" * 60)
    print(f"Summary: {compliant}/{total_actionable} actionable turns compliant", end="")
    if total_actionable > 0:
        pct = (compliant / total_actionable) * 100
        print(f" ({pct:.0f}%)")
    else:
        print(" (no actionable turns)")

    print(f"  Compliant: {compliant}")
    print(f"  Skipped:   {skipped}")
    print(f"  No action: {no_action}")
    print(f"  Slash cmd: {slash_cmd}")
    if system_msg:
        print(f"  System:    {system_msg}")
    print(f"  Total:     {len(results)}")


def main():
    parser = argparse.ArgumentParser(description="Routing compliance audit for Claude Code sessions")
    parser.add_argument("target", nargs="?", help="Session ID or path to JSONL file")
    parser.add_argument("--dir", help="Projects directory to search for session files")
    parser.add_argument("--session", help="Session ID (alternative to positional argument)")
    args = parser.parse_args()

    target = args.target or args.session
    if not target:
        parser.print_help()
        sys.exit(1)

    # Determine file path
    if os.path.isfile(target):
        filepath = target
    else:
        filepath = find_session_file(target, args.dir)
        if not filepath:
            print(f"Error: Could not find session file for '{target}'", file=sys.stderr)
            sys.exit(1)

    print(f"Auditing: {filepath}")
    print("=" * 60)

    # Parse JSONL
    messages = []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not messages:
        print("No messages found in file.", file=sys.stderr)
        sys.exit(1)

    results = analyze_session(messages)
    print_report(results)


if __name__ == "__main__":
    main()
