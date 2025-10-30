"""Shared utilities for the Trading API.

Provides helper functions for module discovery, configuration, and common utilities.
"""

from pathlib import Path


def discover_modules(base_dir: Path | str | None = None) -> list[str]:
    """Discover all available modules in the modules directory.

    Args:
        base_dir: Base directory containing modules/ folder. If None, uses
                 the trading_api root directory.

    Returns:
        List of module names (directory names in modules/)

    Examples:
        >>> discover_modules()
        ['broker', 'datafeed']
    """
    if base_dir is None:
        # Default to trading_api/modules
        base_dir = Path(__file__).parent.parent / "modules"
    else:
        base_dir = Path(base_dir)

    if not base_dir.exists():
        return []

    # Find all directories that are not __pycache__ and have __init__.py
    modules = []
    for item in base_dir.iterdir():
        if (
            item.is_dir()
            and not item.name.startswith("_")
            and (item / "__init__.py").exists()
        ):
            modules.append(item.name)

    return sorted(modules)


def discover_modules_with_websockets(base_dir: Path | str | None = None) -> list[str]:
    """Discover modules that have WebSocket routers.

    Args:
        base_dir: Base directory containing modules/ folder. If None, uses
                 the trading_api root directory.

    Returns:
        List of module names that have ws.py or ws/ directory

    Examples:
        >>> discover_modules_with_websockets()
        ['broker', 'datafeed']
    """
    all_modules = discover_modules(base_dir)

    if base_dir is None:
        base_dir = Path(__file__).parent.parent / "modules"
    else:
        base_dir = Path(base_dir)

    # Filter modules that have WebSocket support
    ws_modules = []
    for module_name in all_modules:
        module_dir = base_dir / module_name
        # Check for ws.py or ws/ directory
        if (module_dir / "ws.py").exists() or (module_dir / "ws").is_dir():
            ws_modules.append(module_name)

    return ws_modules
