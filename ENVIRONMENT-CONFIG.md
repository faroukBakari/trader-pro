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

The frontend client generation uses these environment variables:

1. **`VITE_API_URL`** - Used to fetch OpenAPI spec from live backend
2. **Empty `basePath`** - Generated client uses relative URLs for same-origin requests

This configuration allows the frontend to work with backend and frontend on:
- Same domain (production)
- Different ports (development with proxy)

## Usage Examples

### Development with Custom Ports

```bash
# Start backend on port 9000
export BACKEND_PORT=9000

# Update frontend API URL
export VITE_API_URL=http://localhost:9000

# Start development
./scripts/dev-fullstack.sh
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