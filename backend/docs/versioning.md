# API Versioning Strategy

This document outlines the versioning strategy for the Trading API.

## Overview

The Trading API uses **URL-based versioning** to ensure backwards compatibility and smooth transitions for API consumers.

## Version Format

- **Pattern**: `/api/{version}/`
- **Current**: `/api/v1/`
- **Future**: `/api/v2/`, `/api/v3/`, etc.

## Version Lifecycle

### 1. **Stable**
- Fully supported and recommended for production use
- No breaking changes will be introduced
- Bug fixes and minor enhancements only

### 2. **Deprecated**
- Still functional but not recommended for new development
- Will include deprecation warnings
- Sunset date announced

### 3. **Sunset**
- Version is no longer supported
- Endpoints return 410 Gone status

## Current Versions

### Version 1 (v1) - Stable
- **Release Date**: 2025-10-04
- **Status**: Stable
- **Base URL**: `/api/v1/`
- **Features**:
  - Health check endpoint
  - Version information endpoints
  - OpenAPI documentation

### Version 2 (v2) - Planned
- **Status**: Planned
- **Base URL**: `/api/v2/`
- **Breaking Changes**:
  - Authentication required for all endpoints
  - New response format for error messages
  - Renamed health endpoint to status
  - Enhanced error handling structure

## API Endpoints

### Version Information
```http
GET /api/v1/versions
```
Returns information about all available API versions.

```http
GET /api/v1/version
```
Returns information about the current API version.

### Health Check
```http
GET /api/v1/health
```
Returns service health status with version information.

## Response Examples

### Version Information Response
```json
{
  "current_version": "v1",
  "available_versions": [
    {
      "version": "v1",
      "release_date": "2025-10-04",
      "status": "stable",
      "breaking_changes": [],
      "deprecation_notice": null,
      "sunset_date": null
    },
    {
      "version": "v2",
      "release_date": "TBD",
      "status": "planned",
      "breaking_changes": [
        "Authentication required for all endpoints",
        "New response format for error messages",
        "Renamed health endpoint to status"
      ],
      "deprecation_notice": null,
      "sunset_date": null
    }
  ],
  "documentation_url": "https://api.trading.com/docs",
  "support_contact": "support@trading.com"
}
```

### Health Check Response
```json
{
  "status": "ok",
  "message": "Trading API is running",
  "timestamp": "2025-10-04T14:30:00Z",
  "api_version": "v1",
  "version_info": {
    "version": "v1",
    "release_date": "2025-10-04",
    "status": "stable",
    "deprecation_notice": null
  }
}
```

## Client Implementation

### Version-Aware Client
```typescript
// Vue.js TypeScript Client Example
import { Configuration, HealthApi, VersionsApi } from '@/api'

class TradingApiClient {
  private config: Configuration
  private healthApi: HealthApi
  private versionsApi: VersionsApi

  constructor(baseUrl: string, version: string = 'v1') {
    this.config = new Configuration({
      basePath: `${baseUrl}/api/${version}`
    })
    this.healthApi = new HealthApi(this.config)
    this.versionsApi = new VersionsApi(this.config)
  }

  async checkHealth() {
    const response = await this.healthApi.getHealthStatus()
    return response.data
  }

  async getVersionInfo() {
    const response = await this.versionsApi.getAPIVersions()
    return response.data
  }

  // Check for deprecation warnings
  async checkForDeprecation() {
    const versionInfo = await this.getVersionInfo()
    const currentVersion = versionInfo.available_versions.find(
      v => v.version === versionInfo.current_version
    )

    if (currentVersion?.deprecation_notice) {
      console.warn('API Deprecation Warning:', currentVersion.deprecation_notice)
    }

    return currentVersion
  }
}
```

### Python Client Example
```python
import httpx
from typing import Optional

class TradingApiClient:
    def __init__(self, base_url: str, version: str = "v1"):
        self.base_url = f"{base_url}/api/{version}"
        self.client = httpx.AsyncClient()

    async def check_health(self):
        response = await self.client.get(f"{self.base_url}/health")
        return response.json()

    async def get_version_info(self):
        response = await self.client.get(f"{self.base_url}/versions")
        return response.json()

    async def check_for_deprecation(self) -> Optional[str]:
        version_info = await self.get_version_info()
        current_version = next(
            (v for v in version_info["available_versions"]
             if v["version"] == version_info["current_version"]),
            None
        )

        if current_version and current_version.get("deprecation_notice"):
            return current_version["deprecation_notice"]

        return None
```

## Migration Guidelines

### When a New Version is Released

1. **Review Breaking Changes**: Check `/api/v1/versions` for detailed changes
2. **Test Compatibility**: Run your tests against the new version
3. **Plan Migration**: Schedule updates based on deprecation timeline
4. **Update Clients**: Generate new clients from updated OpenAPI spec
5. **Monitor**: Watch for deprecation notices in current version

### Handling Deprecation

1. **Subscribe to Notifications**: Monitor `/api/v1/versions` endpoint
2. **Update Code**: Address breaking changes before sunset date
3. **Test Thoroughly**: Validate all functionality with new version
4. **Deploy Gradually**: Use feature flags for gradual rollout

## Best Practices

### For API Consumers
- Always specify the version in your requests
- Regularly check for deprecation notices
- Test against beta versions before they become stable
- Have a migration plan for version upgrades

### For API Development
- Never introduce breaking changes within a version
- Provide advance notice for deprecations (minimum 6 months)
- Maintain clear documentation of changes
- Support previous version during transition period

## Support Policy

- **Current Version**: Full support and active development
- **Previous Version**: Security fixes and critical bugs only
- **Deprecated Versions**: Limited support, scheduled for sunset
- **Sunset Versions**: No support, returns 410 Gone

## Contact

For questions about API versioning:
- Documentation: `/api/v1/docs`
- Support: support@trading.com
- Status: `/api/v1/health`
