# Development Guide

## Quick Start

### Prerequisites

- **Python**: 3.11+ with Poetry
- **Node.js**: 20.19+ or 22.12+ with npm
- **Git**: For version control
- **VS Code**: Recommended (open `trader-pro.code-workspace`)

### One-Command Setup

```bash
# Clone and install everything
git clone <repository>
cd trader-pro
make -f project.mk install
```

This automatically:

- Checks Python/Node.js versions
- Offers to install missing versions via pyenv/nvm
- Installs all dependencies
- Sets up Git hooks

## Development Workflows

### Full-Stack Development

```bash
# Terminal 1: Backend
make -f project.mk dev-backend

# Terminal 2: Frontend
make -f project.mk dev-frontend
```

- **Backend**: http://localhost:8000
- **Frontend**: http://localhost:5173
- **API Docs**: http://localhost:8000/docs

### Backend-Only Development

```bash
cd backend
make install  # One-time setup
make dev      # Start server
make test     # Run tests
```

### Frontend-Only Development

```bash
cd frontend
make install  # One-time setup
make dev      # Start dev server
make test-run # Run tests
```

**Note**: Frontend works standalone with mock data when backend unavailable.

## Testing

### Run All Tests

```bash
make -f project.mk test-all
```

### Component Tests

```bash
# Backend only
cd backend && make test

# Frontend only
cd frontend && make test-run

# Integration tests
make -f project.mk test-integration
```

### Test Coverage

```bash
cd backend && make test-cov
```

## Code Quality

### Linting

```bash
# All components
make -f project.mk lint-all

# Backend only
cd backend && make lint-check

# Frontend only
cd frontend && make lint
```

### Formatting

```bash
# All components
make -f project.mk format-all

# Backend only
cd backend && make format

# Auto-formats code
```

## Git Hooks

Automatically installed by `make install`:

- **Pre-commit**: Runs linters and formatters
- **Pre-push**: Runs tests

### Skip Hooks Temporarily

```bash
git commit --no-verify
git push --no-verify
```

## Environment Configuration

### Backend Environment

```bash
# .env or export
export BACKEND_PORT=8000
export BACKEND_APP_NAME=app
```

### Frontend Environment

```bash
# .env or export
export FRONTEND_PORT=5173
export VITE_API_URL=http://localhost:8000
```

See `ENVIRONMENT-CONFIG.md` for full details.

## Client Generation

Clients auto-generate before dev/build. Manual generation:

```bash
cd frontend
make client-generate
```

See `docs/CLIENT-GENERATION.md` for details.

## Common Tasks

### Add New API Endpoint

1. **Backend**: Add route in `src/trading_api/api/`
2. **Backend**: Run `make test` to verify
3. **Frontend**: Run `make client-generate` to update client
4. **Frontend**: Use new endpoint in services

### Add New WebSocket Channel

1. **Backend**: Add router in `src/trading_api/ws/`
2. **Backend**: Update AsyncAPI spec
3. **Frontend**: Run `make client-generate`
4. **Frontend**: New client factory auto-available

### Debug Issues

```bash
# Backend debugging (with debugpy)
cd backend && make dev
# Attach debugger to localhost:5678

# Frontend debugging
cd frontend && npm run dev
# Use browser DevTools
```

### Clean Build Artifacts

```bash
# Clean everything
make -f project.mk clean-all

# Clean generated clients only
make -f project.mk clean-generated
```

## VS Code Workspace

**Recommended**: Open `trader-pro.code-workspace` for:

- Proper TypeScript/Python resolution
- Multi-root workspace support
- Integrated debugging
- Better IntelliSense

## Makefile Reference

### Project-Level (`project.mk`)

```bash
make -f project.mk help           # Show all commands
make -f project.mk install        # Install all dependencies
make -f project.mk dev-fullstack  # Start backend + frontend
make -f project.mk test-all       # Run all tests
make -f project.mk lint-all       # Lint all code
make -f project.mk format-all     # Format all code
```

### Component-Level

```bash
# Backend (backend/Makefile)
make install   # Install dependencies
make dev       # Start server
make test      # Run tests
make lint      # Check code quality

# Frontend (frontend/Makefile)
make install   # Install dependencies
make dev       # Start dev server
make test-run  # Run tests once
make build     # Production build
```

## Troubleshooting

### Python Version Issues

```bash
cd backend
make ensure-python  # Offers to install Python 3.11+ via pyenv
```

### Node.js Version Issues

```bash
cd frontend
make ensure-node  # Offers to install Node.js 20.19+ via nvm
```

### Backend Won't Start

```bash
cd backend
poetry env info  # Check environment
make clean       # Clean artifacts
make install     # Reinstall
```

### Frontend Won't Start

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### Client Generation Fails

```bash
# Ensure backend specs exist
cd backend && make export-openapi-offline

# Regenerate clients
cd frontend && make client-generate
```

## Performance Tips

### Backend

- Use `make dev-no-debug` to skip debugpy overhead
- Enable `--reload` for auto-restart on changes
- Use `make test` frequently for fast feedback

### Frontend

- Vite HMR provides instant updates
- Use `make test` in watch mode during development
- Build with `make build` before deployment

## Related Documentation

- **Architecture**: See `ARCHITECTURE.md`
- **Client Generation**: See `docs/CLIENT-GENERATION.md`
- **WebSocket Clients**: See `docs/WEBSOCKET-CLIENTS.md`
- **Testing Strategy**: See `docs/TESTING.md`
- **Workspace Setup**: See `WORKSPACE-SETUP.md`
