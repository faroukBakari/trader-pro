#!/usr/bin/env python3
"""
Validate package names for generated clients.

This script ensures that:
1. Package names are unique across all generated clients (OpenAPI, AsyncAPI, Python)
2. Package names correspond to module names (e.g., @trader-pro/client-{module}, ws-types-{module})
3. No package name conflicts exist

Usage:
    poetry run python scripts/validate_modules.py
    poetry run python scripts/validate_modules.py --check-only

Exit Codes:
    0: All validations passed
    1: Validation errors found
"""

import json
import sys
from pathlib import Path
from typing import Any

# Add trading_api to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trading_api.shared.utils import discover_modules, discover_modules_with_websockets


class PackageNameValidator:
    """Validates package names for generated clients."""

    def __init__(self, backend_root: Path):
        """Initialize validator.

        Args:
            backend_root: Path to backend root directory
        """
        self.backend_root = backend_root
        self.modules_dir = backend_root / "src" / "trading_api" / "modules"
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def validate_openapi_package_names(self) -> dict[str, str]:
        """Validate OpenAPI client package names.

        Returns:
            Dict mapping module_name -> package_name
        """
        package_names: dict[str, str] = {}
        modules = discover_modules()

        for module_name in modules:
            spec_path = self.modules_dir / module_name / "specs" / "openapi.json"
            if not spec_path.exists():
                continue

            # Expected package name pattern: @trader-pro/client-{module}
            expected_package = f"@trader-pro/client-{module_name}"

            # Check if spec is valid JSON
            try:
                with open(spec_path) as f:
                    spec = json.load(f)
            except json.JSONDecodeError as e:
                self.errors.append(
                    f"OpenAPI spec for module '{module_name}' is invalid JSON: {e}"
                )
                continue

            # Validate spec has required fields
            if "info" not in spec:
                self.errors.append(
                    f"OpenAPI spec for module '{module_name}' missing 'info' field"
                )
                continue

            if "title" not in spec["info"]:
                self.errors.append(
                    f"OpenAPI spec for module '{module_name}' missing 'info.title' field"
                )
                continue

            # Extract title and validate it matches module name
            title = spec["info"]["title"]
            # Title should contain module name (case-insensitive)
            if module_name.lower() not in title.lower():
                self.warnings.append(
                    f"OpenAPI spec for module '{module_name}' has title '{title}' "
                    f"that doesn't clearly indicate module name"
                )

            # Check for duplicates
            if expected_package in package_names.values():
                duplicate_module = [
                    k for k, v in package_names.items() if v == expected_package
                ][0]
                self.errors.append(
                    f"Duplicate package name '{expected_package}' found for modules "
                    f"'{duplicate_module}' and '{module_name}'"
                )
            else:
                package_names[module_name] = expected_package

        return package_names

    def validate_asyncapi_package_names(self) -> dict[str, str]:
        """Validate AsyncAPI type package names.

        Returns:
            Dict mapping module_name -> package_name
        """
        package_names: dict[str, str] = {}
        modules = discover_modules_with_websockets()

        for module_name in modules:
            spec_path = self.modules_dir / module_name / "specs" / "asyncapi.json"
            if not spec_path.exists():
                continue

            # Expected package name pattern: ws-types-{module}
            expected_package = f"ws-types-{module_name}"

            # Check if spec is valid JSON
            try:
                with open(spec_path) as f:
                    spec = json.load(f)
            except json.JSONDecodeError as e:
                self.errors.append(
                    f"AsyncAPI spec for module '{module_name}' is invalid JSON: {e}"
                )
                continue

            # Validate spec has required fields
            if "info" not in spec:
                self.errors.append(
                    f"AsyncAPI spec for module '{module_name}' missing 'info' field"
                )
                continue

            if "title" not in spec["info"]:
                self.errors.append(
                    f"AsyncAPI spec for module '{module_name}' missing 'info.title' field"
                )
                continue

            # Extract title and validate it matches module name
            title = spec["info"]["title"]
            # Title should contain module name (case-insensitive)
            if module_name.lower() not in title.lower():
                self.warnings.append(
                    f"AsyncAPI spec for module '{module_name}' has title '{title}' "
                    f"that doesn't clearly indicate module name"
                )

            # Check for duplicates
            if expected_package in package_names.values():
                duplicate_module = [
                    k for k, v in package_names.items() if v == expected_package
                ][0]
                self.errors.append(
                    f"Duplicate package name '{expected_package}' found for modules "
                    f"'{duplicate_module}' and '{module_name}'"
                )
            else:
                package_names[module_name] = expected_package

        return package_names

    def validate_python_client_package_names(self) -> dict[str, str]:
        """Validate Python HTTP client package names.

        Returns:
            Dict mapping module_name -> class_name
        """
        class_names: dict[str, str] = {}
        modules = discover_modules()

        for module_name in modules:
            spec_path = self.modules_dir / module_name / "specs" / "openapi.json"
            if not spec_path.exists():
                continue

            # Expected class name pattern: {Module}Client
            expected_class = f"{module_name.capitalize()}Client"

            # Check for duplicates
            if expected_class in class_names.values():
                duplicate_module = [
                    k for k, v in class_names.items() if v == expected_class
                ][0]
                self.errors.append(
                    f"Duplicate Python client class '{expected_class}' found for modules "
                    f"'{duplicate_module}' and '{module_name}'"
                )
            else:
                class_names[module_name] = expected_class

        return class_names

    def validate_cross_package_uniqueness(
        self,
        openapi_packages: dict[str, str],
        asyncapi_packages: dict[str, str],
        python_classes: dict[str, str],
    ) -> None:
        """Validate that package names don't conflict across different client types.

        Args:
            openapi_packages: OpenAPI package names by module
            asyncapi_packages: AsyncAPI package names by module
            python_classes: Python client class names by module
        """
        # Collect all package identifiers
        all_packages: dict[str, list[tuple[str, str]]] = {}

        # Add OpenAPI packages
        for module, package in openapi_packages.items():
            all_packages.setdefault(package, []).append(("OpenAPI", module))

        # Add AsyncAPI packages
        for module, package in asyncapi_packages.items():
            all_packages.setdefault(package, []).append(("AsyncAPI", module))

        # Add Python classes (prefix to make them comparable)
        for module, class_name in python_classes.items():
            package_id = f"python-{class_name}"
            all_packages.setdefault(package_id, []).append(("Python", module))

        # Check for conflicts (same package from different modules)
        for package, sources in all_packages.items():
            if len(sources) > 1:
                sources_str = ", ".join([f"{typ}:{mod}" for typ, mod in sources])
                self.errors.append(
                    f"Package identifier '{package}' used by multiple sources: {sources_str}"
                )

    def validate_module_name_correspondence(
        self,
        openapi_packages: dict[str, str],
        asyncapi_packages: dict[str, str],
        python_classes: dict[str, str],
    ) -> None:
        """Validate that package names correspond to module names.

        Args:
            openapi_packages: OpenAPI package names by module
            asyncapi_packages: AsyncAPI package names by module
            python_classes: Python client class names by module
        """
        # Validate OpenAPI package naming convention
        for module, package in openapi_packages.items():
            expected = f"@trader-pro/client-{module}"
            if package != expected:
                self.errors.append(
                    f"OpenAPI package for module '{module}' is '{package}', "
                    f"expected '{expected}'"
                )

        # Validate AsyncAPI package naming convention
        for module, package in asyncapi_packages.items():
            expected = f"ws-types-{module}"
            if package != expected:
                self.errors.append(
                    f"AsyncAPI package for module '{module}' is '{package}', "
                    f"expected '{expected}'"
                )

        # Validate Python client class naming convention
        for module, class_name in python_classes.items():
            expected = f"{module.capitalize()}Client"
            if class_name != expected:
                self.errors.append(
                    f"Python client class for module '{module}' is '{class_name}', "
                    f"expected '{expected}'"
                )

    def validate_all(self) -> bool:
        """Run all validations.

        Returns:
            True if all validations passed, False otherwise
        """
        print("🔍 Validating backend modules for generated clients...")
        print()

        # Validate each client type
        openapi_packages = self.validate_openapi_package_names()
        asyncapi_packages = self.validate_asyncapi_package_names()
        python_classes = self.validate_python_client_package_names()

        # Validate cross-package uniqueness
        self.validate_cross_package_uniqueness(
            openapi_packages, asyncapi_packages, python_classes
        )

        # Validate module name correspondence
        self.validate_module_name_correspondence(
            openapi_packages, asyncapi_packages, python_classes
        )

        # Print results
        print("=" * 70)
        print("📋 Package Name Validation Results")
        print("=" * 70)

        if openapi_packages:
            print()
            print(f"✅ OpenAPI Clients ({len(openapi_packages)} modules):")
            for module, package in sorted(openapi_packages.items()):
                print(f"   {module:15} → {package}")

        if asyncapi_packages:
            print()
            print(f"✅ AsyncAPI Types ({len(asyncapi_packages)} modules):")
            for module, package in sorted(asyncapi_packages.items()):
                print(f"   {module:15} → {package}")

        if python_classes:
            print()
            print(f"✅ Python Clients ({len(python_classes)} modules):")
            for module, class_name in sorted(python_classes.items()):
                print(f"   {module:15} → {class_name}")

        # Print warnings
        if self.warnings:
            print()
            print(f"⚠️  Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   - {warning}")

        # Print errors
        if self.errors:
            print()
            print(f"❌ Errors ({len(self.errors)}):")
            for error in self.errors:
                print(f"   - {error}")
            print()
            print("=" * 70)
            return False

        print()
        print("=" * 70)
        print("✅ All package name validations passed!")
        print()
        return True


def main() -> int:
    """Main entry point.

    Returns:
        0 if all validations passed, 1 otherwise
    """
    backend_root = Path(__file__).parent.parent
    validator = PackageNameValidator(backend_root)

    if validator.validate_all():
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
