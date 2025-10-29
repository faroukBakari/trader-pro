#!/usr/bin/env python3
"""
WebSocket Router Code Generator

Generates concrete (non-generic) WebSocket router classes by substituting
generic type parameters with actual types from instantiation signatures.

Supports both legacy (ws/*.py) and modular (modules/*/ws.py) architectures.
"""

import re
import shutil
from pathlib import Path
from typing import NamedTuple


class RouterSpec(NamedTuple):
    """Specification for generating a router."""

    class_name: str
    request_type: str
    data_type: str
    module_name: str | None = (
        None  # None for legacy ws/, module name for modules/*/ws.py
    )


# TODO: validate router syntax and report errors more gracefully
def parse_router_specs_from_file(
    file_path: Path, module_name: str | None = None
) -> list[RouterSpec]:
    """
    Parse a single WebSocket router file to extract TypeAlias definitions.

    Args:
        file_path: Path to the ws.py file to parse
        module_name: Name of the module (datafeed, broker, etc.) or None for legacy

    Looks for patterns like:
        BarWsRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]
        BrokerConnectionWsRouter: TypeAlias = WsRouter[
            BrokerConnectionSubscriptionRequest, BrokerConnectionStatus
        ]

    Returns a list of RouterSpec instances.
    """
    router_specs = []
    # Pattern matches both single-line and multi-line TypeAlias declarations
    # re.DOTALL makes . match newlines, allowing matching across multiple lines
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


def find_module_ws_files(base_dir: Path) -> list[tuple[str, Path]]:
    """
    Find all ws.py files in modules/ directory.

    Returns:
        List of (module_name, ws_file_path) tuples
    """
    modules_dir = base_dir / "src/trading_api/modules"
    if not modules_dir.exists():
        return []

    ws_files = []
    for module_dir in modules_dir.iterdir():
        if not module_dir.is_dir():
            continue
        ws_file = module_dir / "ws.py"
        if ws_file.exists():
            ws_files.append((module_dir.name, ws_file))

    return ws_files


def parse_router_specs(ws_dir: Path) -> list[RouterSpec]:
    """
    Parse WebSocket router files to extract TypeAlias definitions.

    LEGACY FUNCTION - supports old ws/*.py file structure.
    New code should use find_module_ws_files() + parse_router_specs_from_file().

    Returns a list of RouterSpec instances.
    """
    router_specs = []

    # Find all .py files except generic_route.py and files in generated/
    for py_file in ws_dir.glob("*.py"):
        if py_file.name in ("__init__.py", "generic_route.py", "router_interface.py"):
            continue

        router_specs.extend(parse_router_specs_from_file(py_file, module_name=None))

    return router_specs


def generate_router_code(spec: RouterSpec, template: str) -> str:
    """Generate concrete router code from template and spec."""
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
            result_lines.append(f"class {spec.class_name}(WsRouterInterface):")
            continue
        # Replace type parameters
        modified_line = line.replace("_TRequest", spec.request_type)
        modified_line = modified_line.replace("_TData", spec.data_type)
        result_lines.append(modified_line)
    return "\n".join(result_lines)


def generate_init_file(specs: list[RouterSpec]) -> str:
    """Generate __init__.py for the generated package."""
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

