# Trader Pro - Documentation Guide

Complete index of all project documentation with descriptions and reading paths.

## 🎯 Root Level Documentation (Project-Wide)

| File                               | Purpose                                                    |
| ---------------------------------- | ---------------------------------------------------------- |
| **README.md**                      | Project overview, quick start, and basic setup             |
| **ARCHITECTURE.md**                | System architecture, technology stack, design patterns     |
| **BACKEND-API-METHODOLOGY.md**     | Generic TDD methodology for backend service implementation |
| **WORKSPACE-SETUP.md**             | VS Code multi-root workspace configuration guide           |
| **MAKEFILE-GUIDE.md**              | Makefile commands reference for all components             |
| **HOOKS-SETUP.md**                 | Git hooks installation and usage                           |
| **ENVIRONMENT-CONFIG.md**          | Environment variables configuration                        |
| **PLAYWRIGHT-MCP-instructions.md** | Playwright MCP server usage instructions                   |

---

## 📖 docs/ Folder (Core Cross-Cutting Documentation)

| File                          | Purpose                                   |
| ----------------------------- | ----------------------------------------- |
| **docs/README.md**            | Documentation index and navigation guide  |
| **docs/CLIENT-GENERATION.md** | REST and WebSocket client auto-generation |
| **docs/WEBSOCKET-CLIENTS.md** | WebSocket implementation overview         |
| **docs/DEVELOPMENT.md**       | Development workflows and setup           |
| **docs/TESTING.md**           | Testing strategy and best practices       |

---

## 🔧 Backend Documentation

### backend/docs/ (Backend-Specific)

| File                                                   | Purpose                                    |
| ------------------------------------------------------ | ------------------------------------------ |
| **backend/README.md**                                  | Backend overview, setup, and API reference |
| **backend/docs/WEBSOCKETS.md**                         | WebSocket API reference and patterns       |
| **backend/docs/VERSIONING.md**                         | API versioning strategy and lifecycle      |
| **backend/src/trading_api/ws/WS-ROUTER-GENERATION.md** | WebSocket router auto-generation           |

### backend/examples/ (Implementation Examples)

| File                                        | Purpose                     |
| ------------------------------------------- | --------------------------- |
| **backend/examples/FASTWS-INTEGRATION.md**  | FastWS integration examples |
| **backend/examples/VERSIONING-EXAMPLES.md** | API versioning examples     |
| **backend/examples/VUE-INTEGRATION.md**     | Vue.js integration examples |

---

## 🎨 Frontend Documentation

### frontend/ (Frontend Root)

| File                                     | Purpose                                                          |
| ---------------------------------------- | ---------------------------------------------------------------- |
| **frontend/README.md**                   | Frontend overview, setup, and structure                          |
| **frontend/BROKER-TERMINAL-SERVICE.md**  | Broker terminal service implementation (TradingView integration) |
| **frontend/TRADER_TERMINAL_UI_USAGE.md** | TradingView Trading Terminal UI usage with Playwright MCP        |
| **frontend/TRADINGVIEW-TYPES.md**        | TradingView TypeScript type definitions guide                    |
| **frontend/FRONTEND-EXCLUSIONS.md**      | Public folder exclusions (linting, testing, etc.)                |

### frontend/ (WebSocket Documentation)

| File                                            | Purpose                                         |
| ----------------------------------------------- | ----------------------------------------------- |
| **frontend/WEBSOCKET-CLIENT-PATTERN.md**        | Detailed WebSocket client pattern documentation |
| **frontend/WEBSOCKET-CLIENT-BASE.md**           | Base WebSocket client implementation deep dive  |
| **frontend/WEBSOCKET-ARCHITECTURE-DIAGRAMS.md** | WebSocket architecture visual diagrams          |

### frontend/src/ (Component Documentation)

| File                                          | Purpose                                             |
| --------------------------------------------- | --------------------------------------------------- |
| **frontend/src/plugins/WS-PLUGIN-USAGE.md**   | WebSocket plugin integration guide                  |
| **frontend/src/plugins/mappers.ts**           | Type-safe data transformations (backend ↔ frontend) |
| **frontend/src/plugins/wsAdapter.ts**         | Centralized WebSocket clients wrapper               |
| **frontend/src/services/README.md**           | Services layer overview                             |
| **frontend/src/services/**tests**/README.md** | Testing guide for services                          |

### frontend/src/clients/trader-client-generated/

