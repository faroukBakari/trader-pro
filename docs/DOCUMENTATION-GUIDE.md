---
document_type: documentation_index
primary_purpose: discovery_and_navigation
target_audience: ai_agents
last_updated: 2025-11-30
total_documents: 45
coverage_areas:
  [
    architecture,
    setup,
    testing,
    api,
    websockets,
    authentication,
    tradingview,
    tws_api,
    devops,
  ]
---

# Trader Pro - Documentation Guide

Complete index of all project documentation with descriptions and reading paths.

---

## AI Agent Discovery Rules

### When to Consult This Guide

1. User asks about project structure → [Structure & Organization](#structure--organization)
2. User mentions a technology/topic → [Quick Reference by Topic](#quick-reference-by-topic)
3. User specifies their role → [Reading Paths by Role](#reading-paths-by-role)
4. User asks "where is X documented" → Search [Quick Reference by Topic](#quick-reference-by-topic), then file listings
5. User needs implementation guidance → [Document Dependencies](#document-dependencies) + relevant methodology

### Document Loading Priority

1. **Foundation (load first)**: `ARCHITECTURE.md`, `backend/docs/MODULAR_BACKEND_ARCHITECTURE.md`
2. **Context (load for understanding)**: Topic-specific docs from [Quick Reference](#quick-reference-by-topic)
3. **Implementation (load for work)**: Module/component READMEs, methodology docs
4. **Reference (load as needed)**: API docs, testing guides, troubleshooting

### Delegation Strategy

- **Specific file questions**: Load 1-2 most relevant docs directly
- **System/feature questions**: Load 3-5 related docs from topic index
- **Getting started**: Load complete reading path for specified role
- **Implementation tasks**: Load methodology + architecture + module docs in sequence
- **Troubleshooting**: Load relevant architecture + CI-TROUBLESHOOTING.md

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
    │   ├── WEBSOCKET-ARCHITECTURE.md
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

| File                  | Purpose                                                |
| --------------------- | ------------------------------------------------------ |
| **README.md**         | Project overview, quick start, and basic setup         |
| **ARCHITECTURE.md**   | System architecture, technology stack, design patterns |
| **MAKEFILE-GUIDE.md** | Makefile commands reference for all components         |

---

## 📖 docs/ Folder (Core Cross-Cutting Documentation)

| File                            | Purpose                                                           |
| ------------------------------- | ----------------------------------------------------------------- |
| **docs/README.md**              | Documentation index and navigation guide                          |
| **docs/DOCUMENTATION-GUIDE.md** | This file - complete documentation index                          |
| **docs/GETTING-STARTED.md**     | Complete setup guide (workspace, hooks, env)                      |
| **docs/BROKER-ARCHITECTURE.md** | Fakebroker provider execution simulator (`providers/fakebroker/`) |
| **docs/CLIENT-GENERATION.md**   | REST and WebSocket client auto-generation                         |
| **docs/DEVELOPMENT.md**         | Development workflows and setup                                   |
| **docs/TESTING.md**             | Testing strategy and best practices                               |
| **docs/FULLSTACK-DEV-MODE.md**  | Full-stack dev mode with auto-regeneration                        |
| **docs/CI-TROUBLESHOOTING.md**  | CI/CD troubleshooting guide                                       |

### docs/methodologies/ (Implementation Methodologies)

| File                                            | Purpose                                        |
| ----------------------------------------------- | ---------------------------------------------- |
| **docs/methodologies/README.md**                | Implementation methodologies index             |
| **docs/methodologies/API-METHODOLOGY.md**       | TDD methodology for REST API backend services  |
| **docs/methodologies/WEBSOCKET-METHODOLOGY.md** | 6-phase TDD methodology for WebSocket features |

---

## 🔧 Backend Documentation

### backend/docs/ (Current Backend Documentation)

| File                                             | Purpose                                                                                                |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------------ |
| **backend/docs/MODULAR_BACKEND_ARCHITECTURE.md** | Modular backend architecture, functional `ModuleRegistry.get_modules(...)` workflow, and module system |
| **backend/docs/AUTHENTICATION.md**               | JWT-based authentication with Google OAuth, cookies, security                                          |
| **backend/docs/ERROR-MANAGEMENT.md**             | ⭐ Exception hierarchy, error codes, global handlers, testing patterns                                 |
| **backend/docs/PROVIDER-SYSTEM.md**              | Provider/capability system developer guide                                                             |
| **backend/docs/MODULAR_VERSIONNING.md**          | Module-level API versioning strategy                                                                   |
| **backend/docs/BACKEND_MANAGER_GUIDE.md**        | Multi-process backend management with nginx                                                            |
| **backend/docs/BACKEND_WEBSOCKETS.md**           | FastWS integration and WebSocket-ready modules                                                         |
| **backend/docs/SPECS_AND_CLIENT_GEN.md**         | OpenAPI/AsyncAPI spec and client generation                                                            |
| **backend/docs/BACKEND_TESTING.md**              | Backend testing strategy and overhead optimization                                                     |

> **Note**: Historical documentation from previous refactors has been cleaned up. All current backend documentation listed above is accurate and actively maintained.

### backend/external_packages/ (Third-Party Documentation)

| File                                           | Purpose                      |
| ---------------------------------------------- | ---------------------------- |
| **backend/external_packages/fastws/README.md** | FastWS package documentation |

### backend/src/trading_api/providers/tws/ (TWS Provider Implementation)

| File                                                | Purpose                                                                                                                                                      |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **backend/src/trading_api/providers/tws/README.md** | ⭐ **TWS Datafeed Provider implementation guide** - Three-layer architecture (TWSDatafeedProvider → TWSClient → IBSocket), threading model, testing patterns |

### backend/src/trading_api/modules/ (Module Documentation)

| File                                                   | Purpose                                                                             |
| ------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| **backend/src/trading_api/modules/broker/README.md**   | ⭐ Broker module - BFF layer for trading operations (REST API + 5 WebSocket topics) |
| **backend/src/trading_api/modules/datafeed/README.md** | ⭐ Datafeed module - BFF layer for market data (REST API + 2 WebSocket topics)      |
| **backend/src/trading_api/modules/auth/README.md**     | Auth module - Google OAuth, JWT tokens, session management (83 tests)               |

> **Note**: Broker and datafeed module documentation created January 2, 2026 documenting BFF patterns, WebSocket topic handling, and provider capability delegation.

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
| **backend/external_packages/tws/docs/TWS-GENERIC-TICK-LIST.md**             | Complete `genericTickList` reference: tick types (100-623), `mdoff` prefix, news sources (BZ, FLY, DJNL)    |

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
| **frontend/docs/ERROR-MANAGEMENT.md**       | ⭐ Frontend error handling architecture (v1.0.0)  |
| **frontend/docs/WEBSOCKET-ARCHITECTURE.md** | ✅ Complete WebSocket architecture guide (v3.3.0) |
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

1. **backend/docs/MODULAR_BACKEND_ARCHITECTURE.md** - Modular architecture, functional `ModuleRegistry.get_modules(...)` lifecycle, and module system
2. **backend/docs/MODULAR_VERSIONNING.md** - Module-level API versioning strategy
3. **backend/docs/PROVIDER-SYSTEM.md** - Provider/capability system for external integrations
4. **backend/docs/BACKEND_MANAGER_GUIDE.md** - Multi-process deployment with nginx
5. **backend/docs/BACKEND_WEBSOCKETS.md** - FastWS integration and creating WebSocket modules
6. **backend/docs/SPECS_AND_CLIENT_GEN.md** - Spec and client generation flow
7. **docs/methodologies/API-METHODOLOGY.md** - TDD implementation workflow
8. **docs/methodologies/WEBSOCKET-METHODOLOGY.md** - WebSocket integration methodology
9. **backend/docs/BACKEND_TESTING.md** - Testing strategy and overhead optimization
10. **docs/TESTING.md** - General testing strategies
11. **backend/src/trading_api/providers/tws/README.md** - TWS Datafeed Provider implementation guide
12. **backend/external_packages/tws/docs/README.md** - TWS API documentation (for broker integration)

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
6. **frontend/docs/WEBSOCKET-ARCHITECTURE.md** - Real-time communication
7. **docs/DEVELOPMENT.md** - Full-stack workflows

---

## Query Pattern Mapping

| User Query Pattern             | Relevant Documents                                                                  | Load Order            |
| ------------------------------ | ----------------------------------------------------------------------------------- | --------------------- |
| "How do I set up..."           | `GETTING-STARTED.md` → `DEVELOPMENT.md`                                             | Sequential            |
| "How does [feature] work"      | `ARCHITECTURE.md` → topic-specific docs                                             | Architecture first    |
| "Implement [backend feature]"  | `MODULAR_BACKEND_ARCHITECTURE.md` → `API-METHODOLOGY.md` → module docs              | Sequential            |
| "Implement [frontend feature]" | `frontend/README.md` → component docs                                               | Sequential            |
| "WebSocket [anything]"         | `BACKEND_WEBSOCKETS.md` + `WEBSOCKET-ARCHITECTURE.md` + `WEBSOCKET-METHODOLOGY.md`  | All three             |
| "Authentication/auth/login"    | `backend/docs/AUTHENTICATION.md` → `backend/src/trading_api/modules/auth/README.md` | Auth doc first        |
| "Testing [component]"          | `TESTING.md` → component-specific testing docs                                      | General first         |
| "Error/CI/build issue"         | `CI-TROUBLESHOOTING.md` + relevant architecture docs                                | Troubleshooting first |
| "Error handling/exceptions"    | `ERROR-MANAGEMENT.md` → `BACKEND_TESTING.md` (for testing)                          | Error doc first       |
| "TWS API/broker integration"   | `providers/tws/README.md` → `tws/docs/README.md` → specific API docs                | Provider then API     |
| "TradingView [anything]"       | `BROKER-INTEGRATION.md` → `tradingview/` docs                                       | Integration first     |
| "Client generation"            | `SPECS_AND_CLIENT_GEN.md` → `CLIENT-GENERATION.md`                                  | Backend then frontend |
| "Module/versioning"            | `MODULAR_BACKEND_ARCHITECTURE.md` → `MODULAR_VERSIONNING.md`                        | Architecture first    |

---

## Document Dependencies

### Core Foundation (load together)

- `ARCHITECTURE.md` ← `backend/docs/MODULAR_BACKEND_ARCHITECTURE.md`
- `ARCHITECTURE.md` ← `frontend/README.md`
- `GETTING-STARTED.md` ← `DEVELOPMENT.md`

### Feature Implementation Chains

- **REST API Development**: `API-METHODOLOGY.md` → `MODULAR_BACKEND_ARCHITECTURE.md` → `SPECS_AND_CLIENT_GEN.md`
- **WebSocket Development**: `WEBSOCKET-METHODOLOGY.md` → `BACKEND_WEBSOCKETS.md` + `WEBSOCKET-ARCHITECTURE.md` + `ERROR-MANAGEMENT.md` (subscription errors)
- **Authentication**: `backend/docs/AUTHENTICATION.md` → `backend/src/trading_api/modules/auth/README.md`
- **Error Handling**: `ERROR-MANAGEMENT.md` → `PROVIDER-SYSTEM.md` (providers) + `BACKEND_TESTING.md` (testing)
- **TradingView Integration**: `BROKER-INTEGRATION.md` → `tradingview/BROKER-CONNECTION-ADAPTER.md`
- **TWS Provider Integration**: `PROVIDER-SYSTEM.md` → `providers/tws/README.md` → `tws/docs/README.md` → specific API reference docs
- **Client Generation**: `SPECS_AND_CLIENT_GEN.md` → `CLIENT-GENERATION.md`

### Testing Chains

- `TESTING.md` → `BACKEND_TESTING.md` (backend testing)
- `TESTING.md` → `frontend/src/services/tests/README.md` (frontend testing)
- `TESTING.md` → `smoke-tests/README.md` (E2E testing)

### Deployment Chains

- `FULLSTACK-DEV-MODE.md` → `BACKEND_MANAGER_GUIDE.md`
- `MAKEFILE-GUIDE.md` → component-specific Makefiles

---

## 🔍 Quick Reference by Topic

### Architecture & Design

**Keywords**: system design, component architecture, design patterns, module structure, provider system, broker integration, modular architecture

**Scope**: System-level design, architectural patterns, module organization  
**Out of Scope**: Implementation details, code examples

- **ARCHITECTURE.md** - System architecture, technology stack, design patterns
  - Component architecture with detailed backend/frontend structure
  - Backend Models Architecture: Topic-based organization principles
- **backend/docs/PROVIDER-SYSTEM.md** - ⭐ Provider/capability system for pluggable integrations
  - Keywords: integration patterns, capability system, service abstraction, external services
- **docs/BROKER-ARCHITECTURE.md** - Fakebroker provider execution simulator architecture
  - Keywords: fakebroker, execution simulator, order execution, trade simulation, providers/fakebroker
- **backend/docs/AUTHENTICATION.md** - JWT-based authentication with Google OAuth
  - Keywords: JWT, OAuth, Google login, cookies, security, stateless auth
- **docs/methodologies/API-METHODOLOGY.md** - TDD methodology for API development
  - Keywords: test-driven development, API design, implementation workflow
- **frontend/docs/WEBSOCKET-ARCHITECTURE.md** - WebSocket architecture diagrams and patterns
  - Keywords: real-time, client patterns, connection management

### Setup & Configuration

**Keywords**: installation, environment setup, workspace configuration, git hooks, development environment

**Scope**: Initial project setup, development environment configuration  
**Out of Scope**: Production deployment, infrastructure provisioning

- **docs/GETTING-STARTED.md** - Complete setup guide (workspace, hooks, environment)
- **docs/DEVELOPMENT.md** - Development workflows and tooling
- **docs/FULLSTACK-DEV-MODE.md** - Full-stack dev mode with auto-regeneration and watch system

### API & Client Generation

**Keywords**: OpenAPI, AsyncAPI, code generation, client generation, REST clients, WebSocket types, auto-generation, InterModuleClients, inter-module HTTP, client_factory, smart URL defaults

**Scope**: Automated client and type generation from specs  
**Out of Scope**: Manual API implementation, custom client code

- **backend/docs/SPECS_AND_CLIENT_GEN.md** - ⭐ Complete generation guide (OpenAPI/AsyncAPI/Python clients, inter-module communication)
- **docs/CLIENT-GENERATION.md** - Client auto-generation overview and frontend integration
- **frontend/src/clients_generated/** - Per-module generated clients (REST + WebSocket types)

### API Versioning

**Keywords**: versioning strategy, module versions, API versioning, independent versioning, semantic versioning

**Scope**: Module-level API versioning strategy  
**Out of Scope**: Database migrations, data versioning

- **backend/docs/MODULAR_VERSIONNING.md** - ⭐ Module-level versioning (independent module versions)
- **docs/methodologies/API-METHODOLOGY.md** - TDD methodology for API implementation

### WebSocket & Real-Time

**Keywords**: WebSocket, real-time communication, FastWS, bidirectional communication, async messaging, event streaming, subscription errors, error broadcasting, topic_error callback, SubscriptionError, recoverable errors

**Scope**: WebSocket implementation (backend + frontend)  
**Out of Scope**: HTTP polling, SSE, long-polling alternatives

- **backend/docs/BACKEND_WEBSOCKETS.md** - ⭐ FastWS integration guide (WebSocket modules)
- **frontend/docs/WEBSOCKET-ARCHITECTURE.md** - Frontend WebSocket architecture patterns (comprehensive)

### Testing

**Keywords**: testing strategy, unit tests, integration tests, E2E tests, test automation, Playwright, pytest, vitest

**Scope**: All testing strategies (unit, integration, E2E)  
**Out of Scope**: Production monitoring, observability

- **docs/TESTING.md** - General testing strategies and patterns
- **backend/docs/BACKEND_TESTING.md** - Backend integration testing and overhead optimization
- **smoke-tests/README.md** - E2E smoke tests with Playwright
- **frontend/src/services/tests/README.md** - Service layer testing

### TradingView Integration

**Keywords**: TradingView, broker API, Trading Host, charting library, order execution, broker adapter, UDF, LibrarySymbolInfo, SymbolInfo, currency_code, original_currency_code, expired, expiration_date, industry, sector, con_id, symbol metadata, DatafeedConfiguration, quote deduplication, subscribeQuotes

**Scope**: TradingView Trading Terminal integration  
**Out of Scope**: Custom charting solutions, alternative charting libraries

- **frontend/docs/BROKER-INTEGRATION.md** - Complete broker integration implementation guide
- **frontend/docs/tradingview/BROKER-CONNECTION-ADAPTER.md** - Trading Host API reference
- **frontend/docs/tradingview/UI-USAGE-GUIDE.md** - UI testing with Playwright
- **frontend/docs/tradingview/TYPE-DEFINITIONS.md** - TradingView TypeScript type definitions
- **frontend/public/README.md** - TradingView public assets and datafeeds reference

### Authentication & Security

**Keywords**: authentication, authorization, JWT, OAuth, Google login, cookies, security, stateless auth, middleware

**Scope**: Complete authentication system (backend + frontend)  
**Out of Scope**: User management, permissions/roles system

- **backend/docs/AUTHENTICATION.md** - ⭐ Complete authentication system (Google OAuth, JWT, cookies, security)
- **backend/src/trading_api/modules/auth/README.md** - Auth module implementation
- **backend/src/trading_api/shared/middleware/auth.py** - Stateless middleware (public key validation)
- **frontend/src/services/README.md** - Auth service architecture
- **frontend/src/router/README.md** - Router authentication guards
- **frontend/src/views/LoginView.vue** - Google OAuth login UI
- **docs/TESTING.md** - Authentication testing strategies

### Error Handling

**Keywords**: exceptions, error codes, error handling, HTTP status, WebSocket close codes, TradingApiException, ServiceException, ProviderException, CommonException, global handlers, subscription errors, recoverable errors, ErrorPayload, SubscriptionError, topic_error callback, AppError, WebSocketError, NetworkError, AuthError, ValidationError, errorService, toast notifications

**Scope**: Backend exception hierarchy and frontend error handling  
**Out of Scope**: User-facing error messages content

- **backend/docs/ERROR-MANAGEMENT.md** - ⭐ Complete backend error management guide (exception hierarchy, error codes, handlers, subscription errors)
- **frontend/docs/ERROR-MANAGEMENT.md** - ⭐ Complete frontend error management guide (error classes, errorService, toast notifications)
- **backend/docs/PROVIDER-SYSTEM.md** - ProviderException usage in providers (Section 8.4)
- **backend/docs/BACKEND_WEBSOCKETS.md** - WebSocket error handling (close codes, subscription-level errors)
- **frontend/docs/WEBSOCKET-ARCHITECTURE.md** - WebSocket subscription error handling (globalErrorHandler)
- **backend/docs/BACKEND_TESTING.md** - Testing error responses (test client configuration)

### Build & DevOps

**Keywords**: build system, deployment, CI/CD, nginx, multi-process, development mode, make commands

**Scope**: Build automation, deployment, CI/CD  
**Out of Scope**: Cloud infrastructure, Kubernetes, Docker

- **MAKEFILE-GUIDE.md** - Makefile commands reference
- **docs/FULLSTACK-DEV-MODE.md** - Development mode orchestration and watch system
- **backend/docs/BACKEND_MANAGER_GUIDE.md** - Multi-process backend management with nginx
- **docs/CI-TROUBLESHOOTING.md** - CI/CD troubleshooting guide

### Code Quality

**Keywords**: code quality, linting, type checking, git hooks, coding standards, pre-commit hooks

**Scope**: Code quality tools and standards  
**Out of Scope**: Code reviews, pull request processes

- **docs/GETTING-STARTED.md** - Git hooks setup (section 5)
- **.github/copilot-instructions.md** - Coding guidelines and AI assistant rules
- **frontend/docs/FRONTEND-EXCLUSIONS.md** - Exclusion patterns for linting/testing

### TWS API Integration

**Keywords**: Interactive Brokers, TWS API, IB Gateway, broker integration, trading API, market data, order execution, order modification, modifiable fields, lmtPrice, auxPrice, totalQuantity, tif, type stubs, .pyi files, Pylance, ibapi, TWSDatafeedProvider, TWSBrokerProvider, TWSClient, IBSocket, genericTickList, tick types, mdoff, news sources, business key, stream data, StreamData, CachedContract, OrderTracker, AssetConfig, Resolution enum, ticker naming convention, snapshot pattern, stream pattern, overnight_hours, darkpool, Blue Ocean ATS, build_best_contract, is_session_closed, is_darkpool_closed, infer_sec_type, FOREX_CURRENCIES, req_ticker_details, \_resolve_trading_contract, session-aware routing, bracket grouping, OCA pattern, parse_bracket_oca, \_group_orders_by_bracket, ParentType, BracketContext, tracked_order_to_placed_order

**Scope**: Interactive Brokers TWS API integration  
**Out of Scope**: Other broker APIs, custom trading protocols

- **backend/src/trading_api/providers/tws/README.md** - ⭐ TWS Datafeed Provider implementation guide (start here for integration)
  - Three-layer architecture: TWSDatafeedProvider → TWSClient → IBSocket
  - Business key tracking system (`{capability}:{operation}:{params}`)
  - StreamData dataclass for typed data accumulation
  - CachedContract for contract caching with lazy upgrade pattern and session-aware methods
  - Snapshot/stream pattern separation, domain mappers, testing patterns
  - Session-aware routing: `build_best_contract()`, `overnight_hours`, darkpool support
  - Bracket order grouping: `_group_orders_by_bracket()`, OCA pattern parsing, parent/child enrichment
- **backend/external_packages/tws/docs/README.md** - TWS API documentation index (includes local modifications)
- **backend/external_packages/tws/docs/06-SETUP-GUIDE.md** - TWS/Gateway installation and configuration
- **backend/external_packages/tws/docs/07-CONNECTIVITY-GUIDE.md** - Connection management, threading, error handling
- **backend/external_packages/tws/docs/01-API-REFERENCE-CLASSES.md** - Core API classes (EClient, EWrapper, Contract)
- **backend/external_packages/tws/docs/02-API-REFERENCE-CONTRACTS-ORDERS.md** - Order placement, execution, and **order modification guidelines**
- **backend/external_packages/tws/docs/04-API-REFERENCE-CONDITIONS.md** - Advanced conditional orders
- **Type Stubs**: 15 `.pyi` files in `backend/external_packages/tws/source/pythonclient/ibapi/` for Pylance/Pyright support
- **backend/external_packages/tws/docs/TWS-GENERIC-TICK-LIST.md** - `genericTickList` parameter complete reference

---

## 📊 Documentation Overview

### Categories Summary

- **Root Documentation**: 10 essential project-wide guides
- **docs/ Folder**: 9 core cross-cutting documentation files
- **Backend Documentation**: 9 current backend guides + 8 TWS API guides + 1 third-party doc
- **Frontend Documentation**: 10 frontend-specific guides + 2 third-party docs
- **Auto-Generated Docs**: Per-module generated clients and type definitions
- **DevOps & Git**: 2 setup and operations guides
- **Testing**: 3 testing guides

### Total Documentation Files

- **User-Maintained**: ~47 actively maintained documentation files
  - Files consolidated: 5 → 2 (Nov 12, 2025 documentation refactoring)
  - Files archived: 5 old files preserved in `frontend/docs/archive/`
  - New organization: TradingView docs in dedicated `frontend/docs/tradingview/` subdirectory
  - TWS API docs added: 8 files (Nov 19, 2025)
  - Module READMEs added: broker, datafeed (Jan 2, 2026)
- **Auto-Generated**: Per-module client documentation (regenerated on API changes)
- **Third-Party**: 3 external package documentation files

### Maintenance

**Status**: All user-maintained documentation actively maintained and accurate (A+ grade, 95% accuracy)  
**Policy**: Auto-generated docs regenerated on API changes  
**Exclusions**: Files in `**/tmp/` directories (temporary/scratch files)

**Recent Changes Timeline**:

- **2026-01-11**: Inter-module HTTP client factory - Updated SPECS_AND_CLIENT_GEN.md (InterModuleClients singleton, smart URL defaults, env overrides), TWS README.md (`_get_symbol_price()` inter-module pattern), DOCUMENTATION-GUIDE.md (keywords)
- **2026-01-11**: Order modification constraints - Updated TWS README.md (order modification field restrictions, `clone_order()` deep copy pattern, `placeWhatifOrder()` method separation, leverage info via WhatIf margin simulation), broker module README.md (`confirmId` parameter for audit trail), `02-API-REFERENCE-CONTRACTS-ORDERS.md` (Section 3.2 Order Modification guidelines), DOCUMENTATION-GUIDE.md (TWS keywords)
- **2026-01-11**: TWS Bracket order grouping - Updated TWS README.md (bracket order grouping helpers, OCA naming convention, get_orders enrichment, parse_bracket_oca utility, preview_order error propagation), broker module README.md (bracket relationship handling), DOCUMENTATION-GUIDE.md (TWS keywords)
- **2026-01-07**: SymbolInfo/DatafeedConfiguration enhancement - Updated datafeed README.md (quote deduplication pattern, enhanced SymbolInfo fields table, quote-specific error handling), TWS README.md (contract_details_to_symbol_info() field mappings, SymbolInfo priority fields), DOCUMENTATION-GUIDE.md (TradingView keywords)
- **2026-01-02**: Documentation assessment wave execution - Created broker/README.md and datafeed/README.md (BFF pattern, WebSocket topics, provider delegation), fixed BROKER-ARCHITECTURE.md (renamed to Fakebroker, updated class names), updated SPECS_AND_CLIENT_GEN.md (versioned file naming), FULLSTACK-DEV-MODE.md (per-module watching), CLIENT-GENERATION.md (deprecated commands), TESTING.md (provider testing section), frontend README.md (routes), BROKER-INTEGRATION.md (Phase 5 status), MODULAR_BACKEND_ARCHITECTURE.md (get_capability_provider method)
- **2026-01-02**: TWS Provider major refactoring documentation - Updated TWS README.md (business key system, StreamData dataclass, CachedContract caching, snapshot/stream pattern separation, error routing with tws_key), PROVIDER-SYSTEM.md (BrokerCapability stub notes), DOCUMENTATION-GUIDE.md (keywords, dependencies)
- **2025-12-19**: Frontend error management documentation - Created frontend/docs/ERROR-MANAGEMENT.md (error classes, errorService, toast notifications, philosophy emphasis), expanded backend ERROR-MANAGEMENT.md philosophy section (decision matrix, anti-patterns), updated WEBSOCKET-ARCHITECTURE.md v3.3.0 (globalErrorHandler integration), added error handling section to services README
- **2025-12-19**: WebSocket subscription error handling - Updated BACKEND_WEBSOCKETS.md (unified error broadcasting), WEBSOCKET-ARCHITECTURE.md v3.2.0 (frontend error handling section), generic_route.py (all errors now broadcast before cleanup)
- **2025-12-11**: Error management documentation - Created ERROR-MANAGEMENT.md (exception hierarchy, error codes, handlers), updated MODULAR_BACKEND_ARCHITECTURE.md, PROVIDER-SYSTEM.md, BACKEND_TESTING.md, BACKEND_WEBSOCKETS.md with error handling sections
- **2025-12-07**: ws-refinements documentation sync - TWS README overhauled (ticker-slot pattern, stream keys, AsyncMock testing), BACKEND_WEBSOCKETS.md and WEBSOCKET-METHODOLOGY.md updated (sync create_topic), DOCUMENTATION-GUIDE.md keywords updated
- **2025-11-30**: Wave 4 final validation - Verified all internal links, fixed remaining broken refs (ENVIRONMENT-CONFIG.md, WORKSPACE-SETUP.md → GETTING-STARTED.md), updated docs/README.md, validated cross-references and section anchors
- **2025-11-30**: Wave 3 documentation assessment - Fixed ARCHITECTURE.md links, BROKER-ARCHITECTURE.md links, CLIENT-GENERATION.md refs, methodologies updates, root README.md links. RE-GROUP operations deferred (low ROI)
- **2025-11-30**: Wave 2 documentation assessment - WEBSOCKET-CLIENTS.md archived (merged into WEBSOCKET-ARCHITECTURE.md), fixed broken links across backend/frontend docs, AUTHENTICATION.md consolidated in backend/docs/
- **2025-11-26**: TWS Provider documentation refresh (type stubs, local modifications, expanded chains)
- **2025-11-21**: AI agent optimization (added metadata, discovery rules, query patterns, dependencies)
- **2025-11-19**: TWS API docs added (8 files in `backend/external_packages/tws/docs/`)
- **2025-11-18**: Setup consolidation (3→1), methodologies organization, TradingView public docs (2→1)
- **2025-11-12**: WebSocket consolidation (3→1), broker integration consolidation (2→1), TradingView reorganization
- **2025-11-11**: Documentation assessment (A+ grade, 95% accuracy, 43 files assessed)

**For detailed refactoring history**: See `docs/tmp/documentation-assessment-report.md`

### Link Format

- All internal documentation references use **relative links**
- All file paths and cross-references are validated
- Links are verified during documentation updates

### Document Status Markers

- ⭐ = Primary entry point for topic
- ✅ = Recently updated/verified (< 30 days)
- 🔧 = Technical deep-dive

---

**Last Updated**: January 11, 2026  
**Maintained by**: Development Team