DO NOT EDIT MANUALLY - Generated by scripts/generate_ws_router.py
"""

{imports_str}

__all__ = [
    {exports_str},
]
'''


def generate_for_module(
    module_name: str,
    ws_file: Path,
    template: str,
    base_dir: Path,
) -> list[RouterSpec]:
    """
    Generate routers for a specific module.

    Args:
        module_name: Name of the module (datafeed, broker, etc.)
        ws_file: Path to the module's ws.py file
        template: Template code to use for generation
        base_dir: Base directory (backend root)

    Returns:
        List of generated RouterSpec instances
    """
    # Parse router specs from the module's ws.py file
    router_specs = parse_router_specs_from_file(ws_file, module_name=module_name)

    if not router_specs:
        return []

    # Output directory for this module
    output_dir = base_dir / f"src/trading_api/modules/{module_name}/ws_generated"

    # Clear and recreate output directory
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📁 Generating routers for module '{module_name}':")
    print(f"   Output: {output_dir.relative_to(base_dir)}")

    # Generate each router class
    for spec in router_specs:
        module_file_name = spec.class_name.lower()
        output_file = output_dir / f"{module_file_name}.py"

        content = generate_router_code(spec, template)
        output_file.write_text(content)
        print(f"  ✓ Generated {module_file_name}.py")
        print(f"    - Class: {spec.class_name}")
        print(f"    - Request: {spec.request_type}")
        print(f"    - Data: {spec.data_type}")

    # Generate __init__.py for the module's ws_generated package
    init_file = output_dir / "__init__.py"
    init_content = generate_init_file(router_specs)
    init_file.write_text(init_content)
    print(f"  ✓ Generated __init__.py")

    return router_specs


def main():
    """Generate all router classes (supports both legacy and modular architectures)."""
    base_dir = Path.cwd()

    # Read template from shared location (or fallback to ws/)
    template_path = base_dir / "src/trading_api/shared/ws/generic_route.py"
    if not template_path.exists():
        template_path = base_dir / "src/trading_api/ws/generic_route.py"

    template = template_path.read_text()
    print(f"📖 Read generic template from {template_path.relative_to(base_dir)}")

    total_routers = 0

    # Check for modular architecture (modules/*/ws.py files)
    module_ws_files = find_module_ws_files(base_dir)

    if module_ws_files:
        print(f"\n🔧 Found {len(module_ws_files)} module(s) with ws.py files")
        print("   Using modular architecture (modules/*/ws_generated/)")

        for module_name, ws_file in module_ws_files:
            specs = generate_for_module(module_name, ws_file, template, base_dir)
            total_routers += len(specs)

        print(
            f"\n✅ Generated {total_routers} router class(es) across {len(module_ws_files)} module(s)"
        )
        print(f"\n📝 Usage example (modular):")
        print(f"  from trading_api.modules.datafeed.ws_generated import BarWsRouter")
        print(f"  router = BarWsRouter(route='bars', service=datafeed_service)")

    else:
        # Fall back to legacy architecture (ws/*.py files → ws/generated/)
        print("\n🔧 No modules/*/ws.py files found")
        print("   Using legacy architecture (ws/generated/)")

        output_dir = base_dir / "src/trading_api/ws/generated"
        if output_dir.exists():
            shutil.rmtree(output_dir)
            print(f"🧹 Removed existing directory: {output_dir.relative_to(base_dir)}")
        output_dir.mkdir(parents=True, exist_ok=True)

        print(
            f"\n📁 Generating WebSocket routers in: {output_dir.relative_to(base_dir)}"
        )

        ws_dir = base_dir / "src/trading_api/ws"
        router_specs = parse_router_specs(ws_dir)

        for spec in router_specs:
            # Derive module name from class name (e.g., BarWsRouter -> bar.py)
            module_name = spec.class_name.lower()
            output_file = output_dir / f"{module_name}.py"

            content = generate_router_code(spec, template)
            output_file.write_text(content)
            print(f"  ✓ Generated {module_name}.py")
            print(f"    - Class: {spec.class_name}")
            print(f"    - Request type: {spec.request_type}")
            print(f"    - Data type: {spec.data_type}")

        init_file = output_dir / "__init__.py"
        init_content = generate_init_file(router_specs)
        init_file.write_text(init_content)
        print(f"  ✓ Generated __init__.py")

        total_routers = len(router_specs)

        print(f"\n✅ Generated {total_routers} router class(es)")
        print(f"\n📝 Usage example (legacy):")
        print(f"  from trading_api.ws.generated import BarWsRouter")
        print(f"  router = BarWsRouter(route='bars', tags=['datafeed'])")

    print(f"\n💡 To regenerate: make generate-ws-routers")


if __name__ == "__main__":
    main()
