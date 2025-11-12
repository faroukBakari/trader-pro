#!/usr/bin/env python3
"""
Module-scoped WebSocket Router Generator

Generates WebSocket routers for individual modules on-demand during app initialization.
Integrated into the module loading process for fail-fast error detection.

Key features:
- Module-scoped generation (one module at a time)
- Auto-detection (checks for modules/<module_name>/ws.py)
- Fail-fast with detailed error messages
- Quality checks (Black, Ruff, Flake8, Mypy, Isort)
- Import verification during generation (lightweight)
- Automatic validation in base classes (WsRouter, WsRouteInterface)

Usage:
    >>> from trading_api.shared.ws.module_router_generator import generate_module_routers
    >>> # Generate routers for datafeed module
    >>> generated = generate_module_routers("datafeed")
    >>> print(generated)  # True if routers generated, False if no ws.py

    >>> # Validation happens automatically during router instantiation
    >>> # If service doesn't implement WsRouteService protocol -> TypeError
    >>> # If route is empty or invalid -> ValueError
"""

import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import NamedTuple

logger = logging.getLogger(__name__)


class RouterSpec(NamedTuple):
    """Specification for generating a router."""

    class_name: str
    request_type: str
    data_type: str
    module_name: str


def parse_router_specs_from_file(file_path: Path, module_name: str) -> list[RouterSpec]:
    """
    Parse TypeAlias declarations from a ws.py file.

    Args:
        file_path: Path to the ws.py file
        module_name: Name of the module (e.g., 'datafeed', 'broker')

    Returns:
        List of RouterSpec instances

    Example:
        >>> # Parse datafeed/ws.py
        >>> specs = parse_router_specs_from_file(
        ...     Path("modules/datafeed/ws.py"),
        ...     "datafeed"
        ... )
        >>> print(specs[0].class_name)  # "BarWsRouter"
    """
    router_specs = []
    # Pattern matches both single-line and multi-line TypeAlias declarations
    # Examples:
    #   BarWsRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]
    #   BrokerConnectionWsRouter: TypeAlias = WsRouter[
    #       BrokerConnectionSubscriptionRequest, BrokerConnectionStatus
    #   ]
    pattern = re.compile(
        r"^\s*(\w+):\s*TypeAlias\s*=\s*WsRouter\[\s*(\w+)\s*,\s*(\w+)\s*\]",
        re.MULTILINE | re.DOTALL,
    )

    content = file_path.read_text()

    # Find all matches in the file
    for match in pattern.finditer(content):
        class_name = match.group(1)
        request_type = match.group(2)
        data_type = match.group(3)

        router_specs.append(
            RouterSpec(
                class_name=class_name,
                request_type=request_type,
                data_type=data_type,
                module_name=module_name,
            )
        )

    return router_specs


def generate_router_code(spec: RouterSpec, template: str) -> str:
    """
    Generate concrete router code from template and spec.

    Args:
        spec: Router specification
        template: Template code from generic_route.py

    Returns:
        Generated router code as string

    The function:
    1. Replaces _TRequest with spec.request_type
    2. Replaces _TData with spec.data_type
    3. Removes TypeVar declarations
    4. Removes Generic and TypeVar imports
    5. Updates class declaration
    """
    lines = template.split("\n")
    result_lines = [
        f"from trading_api.models import {spec.request_type}, {spec.data_type}"
    ]
    for line in lines:
        # Skip TypeVar declarations
        if "TypeVar(" in line:
            continue
        # Skip Generic and TypeVar imports, but keep Any
        if "from typing import" in line and ("Generic" in line or "TypeVar" in line):
            # Extract only the 'Any' import if present
            if "Any" in line:
                result_lines.append("from typing import Any")
            continue
        # Skip BaseModel import if it only imports BaseModel (we don't need it)
        if line.strip() == "from pydantic import BaseModel":
            continue
        # Replace class declaration
        if "class WsRouter(" in line:
            result_lines.append(f"class {spec.class_name}(WsRouteInterface):")
            continue
        # Replace type parameters
        modified_line = line.replace("_TRequest", spec.request_type)
        modified_line = modified_line.replace("_TData", spec.data_type)
        result_lines.append(modified_line)
    return "\n".join(result_lines)


def generate_init_file(specs: list[RouterSpec]) -> str:
    """
    Generate __init__.py for the ws_generated package.

    Args:
        specs: List of router specifications

    Returns:
        __init__.py content as string
    """
    imports = []
    exports = []

    for spec in specs:
        module_name = spec.class_name.lower()
        imports.append(f"from .{module_name} import {spec.class_name}")
        exports.append(f'"{spec.class_name}"')

    imports_str = "\n".join(imports)
    exports_str = ",\n    ".join(exports)

    return f'''"""
Auto-generated WebSocket routers.

DO NOT EDIT MANUALLY - Generated by module_router_generator.py
"""

{imports_str}

__all__ = [
    {exports_str},
]
'''


