"""Tests for TWS provider configuration."""

import pytest
from pydantic import ValidationError

from trading_api.models.providers.tws.tws_configs import TWSProviderConfig


class TestTWSProviderConfig:
    """Tests for TWSProviderConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = TWSProviderConfig()

        assert config.enabled is True
        assert config.host == "127.0.0.1"
        assert config.port == 7497  # Paper trading port
        assert config.client_id == 1
        assert config.connection_timeout == 10.0
        assert config.realtime_bar_size == 5
        assert config.market_data_type == 1

    def test_invalid_port(self) -> None:
        """Test port validation with invalid port."""
        with pytest.raises(ValidationError) as exc_info:
            TWSProviderConfig(port=9999)

        errors = exc_info.value.errors()
        assert any("port" in str(e).lower() for e in errors)
        assert any("7497" in str(e) or "7496" in str(e) for e in errors)

    def test_valid_ports(self) -> None:
        """Test all valid TWS/Gateway ports."""
        valid_ports = [7497, 7496, 4002, 4001]

        for port in valid_ports:
            config = TWSProviderConfig(port=port)
            assert config.port == port

    def test_invalid_client_id_below_range(self) -> None:
        """Test client ID validation (below minimum)."""
        with pytest.raises(ValidationError) as exc_info:
            TWSProviderConfig(client_id=0)

        errors = exc_info.value.errors()
        assert any("client_id" in str(e).lower() for e in errors)

    def test_invalid_client_id_above_range(self) -> None:
        """Test client ID validation (above maximum)."""
        with pytest.raises(ValidationError) as exc_info:
            TWSProviderConfig(client_id=33)

        errors = exc_info.value.errors()
        assert any("client_id" in str(e).lower() for e in errors)

    def test_valid_client_id_range(self) -> None:
        """Test valid client ID range (1-32)."""
        for client_id in [1, 16, 32]:
            config = TWSProviderConfig(client_id=client_id)
            assert config.client_id == client_id

    def test_invalid_bar_size(self) -> None:
        """Test real-time bar size validation."""
        with pytest.raises(ValidationError) as exc_info:
            TWSProviderConfig(realtime_bar_size=1)

        errors = exc_info.value.errors()
        assert any(
            "realtime_bar_size" in str(e).lower() or "bar" in str(e).lower()
            for e in errors
        )

    def test_valid_bar_sizes(self) -> None:
        """Test valid real-time bar sizes (5 and 10)."""
        for bar_size in [5, 10]:
            config = TWSProviderConfig(realtime_bar_size=bar_size)
            assert config.realtime_bar_size == bar_size

    def test_env_loading(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test environment variable auto-loading."""
        monkeypatch.setenv("TWS_HOST", "192.168.1.1")
        monkeypatch.setenv("TWS_PORT", "4002")
        monkeypatch.setenv("TWS_CLIENT_ID", "2")
        monkeypatch.setenv("TWS_CONNECTION_TIMEOUT", "15.0")
        monkeypatch.setenv("TWS_REALTIME_BAR_SIZE", "10")
        monkeypatch.setenv("TWS_MARKET_DATA_TYPE", "3")

        config = TWSProviderConfig()

        assert config.host == "192.168.1.1"
        assert config.port == 4002
        assert config.client_id == 2
        assert config.connection_timeout == 15.0
        assert config.realtime_bar_size == 10
        assert config.market_data_type == 3

    def test_connection_timeout_minimum(self) -> None:
        """Test connection timeout validation (minimum 5.0 seconds)."""
        with pytest.raises(ValidationError) as exc_info:
            TWSProviderConfig(connection_timeout=2.0)

        errors = exc_info.value.errors()
        assert any(
            "connection_timeout" in str(e).lower() or "timeout" in str(e).lower()
            for e in errors
        )

    def test_market_data_type_range(self) -> None:
        """Test market data type validation (1-4)."""
        # Valid values
        for data_type in [1, 2, 3, 4]:
            config = TWSProviderConfig(market_data_type=data_type)
            assert config.market_data_type == data_type

        # Invalid values
        with pytest.raises(ValidationError):
            TWSProviderConfig(market_data_type=0)

        with pytest.raises(ValidationError):
            TWSProviderConfig(market_data_type=5)
