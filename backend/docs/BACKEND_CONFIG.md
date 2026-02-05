# Backend Configuration Management

**Status**: ✅ Production Ready  
**Last Updated**: January 2026  
**Version**: 1.0.0

## Table of Contents

- [Philosophy](#philosophy)
- [The SSOT Pattern](#the-ssot-pattern)
- [Settings Class Architecture](#settings-class-architecture)
- [Environment File Conventions](#environment-file-conventions)
- [Dual-Consumption Model](#dual-consumption-model)
- [Adding New Configuration](#adding-new-configuration)
- [Anti-Patterns (PROHIBITED)](#anti-patterns-prohibited)
- [Configuration Categories](#configuration-categories)
- [Gaps to Address](#gaps-to-address)

---

## Philosophy

Our configuration management follows the **12-Factor App methodology** (Factor III: Store config in the environment):

> **Configuration** = anything that is likely to vary between deploys (staging, production, developer environments).

### Core Principles

| Principle                  | Description                                                  |
| -------------------------- | ------------------------------------------------------------ |
| **Single Source of Truth** | All runtime configuration lives in `.env`                    |
| **Type Safety**            | All config values have explicit Python types with validation |
| **Fail-Fast**              | Invalid configuration causes immediate startup failures      |
| **No Secrets in Code**     | Credentials and keys loaded from environment only            |
| **Environment Parity**     | Same config mechanism across dev/staging/prod                |

### What IS Configuration

- Database connection parameters (host, port, credentials)
- External service URLs and API keys
- Feature toggles that vary by environment
- Timeouts and pool sizes
- File paths for secrets/keys

### What is NOT Configuration

- Business logic constants (use code)
- Algorithm parameters that don't change between environments (use code)
- Static mappings (use code constants)

---

## The SSOT Pattern

The `.env` file is the **Single Source of Truth (SSOT)** for all runtime configuration:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         .env (SSOT)                                      │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ DATASTORE_POSTGRES_USER=trader                                     │  │
│  │ DATASTORE_POSTGRES_PASSWORD=trader_dev                             │  │
│  │ DATASTORE_POSTGRES_HOST=localhost                                  │  │
│  │ DATASTORE_POSTGRES_PORT=5433                                       │  │
│  │ DATASTORE_POSTGRES_DB=trader_pro                                   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────┬───────────────────────────────┬───────────────────┘
                      │                               │
                      ▼                               ▼
        ┌─────────────────────────┐     ┌─────────────────────────────────┐
        │   Python Application    │     │     Docker Compose               │
        │                         │     │                                  │
        │  from pydantic_settings │     │  environment:                    │
        │  class Settings(...)    │     │    POSTGRES_USER: ${...:-trader} │
        │                         │     │    POSTGRES_DB: ${...:-trader_pro}│
        │  settings.postgres_dsn  │     │                                  │
        └─────────────────────────┘     └─────────────────────────────────┘
```

### Why SSOT Matters

| Without SSOT                                    | With SSOT                     |
| ----------------------------------------------- | ----------------------------- |
| 🔴 Config drift between Python and Docker       | ✅ Single file, both consume  |
| 🔴 Different variable names in different places | ✅ Identical names everywhere |
| 🔴 "Works on my machine" issues                 | ✅ Reproducible environments  |
| 🔴 Duplicate defaults to maintain               | ✅ One default per variable   |

---

## Settings Class Architecture

All configuration is accessed through the centralized `Settings` class:

```python
# backend/src/trading_api/shared/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Type hints provide validation
    DATASTORE_POSTGRES_HOST: str = "localhost"
    DATASTORE_POSTGRES_PORT: int = 5433  # ← int, not str
    DATASTORE_POSTGRES_POOL_OPEN_TIMEOUT: float = 30.0

    # Path resolution
    JWT_PRIVATE_KEY_PATH: Path = Path(".local/secrets/jwt_private.pem")

    # List types supported
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # Load from .env file
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Derived values as properties
    @property
    def postgres_dsn(self) -> str:
        """Build PostgreSQL DSN from components or use explicit DSN."""
        if self.DATASTORE_POSTGRES_DSN:
            return self.DATASTORE_POSTGRES_DSN
        return (
            f"postgresql://{self.DATASTORE_POSTGRES_USER}:"
            f"{self.DATASTORE_POSTGRES_PASSWORD}@"
            f"{self.DATASTORE_POSTGRES_HOST}:{self.DATASTORE_POSTGRES_PORT}/"
            f"{self.DATASTORE_POSTGRES_DB}"
        )

# Singleton instance - import this everywhere
settings = Settings()
```

### Key Features

| Feature                 | Description                     | Example            |
| ----------------------- | ------------------------------- | ------------------ |
| **Type Validation**     | Pydantic validates on load      | `PORT: int = 8000` |
| **Default Values**      | Development defaults in code    | Safe for local dev |
| **Property Derivation** | Computed values from primitives | `postgres_dsn`     |
| **Path Resolution**     | Relative → absolute conversion  | `resolve_paths()`  |
| **Secret Loading**      | Read files at property access   | `jwt_private_key`  |

### Usage Pattern

```python
# ✅ CORRECT: Import settings singleton
from trading_api.shared.config import settings

dsn = settings.postgres_dsn
timeout = settings.DATASTORE_POSTGRES_POOL_OPEN_TIMEOUT

# ✅ CORRECT: Type-safe access
port: int = settings.API_PORT  # Already an int, no conversion needed
```

---

## Environment File Conventions

### File Structure

| File           | Purpose                                    | Git Status     |
| -------------- | ------------------------------------------ | -------------- |
| `.env`         | Active configuration (your local settings) | **gitignored** |
| `.env.example` | Template with documented defaults          | **committed**  |

### Variable Naming Convention

```
{COMPONENT}_{SUBSYSTEM}_{SETTING}

Examples:
  DATASTORE_POSTGRES_HOST      Component=DATASTORE, Subsystem=POSTGRES, Setting=HOST
  JWT_PRIVATE_KEY_PATH         Component=JWT, Setting=PRIVATE_KEY_PATH
  CORS_ORIGINS                 Component=CORS, Setting=ORIGINS
```

### Documentation in `.env.example`

```bash
# Environment Variables Configuration
# Copy this file to .env and modify values as needed
# The .env file is the Single Source of Truth (SSOT) for configuration

# PostgreSQL Datastore Configuration
# These values are loaded by both Python (pydantic-settings) and docker-compose
# Option 1: Full DSN (takes precedence if set)
# DATASTORE_POSTGRES_DSN=postgresql://trader:trader_dev@localhost:5433/trader_pro

# Option 2: Individual variables (recommended for docker-compose compatibility)
DATASTORE_POSTGRES_USER=trader
DATASTORE_POSTGRES_PASSWORD=trader_dev
DATASTORE_POSTGRES_HOST=localhost
DATASTORE_POSTGRES_PORT=5433
DATASTORE_POSTGRES_DB=trader_pro
```

---

## Dual-Consumption Model

Both Python and Docker Compose read from the same `.env` file:

### Python (pydantic-settings)

```python
# Automatic loading via SettingsConfigDict
model_config = SettingsConfigDict(env_file=".env")

# Access
settings.DATASTORE_POSTGRES_HOST  # → "localhost"
```

### Docker Compose

```yaml
# docker-compose.dev.yml
services:
  postgres:
    environment:
      POSTGRES_USER: ${DATASTORE_POSTGRES_USER:-trader}
      POSTGRES_PASSWORD: ${DATASTORE_POSTGRES_PASSWORD:-trader_dev}
      POSTGRES_DB: ${DATASTORE_POSTGRES_DB:-trader_pro}
    ports:
      - "${DATASTORE_POSTGRES_PORT:-5433}:5432"
```

### Critical Rule: Defaults MUST Match

The default values in `docker-compose.yml` **MUST** match the defaults in `Settings`:

```python
# config.py
DATASTORE_POSTGRES_PORT: int = 5433  # ← Default: 5433
```

```yaml
# docker-compose.dev.yml
- "${DATASTORE_POSTGRES_PORT:-5433}:5432" # ← Default: 5433 (MUST match)
```

If these diverge, you get "works in Python, fails in Docker" bugs.

---

## Adding New Configuration

### Mandatory Checklist

When adding new configuration, **ALL steps are required**:

- [ ] **1. Add to `Settings` class** (`shared/config.py`)

  ```python
  # With type hint, default, and descriptive comment
  MY_NEW_SETTING: str = "default_value"  # Description of what this controls
  ```

- [ ] **2. Add to `.env.example`** (root directory)

  ```bash
  # Description of the setting
  MY_NEW_SETTING=default_value
  ```

- [ ] **3. If Docker needs it**, add to `docker-compose.dev.yml`

  ```yaml
  environment:
    MY_NEW_SETTING: ${MY_NEW_SETTING:-default_value}
  ```

- [ ] **4. Document in relevant README** with cross-reference

  ```markdown
  See [BACKEND_CONFIG.md](../docs/BACKEND_CONFIG.md) for configuration details.
  ```

- [ ] **5. Use via `settings` object** (never `os.environ`)
  ```python
  from trading_api.shared.config import settings
  value = settings.MY_NEW_SETTING
  ```

### Example: Adding a New Timeout Setting

```python
# 1. config.py
class Settings(BaseSettings):
    # ... existing settings ...

    # Redis connection timeout in seconds
    REDIS_CONNECTION_TIMEOUT: float = 5.0
```

```bash
# 2. .env.example
# Redis Configuration
REDIS_CONNECTION_TIMEOUT=5.0
```

```yaml
# 3. docker-compose.dev.yml (if Redis container needs it)
redis:
  environment:
    REDIS_TIMEOUT: ${REDIS_CONNECTION_TIMEOUT:-5.0}
```

```python
# 5. Usage in code
from trading_api.shared.config import settings

async def connect_redis():
    return await aioredis.from_url(
        settings.REDIS_URL,
        socket_timeout=settings.REDIS_CONNECTION_TIMEOUT,  # ✅
    )
```

---

## Anti-Patterns (PROHIBITED)

### 🚫 Direct `os.environ` Access

```python
# ❌ PROHIBITED - bypasses type validation and centralized config
import os
host = os.environ.get("DATASTORE_POSTGRES_HOST", "localhost")

# ✅ CORRECT - use settings singleton
from trading_api.shared.config import settings
host = settings.DATASTORE_POSTGRES_HOST
```

### 🚫 Hardcoded Environment-Specific Values

```python
# ❌ PROHIBITED - hardcoded value that should be configurable
POOL_SIZE = 10  # What if prod needs 50?

# ✅ CORRECT - make it configurable
class Settings(BaseSettings):
    DATASTORE_POSTGRES_POOL_MAX_SIZE: int = 10
```

### 🚫 Configuration in Separate Files

```python
# ❌ PROHIBITED - creating parallel config files
# config/database.yaml, config/redis.yaml, etc.

# ✅ CORRECT - all config in .env, accessed via Settings
```

### 🚫 Mismatched Defaults

```python
# ❌ PROHIBITED - different defaults in different places
# config.py
PORT: int = 8000

# docker-compose.yml
- "${PORT:-8080}:8000"  # Mismatch! Should be 8000

# ✅ CORRECT - identical defaults everywhere
```

### 🚫 Undocumented Environment Variables

```python
# ❌ PROHIBITED - adding to Settings without .env.example
class Settings(BaseSettings):
    SECRET_THING: str = "hidden"  # Not in .env.example!

# ✅ CORRECT - always update .env.example with comments
```

### 🚫 Untyped Configuration

```python
# ❌ PROHIBITED - no type hint
class Settings(BaseSettings):
    SOME_VALUE = "default"  # Type is inferred, not explicit

# ✅ CORRECT - explicit type hint
class Settings(BaseSettings):
    SOME_VALUE: str = "default"
```

---

## Configuration Categories

Current configuration groups in `Settings`:

| Category          | Prefix                | Variables                                     | Purpose               |
| ----------------- | --------------------- | --------------------------------------------- | --------------------- |
| **API Server**    | `API_`                | `API_PREFIX`, `API_PORT`, `DEFAULT_TIMEOUT`   | FastAPI server config |
| **PostgreSQL**    | `DATASTORE_POSTGRES_` | Host, port, user, password, DB, pool settings | Database connection   |
| **JWT Auth**      | `JWT_`                | `JWT_ALGORITHM`, key paths, token expiry      | Authentication tokens |
| **CORS**          | `CORS_`               | `CORS_ORIGINS`, `CORS_ALLOW_CREDENTIALS`      | Cross-origin requests |
| **Cookie**        | `COOKIE_`             | `COOKIE_SECURE`                               | Session cookies       |
| **Internal Auth** | `INTERNAL_`           | HMAC key path, signature TTL                  | Inter-module auth     |
| **Google OAuth**  | `GOOGLE_`             | `GOOGLE_CLIENT_ID`                            | OAuth provider        |

### PostgreSQL Configuration Reference

| Variable                                    | Type          | Default      | Description                 |
| ------------------------------------------- | ------------- | ------------ | --------------------------- |
| `DATASTORE_POSTGRES_DSN`                    | `str \| None` | `None`       | Full DSN (takes precedence) |
| `DATASTORE_POSTGRES_USER`                   | `str`         | `trader`     | Database username           |
| `DATASTORE_POSTGRES_PASSWORD`               | `str`         | `trader_dev` | Database password           |
| `DATASTORE_POSTGRES_HOST`                   | `str`         | `localhost`  | Database host               |
| `DATASTORE_POSTGRES_PORT`                   | `int`         | `5433`       | Database port               |
| `DATASTORE_POSTGRES_DB`                     | `str`         | `trader_pro` | Database name               |
| `DATASTORE_POSTGRES_POOL_MAX_SIZE`          | `int`         | `10`         | Max pool connections        |
| `DATASTORE_POSTGRES_POOL_RECONNECT_TIMEOUT` | `float`       | `5.0`        | Per-attempt timeout (s)     |
| `DATASTORE_POSTGRES_POOL_OPEN_TIMEOUT`      | `float`       | `30.0`       | Total startup timeout (s)   |

---

## Gaps to Address

Planned improvements for future configuration needs:

| Gap                          | Priority | Notes                                 |
| ---------------------------- | -------- | ------------------------------------- |
| **Redis configuration**      | HIGH     | When caching layer added              |
| **External API keys**        | MEDIUM   | TWS API, market data providers        |
| **Feature flags**            | MEDIUM   | Environment-based feature toggles     |
| **Environment profiles**     | LOW      | Staging/production-specific overrides |
| **Secrets management**       | LOW      | Vault/AWS Secrets Manager integration |
| **Configuration validation** | LOW      | Cross-field validation rules          |

### Future Pattern: External API Keys

```python
# Proposed pattern for sensitive external APIs
class Settings(BaseSettings):
    # Key path pattern (key loaded at access time)
    TWS_API_KEY_PATH: Path | None = None

    @property
    def tws_api_key(self) -> str | None:
        """Load TWS API key from file if configured."""
        if self.TWS_API_KEY_PATH and self.TWS_API_KEY_PATH.exists():
            return self.TWS_API_KEY_PATH.read_text().strip()
        return None
```

---

## Related Documentation

- [shared/config.py](../src/trading_api/shared/config.py) - Settings implementation
- [.env.example](../../.env.example) - Configuration template
- [docker-compose.dev.yml](../docker-compose.dev.yml) - Docker configuration
- [postgres/README.md](../src/trading_api/datastores/postgres/README.md) - PostgreSQL-specific config
- [DEVELOPMENT.md](../../docs/DEVELOPMENT.md) - Development setup
