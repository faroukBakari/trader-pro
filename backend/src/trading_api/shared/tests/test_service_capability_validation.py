"""Test service capability validation (fail-fast protection)."""

from pathlib import Path

import pytest

from trading_api.models.common import CapabilityNotFoundError, CapabilitySpec
from trading_api.shared.service_interface import ServiceInterface


class MockServiceRequiringAuth(ServiceInterface):
    """Mock service that requires auth capability."""

    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        return [CapabilitySpec(name="auth")]

    @property
    def module_name(self) -> str:
        return "mock_auth_service"


def test_service_fails_without_required_capability() -> None:
    """Service requiring capability fails if no provider available."""
    with pytest.raises(
        CapabilityNotFoundError,
        match="requires capability 'auth' but no provider found",
    ):
        MockServiceRequiringAuth(
            module_dir=Path("/tmp"), providers=[]  # No providers → should fail
        )


@pytest.mark.asyncio
async def test_service_succeeds_with_required_capability() -> None:
    """Service succeeds when required provider is available."""
    from trading_api.models.providers.google_oauth_configs import GoogleProviderConfig
    from trading_api.providers.google import GoogleProvider

    # Create provider
    config = GoogleProviderConfig(client_id="test_client_id")
    provider = GoogleProvider(config=config)

    # Should succeed
    service = MockServiceRequiringAuth(module_dir=Path("/tmp"), providers=[provider])

    assert service.get_capability_provider("auth") == provider
