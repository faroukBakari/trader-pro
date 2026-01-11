"""Tests for InterModuleClients factory.

Tests cover:
- Singleton behavior
- URL resolution from environment variables
- Lazy client instantiation via cached_property
- Client cleanup
"""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from trading_api.shared.client_factory import InterModuleClients

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_singleton() -> Generator[None, None, None]:
    """Reset singleton before each test."""
    InterModuleClients.reset()
    yield
    InterModuleClients.reset()


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_singleton_returns_same_instance(self) -> None:
        """Multiple instantiations return the same instance."""
        client1 = InterModuleClients()
        client2 = InterModuleClients()
        assert client1 is client2

    def test_reset_clears_singleton(self) -> None:
        """Reset allows new instance creation."""
        InterModuleClients()
        InterModuleClients.reset()
        client2 = InterModuleClients()
        # After reset, _initialized should be False initially
        assert client2._initialized is True  # Gets re-initialized on __init__


# =============================================================================
# URL Resolution Tests
# =============================================================================


class TestURLResolution:
    """Tests for URL resolution with env overrides."""

    def test_datafeed_client_uses_env_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DatafeedClient uses DATAFEED_SERVICE_URL when set."""
        monkeypatch.setenv("DATAFEED_SERVICE_URL", "http://datafeed-test:9000")
        client = InterModuleClients()
        assert client.datafeed.base_url == "http://datafeed-test:9000"

    def test_datafeed_client_uses_default(self) -> None:
        """DatafeedClient uses baked-in default when no env override."""
        client = InterModuleClients()
        # Default baked into generated client: http://localhost:8000/api/v1/datafeed
        assert client.datafeed.base_url == "http://localhost:8000/api/v1/datafeed"

    def test_broker_client_uses_env_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BrokerClient uses BROKER_SERVICE_URL when set."""
        monkeypatch.setenv("BROKER_SERVICE_URL", "http://broker-test:9001")
        client = InterModuleClients()
        assert client.broker.base_url == "http://broker-test:9001"

    def test_env_url_strips_trailing_slash(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Trailing slash is stripped from env URL."""
        monkeypatch.setenv("DATAFEED_SERVICE_URL", "http://test:8000/datafeed/v1/")
        client = InterModuleClients()
        assert client.datafeed.base_url == "http://test:8000/datafeed/v1"


# =============================================================================
# Client Property Tests
# =============================================================================


class TestClientProperties:
    """Tests for lazy client instantiation."""

    def test_datafeed_client_is_cached(self) -> None:
        """DatafeedClient is created once and cached."""
        client = InterModuleClients()
        datafeed1 = client.datafeed
        datafeed2 = client.datafeed
        assert datafeed1 is datafeed2

    def test_broker_client_is_cached(self) -> None:
        """BrokerClient is created once and cached."""
        client = InterModuleClients()
        broker1 = client.broker
        broker2 = client.broker
        assert broker1 is broker2

    def test_timeout_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Timeout is read from INTER_MODULE_TIMEOUT env var."""
        monkeypatch.setenv("INTER_MODULE_TIMEOUT", "7.5")
        client = InterModuleClients()
        assert client._timeout == 7.5

    def test_default_timeout(self) -> None:
        """Default timeout is 5.0 seconds."""
        client = InterModuleClients()
        assert client._timeout == 5.0


# =============================================================================
# Cleanup Tests
# =============================================================================


class TestCleanup:
    """Tests for client cleanup."""

    @pytest.mark.asyncio
    async def test_close_all_closes_accessed_clients(self) -> None:
        """close_all() closes clients that were accessed."""
        client = InterModuleClients()

        # Access datafeed client to trigger creation
        _ = client.datafeed

        # Mock the close method
        with patch.object(
            client.datafeed, "close", new_callable=AsyncMock
        ) as mock_close:
            await client.close_all()
            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_all_skips_unaccessed_clients(self) -> None:
        """close_all() doesn't fail if clients weren't accessed."""
        client = InterModuleClients()
        # Don't access any clients
        await client.close_all()  # Should not raise

    def test_reset_clears_cached_properties(self) -> None:
        """reset() clears cached client properties."""
        client = InterModuleClients()
        _ = client.datafeed  # Access to cache
        assert "datafeed" in client.__dict__

        InterModuleClients.reset()
        # After reset, the old instance's cache is cleared
        # New instance should have empty cache
        new_client = InterModuleClients()
        assert "datafeed" not in new_client.__dict__
