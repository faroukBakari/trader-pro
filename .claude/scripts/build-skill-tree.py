#!/usr/bin/env python3
"""Build category glossary SKILL.md files from skill-bank skills.

Scans .claude/skill-bank/{name}/SKILL.md for skills that declare a `category`
field in their YAML frontmatter. Groups by category and generates one glossary
SKILL.md per category at .claude/skills/{category}/SKILL.md.

Skills without a `category` field are reported and skipped.

Pure stdlib — zero external dependencies.

Usage:
    python3 .claude/scripts/build-skill-tree.py              # dry-run (preview)
    python3 .claude/scripts/build-skill-tree.py --write       # create/overwrite glossaries
    python3 .claude/scripts/build-skill-tree.py --clean       # remove stale glossary dirs
    python3 .claude/scripts/build-skill-tree.py --check       # exit non-zero on drift
"""

from __future__ import annotations

import argparse
import difflib
import re
import shutil
import sys
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parent.parent          # .claude/
BANK_DIR = CLAUDE_DIR / "skill-bank"                         # .claude/skill-bank/
OUTPUT_DIR = CLAUDE_DIR / "skills"                           # .claude/skills/
AUTO_GENERATED_FIELD = "auto-generated: true"


# ──────────────────────────────────────────────────────────────────────
# 1. Parse frontmatter
# ──────────────────────────────────────────────────────────────────────

def parse_frontmatter(text: str) -> dict[str, str | list[str]]:
    """Extract YAML frontmatter from a SKILL.md file using regex.

    Returns dict with 'name', 'description', 'category', 'keywords', and
    'disable-model-invocation' if present.
    """
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}

    block = match.group(1)
    result: dict[str, str | list[str]] = {}

    # Scalar fields
    for field in ("name", "description", "category", "disable-model-invocation"):
        m = re.search(rf"^{field}:\s*(.+)$", block, re.MULTILINE)
        if m:
            result[field] = m.group(1).strip()

    # Keywords: inline list [a, b, c]
    kw_match = re.search(r"^keywords:\s*\[([^\]]*)\]", block, re.MULTILINE)
    if kw_match:
        raw = kw_match.group(1)
        result["keywords"] = [
            k.strip().strip("\"'") for k in raw.split(",") if k.strip()
        ]
    else:
        # Multi-line list: keywords:\n  - foo\n  - bar
        kw_block = re.search(
            r"^keywords:\s*\n((?:\s+-\s+.+\n?)+)", block, re.MULTILINE
        )
        if kw_block:
            result["keywords"] = [
                line.strip().lstrip("- ").strip("\"'")
                for line in kw_block.group(1).strip().splitlines()
                if line.strip().startswith("-")
            ]

    return result


# ──────────────────────────────────────────────────────────────────────
# 2. Discover skills from skill-bank
# ──────────────────────────────────────────────────────────────────────

SkillInfo = dict[str, str | list[str]]


def discover_bank_skills(
    bank_dir: Path,
) -> tuple[dict[str, list[SkillInfo]], list[SkillInfo]]:
    """Scan skill-bank/ for skills with `category` in frontmatter.

    Returns:
        (categories, uncategorized) where categories is
        {category_name: [skill_info, ...]} and uncategorized is
        [skill_info, ...] for skills missing a category field.
    """
    categories: dict[str, list[SkillInfo]] = {}
    uncategorized: list[SkillInfo] = []

    if not bank_dir.is_dir():
        return categories, uncategorized

    for skill_dir in sorted(bank_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            continue

        text = skill_file.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)

        if not fm.get("name"):
            print(
                f"  WARN: {skill_dir.name} — missing 'name', skipping",
                file=sys.stderr,
            )
            continue

        info: SkillInfo = {
            "name": fm.get("name", skill_dir.name),
            "dir_name": skill_dir.name,
            "description": fm.get("description", ""),
            "keywords": fm.get("keywords", []),
        }

        category = fm.get("category", "")
        if isinstance(category, str) and category:
            if category not in categories:
                categories[category] = []
            categories[category].append(info)
        else:
            uncategorized.append(info)

    # Sort categories alphabetically
    return dict(sorted(categories.items())), uncategorized


# ──────────────────────────────────────────────────────────────────────
# 3. Keyword index
# ──────────────────────────────────────────────────────────────────────

def build_keyword_index(
    leaves: list[SkillInfo],
) -> dict[str, list[str]]:
    """Build keyword → [skill_names] mapping, sorted alphabetically."""
    index: dict[str, list[str]] = {}
    for leaf in leaves:
        keywords = leaf.get("keywords", [])
        if not isinstance(keywords, list):
            continue
        name = str(leaf["name"])
        for kw in keywords:
            kw_str = str(kw).lower()
            if kw_str not in index:
                index[kw_str] = []
            if name not in index[kw_str]:
                index[kw_str].append(name)

    return {k: sorted(v) for k, v in sorted(index.items())}


# ──────────────────────────────────────────────────────────────────────
# 4. Generate glossary
# ──────────────────────────────────────────────────────────────────────

