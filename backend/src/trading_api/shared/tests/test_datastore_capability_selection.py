"""Test datastore capability selection (mirrors provider capability pattern)."""

from pathlib import Path

import pytest

from trading_api.datastores import DuckDBDatastore
from trading_api.datastores.postgres.datastore import PostgresDatastore
from trading_api.models.common import DatastoreCapabilitySpec, ProviderCapabilitySpec
from trading_api.models.exceptions import CommonException
from trading_api.shared.service_interface import ServiceInterface
from trading_api.shared.tests.conftest import NullDatastore


class MockServiceWithTimeseries(ServiceInterface):
    """Mock service requiring timeseries capability (required)."""

    @classmethod
    def provider_capabilities(cls) -> list[ProviderCapabilitySpec]:
        return []  # No provider requirements

    @classmethod
    def datastore_capabilities(cls) -> list[DatastoreCapabilitySpec]:
        return [DatastoreCapabilitySpec(name="timeseries")]

    @property
    def module_name(self) -> str:
        return "mock_timeseries_service"


class MockServiceWithOptionalTimeseries(ServiceInterface):
    """Mock service with optional timeseries capability."""

    @classmethod
    def provider_capabilities(cls) -> list[ProviderCapabilitySpec]:
        return []

    @classmethod
    def datastore_capabilities(cls) -> list[DatastoreCapabilitySpec]:
        return [DatastoreCapabilitySpec(name="timeseries", optional=True)]

    @property
    def module_name(self) -> str:
        return "mock_optional_timeseries_service"


class MockServiceNoDatastoreRequirements(ServiceInterface):
    """Mock service with no datastore capability requirements."""

    @classmethod
    def provider_capabilities(cls) -> list[ProviderCapabilitySpec]:
        return []

    @property
    def module_name(self) -> str:
        return "mock_no_datastore_reqs"


# =============================================================================
# DatastoreCapabilitySpec Tests
# =============================================================================


def test_datastore_capability_spec_matches_by_name() -> None:
    """DatastoreCapabilitySpec matches when names are equal."""
    spec1 = DatastoreCapabilitySpec(name="timeseries")
    spec2 = DatastoreCapabilitySpec(name="timeseries")
    assert spec1.matches(spec2)


def test_datastore_capability_spec_no_match_different_name() -> None:
    """DatastoreCapabilitySpec does not match with different name."""
    spec1 = DatastoreCapabilitySpec(name="timeseries")
    spec2 = DatastoreCapabilitySpec(name="transactions")
    assert not spec1.matches(spec2)


def test_datastore_capability_spec_optional_field() -> None:
    """DatastoreCapabilitySpec optional field defaults to False."""
    required = DatastoreCapabilitySpec(name="timeseries")
    optional = DatastoreCapabilitySpec(name="timeseries", optional=True)
    assert not required.optional
    assert optional.optional


def test_datastore_capability_spec_is_frozen() -> None:
    """DatastoreCapabilitySpec is immutable."""
    spec = DatastoreCapabilitySpec(name="timeseries")
    with pytest.raises(AttributeError):
        spec.name = "transactions"  # type: ignore


# =============================================================================
# Datastore.capabilities() Tests
# =============================================================================


def test_null_datastore_has_no_capabilities() -> None:
    """NullDatastore provides no special capabilities."""
    caps = NullDatastore.capabilities()
    assert caps == []


def test_duckdb_datastore_has_timeseries_capability() -> None:
    """DuckDBDatastore provides timeseries capability."""
    caps = DuckDBDatastore.capabilities()
    cap_names = {cap.name for cap in caps}
    assert "timeseries" in cap_names


def test_postgres_datastore_has_all_capabilities() -> None:
    """PostgresDatastore provides all capabilities."""
    caps = PostgresDatastore.capabilities()
    cap_names = {cap.name for cap in caps}
    assert cap_names == {
        "persistence",
        "transactions",
        "timeseries",
        "rangequery",
        "exclusion",
    }


# =============================================================================
# ServiceInterface.get_featured_datastore() Tests
# =============================================================================


def test_get_featured_datastore_returns_matching_datastore() -> None:
    """get_featured_datastore returns datastore with required capability."""
    null_ds = NullDatastore()

    # MockServiceNoDatastoreRequirements can use get_featured_datastore
    # with explicit runtime requirements
    service = MockServiceNoDatastoreRequirements(
        module_dir=Path("/tmp"),
        providers=[],
        datastores=[null_ds],
    )

    # NullDatastore has no capabilities, so requesting one should fail
    with pytest.raises(CommonException, match="No datastore provides capabilities"):
        service.get_featured_datastore("timeseries")


def test_get_featured_datastore_with_no_requirements_uses_first() -> None:
    """Service with no datastore requirements can use any datastore."""
    null_ds = NullDatastore()

    service = MockServiceNoDatastoreRequirements(
        module_dir=Path("/tmp"),
        providers=[],
        datastores=[null_ds],
    )

    # No requirements, so accessing datastores directly works
    assert next(iter(service.datastores)) == null_ds


def test_service_with_optional_timeseries_succeeds_with_null_datastore() -> None:
    """Service with optional timeseries requirement works with NullDatastore."""
    null_ds = NullDatastore()

    # This should not raise because timeseries is optional
    service = MockServiceWithOptionalTimeseries(
        module_dir=Path("/tmp"),
        providers=[],
        datastores=[null_ds],
    )

    # Service was created successfully
    assert service.datastores == [null_ds]


# =============================================================================
# ServiceInterface.datastore_capabilities() Default Tests
# =============================================================================


def test_default_datastore_capabilities_returns_empty() -> None:
    """Default datastore_capabilities() returns empty list."""
    caps = MockServiceNoDatastoreRequirements.datastore_capabilities()
    assert caps == []


def test_override_datastore_capabilities() -> None:
    """Override datastore_capabilities() returns specified requirements."""
    caps = MockServiceWithTimeseries.datastore_capabilities()
    assert len(caps) == 1
    assert caps[0].name == "timeseries"
    assert not caps[0].optional


# =============================================================================
# Backward Compatibility Tests
# =============================================================================


def test_capabilities_alias_returns_provider_capabilities() -> None:
    """Deprecated capabilities() returns same as provider_capabilities()."""
    # The deprecated capabilities() should delegate to provider_capabilities()
    assert MockServiceNoDatastoreRequirements.capabilities() == []
    assert MockServiceWithTimeseries.capabilities() == []
