"""
Comprehensive tests for Python HTTP client generation.

Tests cover:
1. Type conversion utilities (get_python_type, is_enum_type, extract_schema_name)
2. Body schema expansion (expand_body_schema)
3. Operation extraction from OpenAPI specs
4. Model import collection
5. Route verification for completeness
6. Template rendering validation
7. End-to-end generation cycle

Pattern: Following test_module_router_generator.py for comprehensive coverage
"""

# pyright: reportMissingImports=false
# mypy: disable-error-code="import-not-found"

import ast
import json
from pathlib import Path
from typing import Any

import pytest
from jinja2 import Environment, FileSystemLoader

from scripts.generate_python_clients import (  # type: ignore[import-untyped]
    cleanup_generated_files,
    collect_model_imports,
    expand_body_schema,
    extract_operations,
    extract_schema_name,
    generate_client,
    generate_init_file,
    get_python_type,
    is_enum_type,
    verify_all_routes_generated,
)


class TestTypeConversion:
    """Unit tests for type conversion utilities."""

    @pytest.fixture
    def backend_dir(self) -> Path:
        """Get backend directory path."""
        return Path(__file__).parent.parent

    @pytest.fixture
    def components(self) -> dict[str, Any]:
        """Sample OpenAPI components for testing."""
        return {
            "schemas": {
                "PlacedOrder": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                },
                "OrderType": {"type": "string", "enum": ["MARKET", "LIMIT", "STOP"]},
                "Body_editPositionBrackets": {
                    "type": "object",
                    "properties": {
                        "stopLoss": {"type": "number"},
                        "takeProfit": {"type": "number"},
                    },
                    "required": ["stopLoss"],
                },
            }
        }

    def test_get_python_type_primitives(self, components: dict[str, Any]):
        """Verify primitive type conversion."""
        assert get_python_type({"type": "string"}, components) == "str"
        assert get_python_type({"type": "integer"}, components) == "int"
        assert get_python_type({"type": "number"}, components) == "float"
        assert get_python_type({"type": "boolean"}, components) == "bool"

    def test_get_python_type_arrays(self, components: dict[str, Any]):
        """Verify array type conversion to list[Type]."""
        # Array of strings
        schema = {"type": "array", "items": {"type": "string"}}
        assert get_python_type(schema, components) == "list[str]"

        # Array of models
        schema = {
            "type": "array",
            "items": {"$ref": "#/components/schemas/PlacedOrder"},
        }
        assert get_python_type(schema, components) == "list[PlacedOrder]"

    def test_get_python_type_objects(self, components: dict[str, Any]):
        """Verify object type conversion to dict[str, Any]."""
        schema = {"type": "object"}
        assert get_python_type(schema, components) == "dict[str, Any]"

    def test_get_python_type_refs(self, components: dict[str, Any]):
        """Verify $ref resolution to model names."""
        schema = {"$ref": "#/components/schemas/PlacedOrder"}
        assert get_python_type(schema, components) == "PlacedOrder"

    def test_get_python_type_body_schemas(self, components: dict[str, Any]):
        """Verify Body_ schemas are converted to dict[str, Any]."""
        schema = {"$ref": "#/components/schemas/Body_editPositionBrackets"}
        assert get_python_type(schema, components) == "dict[str, Any]"

    def test_get_python_type_any_fallback(self, components: dict[str, Any]):
        """Verify unknown types fallback to Any."""
        schema = {"type": "unknown"}
        assert get_python_type(schema, components) == "Any"

        schema = {}
        assert get_python_type(schema, components) == "Any"

    def test_is_enum_type_direct(self, components: dict[str, Any]):
        """Verify enum detection in direct schema."""
        schema = {"type": "string", "enum": ["A", "B", "C"]}
        assert is_enum_type(schema, components) is True

    def test_is_enum_type_ref(self, components: dict[str, Any]):
        """Verify enum detection in $ref schema."""
        schema = {"$ref": "#/components/schemas/OrderType"}
        assert is_enum_type(schema, components) is True

    def test_is_enum_type_non_enum(self, components: dict[str, Any]):
        """Verify non-enum schemas return False."""
        # Regular string
        schema = {"type": "string"}
        assert is_enum_type(schema, components) is False

        # Model reference
        schema = {"$ref": "#/components/schemas/PlacedOrder"}
        assert is_enum_type(schema, components) is False

    def test_extract_schema_name(self):
        """Verify $ref string parsing."""
        ref = "#/components/schemas/PlacedOrder"
        assert extract_schema_name(ref) == "PlacedOrder"

        ref = "#/components/schemas/OrderType"
        assert extract_schema_name(ref) == "OrderType"


