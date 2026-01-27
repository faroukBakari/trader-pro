# Provider/Capability System Developer Guide

**Version**: 1.0  
**Last Updated**: November 30, 2025  
**Status**: Production-Ready

---

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Core Concepts](#2-core-concepts)
3. [Creating Your First Provider](#3-creating-your-first-provider)
4. [Configuration Patterns](#4-configuration-patterns)
5. [Testing Guide](#5-testing-guide)
6. [Advanced Patterns](#6-advanced-patterns)
7. [Debugging & Troubleshooting](#7-debugging--troubleshooting)
8. [Best Practices](#8-best-practices)
9. [API Reference](#9-api-reference)

---

## 1. Quick Start

### 1.1 What is the Provider System?

The provider/capability system is a **pluggable architecture** that decouples service logic from external implementations. It allows:

- **Services** to declare what capabilities they need (e.g., "I need authentication")
- **Providers** to implement those capabilities (e.g., GoogleProvider, LocalProvider)
- **Automatic injection** of the right provider into the right service at runtime

**Example Flow:**

```text
AuthService declares: "I need auth capability"
    ↓
ProviderRegistry finds: GoogleProvider implements auth
    ↓
AppFactory injects: GoogleProvider → AuthService
    ↓
AuthService uses: provider.verify_token(token)
```

### 1.2 When to Use This System

**✅ Use providers when:**

- Implementing external integrations (OAuth, broker APIs, data feeds)
- You need to support multiple implementations (Google + local auth)
- You want to mock external services in tests
- The implementation might change or be swapped

**❌ Don't use providers for:**

- Pure business logic (use regular services)
- Database operations (use repositories)
- Internal utilities (use helper functions)

### 1.3 5-Minute Example: Adding Email Auth Provider

```python
# 1. Create provider configuration
# File: backend/src/trading_api/models/providers/google_oauth_configs.py
from trading_api.models.common import ProviderConfig

class LocalProviderConfig(ProviderConfig):
    jwt_secret: str

    class Config:
        env_prefix = "LOCAL_AUTH_"

# 2. Implement provider
# File: backend/src/trading_api/providers/local/__init__.py
from pathlib import Path
from typing import Any
from trading_api.models.common import CapabilitySpec, AuthenticationError
from trading_api.shared import Provider
from trading_api.capabilities.auth import AuthCapability

class LocalProvider(Provider, AuthCapability):
    def __init__(self, config: LocalProviderConfig | None = None):
        self._config = config or LocalProviderConfig()

    @classmethod
    def provider_dir(cls) -> Path:
        return Path(__file__).parent

    @property
    def name(self) -> str:
        return "local"

    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        return [CapabilitySpec(name="auth")]

    @property
    def config(self) -> LocalProviderConfig:
        return self._config

    async def verify_token(self, token: str) -> dict[str, Any]:
        # Your token verification logic here
        import jwt
        try:
            claims = jwt.decode(token, self.config.jwt_secret, algorithms=["HS256"])
            return claims
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid token: {e}")

# 3. Set environment variable
# .env.local
LOCAL_AUTH_JWT_SECRET=your_secret_key_here

# 4. That's it! Provider auto-discovered and ready to use
```

---

## 2. Core Concepts

### 2.1 The Big Picture

```text
┌─────────────────────────────────────────────────────────────┐
│                      Your Application                        │
│                                                              │
│  ┌──────────────┐                    ┌──────────────┐      │
│  │  AuthService │ requires "auth"    │ GoogleProvider│      │
│  │              │◄───────────────────┤ implements    │      │
│  │              │                    │ AuthCapability│      │
│  └──────────────┘                    └──────────────┘      │
│                                                              │
│  ┌──────────────┐                    ┌──────────────┐      │
│  │BrokerService │ requires "broker"  │  IBKRProvider │      │
│  │ (future)     │◄───────────────────┤ implements    │      │
│  │              │                    │BrokerCapability│      │
│  └──────────────┘                    └──────────────┘      │
│                                                              │
│         Managed by: ProviderRegistry + AppFactory           │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Key Components

#### CapabilitySpec

Type-safe capability declaration (what you need/provide).

```python
from trading_api.models.common import CapabilitySpec

# Service declares: "I need any auth provider"
req = CapabilitySpec(name="auth")

# Provider declares: "I provide auth v1"
prov = CapabilitySpec(name="auth", version="v1")

# Matching: Does provider satisfy service requirement?
req.matches(prov)  # True - version matches or not specified
```

#### Provider

Base class for all provider implementations.

```python
from trading_api.shared import Provider

class MyProvider(Provider):
    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        """What this provider offers"""
        return [CapabilitySpec(name="auth")]

    # ... implement abstract methods
```

#### Capability Interface

Contract that providers must implement.

```python
from trading_api.capabilities.auth import AuthCapability

class MyProvider(Provider, AuthCapability):
    async def verify_token(self, token: str) -> dict[str, Any]:
        """Implement the auth capability"""
        # Your verification logic
        return {"sub": "user_id", "email": "user@example.com"}
```

#### ProviderRegistry

Auto-discovers and manages provider instances.

```python
from trading_api.shared import ProviderRegistry

registry = ProviderRegistry()
registry.auto_discover()  # Finds all providers in providers/
providers = await registry.get_providers([CapabilitySpec(name="auth")])
```

### 2.3 Lifecycle

**Application Startup:**

```text
1. AppFactory.create_app() called
   ↓
2. ModuleRegistry.auto_discover() - finds all modules
   ↓
3. ProviderRegistry.auto_discover() - finds all providers
   ↓
4. ModuleRegistry.required_capabilities() - determines what's needed
   ↓
5. ProviderRegistry.get_providers() - lazy-loads matching providers
   ↓
6. ModuleRegistry.get_modules(providers=...) - injects providers
   ↓
7. Service._resolve_capabilities() - builds capability map (FAIL-FAST)
   ↓
8. Application ready!
```

**Request Handling:**

```text
1. API endpoint called
   ↓
2. Service method invoked
   ↓
3. service.auth_provider accessed (O(1) cached lookup)
   ↓
4. provider.verify_token(token) called
   ↓
5. Response returned
```

**Application Shutdown:**

```text
AppFactory cleanup
```

---

## 3. Creating Your First Provider

### 3.1 Provider Naming Convention

**CRITICAL:** Auto-discovery relies on strict naming:

- **Directory:** `providers/{name}/` (lowercase)
- **Class:** `{Name}Provider` (PascalCase + "Provider" suffix)
- **Export:** `__init__.py` must export `{Name}Provider`

**Examples:**

```text
✅ CORRECT:
providers/google/
  __init__.py         # exports GoogleProvider

providers/ibkr/
  __init__.py         # exports IbkrProvider

providers/local/
  __init__.py         # exports LocalProvider

❌ WRONG:
providers/Google/     # Directory must be lowercase
providers/google/
  __init__.py         # exports Google (missing "Provider" suffix)
```

### 3.2 Step-by-Step: Email/Password Provider

#### Step 1: Create Directory Structure

```bash
cd backend/src/trading_api
mkdir -p providers/local/tests
touch providers/local/__init__.py
touch providers/local/tests/__init__.py
touch providers/local/tests/test_local_provider.py
```

#### Step 2: Create Provider Configuration

**File:** `models/providers/google_oauth_configs.py`

```python
from pydantic import Field
from trading_api.models.common import ProviderConfig


class LocalProviderConfig(ProviderConfig):
    """Local email/password authentication configuration."""

    jwt_secret: str = Field(..., description="JWT signing secret")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    token_expiry_minutes: int = Field(default=60, description="Token lifetime")

    class Config:
        env_prefix = "LOCAL_AUTH_"
        # Auto-loads: LOCAL_AUTH_JWT_SECRET, LOCAL_AUTH_JWT_ALGORITHM, etc.
```

#### Step 3: Implement Provider

**File:** `providers/local/__init__.py`

```python
"""Local email/password authentication provider."""

from pathlib import Path
from typing import Any
import jwt

from trading_api.models.providers.google_oauth_configs import LocalProviderConfig
from trading_api.models.common import (
    AuthenticationError,
    CapabilitySpec,
)
from trading_api.shared import Provider
from trading_api.capabilities.auth import AuthCapability


class LocalProvider(Provider, AuthCapability):
    """Local authentication provider using JWT tokens.

    Implements AuthCapability for email/password authentication.
    """

    def __init__(self, config: LocalProviderConfig | None = None) -> None:
        """Initialize local provider.

        Args:
            config: Optional config for testing (None = load from env)
        """
        self._config = config or LocalProviderConfig()

    @classmethod
    def provider_dir(cls) -> Path:
        """Return provider directory."""
        return Path(__file__).parent

    @property
    def name(self) -> str:
        """Provider name."""
        return "local"

    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        """Capabilities provided."""
        return [CapabilitySpec(name="auth")]

    @property
    def config(self) -> LocalProviderConfig:
        """Provider configuration."""
        return self._config

    async def verify_token(self, token: str) -> dict[str, Any]:
        """Verify JWT token.

        Args:
            token: JWT token to verify

        Returns:
            Token claims with user information

        Raises:
            AuthenticationError: If token invalid or expired
        """
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                self.config.jwt_secret,
                algorithms=[self.config.jwt_algorithm]
            )

            # Validate required fields
            if "sub" not in claims or "email" not in claims:
                raise AuthenticationError("Token missing required claims")

            return claims

        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid token: {e}")


__all__ = ["LocalProvider", "LocalProviderConfig"]
```

#### Step 4: Add Unit Tests

**File:** `providers/local/tests/test_local_provider.py`

```python
"""Test LocalProvider implementation."""

import pytest
from datetime import datetime, timedelta
import jwt

from trading_api.models.providers.google_oauth_configs import LocalProviderConfig
from trading_api.models.common import AuthenticationError
from trading_api.providers.local import LocalProvider


@pytest.fixture
def mock_config():
    """Mock local provider config."""
    return LocalProviderConfig(jwt_secret="test_secret_key_at_least_32_chars")


@pytest.fixture
def provider(mock_config):
    """Local provider with mock config."""
    return LocalProvider(config=mock_config)


def create_test_token(secret: str, claims: dict, expired: bool = False) -> str:
    """Helper to create test JWT tokens."""
    payload = {
        **claims,
        "exp": datetime.utcnow() + timedelta(
            minutes=-10 if expired else 60
        )
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.mark.asyncio
async def test_verify_token_success(provider, mock_config):
    """Successful token verification."""
    token = create_test_token(
        mock_config.jwt_secret,
        {"sub": "123", "email": "test@example.com"}
    )

    claims = await provider.verify_token(token)

    assert claims["sub"] == "123"
    assert claims["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_verify_token_expired(provider, mock_config):
    """Expired token fails verification."""
    token = create_test_token(
        mock_config.jwt_secret,
        {"sub": "123", "email": "test@example.com"},
        expired=True
    )

    with pytest.raises(AuthenticationError, match="expired"):
        await provider.verify_token(token)


@pytest.mark.asyncio
async def test_verify_token_invalid_signature(provider):
    """Token with wrong signature fails."""
    token = create_test_token(
        "wrong_secret",
        {"sub": "123", "email": "test@example.com"}
    )

    with pytest.raises(AuthenticationError, match="Invalid token"):
        await provider.verify_token(token)


@pytest.mark.asyncio
async def test_verify_token_missing_claims(provider, mock_config):
    """Token missing required claims fails."""
    token = create_test_token(
        mock_config.jwt_secret,
        {"sub": "123"}  # Missing email
    )

    with pytest.raises(AuthenticationError, match="missing required claims"):
        await provider.verify_token(token)


def test_capabilities():
    """Provider declares auth capability."""
    assert LocalProvider.capabilities() == [CapabilitySpec(name="auth")]


def test_provider_name(provider):
    """Provider name matches directory."""
    assert provider.name == "local"
```

#### Step 5: Set Environment Variables

**File:** `.env.local`

```bash
# Local authentication provider
LOCAL_AUTH_JWT_SECRET=your_super_secret_key_at_least_32_characters_long
LOCAL_AUTH_JWT_ALGORITHM=HS256
LOCAL_AUTH_TOKEN_EXPIRY_MINUTES=60
```

#### Step 6: Run Tests

```bash
# From backend/ directory
make test

# Or specific test
poetry run pytest src/trading_api/providers/local/tests/ -v
```

#### Step 7: Verify Auto-Discovery

The provider is now automatically discovered and available! No registration needed.

```python
# In your code
from trading_api.app_factory import AppFactory

factory = AppFactory()
factory.provider_registry.auto_discover()
print(factory.provider_registry.list_providers())
# Output: ['google', 'local']
```

---

## 4. Configuration Patterns

### 4.1 Environment Variable Auto-Loading

**Pattern:** Use Pydantic's `env_prefix` for automatic environment variable loading.

```python
class MyProviderConfig(ProviderConfig):
    api_key: str
    api_url: str = "https://api.example.com"

    class Config:
        env_prefix = "MY_PROVIDER_"
        # Auto-loads: MY_PROVIDER_API_KEY, MY_PROVIDER_API_URL

# Usage
config = MyProviderConfig()  # Reads from environment automatically
```

### 4.2 Required vs Optional Settings

```python
class BrokerProviderConfig(ProviderConfig):
    # Required (no default)
    api_key: str = Field(..., description="API key")

    # Optional (with default)
    timeout_seconds: int = Field(default=30, description="Request timeout")
    max_retries: int = Field(default=3, description="Max retry attempts")

    # Optional (can be None)
    webhook_url: str | None = Field(None, description="Webhook callback URL")
```

### 4.3 Validation & Constraints

```python
from pydantic import Field, validator

class SecureProviderConfig(ProviderConfig):
    api_key: str = Field(..., min_length=32, description="API key (min 32 chars)")

    @validator("api_key")
    def validate_api_key_format(cls, v):
        """Custom validation logic."""
        if not v.startswith("sk_"):
            raise ValueError("API key must start with 'sk_'")
        return v
```

### 4.4 Secrets Management

**Development:**

```bash
# .env.local (git-ignored)
PROVIDER_API_KEY=test_key_for_development
```

**Production (Docker):**

```yaml
# docker-compose.yml
services:
  backend:
    environment:
      - PROVIDER_API_KEY=${PROVIDER_API_KEY}
```

**Production (Kubernetes):**

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: provider-secrets
data:
  PROVIDER_API_KEY: <base64-encoded>
```

**Security Best Practice:**

```python
class ProviderConfig(ProviderConfig):
    api_key: str

    def __repr__(self) -> str:
        """Safe representation without exposing secrets."""
        return f"{self.__class__.__name__}(api_key=***)"
```

---

## 5. Testing Guide

### 5.1 Unit Testing Providers

**Pattern:** Inject mock config to avoid environment dependencies.

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.fixture
def mock_config():
    """Mock configuration."""
    return MyProviderConfig(api_key="test_key")

@pytest.fixture
def provider(mock_config):
    """Provider with mock config."""
    return MyProvider(config=mock_config)

@pytest.mark.asyncio
async def test_provider_method(provider):
    """Test provider method with mocked external calls."""
    mock_response = AsyncMock()
    mock_response.json.return_value = {"status": "ok"}

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await provider.some_method()

    assert result == expected
```

### 5.2 Testing Capability Resolution

**Test that services fail fast without required providers:**

```python
import pytest
from trading_api.models.common import CapabilityNotFoundError

def test_service_fails_without_provider():
    """Service requiring unavailable capability fails at initialization."""
    from trading_api.modules.auth.service import AuthService
    from pathlib import Path

    with pytest.raises(
        CapabilityNotFoundError,
        match="requires capability 'auth'"
    ):
        AuthService(
            module_dir=Path("/tmp"),
            providers=[]  # No auth provider
        )
```

### 5.3 Integration Testing

**Test full provider injection flow:**

```python
@pytest.mark.asyncio
async def test_provider_integration():
    """Test provider injection into service."""
    from trading_api.app_factory import AppFactory

    factory = AppFactory()
    app = await factory.create_app(enabled_module_names=["auth"])

    # Verify provider was injected
    auth_modules = factory.module_registry.get_modules(module_names=["auth"])
    auth_module = auth_modules[0]
    assert len(auth_module.service._providers) > 0
```

### 5.4 Mocking External APIs

**Pattern:** Use `pytest-mock` or `unittest.mock` to avoid real API calls.

```python
@pytest.mark.asyncio
async def test_verify_token_mocks_google_api(provider):
    """Mock Google tokeninfo endpoint."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "sub": "123",
        "email": "test@example.com",
        "email_verified": True,
        "aud": "test_client_id"
    }

    with patch("httpx.AsyncClient.get", return_value=mock_response):
        claims = await provider.verify_token("mock_token")

    assert claims["sub"] == "123"
```

---

## 6. Advanced Patterns

### 6.1 Multi-Capability Providers

**Use Case:** Single provider implements multiple capabilities.

```python
from trading_api.capabilities.auth import AuthCapability
from trading_api.capabilities.broker import BrokerCapability  # Future

class IBKRProvider(Provider, AuthCapability, BrokerCapability):
    """IBKR provider implementing auth + broker capabilities."""

    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        return [
            CapabilitySpec(name="auth"),
            CapabilitySpec(name="broker"),
        ]

    async def verify_token(self, token: str) -> dict[str, Any]:
        """Implement AuthCapability."""
        # IBKR session token verification
        ...

    async def execute_order(self, order: dict) -> str:
        """Implement BrokerCapability."""
        # IBKR order execution
        ...
```

**Benefit:** Both AuthService and BrokerService share the same IBKR connection.

### 6.2 Conditional Provider Loading

**Use `enabled` flag to disable providers:**

```python
class ProviderConfig(BaseModel):
    enabled: bool = True  # Base class provides this

class DebugProviderConfig(ProviderConfig):
    enabled: bool = Field(
        default=False,  # Disabled by default in production
        description="Enable debug provider"
    )

    class Config:
        env_prefix = "DEBUG_PROVIDER_"

# Usage
# .env.local
DEBUG_PROVIDER_ENABLED=true  # Only in development
```

### 6.3 Versioned Capabilities

**Support multiple versions of same capability:**

```python
class AuthServiceV1(ServiceInterface):
    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        return [CapabilitySpec(name="auth", version="v1")]

class AuthServiceV2(ServiceInterface):
    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        return [CapabilitySpec(name="auth", version="v2")]

# Providers declare specific versions
class GoogleProviderV2(Provider, AuthCapability):
    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        return [CapabilitySpec(name="auth", version="v2")]
```

---

## 7. Debugging & Troubleshooting

### 7.1 Common Errors

#### Error: `CapabilityNotFoundError: No provider found for capability 'auth'`

**Cause:** No provider implements the required capability.

**Solutions:**

1. Check provider auto-discovery:

   ```python
   registry = ProviderRegistry()
   registry.auto_discover()
   print(registry.list_providers())  # Should show your provider
   ```

2. Verify naming convention:
   - Directory: `providers/myProvider/` ❌ → `providers/myprovider/` ✅
   - Class: `MyProvider` ❌ → `MyproviderProvider` ✅

3. Check capability declaration:
   ```python
   print(MyProvider.capabilities())  # Must match service requirement
   ```

#### Error: `ProviderNotFoundError: Provider 'google' not registered`

**Cause:** Provider class not found during auto-discovery.

**Solutions:**

1. Verify `__init__.py` exports class:

   ```python
   # providers/google/__init__.py
   __all__ = ["GoogleProvider"]  # Must export
   ```

2. Check for import errors:

   ```bash
   python -c "from trading_api.providers.google import GoogleProvider"
   ```

3. Verify directory structure:
   ```text
   providers/
     google/
       __init__.py  ← Must exist
   ```

#### Error: `ValidationError: field required (type=value_error.missing)`

**Cause:** Required environment variable not set.

**Solutions:**

1. Set environment variable:

   ```bash
   export PROVIDER_API_KEY=your_key
   ```

2. Add to `.env.local`:

   ```bash
   PROVIDER_API_KEY=your_key
   ```

3. Check `env_prefix` matches:

   ```python
   class MyConfig(ProviderConfig):
       api_key: str

       class Config:
           env_prefix = "MY_PROVIDER_"  # Expects MY_PROVIDER_API_KEY
   ```

### 7.2 Debugging Provider Discovery

**Enable debug logging:**

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("trading_api.providers")
logger.setLevel(logging.DEBUG)

# You'll see:
# DEBUG: Scanning directory: providers/
# INFO: Auto-discovered provider: google
# DEBUG: Lazy-loaded provider instance: google
```

**Manual discovery testing:**

```python
from pathlib import Path
from trading_api.shared import ProviderRegistry

registry = ProviderRegistry(providers_dir=Path("src/trading_api/providers"))
registry.auto_discover()

print("Discovered providers:", registry.list_providers())
print("Provider classes:", registry._provider_classes)

# Test capability resolution
from trading_api.models.common import CapabilitySpec
providers = await registry.get_providers([CapabilitySpec(name="auth")])
print("Matched providers:", [p.name for p in providers])
```

### 7.3 Logging Best Practices

**Add structured logging to your provider:**

```python
import logging

logger = logging.getLogger(__name__)

class MyProvider(Provider):
    async def verify_token(self, token: str) -> dict[str, Any]:
        logger.debug(f"Verifying token for provider: {self.name}")

        try:
            result = await self._call_external_api(token)
            logger.info(f"Token verified successfully: user={result.get('sub')}")
            return result
        except Exception as e:
            logger.error(f"Token verification failed: {e}", exc_info=True)
            raise
```

### 7.4 Provider Observability

Providers include structured logging for production debugging and health monitoring.

#### TWS Provider Logging

**Connection Lifecycle:**

- **Socket creation**: `WARNING` level logs when IBSocket is created/recreated
- **Connection state**: Tracks client_id to distinguish datafeed (1) vs. broker (2) connections

**Contract Resolution:**

- **Empty results**: `WARNING` logged when contract searches return no matches
- **Cache hits**: `DEBUG` level logs for cache performance monitoring (SQLite vs. memory)

**Market Data:**

- **Quote staleness**: `WARNING` logged when quotes are stale (>30 seconds old)
- **Quote liveness**: `DEBUG` level periodic logging (every 5s) to verify subscription health
- **Empty bars**: `WARNING` logged when historical bars request returns no data

**Error Classification:**

- **Rate limiting**: Error 162 now raises `ProviderException` (previously swallowed)
- **Not found**: Error 200/354 treated as informational (empty results, no exception)

#### Logging Strategy

| Component        | Event                | Level   | Frequency      | Purpose                       |
| ---------------- | -------------------- | ------- | -------------- | ----------------------------- |
| IBSocket         | Socket creation      | WARNING | Once           | Track connection lifecycle    |
| ContractTracker  | Empty search results | WARNING | Per request    | Alert to data availability    |
| QuoteTracker     | Quote staleness      | WARNING | Per access     | Alert to delayed updates      |
| QuoteTracker     | Quote liveness       | DEBUG   | Every 5s       | Verify subscription health    |
| DatafeedProvider | Empty bars response  | WARNING | Per request    | Distinguish no-data vs. error |
| TWSModels        | Error code 162       | ERROR   | Per occurrence | Rate limiting should retry    |

**Rationale**: `WARNING` level for lifecycle events and data quality issues enables passive monitoring without DEBUG verbosity. Periodic DEBUG logging (quote liveness) provides health signals for active debugging sessions.

#### Debugging Workflows

**Scenario 1: Quote Not Updating**

1. Check logs for "Quote staleness" warnings → indicates TWS is not sending updates
2. Check logs for "Quote is live" DEBUG messages → verify subscription active
3. Check IBSocket recreation warnings → may indicate connection instability

**Scenario 2: Empty Historical Data**

1. Check logs for "No bars returned" warning → includes ticker, duration, end time
2. Verify symbol is valid for requested time range
3. Check TWS error logs for rate limiting (error 162) or invalid requests

**Scenario 3: Contract Resolution Failures**

1. Check logs for IBSocket creation → verify connection established
2. Check ContractTracker cache search → verify SQLite persistence working
3. Check TWS error logs for "No security definition" (error 200)

**Cross-Reference**: See [CI-TROUBLESHOOTING.md](../../docs/CI-TROUBLESHOOTING.md) for CI-specific debugging patterns.

---

## 8. Best Practices

### 8.1 Design Principles

1. **Single Responsibility:** Each provider handles ONE external system
2. **Stateless:** Providers should not store request-specific state
3. **Fail-Fast:** Validate configuration at startup, not during requests
4. **Idempotent:** Same input should always produce same output
5. **Type-Safe:** Use strict types and MyPy validation

### 8.2 Security

1. **Never log secrets:**

   ```python
   # ❌ BAD
   logger.info(f"API key: {config.api_key}")

   # ✅ GOOD
   logger.info("API key configured")
   ```

2. **Use secrets management in production:**
   - Development: `.env.local` (git-ignored)
   - Production: Environment variables, Kubernetes Secrets, AWS Secrets Manager

3. **Validate tokens completely:**
   ```python
   # Validate: signature, expiration, audience, issuer
   claims = jwt.decode(
       token,
       public_key,
       algorithms=["RS256"],
       audience=config.client_id,
       issuer="https://accounts.google.com"
   )
   ```

### 8.3 Performance

1. **Cache expensive operations:**

   ```python
   from functools import lru_cache

   class MyProvider(Provider):
       @lru_cache(maxsize=128)
       def _get_public_key(self, key_id: str) -> str:
           # Cache public keys to avoid repeated fetches
           ...
   ```

2. **Lazy-load resources:**
   ```python
   class MyProvider(Provider):
       @property
       def api_client(self):
           if self._api_client is None:
               self._api_client = self._create_client()
           return self._api_client
   ```

### 8.4 Error Handling

Providers should use the **ProviderException** class for error handling. This integrates with the global exception handlers for proper HTTP/WebSocket responses.

> **Full Reference:** See [ERROR-MANAGEMENT.md](ERROR-MANAGEMENT.md) for complete error handling documentation.

#### Use ProviderException

```python
from trading_api.models.exceptions import ProviderException

class GoogleProvider(Provider, AuthCapability):
    async def verify_token(self, token: str) -> dict[str, Any]:
        try:
            # Validate with Google
            claims = await self._validate_with_google(token)
            return claims
        except InvalidTokenError:
            raise ProviderException(
                code="PROVIDER_AUTH_TOKEN_INVALID",
                message="Google token validation failed: invalid signature",
            )
        except TokenExpiredError:
            raise ProviderException(
                code="PROVIDER_AUTH_TOKEN_EXPIRED",
                message="Google token has expired",
            )
```

#### Error Code Convention

Provider error codes follow the pattern: `PROVIDER_{CAPABILITY}_{ERROR_TYPE}`

| Code Pattern              | HTTP Status | Description             |
| ------------------------- | ----------- | ----------------------- |
| `PROVIDER_*_NOT_FOUND`    | 404         | Resource not found      |
| `PROVIDER_AUTH_*_INVALID` | 401         | Authentication failure  |
| `PROVIDER_*_INVALID`      | 400         | Invalid input/request   |
| `PROVIDER_*` (other)      | 500         | Internal provider error |

**Examples:**

- `PROVIDER_AUTH_TOKEN_INVALID` → 401 Unauthorized
- `PROVIDER_DATAFEED_SYMBOL_NOT_FOUND` → 404 Not Found
- `PROVIDER_BROKER_ORDER_INVALID` → 400 Bad Request
- `PROVIDER_TWS_CONNECTION_ERROR` → 500 Internal Server Error

#### Real-World Example (GoogleProvider)

```python
# From providers/google/__init__.py
class GoogleProvider(Provider, AuthCapability):
    async def verify_token(self, token: str) -> dict[str, Any]:
        try:
            claims = await self._parse_and_verify_token(token)
        except InvalidClaimError as e:
            raise ProviderException(
                code="PROVIDER_AUTH_TOKEN_INVALID",
                message=f"Google token claims invalid: {e}",
            )

        # Validate audience
        if claims.get("aud") != self._config.client_id:
            raise ProviderException(
                code="PROVIDER_AUTH_AUDIENCE_MISMATCH",
                message="Token audience doesn't match configured client ID",
            )

        return {
            "sub": claims["sub"],
            "email": claims["email"],
            "email_verified": claims.get("email_verified", False),
        }
```

#### Handle Transient Errors with Retries

```python
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

class MyProvider(Provider):
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def _call_api(self, endpoint: str):
        # Automatically retries on transient failures
        try:
            response = await self._client.get(endpoint)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                raise  # Retry on server errors
            # Don't retry client errors
            raise ProviderException(
                code="PROVIDER_API_REQUEST_FAILED",
                message=f"API request failed: {e.response.status_code}",
            )
```

#### Logging Provider Errors

```python
import logging

logger = logging.getLogger(__name__)

class MyProvider(Provider):
    async def some_operation(self, param: str) -> Result:
        try:
            result = await self._external_api_call(param)
            return result
        except ExternalApiError as e:
            logger.error(
                "Provider operation failed",
                extra={
                    "provider": self.name,
                    "operation": "some_operation",
                    "error": str(e),
                },
                exc_info=True,
            )
            raise ProviderException(
                code="PROVIDER_OPERATION_FAILED",
                message=f"External API error: {e}",
            )
```

### 8.5 Documentation

**Document your provider thoroughly:**

```python
class MyProvider(Provider, MyCapability):
    """Brief one-line description.

    Detailed description of what this provider does, when to use it,
    and any important considerations.

    Configuration:
        API_KEY: Required API key from provider dashboard
        API_URL: Optional API endpoint (default: https://api.example.com)

    Environment Variables:
        MY_PROVIDER_API_KEY: Main authentication key
        MY_PROVIDER_TIMEOUT: Request timeout in seconds (default: 30)

    Examples:
        >>> config = MyProviderConfig(api_key="sk_test_123")
        >>> provider = MyProvider(config=config)
        >>> result = await provider.some_method()

    Security:
        - API keys must start with 'sk_'
        - All requests use TLS 1.3+
        - Tokens expire after 1 hour

    Performance:
        - Uses connection pooling (max 100 connections)
        - Caches public keys for 1 hour
        - Average latency: <100ms

    Error Handling:
        - Raises AuthenticationError for auth failures
        - Retries transient errors up to 3 times
        - Logs all errors with correlation IDs
    """
```

---

## 9. API Reference

### 9.1 Core Classes

#### CapabilitySpec

```python
@dataclass(frozen=True)
class CapabilitySpec:
    """Type-safe capability specification."""

    name: CapabilityName  # "auth", "broker", "datafeed", etc.
    version: str | None = None

    def matches(self, provider_capability: CapabilitySpec) -> bool:
        """Check if provider satisfies this requirement."""
```

#### Provider

```python
class Provider(ABC):
    """Abstract base class for all providers."""

    @classmethod
    @abstractmethod
    def provider_dir(cls) -> Path:
        """Return provider directory path."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return provider name."""

    @classmethod
    @abstractmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        """Return provided capabilities."""

    @property
    @abstractmethod
    def config(self) -> ProviderConfig:
        """Return provider configuration."""
```

#### ProviderConfig

```python
class ProviderConfig(BaseModel):
    """Base configuration for providers."""

    enabled: bool = True  # Can disable provider via config
```

#### ProviderRegistry

```python
class ProviderRegistry:
    """Registry for provider discovery and management."""

    def auto_discover(self) -> None:
        """Auto-discover providers from directory."""

    def register(self, provider_class: type[Provider], name: str) -> None:
        """Register provider class manually."""

    async def get_providers(
        self,
        required_capabilities: list[CapabilitySpec]
    ) -> list[Provider]:
        """Get provider instances for capabilities."""

    def list_providers(self) -> list[str]:
```

### 9.2 Capability Interfaces

#### AuthCapability

```python
class AuthCapability(ABC):
    """Authentication capability interface."""

    @abstractmethod
    async def verify_token(self, token: str) -> dict[str, Any]:
        """Verify authentication token.

        Returns:
            dict with claims: sub, email, name, picture, email_verified

        Raises:
            AuthenticationError: If verification fails
        """
```

### 9.3 Exceptions

> **Full Reference:** See [ERROR-MANAGEMENT.md](ERROR-MANAGEMENT.md) for complete exception hierarchy and handlers.

Provider-related exceptions are part of the unified exception hierarchy:

```python
# models/exceptions.py
class TradingApiException(Exception):
    """Base exception with error code."""
    code: str
    message: str

class ProviderException(TradingApiException):
    """Provider layer errors (external integrations)."""
    # Code pattern: PROVIDER_{CAPABILITY}_{ERROR_TYPE}
```

**Usage in providers:**

```python
from trading_api.models.exceptions import ProviderException

# Authentication provider errors
raise ProviderException(
    code="PROVIDER_AUTH_TOKEN_INVALID",
    message="Token signature verification failed"
)

# Datafeed provider errors
raise ProviderException(
    code="PROVIDER_DATAFEED_SYMBOL_NOT_FOUND",
    message=f"Symbol {symbol} not found"
)
```

**HTTP Status Mapping:**

| Code Pattern     | HTTP Status |
| ---------------- | ----------- |
| `*_NOT_FOUND`    | 404         |
| `*AUTH*_INVALID` | 401         |
| `*_INVALID`      | 400         |
| Other            | 500         |

**Legacy Exceptions (deprecated):**

The following exceptions are deprecated in favor of `ProviderException`:

```python
# ❌ DEPRECATED - Do not use in new code
class AuthenticationError(ProviderError):
    """Use ProviderException with PROVIDER_AUTH_* code instead."""

class ProviderNotFoundError(ProviderError):
    """Use CommonException with COMMON_PROVIDER_NOT_FOUND instead."""

class CapabilityNotFoundError(ProviderError):
    """Use CommonException with COMMON_CAPABILITY_NOT_FOUND instead."""
```

---

## Quick Reference Card

**Creating a Provider:**

1. Create directory: `providers/myprovider/`
2. Create config: `models/myprovider/config.py`
3. Implement provider: `providers/myprovider/__init__.py`
4. Add tests: `providers/myprovider/tests/`
5. Set env vars: `.env.local`
6. Run tests: `make test`

**Real-World Example:**

See **[TWS Provider Implementation Guide](../src/trading_api/providers/tws/README.md)** for a production-ready provider implementing:

- Three-layer architecture (TWSDatafeedProvider → TWSClient → IBSocket)
- DatafeedCapability interface (full streaming implementation)
- BrokerCapability interface (order placement, brackets via OCA groups)
- Business key tracking system for async request/response correlation
- StreamData dataclass for typed data accumulation
- CachedContract for contract caching with lazy upgrade pattern
- Comprehensive domain mappers

**Note:** `TWSBrokerProvider` uses in-memory state for position/order tracking while integrating with real TWS for order execution. Features like `edit_position_brackets()` use OCA (One-Cancels-All) groups for proper bracket order linking.

**File Template:**

```python
# providers/myprovider/__init__.py
from pathlib import Path
from trading_api.models.common import CapabilitySpec
from trading_api.shared import Provider
from trading_api.capabilities.auth import AuthCapability

class MyproviderProvider(Provider, AuthCapability):
    @classmethod
    def provider_dir(cls) -> Path:
        return Path(__file__).parent

    @property
    def name(self) -> str:
        return "myprovider"

    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        return [CapabilitySpec(name="auth")]

    @property
    def config(self):
        return self._config

    async def verify_token(self, token: str):
        # Your implementation
        ...
```

---

**Last Updated**: January 4, 2026  
**Questions?** Check [ARCHITECTURE.md](../../docs/ARCHITECTURE.md) or raise an issue.