- **README.md** - Generated client usage guide
- **docs/** - 40+ auto-generated API model documentation files

---

## 🔒 .github/ & .githooks/ (DevOps & Git)

| File                                | Purpose                                            |
| ----------------------------------- | -------------------------------------------------- |
| **.github/copilot-instructions.md** | GitHub Copilot coding guidelines and project rules |
| **.github/detailed-instrctions.md** | Detailed development instructions                  |
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
4. **ARCHITECTURE.md** - Learn the system architecture
5. **MAKEFILE-GUIDE.md** - Familiarize with build commands

### Backend Developers

1. **backend/README.md** - Backend overview
2. **BACKEND-API-METHODOLOGY.md** - TDD implementation workflow
3. **backend/docs/WEBSOCKETS.md** - WebSocket API patterns
4. **docs/TESTING.md** - Testing strategies
5. **backend/docs/VERSIONING.md** - API versioning approach

### Frontend Developers

1. **frontend/README.md** - Frontend overview
2. **docs/CLIENT-GENERATION.md** - Working with auto-generated clients
3. **frontend/BROKER-TERMINAL-SERVICE.md** - TradingView broker integration
4. **frontend/WEBSOCKET-CLIENT-PATTERN.md** - WebSocket client patterns
5. **docs/TESTING.md** - Testing strategies

### DevOps Engineers

1. **MAKEFILE-GUIDE.md** - Build system commands
2. **HOOKS-SETUP.md** - Git hooks setup
3. **ENVIRONMENT-CONFIG.md** - Environment configuration
4. **.github/CI-TROUBLESHOOTING.md** - CI/CD troubleshooting
5. **docs/TESTING.md** - Testing infrastructure

### Full-Stack Developers

1. **ARCHITECTURE.md** - Overall system design
2. **BACKEND-API-METHODOLOGY.md** - Backend service implementation
3. **docs/CLIENT-GENERATION.md** - Client generation workflow
4. **docs/WEBSOCKET-CLIENTS.md** - Real-time communication
5. **docs/DEVELOPMENT.md** - Full-stack workflows

---

## 🔍 Quick Reference by Topic

### Architecture & Design

- **ARCHITECTURE.md** - System architecture
  - Component architecture with detailed backend/frontend structure
  - **Backend Models Architecture** - Topic-based organization principles (business concepts over technical layers)
- **BACKEND-API-METHODOLOGY.md** - TDD methodology
- **frontend/WEBSOCKET-ARCHITECTURE-DIAGRAMS.md** - WebSocket diagrams

### Setup & Configuration

- **WORKSPACE-SETUP.md** - VS Code workspace
- **ENVIRONMENT-CONFIG.md** - Environment variables
- **HOOKS-SETUP.md** - Git hooks
- **docs/DEVELOPMENT.md** - Development setup

### API & Client Generation

- **docs/CLIENT-GENERATION.md** - Client auto-generation
- **backend/docs/VERSIONING.md** - API versioning
- **frontend/src/clients/trader-client-generated/README.md** - Generated client usage

### WebSocket & Real-Time

- **backend/src/trading_api/ws/WS-ROUTER-GENERATION.md** - ⚠️ **WebSocket router code generation (CRITICAL for new features)**
- **docs/WEBSOCKET-CLIENTS.md** - WebSocket overview
- **backend/docs/WEBSOCKETS.md** - Backend WebSocket API
- **frontend/WEBSOCKET-CLIENT-PATTERN.md** - Frontend patterns

### Testing

- **docs/TESTING.md** - Testing strategies
- **smoke-tests/README.md** - E2E smoke tests
- **frontend/src/services/**tests**/README.md** - Service testing

### TradingView Integration

- **frontend/BROKER-TERMINAL-SERVICE.md** - Broker terminal service
- **frontend/TRADER_TERMINAL_UI_USAGE.md** - UI testing with Playwright
- **frontend/TRADINGVIEW-TYPES.md** - TradingView types

### Build & DevOps

- **MAKEFILE-GUIDE.md** - Makefile commands
- **.github/CI-TROUBLESHOOTING.md** - CI/CD issues
- **backend/src/trading_api/ws/WS-ROUTER-GENERATION.md** - Router generation

### Code Quality

- **HOOKS-SETUP.md** - Pre-commit hooks
- **.github/copilot-instructions.md** - Coding guidelines
- **frontend/FRONTEND-EXCLUSIONS.md** - Exclusion patterns

---

## 📊 Documentation Overview

### Categories

- **Core Documentation**: 13 essential project-wide guides
- **Backend Documentation**: 8 backend-specific guides
- **Frontend Documentation**: 11 frontend-specific guides
- **Auto-Generated Docs**: 40+ API model references
- **Configuration & DevOps**: 6 setup and operations guides

### Maintenance

- All documentation is actively maintained
- Historical/obsolete docs removed
- Focus on essential, actionable information
- Regular reviews to ensure accuracy

---

**Last Updated**: October 21, 2025
**Maintained by**: Development Team