class TestBodyExpansion:
    """Tests for Body_ schema expansion."""

    @pytest.fixture
    def components(self) -> dict[str, Any]:
        """Sample components with Body_ schema."""
        return {
            "schemas": {
                "Body_editPositionBrackets": {
                    "type": "object",
                    "properties": {
                        "stopLoss": {
                            "type": "number",
                            "description": "Stop loss price",
                        },
                        "takeProfit": {
                            "type": "number",
                            "description": "Take profit price",
                        },
                        "trailingStop": {"type": "boolean"},
                    },
                    "required": ["stopLoss"],
                },
                "RegularModel": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                },
            }
        }

    def test_expand_body_schema_success(self, components: dict[str, Any]):
        """Verify Body_ schema expands into individual parameters."""
        result = expand_body_schema("Body_editPositionBrackets", components)

        assert result is not None
        assert len(result) == 3

        # Check stopLoss (required)
        stop_loss = next(p for p in result if p["name"] == "stopLoss")
        assert stop_loss["type"] == "float"
        assert stop_loss["required"] is True
        assert stop_loss["in"] == "body"
        assert stop_loss["description"] == "Stop loss price"

        # Check takeProfit (optional)
        take_profit = next(p for p in result if p["name"] == "takeProfit")
        assert take_profit["type"] == "float"
        assert take_profit["required"] is False

        # Check trailingStop (optional)
        trailing = next(p for p in result if p["name"] == "trailingStop")
        assert trailing["type"] == "bool"
        assert trailing["required"] is False

    def test_expand_body_schema_required_fields(self, components: dict[str, Any]):
        """Verify required fields are marked correctly."""
        result = expand_body_schema("Body_editPositionBrackets", components)

        assert result is not None
        required_params = [p for p in result if p["required"]]
        assert len(required_params) == 1
        assert required_params[0]["name"] == "stopLoss"

    def test_expand_body_schema_non_body_schema(self, components: dict[str, Any]):
        """Verify non-Body_ schemas return None."""
        result = expand_body_schema("RegularModel", components)
        assert result is None

    def test_expand_body_schema_missing_schema(self, components: dict[str, Any]):
        """Verify missing schema returns None."""
        result = expand_body_schema("Body_NonExistent", components)
        assert result is None


