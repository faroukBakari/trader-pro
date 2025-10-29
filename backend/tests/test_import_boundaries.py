"""Test to enforce import boundaries between modules."""

import ast
import fnmatch
from pathlib import Path
from typing import Set

import pytest

# Generic rules - no hardcoded module names
BOUNDARY_RULES = {
    "modules/*": {
        "allowed_patterns": [
            "trading_api.models.*",
            "trading_api.shared.*",
            "trading_api.app_factory",
        ],
        "forbidden_patterns": [
            "trading_api.modules.*"
        ],  # Block ALL cross-module imports
        "description": "Modules can import from models, shared, and app_factory, but not from other modules",
    },
    "shared/*": {
        "allowed_patterns": [
            "trading_api.models.*",
            "trading_api.shared.*",
            "trading_api.app_factory",
        ],
        "forbidden_patterns": ["trading_api.modules.*"],
        "description": "Shared code can import from models and other shared code, but not from modules",
    },
    "models/*": {
        "allowed_patterns": [],
        "forbidden_patterns": ["trading_api.*"],
        "description": "Models are pure data - no trading_api imports allowed",
    },
}


def get_imports_from_file(file_path: Path) -> Set[str]:
    """Extract all imports from a Python file using AST parsing."""
    try:
        with open(file_path, "r") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
    except SyntaxError:
        return set()

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)

    return imports


def matches_pattern(path: str, pattern: str) -> bool:
    """Check if path matches glob pattern."""
    return fnmatch.fnmatch(path, pattern)


def get_applicable_rule(relative_path: str) -> dict | None:
    """Get the boundary rule applicable to this file path."""
    for pattern, rule in BOUNDARY_RULES.items():
        if matches_pattern(relative_path, pattern):
            return rule
    return None


def validate_import(import_name: str, allowed: list[str], forbidden: list[str]) -> bool:
    """Check if import violates boundary rules."""
    # Check forbidden patterns first
    for pattern in forbidden:
        # Direct pattern match
        if fnmatch.fnmatch(import_name, pattern):
            return False
        # Check if import starts with forbidden pattern (e.g., trading_api.modules.broker)
        pattern_prefix = pattern.rstrip("*").rstrip(".")
        if import_name.startswith(pattern_prefix):
            return False

    # If no allowed patterns specified, allow all (except forbidden)
    if not allowed:
        return True

    # Check if matches any allowed pattern
    for pattern in allowed:
        # Direct match with wildcard
        if fnmatch.fnmatch(import_name, pattern):
            return True
        # Also match the base package (e.g., "trading_api.models" matches "trading_api.models.*")
        pattern_base = pattern.rstrip("*").rstrip(".")
        if import_name == pattern_base or import_name.startswith(pattern_base + "."):
            return True

    return False


def test_import_boundaries():
    """Validate import boundaries across all modules."""
    src_dir = Path(__file__).parent.parent / "src" / "trading_api"
    violations = []

    for py_file in src_dir.rglob("*.py"):
        if "__pycache__" in str(py_file) or "generated" in str(py_file):
            continue

        relative_path = str(py_file.relative_to(src_dir))
        rule = get_applicable_rule(relative_path)

        if not rule:
            continue  # No rule applies to this file

        imports = get_imports_from_file(py_file)

        for import_name in imports:
            if not import_name.startswith("trading_api."):
                continue  # Only validate internal imports

            is_valid = validate_import(
                import_name, rule["allowed_patterns"], rule["forbidden_patterns"]
            )

            if not is_valid:
                violations.append(
                    {
                        "file": relative_path,
                        "import": import_name,
                        "rule": rule["description"],
                    }
                )

    if violations:
        error_msg = "\n\n❌ Import Boundary Violations Found:\n\n"
        for v in violations:
            error_msg += f"  File: {v['file']}\n"
            error_msg += f"  Forbidden import: {v['import']}\n"
            error_msg += f"  Rule: {v['rule']}\n\n"

        pytest.fail(error_msg)


def test_module_discovery():
    """Verify boundary rules work for any module (future-proof)."""
    src_dir = Path(__file__).parent.parent / "src" / "trading_api"
    modules_dir = src_dir / "modules"

    if not modules_dir.exists():
        pytest.skip("Modules directory does not exist yet")

    discovered_modules = [
        d.name
        for d in modules_dir.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    ]

    assert len(discovered_modules) > 0, "No modules discovered"

    # Verify rules apply to all discovered modules
    for module_name in discovered_modules:
        test_path = f"modules/{module_name}/service.py"
        rule = get_applicable_rule(test_path)
        assert rule is not None, f"No boundary rule applies to modules/{module_name}/"
        assert (
            "trading_api.modules.*" in rule["forbidden_patterns"]
        ), f"Module {module_name} should have cross-module import restrictions"
