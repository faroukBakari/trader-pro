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
│   ├── tmp/               # Store for temporary documents
│   │   ├── workings.md
│   │   └── ...
│   └── ...
│
├── backend/
│   ├── README.md          # Backend overview
│   ├── docs/              # Backend-specific architecture
│   │   ├── BACKEND_MANAGER_GUIDE.md
│   │   ├── tmp/           # Store for temporary documents
│   │   │   ├── workings.md
│   │   │   └── ...
│   │   └── ...
│
└── frontend/
    ├── README.md          # Frontend overview
    ├── docs/              # Frontend-specific architecture
    │   ├── WEBSOCKET-CLIENT-PATTERN.md
    │   ├── tmp/           # Store for temporary documents
    │   │   ├── workings.md
    │   │   └── ...
    │   └── ...
```

**Organization Decision Rules:**

| Scope        | Path                                   | Description                               | Examples                                         |
| :----------- | :------------------------------------- | :---------------------------------------- | :----------------------------------------------- |
| **Root**     | `README.md`, `docs/`                   | Project-wide, cross-cutting concerns      | `docs/TESTING.md`, `docs/GETTING-STARTED.md`     |
| **Backend**  | `backend/README.md`, `backend/docs/`   | Backend-specific architecture & patterns  | `backend/docs/BACKEND_WEBSOCKETS.md`             |
| **Frontend** | `frontend/README.md`, `frontend/docs/` | Frontend-specific architecture & patterns | `frontend/docs/WEBSOCKET-ARCHITECTURE.md`        |
| **Module**   | `.../src/module/README.md`             | Specific implementation details           | `backend/src/trading_api/modules/auth/README.md` |

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

| File                  | Purpose                                                   |
| --------------------- | --------------------------------------------------------- |
| **README.md**         | Project overview, quick start, and basic setup            |
| **ARCHITECTURE.md**   | System architecture, technology stack, design patterns    |
| **AUTHENTICATION.md** | JWT-based authentication with Google OAuth implementation |
| **MAKEFILE-GUIDE.md** | Makefile commands reference for all components            |

---

## 📖 docs/ Folder (Core Cross-Cutting Documentation)

| File                            | Purpose                                         |
| ------------------------------- | ----------------------------------------------- |
| **docs/README.md**              | Documentation index and navigation guide        |
| **docs/DOCUMENTATION-GUIDE.md** | This file - complete documentation index        |
| **docs/GETTING-STARTED.md**     | Complete setup guide (workspace, hooks, env)    |
| **docs/BROKER-ARCHITECTURE.md** | Broker service execution simulator architecture |
| **docs/CLIENT-GENERATION.md**   | REST and WebSocket client auto-generation       |
| **docs/WEBSOCKET-CLIENTS.md**   | WebSocket implementation overview               |
| **docs/DEVELOPMENT.md**         | Development workflows and setup                 |
| **docs/TESTING.md**             | Testing strategy and best practices             |
| **docs/FULLSTACK-DEV-MODE.md**  | Full-stack dev mode with auto-regeneration      |
| **docs/CI-TROUBLESHOOTING.md**  | CI/CD troubleshooting guide                     |

### docs/methodologies/ (Implementation Methodologies)

| File                                            | Purpose                                        |
| ----------------------------------------------- | ---------------------------------------------- |
| **docs/methodologies/README.md**                | Implementation methodologies index             |
| **docs/methodologies/API-METHODOLOGY.md**       | TDD methodology for REST API backend services  |
| **docs/methodologies/WEBSOCKET-METHODOLOGY.md** | 6-phase TDD methodology for WebSocket features |

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

> **Note**: Historical documentation from previous refactors has been cleaned up. All current backend documentation listed above is accurate and actively maintained.

### backend/external_packages/ (Third-Party Documentation)

| File                                           | Purpose                      |
| ---------------------------------------------- | ---------------------------- |
| **backend/external_packages/fastws/README.md** | FastWS package documentation |

### backend/external_packages/tws/docs/ (TWS API Documentation)

Complete offline documentation for Interactive Brokers TWS API for Python.

| File                                                                        | Purpose                                                                                                     |
| --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| **backend/external_packages/tws/docs/README.md**                            | ⭐ **TWS API documentation index (start here)** - Complete navigation, quick start, learning paths          |
| **backend/external_packages/tws/docs/01-API-REFERENCE-CLASSES.md**          | Core API classes: `EClient` (50+ methods), `EWrapper` (70+ callbacks), `Contract`, `ContractDetails`, `Bar` |
| **backend/external_packages/tws/docs/02-API-REFERENCE-CONTRACTS-ORDERS.md** | Order & contract classes: `Order` (100+ parameters), `Execution`, `OrderState`, `ScannerSubscription`       |
| **backend/external_packages/tws/docs/03-API-REFERENCE-EXECUTIONS.md**       | Trade data: `CommissionAndFeesReport`, `Liquidity`, Historical ticks, Tick attributes                       |
| **backend/external_packages/tws/docs/04-API-REFERENCE-CONDITIONS.md**       | Order conditions: Price, Time, Margin, Execution, Volume, PercentChange (with examples)                     |
| **backend/external_packages/tws/docs/05-API-REFERENCE-DATA-TYPES.md**       | Helper classes: Market depth, News providers, Price increments, Smart components                            |
| **backend/external_packages/tws/docs/06-SETUP-GUIDE.md**                    | Installation, TWS/Gateway configuration, Python setup, verification, troubleshooting                        |
| **backend/external_packages/tws/docs/07-CONNECTIVITY-GUIDE.md**             | Connection patterns, threading models, error handling, auto-reconnect strategies                            |

> **Note**: TWS API documentation created November 19, 2025 from [TWS API Campus](https://ibkrcampus.com/campus/ibkr-api-page/) for complete offline development capability. Additional guides (market data, order management, account/portfolio) coming soon.

---

## 🎨 Frontend Documentation

### frontend/ (Frontend Root)

| File                   | Purpose                                 |
| ---------------------- | --------------------------------------- |
| **frontend/README.md** | Frontend overview, setup, and structure |

### frontend/docs/ (Frontend-Specific Documentation)

| File                                        | Purpose                                           |
| ------------------------------------------- | ------------------------------------------------- |
| **frontend/docs/WEBSOCKET-ARCHITECTURE.md** | ✅ Complete WebSocket architecture guide (v2.0.0) |
| **frontend/docs/BROKER-INTEGRATION.md**     | ✅ Complete broker integration guide (v2.0.0)     |
| **frontend/docs/IHM-CONTROLLER.md**         | IHM Controller service design and usage (v1.0.0)  |
| **frontend/docs/FRONTEND-EXCLUSIONS.md**    | Public folder exclusions (linting, testing, etc.) |

> **Note**: These documents were comprehensively updated on November 12, 2025 during documentation refactoring:
>
> - **WEBSOCKET-ARCHITECTURE.md** - Consolidated from 3 separate files (WEBSOCKET-CLIENT-PATTERN.md, WEBSOCKET-CLIENT-BASE.md, WEBSOCKET-ARCHITECTURE-DIAGRAMS.md)
> - **BROKER-INTEGRATION.md** - Merged from 2 separate files (BROKER-TERMINAL-SERVICE.md, BROKER-WEBSOCKET-INTEGRATION.md)
> - All old files archived to `frontend/docs/archive/`

### frontend/docs/tradingview/ (TradingView Integration)

| File                                                       | Purpose                                                |
| ---------------------------------------------------------- | ------------------------------------------------------ |
| **frontend/docs/tradingview/README.md**                    | TradingView documentation index                        |
| **frontend/docs/tradingview/BROKER-CONNECTION-ADAPTER.md** | TradingView Trading Host API reference (comprehensive) |
| **frontend/docs/tradingview/UI-USAGE-GUIDE.md**            | TradingView Trading Terminal UI usage with Playwright  |
| **frontend/docs/tradingview/TYPE-DEFINITIONS.md**          | TradingView TypeScript type definitions guide          |

> **Note**: TradingView-specific documentation was reorganized into dedicated subdirectory on November 12, 2025 for better organization.

### frontend/src/ (Component Documentation)

| File                                          | Purpose                                                       |
| --------------------------------------------- | ------------------------------------------------------------- |
| **frontend/src/services/README.md**           | Services layer overview, multi-module API, and IHM Controller |
| **frontend/src/services/**tests**/README.md** | Testing guide for services                                    |

**Note:** Component-level documentation is primarily in `frontend/README.md`. The API Status component is documented in the "API Status Component" section.

### frontend/src/clients_generated/ (Per-Module Generated Clients)

- **trader-client-{module}\_v{version}/** - REST API clients (one per module)
  - **README.md** - Generated client usage guide
  - **docs/** - Auto-generated API model documentation files
- **ws-types-{module}\_v{version}/** - WebSocket type definitions (one per module)

### frontend/public/ (Third-Party Documentation)

| File                          | Purpose                                                 |
| ----------------------------- | ------------------------------------------------------- |
| **frontend/public/README.md** | TradingView public assets reference (external examples) |

---

## 🔒 .github/ & .githooks/ (DevOps & Git)

| File                                | Purpose                                            |
| ----------------------------------- | -------------------------------------------------- |
| **.github/copilot-instructions.md** | GitHub Copilot coding guidelines and project rules |
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
2. **docs/GETTING-STARTED.md** - Complete setup guide (workspace, hooks, environment)
3. **docs/DEVELOPMENT.md** - Get development workflows
4. **docs/FULLSTACK-DEV-MODE.md** - Learn the dev workflow and watch mode
5. **ARCHITECTURE.md** - Learn the system architecture
6. **MAKEFILE-GUIDE.md** - Familiarize with build commands

### Backend Developers

1. **backend/docs/MODULAR_BACKEND_ARCHITECTURE.md** - Modular architecture and module system
2. **backend/docs/MODULAR_VERSIONNING.md** - Module-level API versioning strategy
3. **backend/docs/BACKEND_MANAGER_GUIDE.md** - Multi-process deployment with nginx
4. **backend/docs/BACKEND_WEBSOCKETS.md** - FastWS integration and creating WebSocket modules
5. **backend/docs/SPECS_AND_CLIENT_GEN.md** - Spec and client generation flow
6. **docs/methodologies/API-METHODOLOGY.md** - TDD implementation workflow
7. **docs/methodologies/WEBSOCKET-METHODOLOGY.md** - WebSocket integration methodology
8. **backend/docs/WS_ROUTERS_GEN.md** - WebSocket router generation
9. **backend/docs/BACKEND_TESTING.md** - Testing strategy and overhead optimization
10. **docs/TESTING.md** - General testing strategies
11. **backend/external_packages/tws/docs/README.md** - TWS API documentation (for broker integration)

### Frontend Developers

1. **frontend/README.md** - Frontend overview
2. **docs/CLIENT-GENERATION.md** - Working with auto-generated clients
3. **frontend/docs/WEBSOCKET-ARCHITECTURE.md** - WebSocket architecture patterns (start here)
4. **frontend/docs/BROKER-INTEGRATION.md** - TradingView broker integration
5. **frontend/docs/tradingview/BROKER-CONNECTION-ADAPTER.md** - TradingView Trading Host API
6. **docs/TESTING.md** - Testing strategies

### DevOps Engineers

1. **MAKEFILE-GUIDE.md** - Build system commands
2. **backend/docs/BACKEND_MANAGER_GUIDE.md** - Multi-process backend deployment
3. **docs/GETTING-STARTED.md** - Setup guide (hooks, environment, workspace)
4. **docs/CI-TROUBLESHOOTING.md** - CI/CD troubleshooting
5. **docs/TESTING.md** - Testing infrastructure

### Full-Stack Developers

1. **ARCHITECTURE.md** - Overall system design
2. **docs/FULLSTACK-DEV-MODE.md** - Development mode and watch system
3. **docs/methodologies/API-METHODOLOGY.md** - Backend service implementation
4. **docs/methodologies/WEBSOCKET-METHODOLOGY.md** - WebSocket integration methodology
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
- **AUTHENTICATION.md** - JWT-based authentication with Google OAuth
- **docs/methodologies/API-METHODOLOGY.md** - TDD methodology
- **frontend/docs/WEBSOCKET-ARCHITECTURE.md** - WebSocket architecture diagrams

### Setup & Configuration

- **docs/GETTING-STARTED.md** - Complete setup guide (workspace, hooks, environment)
- **docs/DEVELOPMENT.md** - Development workflows
- **docs/FULLSTACK-DEV-MODE.md** - Full-stack dev mode and watch system

### API & Client Generation

- **backend/docs/SPECS_AND_CLIENT_GEN.md** - ⭐ **Complete generation guide (OpenAPI/AsyncAPI/Python clients)**
- **docs/CLIENT-GENERATION.md** - Client auto-generation overview
- **backend/docs/WS_ROUTERS_GEN.md** - WebSocket router generation guide
- **frontend/src/clients_generated/** - Per-module generated clients (REST + WebSocket types)

### API Versioning

- **backend/docs/MODULAR_VERSIONNING.md** - ⭐ **Module-level versioning (start here for independent module versions)**
- **docs/methodologies/API-METHODOLOGY.md** - TDD methodology for API implementation

### WebSocket & Real-Time

- **backend/docs/BACKEND_WEBSOCKETS.md** - ⭐ **FastWS integration guide (start here for WebSocket modules)**
- **backend/docs/WS_ROUTERS_GEN.md** - WebSocket router generation details
- **docs/WEBSOCKET-CLIENTS.md** - WebSocket overview
- **frontend/docs/WEBSOCKET-ARCHITECTURE.md** - Frontend WebSocket architecture patterns

### Testing

- **docs/TESTING.md** - General testing strategies
- **backend/docs/BACKEND_TESTING.md** - Backend integration testing and overhead optimization
- **smoke-tests/README.md** - E2E smoke tests
- **frontend/src/services/**tests**/README.md** - Service testing

### TradingView Integration

- **frontend/docs/BROKER-INTEGRATION.md** - Complete broker integration implementation guide
- **frontend/docs/tradingview/BROKER-CONNECTION-ADAPTER.md** - Trading Host API reference
- **frontend/docs/tradingview/UI-USAGE-GUIDE.md** - UI testing with Playwright
- **frontend/docs/tradingview/TYPE-DEFINITIONS.md** - TradingView types
- **frontend/public/datafeeds/README.md** - Datafeeds library documentation
- **frontend/public/datafeeds/udf/README.md** - UDF documentation

### Authentication & Security

- **AUTHENTICATION.md** - ⭐ **Complete authentication system documentation (Google OAuth, JWT, cookies, security)**
- **backend/src/trading_api/modules/auth/README.md** - Auth module implementation (repository, service, API, middleware)
- **backend/src/trading_api/shared/middleware/auth.py** - Stateless middleware implementation (public key validation)
- **frontend/src/services/README.md** - Auth service architecture (service-based, no Pinia store)
- **frontend/src/router/README.md** - Router authentication guards (stateless, API introspection)
- **frontend/src/views/LoginView.vue** - Google OAuth login UI
- **docs/TESTING.md** - Authentication testing strategies (92 backend tests, frontend unit/integration)

### Build & DevOps

- **MAKEFILE-GUIDE.md** - Makefile commands
- **docs/FULLSTACK-DEV-MODE.md** - Development mode orchestration
- **backend/docs/BACKEND_MANAGER_GUIDE.md** - Multi-process backend management
- **docs/CI-TROUBLESHOOTING.md** - CI/CD issues

### Code Quality

- **docs/GETTING-STARTED.md** - Git hooks setup (section 5)
- **.github/copilot-instructions.md** - Coding guidelines
- **frontend/docs/FRONTEND-EXCLUSIONS.md** - Exclusion patterns

### TWS API Integration

- **backend/external_packages/tws/docs/README.md** - ⭐ **TWS API documentation index (start here for broker integration)**
- **backend/external_packages/tws/docs/06-SETUP-GUIDE.md** - TWS/Gateway installation and configuration
- **backend/external_packages/tws/docs/07-CONNECTIVITY-GUIDE.md** - Connection management, threading, error handling
- **backend/external_packages/tws/docs/01-API-REFERENCE-CLASSES.md** - Core API classes (EClient, EWrapper, Contract)
- **backend/external_packages/tws/docs/02-API-REFERENCE-CONTRACTS-ORDERS.md** - Order placement and execution
- **backend/external_packages/tws/docs/04-API-REFERENCE-CONDITIONS.md** - Advanced conditional orders

---

## 📊 Documentation Overview

### Categories Summary

- **Root Documentation**: 10 essential project-wide guides
- **docs/ Folder**: 9 core cross-cutting documentation files
- **Backend Documentation**: 7 current backend guides + 8 TWS API guides + 1 third-party doc
- **Frontend Documentation**: 10 frontend-specific guides + 2 third-party docs
- **Auto-Generated Docs**: Per-module generated clients and type definitions
- **DevOps & Git**: 2 setup and operations guides
- **Testing**: 3 testing guides

### Total Documentation Files

- **User-Maintained**: ~44 actively maintained documentation files
  - Files consolidated: 5 → 2 (Nov 12, 2025 documentation refactoring)
  - Files archived: 5 old files preserved in `frontend/docs/archive/`
  - New organization: TradingView docs in dedicated `frontend/docs/tradingview/` subdirectory
  - TWS API docs added: 8 files (Nov 19, 2025)
- **Auto-Generated**: Per-module client documentation (regenerated on API changes)
- **Third-Party**: 3 external package documentation files

### Maintenance

- All user-maintained documentation is actively kept up-to-date
- Auto-generated docs are regenerated on API changes
- Obsolete/historical docs have been archived
- Focus on essential, actionable information
- Regular reviews ensure accuracy and relevance
- **Note:** Files in `**/tmp/` directories are excluded from documentation updates (temporary/scratch files)

**Documentation Refactoring** (November 18, 2025):

- **Setup Documentation Consolidation**: 3 files → 1 comprehensive guide
  - Created `docs/GETTING-STARTED.md` (merged WORKSPACE-SETUP, HOOKS-SETUP, ENVIRONMENT-CONFIG)
  - Old files archived to `docs/archive/`
- **Methodologies Organization**: Created `docs/methodologies/` subdirectory
  - Moved API-METHODOLOGY.md and WEBSOCKET-METHODOLOGY.md
  - Added `methodologies/README.md` navigation index
  - Updated 13+ cross-references
- **TradingView Public Documentation**: 2 nested files → 1 root file
  - Created `frontend/public/README.md` (merged datafeeds/ and udf/ READMEs)
  - Old files archived to `docs/archive/`
- **Duplicate Removal**: Removed duplicate `frontend/FRONTEND-EXCLUSIONS.md`
- **Result**: Improved organization, clearer structure, enhanced discoverability (see `docs/tmp/documentation-assessment-report.md`)

**TWS API Documentation Addition** (November 19, 2025):

- **Complete Offline TWS API Reference**: Created comprehensive offline documentation for Interactive Brokers TWS API
  - Added 8 documentation files in `backend/external_packages/tws/docs/`
  - **API Reference**: 5 files covering all classes, methods, attributes (01-05)
  - **Implementation Guides**: 2 files for setup and connectivity (06-07)
  - **Navigation**: README.md with quick start, learning paths, cheat sheets
  - **Purpose**: Enable offline development with TWS API without internet searches
  - **Source**: [TWS API Campus](https://ibkrcampus.com/campus/ibkr-api-page/)
  - **Coverage**: Core classes (EClient, EWrapper), Orders (100+ params), Conditions, Setup, Threading patterns
  - **Future**: Additional guides for market data, order management, account/portfolio planned

**Previous Refactoring** (November 12, 2025):

- **WebSocket Documentation Consolidation**: 3 files → 1 comprehensive guide (`frontend/docs/WEBSOCKET-ARCHITECTURE.md`)
- **Broker Integration Consolidation**: 2 files → 1 comprehensive guide (`frontend/docs/BROKER-INTEGRATION.md`)
- **TradingView Organization**: Created `frontend/docs/tradingview/` subdirectory

**Recent Assessment** (November 11, 2025):

- **Comprehensive Assessment**: 43 documentation files assessed
- **Overall Grade**: A+ (95% accuracy)
- **Documents Verified**: 35 files confirmed accurate
- **Documents Flagged**: 4 files (completed rewrite November 11, 2025)
- **Critical Issues**: 0 (all core architecture docs verified)
- See `docs/tmp/documentation-assessment-report.md` for complete details

**Previous Assessment** (November 2025):

- 36 documents assessed for accuracy
- 24 documents updated, 12 verified as accurate
- Overall accuracy: 90% (A- grade)
- 4 documents flagged for future rewrite/removal

### Link Format

- All internal documentation references use **relative links**
- All file paths and cross-references are validated
- Links are verified during documentation updates

---

**Last Updated**: November 19, 2025
**Maintained by**: Development Team
