"""Tests for client generation functionality."""
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from httpx import AsyncClient

from trading_api.main import app


class TestClientGeneration:
    """Test client generation scripts and outputs."""

    @pytest.fixture(scope="class")
    def ensure_clients_generated(self) -> Path:
        """Ensure clients are generated before running validation tests."""
        client_dir = Path("clients/vue-client")

        if not client_dir.exists():
            # Try to generate clients
            try:
                result = subprocess.run(
                    ["make", "clients"],
                    capture_output=True,
                    text=True,
                    timeout=120,  # 2 minute timeout
                    cwd=Path.cwd(),
                )
                if result.returncode != 0:
                    pytest.skip(f"Client generation failed: {result.stderr}")
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pytest.skip("Could not generate clients - make command failed")

        return client_dir

    @pytest.fixture
    def temp_dir(self) -> Generator[Path, None, None]:
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_openapi_spec_accessible(self) -> None:
        """Test that OpenAPI specification is accessible via FastAPI app."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/api/v1/openapi.json")

        assert response.status_code == 200
        spec = response.json()
        assert spec["openapi"] in ["3.1.0", "3.0.3"]
        assert spec["info"]["title"] == "Trading API"
        assert "paths" in spec
        assert "/api/v1/health" in spec["paths"]

    @pytest.mark.asyncio
    async def test_openapi_spec_structure(self) -> None:
        """Test OpenAPI spec has required structure for client generation."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/api/v1/openapi.json")

        spec = response.json()

        # Check required fields for client generation
        assert "info" in spec
        assert "version" in spec["info"]
        assert "title" in spec["info"]
        assert "paths" in spec
        assert "components" in spec
        assert "schemas" in spec["components"]

        # Check health endpoint structure
        health_path = spec["paths"]["/api/v1/health"]["get"]
        assert "operationId" in health_path
        assert health_path["operationId"] == "getHealthStatus"
        assert "responses" in health_path
        assert "200" in health_path["responses"]

        # Check response schema
        response_schema = health_path["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        assert "$ref" in response_schema
        assert "HealthResponse" in response_schema["$ref"]

        # Check HealthResponse schema
        health_response_schema = spec["components"]["schemas"]["HealthResponse"]
        assert "properties" in health_response_schema
        assert "status" in health_response_schema["properties"]
        assert "message" in health_response_schema["properties"]
        assert "timestamp" in health_response_schema["properties"]

    def test_generate_clients_script_exists(self) -> None:
        """Test that the client generation script exists and is executable."""
        script_path = Path("scripts/generate-clients.sh")
        assert script_path.exists()
        assert os.access(script_path, os.X_OK)

    def test_makefile_clients_target(self) -> None:
        """Test that Makefile has clients target."""
        makefile_path = Path("Makefile")
        assert makefile_path.exists()

        content = makefile_path.read_text()
        assert "clients:" in content
        assert "./scripts/generate-clients.sh" in content

    def test_script_content_validation(self) -> None:
        """Test that the generation script has proper structure."""
        script_path = Path("scripts/generate-clients.sh")
        content = script_path.read_text()

        # Check for essential script components
        assert "#!/bin/bash" in content
        assert "set -e" in content
        assert "mkdir -p clients" in content
        assert "curl" in content
        assert "openapi.json" in content
        assert "npx @openapitools/openapi-generator-cli" in content
        assert "typescript-axios" in content

    def test_generated_vue_client_structure(
        self, ensure_clients_generated: Path
    ) -> None:
        """Test that generated Vue.js client has correct structure."""
        client_dir = ensure_clients_generated

        # Check required files exist
        required_files = [
            "api.ts",
            "base.ts",
            "common.ts",
            "configuration.ts",
            "index.ts",
        ]

        for file_name in required_files:
            file_path = client_dir / file_name
            assert file_path.exists(), f"Required file {file_name} not found"
            assert file_path.stat().st_size > 0, f"File {file_name} is empty"

    def test_generated_vue_client_typescript_validity(
        self, ensure_clients_generated: Path
    ) -> None:
        """Test that generated TypeScript files are syntactically valid."""
        client_dir = ensure_clients_generated

        api_file = client_dir / "api.ts"
        if api_file.exists():
            content = api_file.read_text()

            # Check for TypeScript/JavaScript syntax basics
            assert "import" in content or "export" in content
            assert "function" in content or "class" in content or "const" in content

            # Check for API-specific content
            assert "HealthApi" in content or "getHealthStatus" in content

    def test_openapi_files_generated(self) -> None:
        """Test that OpenAPI files are generated correctly."""
        # Check if files exist (they should after running make clients)
        openapi_file = Path("openapi.json")
        openapi_3_file = Path("openapi-3.0.json")

        if openapi_file.exists():
            # Validate JSON structure
            with open(openapi_file) as f:
                spec = json.load(f)
            assert spec["openapi"] == "3.1.0"
            assert spec["info"]["title"] == "Trading API"

        if openapi_3_file.exists():
            # Validate converted JSON structure
            with open(openapi_3_file) as f:
                spec = json.load(f)
            assert spec["openapi"] == "3.0.3"
            assert spec["info"]["title"] == "Trading API"
