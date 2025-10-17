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

## REST API Client

### Generation Command

```bash
cd frontend
make client-generate
# Or
npm run client:generate
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
# Generate types from AsyncAPI
node scripts/generate-ws-types.mjs
```

This runs automatically during `make client-generate`.

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
  "prebuild": "npm run client:generate",
  "predev": "npm run client:generate"
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
      run: make client-generate
      working-directory: frontend
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

The frontend Makefile adapts to CI environments:

```makefile
lint:
ifeq ($(CI),true)
	@echo "CI mode: Skipping client generation"
else
	@$(MAKE) client-generate
endif
	npm run lint
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
cd frontend
rm -rf src/clients/*-generated
make client-generate --verbose
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
