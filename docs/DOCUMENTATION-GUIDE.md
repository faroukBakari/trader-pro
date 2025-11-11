# Trader Pro - Documentation Guide

Complete index of all project documentation with descriptions and reading paths.

---

### Structure & Organization

The documentation follows a strict hierarchical structure:

```
trader-pro/
├── README.md              # Project overview
├── docs/                  # Cross-cutting concerns
│   ├── ARCHITECTURE.md
│   │   ├── tmp/           # Store for temporary documents
│   │   |   ├── workings.md
│   │   │   └── ...
│   └── ...
│
├── backend/
│   ├── README.md          # Backend overview
│   ├── docs/              # Backend-specific architecture
│   │   ├── ARCHITECTURE.md
│   │   ├── tmp/           # Store for temporary documents
│   │   |   ├── workings.md
│   │   │   └── ...
│   │   └── ...
│
└── frontend/
    ├── README.md          # Frontend overview
    ├── docs/              # Frontend-specific architecture
    │   ├── ARCHITECTURE.md
│   │   ├── tmp/           # Store for temporary documents
│   │   |   ├── workings.md
│   │   │   └── ...
    │   └── ...
```

**Organization Decision Rules:**

| Scope        | Path                                   | Description                               | Examples                                     |
| :----------- | :------------------------------------- | :---------------------------------------- | :------------------------------------------- |
| **Root**     | `README.md`, `docs/`                   | Project-wide, cross-cutting concerns      | `docs/TESTING.md`, `docs/WORKSPACE-SETUP.md` |
| **Backend**  | `backend/README.md`, `backend/docs/`   | Backend-specific architecture & patterns  | `backend/docs/BACKEND_WEBSOCKETS.md`         |
| **Frontend** | `frontend/README.md`, `frontend/docs/` | Frontend-specific architecture & patterns | `frontend/docs/WEBSOCKET-CLIENT-PATTERN.md`  |
| **Module**   | `.../src/module/README.md`             | Specific implementation details           | `backend/src/trading_api/auth/README.md`     |

### Update Strategy: Specific-to-Global

When updating documentation for large-scale changes, follow this three-phase approach:

**Phase 1: Module & Implementation Docs (The "Specific")**

- Document new implementation details, function signatures, module responsibilities
- Target: `README.md` files inside specific modules or components

**Phase 2: Sub-System & Architecture Docs (The "Summary")**

- Summarize Phase 1 changes and show impact on sub-system architecture
- Target: Top-level `README.md` and `docs/` for affected area (e.g., `backend/docs/ARCHITECTURE.md`)
- Update architectural diagrams, API contracts, high-level explanations

**Phase 3: Root & Project-Wide Docs (The "Global")**

- Update project-wide documentation for cross-cutting system changes
- Target: Root `README.md` and root `docs/` (e.g., `docs/ARCHITECTURE.md`, `docs/DOCUMENTATION-GUIDE.md`)
- Update main project overview, high-level architecture, cross-cutting guides

---

## 🎯 Root Level Documentation (Project-Wide)

| File                         | Purpose                                                    |
| ---------------------------- | ---------------------------------------------------------- |
| **README.md**                | Project overview, quick start, and basic setup             |
| **ARCHITECTURE.md**          | System architecture, technology stack, design patterns     |
| **AUTH_IMPLEMENTATION.md**   | Authentication system architecture and implementation plan |
| **API-METHODOLOGY.md**       | Generic TDD methodology for backend service implementation |
| **WEBSOCKET-METHODOLOGY.md** | Generic 6-phase TDD methodology for WebSocket features     |
| **WORKSPACE-SETUP.md**       | VS Code multi-root workspace configuration guide           |
| **MAKEFILE-GUIDE.md**        | Makefile commands reference for all components             |
| **HOOKS-SETUP.md**           | Git hooks installation and usage                           |
| **ENVIRONMENT-CONFIG.md**    | Environment variables configuration                        |

---

## 📖 docs/ Folder (Core Cross-Cutting Documentation)