class TestOperationExtraction:
    """Tests for extracting operations from OpenAPI spec."""

    @pytest.fixture
    def minimal_spec(self) -> dict[str, Any]:
        """Minimal OpenAPI spec for testing."""
        return {
            "paths": {
                "/orders": {
                    "get": {
                        "operationId": "getOrders",
                        "description": "Get all orders",
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "array",
                                            "items": {
                                                "$ref": "#/components/schemas/PlacedOrder"
                                            },
                                        }
                                    }
                                }
                            }
                        },
                    },
                    "post": {
                        "operationId": "placeOrder",
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/PreOrder"}
                                }
                            },
                        },
                        "responses": {
                            "201": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/PlaceOrderResult"
                                        }
                                    }
                                }
                            }
                        },
                    },
                },
                "/orders/{order_id}": {
                    "get": {
                        "operationId": "getOrder",
                        "parameters": [
                            {
                                "name": "order_id",
                                "in": "path",
                                "required": True,
                                "schema": {"type": "string"},
                            }
                        ],
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/PlacedOrder"
                                        }
                                    }
                                }
                            }
                        },
                    }
                },
                "/search": {
                    "get": {
                        "operationId": "search",
                        "parameters": [
                            {
                                "name": "query",
                                "in": "query",
                                "required": True,
                                "schema": {"type": "string"},
                            },
                            {
                                "name": "limit",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "integer"},
                            },
                        ],
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        }
                                    }
                                }
                            }
                        },
                    }
                },
            },
            "components": {"schemas": {}},
        }

    def test_extract_operations_all_methods(self, minimal_spec: dict[str, Any]):
        """Verify all HTTP methods are extracted."""
        operations = extract_operations(minimal_spec)

        # Should have GET /orders, POST /orders, GET /orders/{order_id}, GET /search
        assert len(operations) == 4

        methods = {op["method"] for op in operations}
        assert "GET" in methods
        assert "POST" in methods

        operation_ids = {op["operation_id"] for op in operations}
        assert "getOrders" in operation_ids
        assert "placeOrder" in operation_ids
        assert "getOrder" in operation_ids
        assert "search" in operation_ids

    def test_extract_parameters_path(self, minimal_spec: dict[str, Any]):
        """Verify path parameters are extracted with correct types."""
        operations = extract_operations(minimal_spec)
        get_order = next(op for op in operations if op["operation_id"] == "getOrder")

        assert len(get_order["parameters"]) == 1
        param = get_order["parameters"][0]
        assert param["name"] == "order_id"
        assert param["in"] == "path"
        assert param["required"] is True
        assert param["type"] == "str"

    def test_extract_parameters_query(self, minimal_spec: dict[str, Any]):
        """Verify query parameters are extracted."""
        operations = extract_operations(minimal_spec)
        search = next(op for op in operations if op["operation_id"] == "search")

        assert len(search["parameters"]) == 2

        query_param = next(p for p in search["parameters"] if p["name"] == "query")
        assert query_param["in"] == "query"
        assert query_param["required"] is True
        assert query_param["type"] == "str"

        limit_param = next(p for p in search["parameters"] if p["name"] == "limit")
        assert limit_param["in"] == "query"
        assert limit_param["required"] is False
        assert limit_param["type"] == "int"

    def test_extract_request_body_model(self, minimal_spec: dict[str, Any]):
        """Verify regular model request body is extracted."""
        operations = extract_operations(minimal_spec)
        place_order = next(
            op for op in operations if op["operation_id"] == "placeOrder"
        )

        assert place_order["request_body"] is not None
        assert place_order["request_body"]["type"] == "PreOrder"
        assert place_order["request_body"]["required"] is True

    def test_extract_response_type_model(self, minimal_spec: dict[str, Any]):
        """Verify response type extraction for models."""
        operations = extract_operations(minimal_spec)
        place_order = next(
            op for op in operations if op["operation_id"] == "placeOrder"
        )

        assert place_order["response_type"] == "PlaceOrderResult"

    def test_extract_response_type_list(self, minimal_spec: dict[str, Any]):
        """Verify response type extraction for arrays."""
        operations = extract_operations(minimal_spec)
        get_orders = next(op for op in operations if op["operation_id"] == "getOrders")

        assert get_orders["response_type"] == "list[PlacedOrder]"

    def test_extract_response_type_primitive(self, minimal_spec: dict[str, Any]):
        """Verify primitive response types."""
        operations = extract_operations(minimal_spec)
        search = next(op for op in operations if op["operation_id"] == "search")

        assert search["response_type"] == "list[str]"