def generate_glossary(
    category_name: str,
    leaves: list[SkillInfo],
    bank_rel: str = "skill-bank",
) -> str:
    """Generate a category glossary SKILL.md content.

    Args:
        category_name: The category slug (e.g., "testing").
        leaves: Skill info dicts for this category.
        bank_rel: Relative path prefix from .claude/ to the bank dir.
    """
    # Aggregate keywords
    all_keywords: list[str] = []
    for leaf in leaves:
        kws = leaf.get("keywords", [])
        if isinstance(kws, list):
            for kw in kws:
                kw_lower = str(kw).lower()
                if kw_lower not in all_keywords:
                    all_keywords.append(kw_lower)
    all_keywords.sort()

    # Build description (max 120 chars)
    skill_names = [f"`{leaf['name']}`" for leaf in leaves]
    description = (
        f"Category glossary for {category_name}. "
        f"Contains {len(leaves)} skills: {', '.join(skill_names)}. "
        f"Use to discover skills in this category."
    )
    if len(description) > 120:
        description = description[:117] + "..."

    lines: list[str] = []
    lines.append("---")
    lines.append(f"name: {category_name}")
    lines.append(f"description: {description}")
    if all_keywords:
        kw_str = ", ".join(all_keywords)
        lines.append(f"keywords: [{kw_str}]")
    lines.append(AUTO_GENERATED_FIELD)
    lines.append("---")
    lines.append("")
    lines.append(f"# {category_name.replace('-', ' ').title()}")
    lines.append("")

    # Load instruction
    lines.append(
        f"Load any skill below: "
        f"`Read .claude/{bank_rel}/{{skill-name}}/SKILL.md`"
    )
    lines.append("")

    # Skills table
    lines.append("## Skills")
    lines.append("")
    lines.append("| Skill | Description |")
    lines.append("|-------|-------------|")
    for leaf in leaves:
        name = leaf["name"]
        desc = str(leaf.get("description", "")).replace("|", "\\|")
        lines.append(f"| `{name}` | {desc} |")
    lines.append("")

    # Keyword index
    kw_index = build_keyword_index(leaves)
    if kw_index:
        lines.append("## Keyword Index")
        lines.append("")
        lines.append("| Keyword | Skills |")
        lines.append("|---------|--------|")
        for kw, names in kw_index.items():
            skill_refs = ", ".join(f"`{n}`" for n in names)
            lines.append(f"| {kw} | {skill_refs} |")
        lines.append("")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────
# 5. Clean stale glossary directories
# ──────────────────────────────────────────────────────────────────────

def clean_stale_glossaries(
    output_dir: Path,
    active_categories: set[str],
) -> list[str]:
    """Remove glossary dirs in output that are no longer active categories.

    Only removes directories whose SKILL.md contains the auto-generated field.
    Returns list of removed directory names.
    """
    removed: list[str] = []
    if not output_dir.is_dir():
        return removed

    for entry in sorted(output_dir.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name in active_categories:
            continue
        glossary = entry / "SKILL.md"
        if glossary.is_file():
            content = glossary.read_text(encoding="utf-8")
            if AUTO_GENERATED_FIELD in content:
                shutil.rmtree(entry)
                removed.append(entry.name)

    return removed


# ──────────────────────────────────────────────────────────────────────
# 6. Main
# ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build category glossaries from skill-bank skills."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write glossary files (default is dry-run)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare generated glossaries against existing files; exit 1 on drift",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove stale glossary directories (only with --write)",
    )
    parser.add_argument(
        "--bank",
        type=Path,
        default=BANK_DIR,
        help=f"Skill bank directory (default: {BANK_DIR})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Output directory for glossaries (default: {OUTPUT_DIR})",
    )
    args = parser.parse_args()

    bank_dir: Path = args.bank
    output_dir: Path = args.output
    write_mode: bool = args.write

    print(f"Scanning {bank_dir} for categorized skills...")
    categories, uncategorized = discover_bank_skills(bank_dir)

    if not categories and not uncategorized:
        print("No skills found in skill-bank.")
        return

    total = sum(len(v) for v in categories.values())
    print(f"Found {total} categorized skills in {len(categories)} categories.")

    if uncategorized:
        print(
            f"  {len(uncategorized)} skill(s) without category:",
            file=sys.stderr,
        )
        for s in uncategorized:
            print(f"    - {s['name']}", file=sys.stderr)

    # Compute bank_rel: relative path from .claude/ to bank
    try:
        bank_rel = str(bank_dir.relative_to(CLAUDE_DIR))
    except ValueError:
        bank_rel = str(bank_dir)

    check_mode: bool = args.check
    drifted: list[str] = []

    for cat_name, leaves in categories.items():
        glossary = generate_glossary(cat_name, leaves, bank_rel)
        target_dir = output_dir / cat_name
        target = target_dir / "SKILL.md"

        if check_mode:
            existing = target.read_text(encoding="utf-8") if target.is_file() else ""
            if existing != glossary:
                drifted.append(cat_name)
                diff = difflib.unified_diff(
                    existing.splitlines(keepends=True),
                    glossary.splitlines(keepends=True),
                    fromfile=f"existing {target}",
                    tofile=f"generated {target}",
                    n=2,
                )
                print(f"  DRIFT: {target}")
                sys.stdout.writelines(diff)
            else:
                print(f"  OK: {target}")
        elif write_mode:
            target_dir.mkdir(parents=True, exist_ok=True)
            target.write_text(glossary, encoding="utf-8")
            print(f"  WROTE: {target}")
        else:
            print(f"\n{'='*60}")
            print(f"  PREVIEW: {target}")
            print(f"{'='*60}")
            print(glossary)

    # Clean stale glossary dirs
    if write_mode and args.clean:
        removed = clean_stale_glossaries(output_dir, set(categories.keys()))
        for name in removed:
            print(f"  REMOVED stale: {output_dir / name}")

    if check_mode:
        if drifted:
            print(f"\nGlossary drift detected in {len(drifted)} categor{'y' if len(drifted) == 1 else 'ies'}: {', '.join(drifted)}")
            print("Run with --write to fix.")
            sys.exit(1)
        else:
            print("\nAll glossaries in sync.")
    elif not write_mode:
        print("\nDry-run complete. Use --write to create/overwrite glossaries.")


if __name__ == "__main__":
    main()
