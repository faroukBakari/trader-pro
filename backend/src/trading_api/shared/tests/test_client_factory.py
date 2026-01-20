"""Tests for InterModuleClients factory.

Tests cover:
- URL resolution from environment variables
- Lazy client instantiation via cached_property
- Client cleanup
- Caller ID propagation
"""

from unittest.mock import AsyncMock, patch

import pytest

from trading_api.shared.client_factory import InterModuleClients

# =============================================================================
# Instance Tests
# =============================================================================


class TestInstanceBehavior:
    """Tests for instance creation behavior."""

    def test_different_caller_ids_create_different_instances(self) -> None:
        """Different caller_ids create separate instances."""
        client1 = InterModuleClients(caller_id="broker")
        client2 = InterModuleClients(caller_id="datafeed")
        assert client1 is not client2
        assert client1.caller_id == "broker"
        assert client2.caller_id == "datafeed"

    def test_caller_id_is_stored(self) -> None:
        """Caller ID is stored on instance."""
        client = InterModuleClients(caller_id="test-caller")
        assert client.caller_id == "test-caller"


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
        client = InterModuleClients(caller_id="test")
        assert client.datafeed.base_url == "http://datafeed-test:9000"

    def test_datafeed_client_uses_default(self) -> None:
        """DatafeedClient uses baked-in default when no env override."""
        client = InterModuleClients(caller_id="test")
        # Default baked into generated client: http://localhost:8000/api/v1/datafeed
        assert client.datafeed.base_url == "http://localhost:8000/api/v1/datafeed"

    def test_broker_client_uses_env_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BrokerClient uses BROKER_SERVICE_URL when set."""
        monkeypatch.setenv("BROKER_SERVICE_URL", "http://broker-test:9001")
        client = InterModuleClients(caller_id="test")
        assert client.broker.base_url == "http://broker-test:9001"

    def test_env_url_strips_trailing_slash(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Trailing slash is stripped from env URL."""
        monkeypatch.setenv("DATAFEED_SERVICE_URL", "http://test:8000/datafeed/v1/")
        client = InterModuleClients(caller_id="test")
        assert client.datafeed.base_url == "http://test:8000/datafeed/v1"


# =============================================================================
# Client Property Tests
# =============================================================================


class TestClientProperties:
    """Tests for lazy client instantiation."""

    def test_datafeed_client_is_cached(self) -> None:
        """DatafeedClient is created once and cached."""
        client = InterModuleClients(caller_id="test")
        datafeed1 = client.datafeed
        datafeed2 = client.datafeed
        assert datafeed1 is datafeed2

    def test_broker_client_is_cached(self) -> None:
        """BrokerClient is created once and cached."""
        client = InterModuleClients(caller_id="test")
        broker1 = client.broker
        broker2 = client.broker
        assert broker1 is broker2

    def test_timeout_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Timeout is read from INTER_MODULE_TIMEOUT env var."""
        monkeypatch.setenv("INTER_MODULE_TIMEOUT", "7.5")
        client = InterModuleClients(caller_id="test")
        assert client._timeout == 7.5

    def test_default_timeout(self) -> None:
        """Default timeout is 5.0 seconds."""
        client = InterModuleClients(caller_id="test")
        assert client._timeout == 5.0

    def test_caller_id_propagated_to_datafeed_client(self) -> None:
        """Caller ID is passed to DatafeedClient."""
        client = InterModuleClients(caller_id="my-service")
        assert client.datafeed.caller_id == "my-service"

    def test_caller_id_propagated_to_broker_client(self) -> None:
        """Caller ID is passed to BrokerClient."""
        client = InterModuleClients(caller_id="my-service")
        assert client.broker.caller_id == "my-service"


# =============================================================================
# Cleanup Tests
# =============================================================================


class TestCleanup:
    """Tests for client cleanup."""

    @pytest.mark.asyncio
    async def test_close_all_closes_accessed_clients(self) -> None:
        """close_all() closes clients that were accessed."""
        client = InterModuleClients(caller_id="test")

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
        client = InterModuleClients(caller_id="test")
        # Don't access any clients
        await client.close_all()  # Should not raise