class TestModelImports:
    """Tests for model import collection."""

    def test_collect_from_response_types(self):
        """Verify models are collected from response types."""
        operations = [
            {"response_type": "PlacedOrder", "request_body": None, "parameters": []}
        ]

        models = collect_model_imports(operations)
        assert "PlacedOrder" in models

    def test_collect_from_response_lists(self):
        """Verify models are extracted from list[Model] patterns."""
        operations = [
            {"response_type": "list[Position]", "request_body": None, "parameters": []}
        ]

        models = collect_model_imports(operations)
        assert "Position" in models

    def test_collect_from_request_bodies(self):
        """Verify models are collected from request bodies."""
        operations = [
            {
                "response_type": "Any",
                "request_body": {"type": "PreOrder"},
                "parameters": [],
            }
        ]

        models = collect_model_imports(operations)
        assert "PreOrder" in models

    def test_collect_from_parameters(self):
        """Verify models are collected from parameters (enums)."""
        operations = [
            {
                "response_type": "Any",
                "request_body": None,
                "parameters": [{"name": "side", "type": "OrderSide"}],
            }
        ]

        models = collect_model_imports(operations)
        assert "OrderSide" in models

    def test_filter_primitives(self):
        """Verify primitives are NOT collected."""
        operations = [
            {
                "response_type": "str",
                "request_body": None,
                "parameters": [
                    {"name": "id", "type": "str"},
                    {"name": "count", "type": "int"},
                    {"name": "price", "type": "float"},
                    {"name": "active", "type": "bool"},
                ],
            }
        ]

        models = collect_model_imports(operations)
        assert "str" not in models
        assert "int" not in models
        assert "float" not in models
        assert "bool" not in models

    def test_filter_any(self):
        """Verify Any is NOT collected."""
        operations = [{"response_type": "Any", "request_body": None, "parameters": []}]

        models = collect_model_imports(operations)
        assert "Any" not in models

    def test_filter_dict_any(self):
        """Verify dict[str, Any] is NOT collected."""
        operations = [
            {"response_type": "dict[str, Any]", "request_body": None, "parameters": []}
        ]

        models = collect_model_imports(operations)
        assert "dict[str, Any]" not in models

    def test_filter_body_schemas(self):
        """Verify Body_ schemas are NOT collected."""
        operations = [
            {
                "response_type": "Any",
                "request_body": {"type": "Body_editPositionBrackets"},
                "parameters": [],
            }
        ]

        models = collect_model_imports(operations)
        assert "Body_editPositionBrackets" not in models

    def test_no_duplicates(self):
        """Verify duplicate models are deduplicated."""
        operations = [
            {"response_type": "PlacedOrder", "request_body": None, "parameters": []},
            {
                "response_type": "list[PlacedOrder]",
                "request_body": None,
                "parameters": [],
            },
            {
                "response_type": "Any",
                "request_body": {"type": "PlacedOrder"},
                "parameters": [],
            },
        ]

        models = collect_model_imports(operations)
        # Should only appear once despite 3 usages
        models_list = list(models)
        assert models_list.count("PlacedOrder") == 1


class TestRouteVerification:
    """Tests for route completeness verification."""

    @pytest.fixture
    def sample_spec(self) -> dict[str, Any]:
        """Sample OpenAPI spec."""
        return {
            "paths": {
                "/orders": {
                    "get": {"operationId": "getOrders", "responses": {}},
                    "post": {"operationId": "placeOrder", "responses": {}},
                },
                "/positions": {"get": {"operationId": "getPositions", "responses": {}}},
            }
        }

    def test_verify_all_routes_generated_success(self, sample_spec: dict[str, Any]):
        """Verify verification passes when all routes present."""
        operations = [
            {"operation_id": "getOrders"},
            {"operation_id": "placeOrder"},
            {"operation_id": "getPositions"},
        ]

        success, missing = verify_all_routes_generated(sample_spec, operations)
        assert success is True
        assert len(missing) == 0

    def test_verify_all_routes_generated_with_missing(
        self, sample_spec: dict[str, Any]
    ):
        """Verify verification fails when routes missing."""
        # Missing placeOrder
        operations = [
            {"operation_id": "getOrders"},
            {"operation_id": "getPositions"},
        ]

        success, missing = verify_all_routes_generated(sample_spec, operations)
        assert success is False
        assert len(missing) == 1
        assert "placeOrder" in missing

    def test_verify_reports_missing_operation_ids(self, sample_spec: dict[str, Any]):
        """Verify missing operation IDs are reported correctly."""
        # Missing multiple operations
        operations = [{"operation_id": "getOrders"}]

        success, missing = verify_all_routes_generated(sample_spec, operations)
        assert success is False
        assert len(missing) == 2
        assert "placeOrder" in missing
        assert "getPositions" in missing

    def test_verify_with_empty_operations(self, sample_spec: dict[str, Any]):
        """Verify verification handles empty operations list."""
        operations: list[dict[str, Any]] = []

        success, missing = verify_all_routes_generated(sample_spec, operations)
        assert success is False
        assert len(missing) == 3  # All routes missing

    def test_verify_ignores_extra_operations(self, sample_spec: dict[str, Any]):
        """Verify extra operations don't cause failure."""
        # Has all required + extra
        operations = [
            {"operation_id": "getOrders"},
            {"operation_id": "placeOrder"},
            {"operation_id": "getPositions"},
            {"operation_id": "extraOperation"},  # Not in spec
        ]

        success, missing = verify_all_routes_generated(sample_spec, operations)
        assert success is True  # Should still pass
        assert len(missing) == 0


