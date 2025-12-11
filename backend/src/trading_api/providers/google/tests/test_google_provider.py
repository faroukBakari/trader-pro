"""Test GoogleProvider implementation."""

from unittest.mock import AsyncMock, patch

import pytest

from trading_api.models.common import CapabilitySpec
from trading_api.models.exceptions import ProviderException
from trading_api.models.providers.google_oauth_configs import GoogleProviderConfig
from trading_api.providers.google import GoogleProvider


@pytest.fixture
def mock_config() -> GoogleProviderConfig:
    """Mock Google config."""
    return GoogleProviderConfig(client_id="test_client_id")


@pytest.fixture
def provider(mock_config: GoogleProviderConfig) -> GoogleProvider:
    """Google provider with mock config."""
    return GoogleProvider(config=mock_config)


def test_provider_name(provider: GoogleProvider) -> None:
    """Provider has correct name."""
    assert provider.name == "google"


def test_provider_capabilities() -> None:
    """Provider declares auth capability."""
    caps = GoogleProvider.capabilities()
    assert len(caps) == 1
    assert caps[0].name == "auth"
    assert caps[0].version is None


def test_provider_config(
    provider: GoogleProvider, mock_config: GoogleProviderConfig
) -> None:
    """Provider returns configuration."""
    assert provider.config == mock_config
    assert provider.config.client_id == "test_client_id"


@pytest.mark.asyncio
async def test_verify_token_success(provider: GoogleProvider) -> None:
    """Successful token verification."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: {
        "sub": "123456",
        "email": "test@example.com",
        "email_verified": True,
        "aud": "test_client_id",
    }

    with patch("httpx.AsyncClient.get", return_value=mock_response):
        claims = await provider.verify_token("valid_token")

    assert claims["sub"] == "123456"
    assert claims["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_verify_token_invalid_response(provider: GoogleProvider) -> None:
    """Token verification fails with invalid response."""
    mock_response = AsyncMock()
    mock_response.status_code = 401
    mock_response.text = "Invalid token"

    with patch("httpx.AsyncClient.get", return_value=mock_response):
        with pytest.raises(ProviderException, match="Invalid Google token"):
            await provider.verify_token("invalid_token")


@pytest.mark.asyncio
async def test_verify_token_invalid_audience(provider: GoogleProvider) -> None:
    """Token with wrong audience fails."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: {
        "sub": "123456",
        "email": "test@example.com",
        "email_verified": True,
        "aud": "wrong_client_id",  # Wrong audience
    }

    with patch("httpx.AsyncClient.get", return_value=mock_response):
        with pytest.raises(ProviderException, match="Invalid token audience"):
            await provider.verify_token("invalid_token")


@pytest.mark.asyncio
async def test_verify_token_email_not_verified(provider: GoogleProvider) -> None:
    """Token with unverified email fails."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: {
        "sub": "123456",
        "email": "test@example.com",
        "email_verified": False,  # Not verified
        "aud": "test_client_id",
    }

    with patch("httpx.AsyncClient.get", return_value=mock_response):
        with pytest.raises(ProviderException, match="Email not verified"):
            await provider.verify_token("invalid_token")


def test_provider_dir() -> None:
    """Provider directory is correctly identified."""
    provider_dir = GoogleProvider.provider_dir()
    assert provider_dir.name == "google"
    assert provider_dir.parent.name == "providers"


def test_capability_matches_auth_requirement() -> None:
    """Provider capability matches auth service requirement."""
    provider_cap = GoogleProvider.capabilities()[0]
    service_req = CapabilitySpec(name="auth")

    assert service_req.matches(provider_cap)
