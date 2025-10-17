# API Client Generation

**Status**: ✅ Implemented | **Mode**: Offline Generation

## Overview

The Trading Pro frontend automatically generates type-safe TypeScript clients from backend API specifications using an **offline generation** approach that doesn't require a running backend server.

## How It Works

### Offline Generation Mode

```bash
Frontend Build → Export Backend Specs → Generate Clients → Build/Dev
```

**Key Features:**

- ✅ No backend server needed during client generation
- ✅ Fast spec export (< 1 second)
- ✅ Reliable in all environments (local, CI, production)
- ✅ Type-safe TypeScript clients auto-generated

### Generation Process

```
┌─────────────────────────────────────────┐
│ Frontend: make client-generate          │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ Backend: make export-openapi-offline    │
│ • Runs scripts/export_openapi.py        │
│ • Generates openapi.json                │
│ • Generates asyncapi.json               │
│ • No server startup needed              │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ Frontend: Generate TypeScript Clients   │
│ • REST Client (OpenAPI spec)            │
│ • WebSocket Types (AsyncAPI spec)       │
└─────────────────────────────────────────┘
```

### REST API Client

### Generation Command

```bash
# From project root
make generate-openapi-client

# Or from frontend directory
make generate-openapi-client
```

### Generated Files

```
frontend/src/clients/trader-client-generated/
├── api/           # API client classes
├── models/        # TypeScript types
├── configuration.ts
└── index.ts       # Unified exports
```

### Usage

```typescript
import { HealthApi, VersioningApi } from "@/clients/trader-client-generated";

// Use generated clients
const healthApi = new HealthApi();
const health = await healthApi.getHealth();
```

## WebSocket Client

### Generation Command

WebSocket types are automatically generated from AsyncAPI specification:

```bash
# From project root
make generate-asyncapi-types

# Or from frontend directory
make generate-asyncapi-types
```

### Generated Files

```
frontend/src/clients/
└── ws-types-generated/     # TypeScript interfaces
    └── index.ts            # Bar, BarsSubscriptionRequest, etc.
```

### Usage

```typescript
import { WebSocketClientBase } from "@/plugins/wsClientBase";
import type {
  Bar,
  BarsSubscriptionRequest,
} from "@/clients/ws-types-generated";

const client = new WebSocketClientBase<BarsSubscriptionRequest, Bar>("bars");
await client.subscribe({ symbol: "AAPL", resolution: "1" }, (bar: Bar) =>
  console.log("New bar:", bar)
);
```

## Automatic Integration

### NPM Scripts

Client generation runs automatically before build and dev:

```json
{
  # Client generation is now handled by Makefiles
  # Run: make generate-openapi-client && make generate-asyncapi-types
}
```

### CI/CD Integration

```yaml
# Frontend job depends on backend to access spec generation
frontend:
  needs: [backend]
  steps:
    - name: Install backend deps
      run: make install-ci
      working-directory: backend

    - name: Generate clients
      run: make generate-openapi-client && make generate-asyncapi-types
```

## Offline vs Live Mode

### Offline Mode (Current - Default)

**Advantages:**

- ✅ No server startup delays
- ✅ Works in all environments
- ✅ No network connectivity needed
- ✅ Consistent across local/CI
- ✅ Fast (< 1 second)

**Backend Script:**

```python
# backend/scripts/export_openapi.py
openapi_schema = apiApp.openapi()
asyncapi_schema = wsApp.asyncapi()
# Write to files
```

### Live Mode (Deprecated)

Previously required running backend server to download specs. No longer used.

## Environment Variables

```bash
# Optional: Override API base path
export TRADER_API_BASE_PATH="/api"

# Optional: Skip backend spec regeneration
export SKIP_SPEC_GENERATION="true"
```

## CI-Aware Behavior

Client generation is now handled explicitly via Makefile targets:

```makefile
# Generate OpenAPI client
generate-openapi-client:
	cd frontend && ./scripts/generate-openapi-client.sh

# Generate AsyncAPI types
generate-asyncapi-types:
	cd frontend && ./scripts/generate-asyncapi-types.sh
```

## Troubleshooting

### Specs Not Generated

```bash
cd backend
make export-openapi-offline
# Check for openapi.json and asyncapi.json
```

### Client Generation Fails

```bash
# Clean and regenerate
rm -rf frontend/src/clients/*-generated
make generate-openapi-client
make generate-asyncapi-types
```

### Type Errors After Generation

```bash
cd frontend
npm run type-check
# Fix any import issues in services
```

## Related Documentation

- **Backend Spec Export**: See `backend/Makefile` (`export-openapi-offline` target)
- **WebSocket Clients**: See `docs/WEBSOCKET-CLIENTS.md`
- **Architecture**: See `ARCHITECTURE.md`