class TestTemplateRendering:
    """Tests for Jinja2 template rendering."""

    @pytest.fixture
    def backend_dir(self) -> Path:
        """Get backend directory path."""
        return Path(__file__).parent.parent

    @pytest.fixture
    def template_dir(self, backend_dir: Path) -> Path:
        """Get template directory path."""
        return backend_dir / "scripts" / "templates"

    def test_template_renders_valid_python(self, template_dir: Path):
        """Verify rendered template is valid Python syntax."""
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("python_client.py.j2")

        operations = [
            {
                "operation_id": "getOrders",
                "method": "GET",
                "path": "/orders",
                "parameters": [],
                "request_body": None,
                "response_type": "list[PlacedOrder]",
                "description": "Get all orders",
            }
        ]

        models = collect_model_imports(operations)

        rendered = template.render(
            module_name="broker",
            class_name="BrokerClient",
            operations=operations,
            models=sorted(models),
        )

        # Validate syntax
        try:
            ast.parse(rendered)
        except SyntaxError as e:
            pytest.fail(f"Generated code has syntax error: {e}")

    def test_template_class_name(self, template_dir: Path):
        """Verify class name is correctly rendered."""
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("python_client.py.j2")

        rendered = template.render(
            module_name="broker",
            class_name="BrokerClient",
            operations=[],
            models=[],
        )

        assert "class BrokerClient:" in rendered

    def test_template_includes_all_operations(self, template_dir: Path):
        """Verify all operations become methods."""
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("python_client.py.j2")

        operations = [
            {
                "operation_id": "getOrders",
                "method": "GET",
                "path": "/orders",
                "parameters": [],
                "request_body": None,
                "response_type": "list[PlacedOrder]",
                "description": "",
            },
            {
                "operation_id": "placeOrder",
                "method": "POST",
                "path": "/orders",
                "parameters": [],
                "request_body": {"type": "PreOrder", "required": True},
                "response_type": "PlaceOrderResult",
                "description": "",
            },
        ]

        rendered = template.render(
            module_name="broker",
            class_name="BrokerClient",
            operations=operations,
            models=["PlacedOrder", "PreOrder", "PlaceOrderResult"],
        )

        assert "async def getOrders" in rendered
        assert "async def placeOrder" in rendered

    def test_template_handles_required_params(self, template_dir: Path):
        """Verify required parameters have no defaults."""
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("python_client.py.j2")

        operations = [
            {
                "operation_id": "search",
                "method": "GET",
                "path": "/search",
                "parameters": [
                    {
                        "name": "query",
                        "in": "query",
                        "required": True,
                        "type": "str",
                        "is_enum": False,
                    }
                ],
                "request_body": None,
                "response_type": "list[str]",
                "description": "",
            }
        ]

        rendered = template.render(
            module_name="test",
            class_name="TestClient",
            operations=operations,
            models=[],
        )

        # Required param should not have "| None = None"
        assert "query: str," in rendered
        assert "query: str | None = None" not in rendered

    def test_template_handles_optional_params(self, template_dir: Path):
        """Verify optional parameters have defaults."""
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("python_client.py.j2")

        operations = [
            {
                "operation_id": "search",
                "method": "GET",
                "path": "/search",
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "type": "int",
                        "is_enum": False,
                    }
                ],
                "request_body": None,
                "response_type": "list[str]",
                "description": "",
            }
        ]

        rendered = template.render(
            module_name="test",
            class_name="TestClient",
            operations=operations,
            models=[],
        )

        # Optional param should have "| None = None"
        assert "limit: int | None = None" in rendered

    def test_template_handles_path_params(self, template_dir: Path):
        """Verify path parameter replacement."""
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("python_client.py.j2")

        operations = [
            {
                "operation_id": "getOrder",
                "method": "GET",
                "path": "/orders/{order_id}",
                "parameters": [
                    {
                        "name": "order_id",
                        "in": "path",
                        "required": True,
                        "type": "str",
                        "is_enum": False,
                    }
                ],
                "request_body": None,
                "response_type": "PlacedOrder",
                "description": "",
            }
        ]

        rendered = template.render(
            module_name="broker",
            class_name="BrokerClient",
            operations=operations,
            models=["PlacedOrder"],
        )

        # Should have path replacement logic
        assert 'url.replace("{order_id}", str(order_id))' in rendered


