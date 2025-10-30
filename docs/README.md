# Documentation Index

This directory contains the consolidated, streamlined documentation for the Trading Pro project.

## Core Documentation

### [CLIENT-GENERATION.md](CLIENT-GENERATION.md)

**API Client Auto-Generation**

- Offline generation mode (no server required)
- REST API client from OpenAPI spec
- WebSocket client from AsyncAPI spec
- Automatic integration with build process
- CI/CD configuration

**When to read**: Understanding how TypeScript clients are generated from backend specs

---

### [WEBSOCKET-CLIENTS.md](WEBSOCKET-CLIENTS.md)

**Real-Time WebSocket Implementation**

- Auto-generated client factories
- Three-layer architecture
- Message protocol and topics
- Plugin-based client loading
- Usage examples and patterns

**When to read**: Working with WebSocket real-time data streaming

---

### [DEVELOPMENT.md](DEVELOPMENT.md)

**Development Workflows and Setup**

- Quick start guide
- Development workflows (full-stack, backend-only, frontend-only)
- Testing and code quality
- Git hooks and automation
- Common tasks and troubleshooting

**When to read**: Setting up development environment or daily development work

---

### [TESTING.md](TESTING.md)

**Testing Strategy and Best Practices**

- Independent component testing
- Backend testing (pytest, no HTTP server)
- Frontend testing (Vitest, with mocks)
- Integration testing
- CI/CD testing strategy

**When to read**: Writing tests or understanding testing approach

---

## Project-Level Documentation

Located in the project root:

- **[../ARCHITECTURE.md](../ARCHITECTURE.md)** - Complete system architecture
- **[../README.md](../README.md)** - Project overview and quick start
- **[../WORKSPACE-SETUP.md](../WORKSPACE-SETUP.md)** - VS Code configuration
- **[../ENVIRONMENT-CONFIG.md](../ENVIRONMENT-CONFIG.md)** - Environment variables
- **[../MAKEFILE-GUIDE.md](../MAKEFILE-GUIDE.md)** - Makefile commands

## Component-Specific Documentation

### Backend Documentation

Located in `backend/docs/`:

- **WEBSOCKETS.md** - WebSocket API reference
- **VERSIONING.md** - API versioning strategy
- **WS-ROUTER-GENERATION.md** - Router generation details

### Frontend Documentation

Located in `frontend/`:

- **WEBSOCKET-CLIENT-PATTERN.md** - Detailed WebSocket pattern documentation
- **WEBSOCKET-QUICK-REFERENCE.md** - Quick reference for daily usage
- **WEBSOCKET-CLIENT-BASE.md** - Base client implementation deep dive
- **WEBSOCKET-SINGLETON-REFACTORING.md** - Singleton pattern migration
- **WEBSOCKET-ARCHITECTURE-DIAGRAMS.md** - Visual architecture diagrams
- **WS-CLIENT-AUTO-GENERATION.md** - Client generation implementation
- **src/plugins/ws-plugin-usage.md** - Plugin integration guide

## Reading Paths

### For New Developers

1. **[../README.md](../README.md)** - Project overview
2. **[DEVELOPMENT.md](DEVELOPMENT.md)** - Setup and workflows
3. **[CLIENT-GENERATION.md](CLIENT-GENERATION.md)** - Understanding auto-generated clients
4. **[../ARCHITECTURE.md](../ARCHITECTURE.md)** - System architecture

**Time**: ~30-45 minutes

---

### For Frontend Developers

1. **[DEVELOPMENT.md](DEVELOPMENT.md)** - Development setup
2. **[CLIENT-GENERATION.md](CLIENT-GENERATION.md)** - API client generation
3. **[WEBSOCKET-CLIENTS.md](WEBSOCKET-CLIENTS.md)** - WebSocket implementation
4. **[../frontend/WEBSOCKET-QUICK-REFERENCE.md](../frontend/WEBSOCKET-QUICK-REFERENCE.md)** - Daily reference

**Time**: ~25-35 minutes

---

### For Backend Developers

1. **[DEVELOPMENT.md](DEVELOPMENT.md)** - Development setup
2. **[../backend/docs/WEBSOCKETS.md](../backend/docs/WEBSOCKETS.md)** - WebSocket API
3. **[../backend/docs/VERSIONING.md](../backend/docs/VERSIONING.md)** - API versioning
4. **[TESTING.md](TESTING.md)** - Testing strategy

**Time**: ~20-30 minutes

---

### For DevOps/CI Engineers

1. **[../README.md](../README.md)** - Quick start
2. **[TESTING.md](TESTING.md)** - Testing strategy
3. **[CLIENT-GENERATION.md](CLIENT-GENERATION.md)** - Build-time client generation
4. **[../.github/workflows/ci.yml](../.github/workflows/ci.yml)** - CI configuration

**Time**: ~20-30 minutes

---

## Documentation Organization Principles

### 1. Clear Separation

- **docs/** - Core cross-cutting concerns (generation, testing, development)
- **root/** - Architecture and project overview
- **component/** - Component-specific implementation details

### 2. Avoid Duplication

- Single source of truth for each topic
- Cross-references instead of copying content
- Consolidated related topics

### 3. Layered Detail

- **README** - High-level overview
- **Core Docs** - Essential information, concise
- **Component Docs** - Deep dives and implementation details

### 4. Actionable Content

- Focus on what developers need to do
- Include code examples
- Provide troubleshooting guidance

## Documentation Maintenance

### When to Update

- **After architectural changes** - Update ARCHITECTURE.md
- **After adding features** - Update relevant topic docs
- **After changing workflows** - Update DEVELOPMENT.md
- **After refactoring** - Update component docs

### Keeping It Current

- Review docs during PR reviews
- Test examples when updating docs
- Remove outdated content promptly
- Update cross-references when moving content

## Getting Help

If documentation is unclear or missing:

1. Check component-specific docs in `backend/docs/` or `frontend/`
2. Review code comments and examples
3. Ask the development team
4. Submit a documentation improvement PR

---

**Last Updated**: [Current Date]
**Maintained By**: Development Team
