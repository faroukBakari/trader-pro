# Environment Variables Configuration

**Last Updated:** November 11, 2025

Environment variables for configuring ports, URLs, and settings across development, testing, and production.

## Environment Variables

### Backend

- **`BACKEND_PORT`** (default: `8000`) - FastAPI server port
- **`ENABLED_MODULES`** (default: all modules) - Comma-separated list of modules to load
  - Example: `ENABLED_MODULES=broker,datafeed`
  - Used for: Module-specific deployment, testing isolated modules
  - Available modules: `broker`, `datafeed`
- Used by: Backend Makefile, dev scripts, CI/CD

### Frontend

- **`FRONTEND_PORT`** (default: `5173`) - Vite dev server port
- **`VITE_API_URL`** (default: `http://localhost:8000`) - API base URL
  - Must start with `VITE_` to be accessible in frontend code
  - Used by: Vite proxy, client generation
- **`FRONTEND_URL`** (default: `http://localhost:5173`) - Frontend URL
  - Used by: Smoke tests, integration tests

### Bar Broadcaster

- **`BAR_BROADCASTER_ENABLED`** (default: `true`) - Enable/disable broadcaster
- **`BAR_BROADCASTER_INTERVAL`** (default: `2.0`) - Broadcast interval (seconds)
- **`BAR_BROADCASTER_SYMBOLS`** (default: `AAPL,GOOGL,MSFT`) - Symbols to broadcast
- **`BAR_BROADCASTER_RESOLUTIONS`** (default: `1`) - Resolutions (comma-separated)

### Mock Services

- **`VITE_USE_MOCK_BROKER`** (default: `true`) - Use mock broker service
- **`VITE_USE_MOCK_DATAFEED`** (default: `true`) - Use mock datafeed service

## Configuration Files

### `.env.example` (Git-tracked template)

```bash
# Ports
BACKEND_PORT=8000
FRONTEND_PORT=5173

# URLs
VITE_API_URL=http://localhost:8000
FRONTEND_URL=http://localhost:5173
```

### `.env.local` (Local overrides, not tracked)

Create `.env.local` for custom configurations:

```bash
cp .env.example .env.local
# Edit .env.local with your custom settings
```

**Note:** The project does not use a `.env` file by default. Use system environment variables or `.env.local` for customization.

## Client Generation

The frontend uses an efficient file-based approach:

1. **Auto-Generation**: Backend generates `backend/openapi.json` on startup
2. **File Watching**: Dev script watches file for changes (not server polling)
3. **Local Priority**: Uses local file when available, HTTP as fallback
4. **Relative URLs**: Generated client uses `basePath: ""` for same-origin requests

**Benefits**:

- No server spam
- Efficient file monitoring
- Only regenerates on actual schema changes
- Works offline after first generation

## Usage Examples

### Development with Custom Ports

```bash
export BACKEND_PORT=9000
export FRONTEND_PORT=3001
export VITE_API_URL=http://localhost:9000
export FRONTEND_URL=http://localhost:3001

make dev-fullstack
```

### Production Configuration

```bash
export BACKEND_PORT=80
export VITE_API_URL=https://api.traderpro.com
export FRONTEND_URL=https://traderpro.com
export NODE_ENV=production
```

### Fast Broadcasting for Testing

```bash
export BAR_BROADCASTER_INTERVAL=0.5
export BAR_BROADCASTER_SYMBOLS=AAPL,TSLA
make dev
```

### Disable Mock Services

```bash
export VITE_USE_MOCK_BROKER=false
export VITE_USE_MOCK_DATAFEED=false
npm run dev
```

## Testing Configuration

```bash
# Integration tests with custom config
export BACKEND_PORT=8001
export FRONTEND_PORT=5174
make test-integration

# Run frontend tests against real backend
export VITE_USE_MOCK_BROKER=false
cd frontend && npm test
```

## Best Practices

1. **Development**: Use `.env.example` as template
2. **Local Customization**: Create `.env.local` (not tracked)
3. **Production**: Set via deployment platform env vars
4. **CI/CD**: Set in GitHub Actions secrets/variables
5. **Testing**: Override as needed in test scripts

## Environment Variable Precedence

1. System environment variables (highest)
2. `.env.local` (local overrides, if exists)
3. `.env.example` (template defaults, lowest)
