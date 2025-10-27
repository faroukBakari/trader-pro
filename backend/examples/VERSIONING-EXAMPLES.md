# API Versioning Examples

This directory contains examples of how to work with different API versions.

## Client Generation

When generating clients, you can target specific API versions:

```bash
# Generate client for current version (v1)
make clients

# The generated clients will use the /api/v1 endpoints by default
```

## Version-Aware Requests

### cURL Examples

```bash
# Get version information
curl http://localhost:8000/api/v1/versions

# Get current version details
curl http://localhost:8000/api/v1/version

# Health check with version info
curl http://localhost:8000/api/v1/health

# API root information
curl http://localhost:8000/
```

### JavaScript/TypeScript

```typescript
// Using the generated client
import { Configuration, HealthApi, VersionsApi } from './clients/vue-client'

const config = new Configuration({
  basePath: 'http://localhost:8000/api/v1'
})

const healthApi = new HealthApi(config)
const versionsApi = new VersionsApi(config)

// Check health with version info
const health = await healthApi.getHealthStatus()
console.log(`API Version: ${health.data.api_version}`)

// Get all version information
const versions = await versionsApi.getAPIVersions()
console.log('Available versions:', versions.data.available_versions)
```

### Python

```python
import asyncio
import httpx

async def check_api_versions():
    async with httpx.AsyncClient() as client:
        # Get version information
        response = await client.get("http://localhost:8000/api/v1/versions")
        versions = response.json()

        print(f"Current version: {versions['current_version']}")

        for version in versions['available_versions']:
            print(f"Version {version['version']}: {version['status']}")
            if version['deprecation_notice']:
                print(f"  Deprecation: {version['deprecation_notice']}")

# Run the example
asyncio.run(check_api_versions())
```

## Migration Scenarios

### Scenario 1: Checking for Deprecation

```typescript
async function checkDeprecation() {
  const versionsApi = new VersionsApi(config)
  const versionInfo = await versionsApi.getAPIVersions()

  const currentVersion = versionInfo.data.available_versions.find(
    v => v.version === versionInfo.data.current_version
  )

  if (currentVersion?.deprecation_notice) {
    console.warn('⚠️ API Deprecation Warning:', currentVersion.deprecation_notice)
    console.warn('⚠️ Sunset Date:', currentVersion.sunset_date)
  }
}
```

### Scenario 2: Preparing for V2 Migration

```typescript
// When v2 becomes available, you'll need to update your client configuration
const v2Config = new Configuration({
  basePath: 'http://localhost:8000/api/v2',
  // v2 will require authentication
  apiKey: 'your-api-key'
})

// The health endpoint will be renamed to 'status' in v2
const statusApi = new StatusApi(v2Config) // hypothetical v2 client
```

## Testing Different Versions

### Jest/Vitest Tests

```typescript
describe('API Versioning', () => {
  test('should include version information in health response', async () => {
    const health = await healthApi.getHealthStatus()

    expect(health.data.api_version).toBe('v1')
    expect(health.data.version_info.status).toBe('stable')
  })

  test('should provide version metadata', async () => {
    const versions = await versionsApi.getAPIVersions()

    expect(versions.data.current_version).toBe('v1')
    expect(versions.data.available_versions).toHaveLength(2)
  })
})
```

### Python Tests

```python
import pytest
import httpx

@pytest.mark.asyncio
async def test_version_consistency():
    async with httpx.AsyncClient() as client:
        # Get version from different endpoints
        health = await client.get("http://localhost:8000/api/v1/health")
        versions = await client.get("http://localhost:8000/api/v1/versions")

        health_data = health.json()
        versions_data = versions.json()

        # Version should be consistent across endpoints
        assert health_data["api_version"] == versions_data["current_version"]
```

## Error Handling

### Version Not Found

```typescript
try {
  // Trying to access a non-existent version
  const response = await fetch('http://localhost:8000/api/v99/health')
  if (response.status === 404) {
    console.error('API version not found')
  }
} catch (error) {
  console.error('Version access error:', error)
}
```

### Sunset Version

```typescript
try {
  // Accessing a sunset version (future scenario)
  const response = await fetch('http://localhost:8000/api/v0/health')
  if (response.status === 410) {
    console.error('API version has been sunset')
    // Redirect to current version
    window.location.href = '/api/v1/docs'
  }
} catch (error) {
  console.error('Sunset version error:', error)
}
```