def run_quality_checks_for_module(
    module_name: str,
    generated_dir: Path,
) -> None:
    """
    Run formatters and linters on generated code for one module.

    Quality checks pipeline:
    1. Black formatting
    2. Ruff formatting
    3. Ruff auto-fix
    4. Flake8 linting
    5. Ruff linting
    6. Mypy type checking
    7. Isort import sorting

    Args:
        module_name: Name of the module
        generated_dir: Path to the ws_generated directory

    Raises:
        RuntimeError: If any check fails with detailed error message

    Example:
        >>> run_quality_checks_for_module(
        ...     "datafeed",
        ...     Path("src/trading_api/modules/datafeed/ws_generated")
        ... )
    """
    checks = [
        (["poetry", "run", "black", str(generated_dir)], "Black formatting"),
        (["poetry", "run", "ruff", "format", str(generated_dir)], "Ruff formatting"),
        (
            ["poetry", "run", "ruff", "check", str(generated_dir), "--fix"],
            "Ruff auto-fix",
        ),
        (["poetry", "run", "flake8", str(generated_dir)], "Flake8 linting"),
        (["poetry", "run", "ruff", "check", str(generated_dir)], "Ruff linting"),
        (["poetry", "run", "mypy", str(generated_dir)], "Mypy type checking"),
        (["poetry", "run", "isort", str(generated_dir)], "Isort import sorting"),
    ]

    for cmd, name in checks:
        try:
            subprocess.run(
                cmd,
                cwd=generated_dir.parent.parent.parent.parent.parent,  # backend/
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"{name} failed for module '{module_name}'!\n"
                f"Command: {' '.join(cmd)}\n"
                f"STDOUT:\n{e.stdout}\n"
                f"STDERR:\n{e.stderr}"
            ) from e


def verify_router_imports(
    module_name: str,
    version: str,
    router_class_name: str,
) -> tuple[bool, str]:
    """Verify a generated router can be imported (lightweight check).

    This is a lightweight verification that only checks if the router class
    can be imported from the ws_generated package. It does NOT instantiate
    the module or service to avoid circular dependencies.

    For full end-to-end verification (including instantiation), use the
    verify_generated_routers() function after app creation.

    Args:
        module_name: Name of the module (e.g., 'datafeed', 'broker')
        version: Version of the module (e.g., 'v1', 'v2')
        router_class_name: Name of the router class (e.g., 'BarWsRouter')

    Returns:
        Tuple of (success: bool, message: str)

    Example:
        >>> success, msg = verify_router_imports("datafeed", "v1", "BarWsRouter")
        >>> print(success, msg)  # True, "✓ BarWsRouter imports successfully"
    """
    try:
        # Dynamically import module's version-specific generated package
        module_path = f"trading_api.modules.{module_name}.ws.{version}.ws_generated"
        generated_module = __import__(module_path, fromlist=[router_class_name])

        # Verify router class exists
        router_class = getattr(generated_module, router_class_name)

        # Basic sanity checks without instantiation
        if not hasattr(router_class, "__init__"):
            return False, "Router class missing __init__ method"

        return True, f"✓ {router_class_name} imports successfully"

    except ImportError as e:
        return False, f"Import failed: {e}"
    except AttributeError as e:
        return False, f"Router class not found: {e}"
    except Exception as e:
        return False, f"Verification failed: {e}"


