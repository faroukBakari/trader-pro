#!/usr/bin/env python3
"""
Pre-commit hook to validate FastAPI routes have response_model defined
"""

import ast
import sys
from pathlib import Path
from typing import List, Set


class RouteVisitor(ast.NodeVisitor):
    """AST visitor to find FastAPI route decorators without response_model"""

    def __init__(self) -> None:
        self.violations: List[str] = []
        self.current_file = ""

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definitions to check for route decorators"""
        for decorator in node.decorator_list:
            if self._is_route_decorator(decorator):
                if isinstance(decorator, ast.Call) and not self._has_response_model(
                    decorator
                ):
                    line_num = decorator.lineno
                    func_name = node.name
                    self.violations.append(
                        f"{self.current_file}:{line_num}: "
                        f"Route '{func_name}' missing response_model"
                    )

        self.generic_visit(node)

    def _is_route_decorator(self, decorator: ast.AST) -> bool:
        """Check if decorator is a FastAPI route decorator"""
        route_methods = {
            "get",
            "post",
            "put",
            "patch",
            "delete",
            "options",
            "head",
            "trace",
        }

        if isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Attribute):
                # router.get(), router.post(), etc.
                return decorator.func.attr in route_methods
            elif isinstance(decorator.func, ast.Name):
                # @get(), @post(), etc. (direct imports)
                return decorator.func.id in route_methods

        return False

    def _has_response_model(self, decorator: ast.Call) -> bool:
        """Check if the decorator has response_model argument"""
        # Check keyword arguments
        for keyword in decorator.keywords:
            if keyword.arg == "response_model":
                return True

        return False


def check_file(file_path: Path) -> List[str]:
    """Check a single Python file for response_model violations"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content)
        visitor = RouteVisitor()
        visitor.current_file = str(file_path)
        visitor.visit(tree)

        return visitor.violations

    except Exception as e:
        return [f"{file_path}: Error parsing file: {e}"]


def main() -> None:
    """Main function for pre-commit hook"""
    if len(sys.argv) < 2:
        print("Usage: check_response_models.py <file1> [file2] ...")
        sys.exit(1)

    all_violations = []

    for file_path in sys.argv[1:]:
        path = Path(file_path)
        if path.suffix == ".py" and path.exists():
            violations = check_file(path)
            all_violations.extend(violations)

    if all_violations:
        print("❌ FastAPI Response Model Violations Found:")
        for violation in all_violations:
            print(f"  {violation}")
        print(
            "\nAll FastAPI routes must have response_model defined for OpenAPI compliance."
        )
        sys.exit(1)

    print("✅ All FastAPI routes have response_model defined")
    sys.exit(0)


if __name__ == "__main__":
    main()