class TestClientGeneration:
    """E2E tests for full client generation."""

    @pytest.fixture
    def backend_dir(self) -> Path:
        """Get backend directory path."""
        return Path(__file__).parent.parent

    @pytest.fixture
    def test_module_name(self) -> str:
        """Name for temporary test module."""
        return "test_client_gen"

    @pytest.fixture
    def test_output_dir(self, tmp_path: Path) -> Path:
        """Temporary output directory for generated clients."""
        output_dir = tmp_path / "clients"
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    @pytest.fixture
    def minimal_openapi_spec(self) -> dict[str, Any]:
        """Minimal OpenAPI spec for testing."""
        return {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/items": {
                    "get": {
                        "operationId": "getItems",
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        }
                                    }
                                }
                            }
                        },
                    }
                }
            },
            "components": {"schemas": {}},
        }

    def test_generate_client_from_spec(
        self,
        test_module_name: str,
        test_output_dir: Path,
        minimal_openapi_spec: dict[str, Any],
        backend_dir: Path,
    ):
        """Verify generation from OpenAPI spec produces client file."""
        # Create spec file
        spec_path = test_output_dir / "openapi.json"
        with open(spec_path, "w") as f:
            json.dump(minimal_openapi_spec, f)

        # Setup template environment
        template_dir = backend_dir / "scripts" / "templates"
        template_env = Environment(loader=FileSystemLoader(template_dir))

        # Generate client
        success, missing = generate_client(
            test_module_name, spec_path, test_output_dir, template_env
        )

        # Verify
        assert success is True
        assert len(missing) == 0

        client_file = test_output_dir / f"{test_module_name}_client.py"
        assert client_file.exists()

    def test_generated_client_passes_syntax_check(
        self,
        test_module_name: str,
        test_output_dir: Path,
        minimal_openapi_spec: dict[str, Any],
        backend_dir: Path,
    ):
        """Verify generated code is valid Python."""
        # Create spec file
        spec_path = test_output_dir / "openapi.json"
        with open(spec_path, "w") as f:
            json.dump(minimal_openapi_spec, f)

        # Setup template environment
        template_dir = backend_dir / "scripts" / "templates"
        template_env = Environment(loader=FileSystemLoader(template_dir))

        # Generate client
        generate_client(test_module_name, spec_path, test_output_dir, template_env)

        # Read generated code
        client_file = test_output_dir / f"{test_module_name}_client.py"
        code = client_file.read_text()

        # Validate syntax
        try:
            ast.parse(code)
        except SyntaxError as e:
            pytest.fail(f"Generated client has syntax error: {e}")

    def test_cleanup_old_files_during_regeneration(
        self, test_output_dir: Path, backend_dir: Path
    ):
        """Verify old client files are removed before generation."""
        # Create dummy old files
        old_client = test_output_dir / "old_client.py"
        old_client.write_text("# Old client")
        old_init = test_output_dir / "__init__.py"
        old_init.write_text("# Old init")

        assert old_client.exists()
        assert old_init.exists()

        # Run cleanup
        cleanup_generated_files(test_output_dir)

        # Verify cleanup
        assert not old_client.exists()
        assert not old_init.exists()

    def test_generate_init_file(self, test_output_dir: Path):
        """Verify __init__.py is generated with correct exports."""
        modules = ["broker", "datafeed"]
        generate_init_file(test_output_dir, modules)

        init_file = test_output_dir / "__init__.py"
        assert init_file.exists()

        content = init_file.read_text()
        assert "from .broker_client import BrokerClient" in content
        assert "from .datafeed_client import DatafeedClient" in content
        assert "__all__ = [" in content
        assert '"BrokerClient",' in content
        assert '"DatafeedClient",' in content
        assert '"BrokerClient",' in content
        assert '"DatafeedClient",' in content
        assert '"DatafeedClient",' in content
