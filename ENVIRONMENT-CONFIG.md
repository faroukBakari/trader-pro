# Environment Variables Configuration

This document describes the environment variables used throughout the Trader Pro project for configuring ports, URLs, and other settings.

## Overview

The project uses environment variables to avoid hardcoded values and make it easy to configure for different environments (development, testing, production).

## Environment Variables

### Backend Configuration

- **`BACKEND_PORT`** (default: `8000`)
  - Port on which the FastAPI backend server runs
  - Used by: Backend Makefile, development scripts, CI/CD

### Frontend Configuration

- **`FRONTEND_PORT`** (default: `5173`)

  - Port on which the Vite development server runs
  - Used by: Vite config, development scripts

- **`VITE_API_URL`** (default: `http://localhost:8000`)

  - Base URL for API requests from the frontend
  - Used by: Vite proxy configuration, client generation
  - **Important**: Must start with `VITE_` to be accessible in frontend code

- **`FRONTEND_URL`** (default: `http://localhost:5173`)
  - Full URL where the frontend is accessible
  - Used by: Smoke tests, integration tests

## Configuration Files

### `.env` (Git-tracked defaults)

```bash
# Global Environment Configuration
BACKEND_PORT=8000
VITE_API_URL=http://localhost:8000
FRONTEND_PORT=5173
FRONTEND_URL=http://localhost:5173
NODE_ENV=development
```

### `.env.example` (Template for custom configurations)

Copy this file to `.env.local` for custom configurations:

```bash
cp .env.example .env.local
```

## Client Generation Configuration

The frontend client generation uses an efficient file-based approach:

1. **FastAPI Auto-Generation**: Backend automatically generates `backend/openapi.json` on startup/reload
2. **File Watching**: Development script watches the file for changes (instead of polling the server)
3. **Local File Priority**: Client generation prefers local file over HTTP requests
4. **Empty `basePath`** - Generated client uses relative URLs for same-origin requests

### How it Works:

1. **Backend Startup**: FastAPI generates `openapi.json` file automatically
2. **File Watcher**: Monitors file modification time every 2 seconds (vs. 5-second server polling)
3. **Smart Generation**: Uses local file when available, falls back to HTTP if needed
4. **Efficient**: No more server spam - only regenerates when schema actually changes

This configuration allows the frontend to work with backend and frontend on:

- Same domain (production)
- Different ports (development with proxy)

## Usage Examples

### Development with Custom Ports

```bash
# Set custom ports
export BACKEND_PORT=9000
export FRONTEND_PORT=3001
export VITE_API_URL=http://localhost:9000
export FRONTEND_URL=http://localhost:3001

# Start development (will check port availability first)
make -f project.mk dev-fullstack
```

### Production Configuration

```bash
export BACKEND_PORT=80
export VITE_API_URL=https://api.traderpro.com
export FRONTEND_URL=https://traderpro.com
```

### Testing with Different Configuration

```bash
export BACKEND_PORT=8001
export FRONTEND_PORT=3000
export VITE_API_URL=http://localhost:8001
export FRONTEND_URL=http://localhost:3000

# Run integration tests
./scripts/test-integration.sh
```

## Component Integration

### Port Availability Checking

Both backend and frontend Makefiles check port availability before starting:

**Backend (backend/Makefile)**:

```makefile
dev:
	@if lsof -Pi :$(BACKEND_PORT) -sTCP:LISTEN -t >/dev/null 2>&1; then \
		echo "Error: Port $(BACKEND_PORT) already in use"; \
		exit 1; \
	fi
	poetry run uvicorn ...
```

**Frontend (frontend/Makefile)**:

```makefile
dev:
	@if lsof -Pi :$(FRONTEND_PORT) -sTCP:LISTEN -t >/dev/null 2>&1; then \
		echo "Error: Port $(FRONTEND_PORT) already in use"; \
		exit 1; \
	fi
	npm run dev
```

**dev-fullstack Script**:
Checks both ports before starting anything, preventing partial startup failures.

### Cleanup System

The project includes comprehensive cleanup to ensure fresh starts:

**Automatic Cleanup (on dev start)**:

- `dev-fullstack`: Cleans all generated files (specs, clients, build artifacts) before starting
- `dev-backend`: No cleanup (specs regenerate on startup)
- `dev-frontend`: No cleanup (relies on explicit generation)
- File watchers automatically regenerate clients when specs change

**Manual Cleanup Commands**:

- `make -f project.mk clean-generated`: Quick cleanup (generated files only)
- `make -f project.mk clean-all`: Full cleanup (includes build artifacts)
- Individual: `make -C backend clean`, `make -C frontend clean`

**Files Cleaned by dev-fullstack**:

- Backend: `backend/openapi.json`, `backend/asyncapi.json`
- Frontend: `frontend/src/clients/*-generated/`, `frontend/dist`, `frontend/node_modules/.vite`

### Backend (FastAPI)

- No hardcoded servers in OpenAPI spec
- Uses `BACKEND_PORT` for uvicorn startup
- Makefile targets respect environment variables

### Frontend (Vue/Vite)

- Vite proxy forwards `/api/*` to `VITE_API_URL`
- Generated client uses empty `basePath` for relative URLs
- Frontend runs on `FRONTEND_PORT`

### Client Generation

- Fetches OpenAPI spec from `VITE_API_URL/api/v1/openapi.json`
- Generated client configured with empty `basePath`
- Falls back to mock client if backend unavailable

### Scripts and CI

- All development scripts use environment variables
- CI/CD pipelines configure appropriate values
- Smoke tests use `FRONTEND_URL` for base URL

## Benefits

1. **Flexibility**: Easy to run on different ports/URLs
2. **Environment Separation**: Different configs for dev/test/prod
3. **CI/CD Friendly**: No hardcoded values in automation
4. **Same-Origin Support**: Client works with relative URLs
5. **Mock Fallback**: Frontend works without backend for development

## Migration Notes

The following hardcoded values were replaced:

- Backend: `localhost:8000` → `$BACKEND_PORT`
- Frontend: `localhost:5173` → `$FRONTEND_PORT`
- API URL: `http://localhost:8000` → `$VITE_API_URL`
- Client basePath: `http://localhost:8000` → `''` (empty for relative URLs)

All scripts, Makefiles, and configuration files now use environment variables.