| File                            | Purpose                                         |
| ------------------------------- | ----------------------------------------------- |
| **docs/README.md**              | Documentation index and navigation guide        |
| **docs/DOCUMENTATION-GUIDE.md** | This file - complete documentation index        |
| **docs/BROKER-ARCHITECTURE.md** | Broker service execution simulator architecture |
| **docs/CLIENT-GENERATION.md**   | REST and WebSocket client auto-generation       |
| **docs/WEBSOCKET-CLIENTS.md**   | WebSocket implementation overview               |
| **docs/DEVELOPMENT.md**         | Development workflows and setup                 |
| **docs/TESTING.md**             | Testing strategy and best practices             |
| **docs/FULLSTACK-DEV-MODE.md**  | Full-stack dev mode with auto-regeneration      |

---

## 🔧 Backend Documentation

### backend/docs/ (Current Backend Documentation)

| File                                             | Purpose                                            |
| ------------------------------------------------ | -------------------------------------------------- |
| **backend/docs/MODULAR_BACKEND_ARCHITECTURE.md** | Modular backend architecture and module system     |
| **backend/docs/MODULAR_VERSIONNING.md**          | Module-level API versioning strategy               |
| **backend/docs/BACKEND_MANAGER_GUIDE.md**        | Multi-process backend management with nginx        |
| **backend/docs/BACKEND_WEBSOCKETS.md**           | FastWS integration and WebSocket-ready modules     |
| **backend/docs/SPECS_AND_CLIENT_GEN.md**         | OpenAPI/AsyncAPI spec and client generation        |
| **backend/docs/WS_ROUTERS_GEN.md**               | WebSocket router generation guide                  |
| **backend/docs/BACKEND_TESTING.md**              | Backend testing strategy and overhead optimization |

> **Note**: backend/docs/outdated/ contains historical documentation from previous refactors. These files are kept for reference only and should NOT be used for current implementation guidance.

### backend/external_packages/ (Third-Party Documentation)

| File                                           | Purpose                      |
| ---------------------------------------------- | ---------------------------- |
| **backend/external_packages/fastws/README.md** | FastWS package documentation |

---

## 🎨 Frontend Documentation

### frontend/ (Frontend Root)

| File                                         | Purpose                                                          |
| -------------------------------------------- | ---------------------------------------------------------------- |
| **frontend/README.md**                       | Frontend overview, setup, and structure                          |
| **frontend/BROKER-TERMINAL-SERVICE.md**      | Broker terminal service implementation (TradingView integration) |
| **frontend/BROKER-WEBSOCKET-INTEGRATION.md** | Broker WebSocket integration implementation details              |
| **frontend/IBROKERCONNECTIONADAPTERHOST.md** | TradingView Trading Host API reference (comprehensive)           |
| **frontend/TRADER_TERMINAL_UI_USAGE.md**     | TradingView Trading Terminal UI usage with Playwright MCP        |
| **frontend/TRADINGVIEW-TYPES.md**            | TradingView TypeScript type definitions guide                    |
| **frontend/FRONTEND-EXCLUSIONS.md**          | Public folder exclusions (linting, testing, etc.)                |

### frontend/ (WebSocket Documentation - Read in Order)

| File                                            | Purpose                                        |
| ----------------------------------------------- | ---------------------------------------------- |
| **frontend/WEBSOCKET-CLIENT-PATTERN.md**        | ⭐ Start here - WebSocket client pattern guide |
| **frontend/WEBSOCKET-CLIENT-BASE.md**           | Deep dive - Base client implementation details |
| **frontend/WEBSOCKET-ARCHITECTURE-DIAGRAMS.md** | Visual reference - Architecture diagrams       |

> **Note**: These docs form a cohesive guide. Start with PATTERN, reference BASE for implementation details, and use DIAGRAMS for visual understanding.

### frontend/src/ (Component Documentation)

| File                                          | Purpose                            |
| --------------------------------------------- | ---------------------------------- |
| **frontend/src/plugins/WS-PLUGIN-USAGE.md**   | WebSocket plugin integration guide |
| **frontend/src/services/README.md**           | Services layer overview            |
| **frontend/src/services/**tests**/README.md** | Testing guide for services         |

### frontend/src/clients_generated/trader-client-generated/