def generate_ws_routers(
    ws_file: str,
    *,
    silent: bool = False,
    skip_quality_checks: bool = False,
) -> bool:
    """
    Generate WebSocket routers for a specific module version.

    Detection:
    1. Extract module name and version from ws_file path
    2. Expected path: modules/{module_name}/ws/{version}/__init__.py
    3. Parse TypeAlias declarations and generate routers

    Generation:
    1. Parse router specs from ws file
    2. Load template from shared/ws/generic_route.py
    3. Generate concrete router classes
    4. Generate __init__.py with exports
    5. Optionally run quality checks

    Args:
        ws_file: Path to the WebSocket router file
                 (e.g., "modules/broker/ws/v1/__init__.py")
        silent: If True, suppress output except errors (default: False)
        skip_quality_checks: If True, skip formatters/linters for faster iteration
            (default: False)

    Returns:
        bool: True if routers were generated, False if no ws file found

    Raises:
        RuntimeError: If generation or quality checks fail
        ValueError: If ws_file path doesn't match expected pattern

    Example:
        >>> # Generate routers for broker v1
        >>> generate_ws_routers("modules/broker/ws/v1/__init__.py")
        True
        >>> # Generate routers for datafeed v2
        >>> generate_ws_routers("modules/datafeed/ws/v2/__init__.py")
        True
        >>> # Development mode (skip quality checks for speed)
        >>> generate_ws_routers(
        ...     "modules/broker/ws/v1/__init__.py",
        ...     silent=False,
        ...     skip_quality_checks=True
        ... )
        True
    """
    # Get backend base directory (from this file's location)
    # This file is at: backend/src/trading_api/shared/ws/module_router_generator.py
    # So we go up 5 levels to reach backend/
    base_dir = Path(__file__).parent.parent.parent.parent.parent

    # Convert ws_file to Path and resolve to absolute path
    ws_path = Path(ws_file)
    if not ws_path.is_absolute():
        # If relative, assume it's relative to backend/src/trading_api/
        ws_path = base_dir / "src" / "trading_api" / ws_file

    # Extract module name and version from path
    # Expected: .../modules/{module_name}/ws/{version}/__init__.py
    parts = ws_path.parts
    try:
        modules_idx = parts.index("modules")
        module_name = parts[modules_idx + 1]
        # Check if there's a ws directory
        if parts[modules_idx + 2] != "ws":
            raise ValueError(
                f"Expected 'ws' directory in path, got: {parts[modules_idx + 2]}"
            )
        version = parts[modules_idx + 3]
    except (ValueError, IndexError) as e:
        raise ValueError(
            f"Invalid ws_file path: {ws_file}. "
            f"Expected pattern: modules/{{module_name}}/ws/{{version}}/__init__.py"
        ) from e

    router_path = ws_path

    if not router_path.exists():
        return False  # No ws.py, no generation needed

    # Parse router specs
    try:
        router_specs = parse_router_specs_from_file(router_path, module_name)
    except Exception as e:
        raise RuntimeError(
            f"Failed to parse ws file for module '{module_name}' version '{version}': {e}"
        ) from e

    if not router_specs:
        return False  # No routers defined

    # Load template
    template_path = base_dir / "src/trading_api/shared/ws/generic_route.py"
    template = template_path.read_text()

    # Output directory - place in same directory level as ws router file
    # e.g., modules/broker/ws/v1/ws_generated/
    output_dir = router_path.parent / "ws_generated"

    # Completely remove and recreate to ensure clean state
    # This removes all generated files, __pycache__, and any leftover artifacts
    if output_dir.exists():
        shutil.rmtree(output_dir, ignore_errors=True)

    # Ensure parent ws version directory's __pycache__ is also cleared to avoid import issues
    ws_version_dir = router_path.parent
    pycache_dir = ws_version_dir / "__pycache__"
    if pycache_dir.exists():
        # Remove any cached imports of ws_generated
        for cache_file in pycache_dir.glob("*ws_generated*"):
            cache_file.unlink(missing_ok=True)

    # Create fresh directory
    output_dir.mkdir(parents=True, exist_ok=True)

    if not silent:
        print(f"📁 Generating routers for module '{module_name}' version '{version}'")

    # Generate each router
    for spec in router_specs:
        module_file_name = spec.class_name.lower()
        output_file = output_dir / f"{module_file_name}.py"
        content = generate_router_code(spec, template)
        output_file.write_text(content)
        if not silent:
            print(f"  ✓ {spec.class_name}")

    # Generate __init__.py
    init_file = output_dir / "__init__.py"
    init_content = generate_init_file(router_specs)
    init_file.write_text(init_content)

    # Quality checks
    if not skip_quality_checks:
        try:
            run_quality_checks_for_module(module_name, output_dir)
        except RuntimeError:
            # Clean up on failure
            shutil.rmtree(output_dir)
            raise

    # Lightweight verification: check that routers can be imported
    # (does NOT instantiate modules/services to avoid circular dependencies)
    if not silent:
        print("  🧪 Verifying router imports...")

    for spec in router_specs:
        success, message = verify_router_imports(
            module_name=module_name,
            version=version,
            router_class_name=spec.class_name,
        )
        if not success:
            # Clean up on verification failure
            shutil.rmtree(output_dir)
            raise RuntimeError(
                f"Router import verification failed for '{spec.class_name}' "
                f"in module '{module_name}' version '{version}': {message}"
            )
        if not silent:
            print(f"    {message}")

    if not silent:
        logger.info(f"✓ Generated WS routers for '{module_name}' version '{version}'")

    return True