- **README.md** - Generated client usage guide
- **docs/** - 40+ auto-generated API model documentation files

### frontend/public/ (Third-Party Documentation)

| File                                        | Purpose                                     |
| ------------------------------------------- | ------------------------------------------- |
| **frontend/public/datafeeds/README.md**     | TradingView datafeeds library documentation |
| **frontend/public/datafeeds/udf/README.md** | UDF (Universal Data Feed) documentation     |

---

## 🔒 .github/ & .githooks/ (DevOps & Git)

| File                                | Purpose                                            |
| ----------------------------------- | -------------------------------------------------- |
| **.github/copilot-instructions.md** | GitHub Copilot coding guidelines and project rules |
| **.github/CI-TROUBLESHOOTING.md**   | CI/CD troubleshooting guide                        |
| **.githooks/README.md**             | Git hooks implementation details                   |

---

## 🧪 smoke-tests/

| File                      | Purpose                                |
| ------------------------- | -------------------------------------- |
| **smoke-tests/README.md** | End-to-end smoke tests with Playwright |

---

## 📋 Reading Paths by Role

### New Developers (Start Here)

1. **README.md** - Understand the project
2. **docs/DEVELOPMENT.md** - Get development environment set up
3. **WORKSPACE-SETUP.md** - Configure VS Code workspace
4. **docs/FULLSTACK-DEV-MODE.md** - Learn the dev workflow and watch mode
5. **ARCHITECTURE.md** - Learn the system architecture
6. **MAKEFILE-GUIDE.md** - Familiarize with build commands

### Backend Developers

1. **backend/docs/MODULAR_BACKEND_ARCHITECTURE.md** - Modular architecture and module system
2. **backend/docs/MODULAR_VERSIONNING.md** - Module-level API versioning strategy
3. **backend/docs/BACKEND_MANAGER_GUIDE.md** - Multi-process deployment with nginx
4. **backend/docs/BACKEND_WEBSOCKETS.md** - FastWS integration and creating WebSocket modules
5. **backend/docs/SPECS_AND_CLIENT_GEN.md** - Spec and client generation flow
6. **API-METHODOLOGY.md** - TDD implementation workflow
7. **WEBSOCKET-METHODOLOGY.md** - WebSocket integration methodology
8. **backend/docs/WS_ROUTERS_GEN.md** - WebSocket router generation
9. **backend/docs/BACKEND_TESTING.md** - Testing strategy and overhead optimization
10. **docs/TESTING.md** - General testing strategies

### Frontend Developers

1. **frontend/README.md** - Frontend overview
2. **docs/CLIENT-GENERATION.md** - Working with auto-generated clients
3. **frontend/WEBSOCKET-CLIENT-PATTERN.md** - WebSocket client patterns (start here)
4. **frontend/BROKER-TERMINAL-SERVICE.md** - TradingView broker integration
5. **frontend/IBROKERCONNECTIONADAPTERHOST.md** - TradingView Trading Host API
6. **docs/TESTING.md** - Testing strategies

### DevOps Engineers

1. **MAKEFILE-GUIDE.md** - Build system commands
2. **backend/docs/BACKEND_MANAGER_GUIDE.md** - Multi-process backend deployment
3. **HOOKS-SETUP.md** - Git hooks setup
4. **ENVIRONMENT-CONFIG.md** - Environment configuration
5. **.github/CI-TROUBLESHOOTING.md** - CI/CD troubleshooting
6. **docs/TESTING.md** - Testing infrastructure

### Full-Stack Developers

1. **ARCHITECTURE.md** - Overall system design
2. **docs/FULLSTACK-DEV-MODE.md** - Development mode and watch system
3. **API-METHODOLOGY.md** - Backend service implementation
4. **WEBSOCKET-METHODOLOGY.md** - WebSocket integration methodology
5. **docs/CLIENT-GENERATION.md** - Client generation workflow
6. **docs/WEBSOCKET-CLIENTS.md** - Real-time communication
7. **docs/DEVELOPMENT.md** - Full-stack workflows

---

## 🔍 Quick Reference by Topic

### Architecture & Design

- **ARCHITECTURE.md** - System architecture
  - Component architecture with detailed backend/frontend structure
  - **Backend Models Architecture** - Topic-based organization principles (business concepts over technical layers)
- **docs/BROKER-ARCHITECTURE.md** - Broker service execution simulator architecture
- **AUTH_IMPLEMENTATION.md** - Authentication system design and planning
- **API-METHODOLOGY.md** - TDD methodology
- **frontend/WEBSOCKET-ARCHITECTURE-DIAGRAMS.md** - WebSocket diagrams

### Setup & Configuration

- **WORKSPACE-SETUP.md** - VS Code workspace
- **ENVIRONMENT-CONFIG.md** - Environment variables
- **HOOKS-SETUP.md** - Git hooks
- **docs/DEVELOPMENT.md** - Development setup
- **docs/FULLSTACK-DEV-MODE.md** - Full-stack dev mode and watch system

### API & Client Generation

- **backend/docs/SPECS_AND_CLIENT_GEN.md** - ⭐ **Complete generation guide (OpenAPI/AsyncAPI/Python clients)**
- **docs/CLIENT-GENERATION.md** - Client auto-generation overview
- **backend/docs/WS_ROUTERS_GEN.md** - WebSocket router generation guide
- **frontend/src/clients_generated/trader-client-generated/README.md** - Generated client usage

### API Versioning

- **backend/docs/MODULAR_VERSIONNING.md** - ⭐ **Module-level versioning (start here for independent module versions)**
- **API-METHODOLOGY.md** - TDD methodology for API implementation

### WebSocket & Real-Time

- **backend/docs/BACKEND_WEBSOCKETS.md** - ⭐ **FastWS integration guide (start here for WebSocket modules)**
- **backend/docs/WS_ROUTERS_GEN.md** - WebSocket router generation details
- **docs/WEBSOCKET-CLIENTS.md** - WebSocket overview
- **frontend/WEBSOCKET-CLIENT-PATTERN.md** - Frontend patterns

### Testing

- **docs/TESTING.md** - General testing strategies
- **backend/docs/BACKEND_TESTING.md** - Backend integration testing and overhead optimization
- **smoke-tests/README.md** - E2E smoke tests
- **frontend/src/services/**tests**/README.md** - Service testing

### TradingView Integration

- **frontend/BROKER-TERMINAL-SERVICE.md** - Broker terminal service implementation
- **frontend/IBROKERCONNECTIONADAPTERHOST.md** - Trading Host API reference
- **frontend/BROKER-WEBSOCKET-INTEGRATION.md** - WebSocket integration details
- **frontend/TRADER_TERMINAL_UI_USAGE.md** - UI testing with Playwright
- **frontend/TRADINGVIEW-TYPES.md** - TradingView types
- **frontend/public/datafeeds/README.md** - Datafeeds library documentation
- **frontend/public/datafeeds/udf/README.md** - UDF documentation

### Build & DevOps

- **MAKEFILE-GUIDE.md** - Makefile commands
- **docs/FULLSTACK-DEV-MODE.md** - Development mode orchestration
- **backend/docs/BACKEND_MANAGER_GUIDE.md** - Multi-process backend management
- **.github/CI-TROUBLESHOOTING.md** - CI/CD issues

### Code Quality

- **HOOKS-SETUP.md** - Pre-commit hooks
- **.github/copilot-instructions.md** - Coding guidelines
- **frontend/FRONTEND-EXCLUSIONS.md** - Exclusion patterns

---

## 📊 Documentation Overview

### Categories Summary

- **Root Documentation**: 10 essential project-wide guides
- **docs/ Folder**: 8 core cross-cutting documentation files
- **Backend Documentation**: 7 current backend guides + 1 third-party doc
- **Frontend Documentation**: 15 frontend-specific guides + 2 third-party docs
- **Auto-Generated Docs**: 40+ API model references
- **DevOps & Git**: 3 setup and operations guides
- **Testing**: 3 testing guides

### Total Documentation Files

- **User-Maintained**: ~42 actively maintained documentation files
- **Auto-Generated**: 40+ API model documentation files
- **Third-Party**: 3 external package documentation files
- **Outdated/Historical**: 13 files in backend/docs/outdated/ (reference only)

### Maintenance

- All user-maintained documentation is actively kept up-to-date
- Auto-generated docs are regenerated on API changes
- Obsolete/historical docs have been removed
- Focus on essential, actionable information
- Regular reviews ensure accuracy and relevance
- **Note:** Files in `**/tmp/` directories are excluded from documentation updates (temporary/scratch files)

### Link Format

- All internal documentation references use **relative links**
- All file paths and cross-references are validated
- Links are verified during documentation updates

---

**Last Updated**: November 11, 2025
**Maintained by**: Development Team
