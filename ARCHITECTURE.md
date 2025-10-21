# Trading Pro - Architecture Documentation

**Version**: 2.0.0  
**Last Updated**: October 21, 2025  
**Status**: ✅ Production Ready

## Overview

Trading Pro is a modern full-stack trading platform built with **FastAPI** backend and **Vue.js** frontend, featuring RESTful API (OpenAPI) and real-time WebSocket streaming (AsyncAPI). Designed with **TDD** principles and modern DevOps practices.

## Core Principles

1. **Decoupled Architecture** - Independent frontend/backend development and deployment
2. **Type Safety** - End-to-end TypeScript/Python type safety with automatic client generation
3. **Test-Driven Development** - TDD workflow with comprehensive coverage
4. **Real-Time Streaming** - WebSocket-based market data with FastWS framework
5. **API Versioning** - Backwards-compatible evolution strategy
6. **DevOps Ready** - Automated CI/CD with parallel testing

##  System Architecture

### High-Level View

```
┌──────────────────────────────────────────────────────────┐
│                   Trading Pro Platform                    │
├──────────────────────────────────────────────────────────┤
│  Frontend (Vue 3)        │  Backend (FastAPI)            │
│  • Composition API       │  • REST API (OpenAPI)         │
│  • TypeScript + Vite     │  • WebSocket (AsyncAPI)       │
│  • Pinia State Mgmt      │  • API Versioning (v1)        │
│  • Auto Client Gen       │  • TradingView Integration    │
│  • Smart Fallbacks       │  • Broker & Datafeed APIs     │
└──────────────────────────────────────────────────────────┘
```

### Technology Stack

#### Backend
- **Framework**: FastAPI 0.104+ (ASGI async)
- **WebSocket**: FastWS 0.1.7 (AsyncAPI documented)
- **Runtime**: Python 3.11 + Uvicorn
- **Package Mgmt**: Poetry
- **Testing**: pytest + pytest-asyncio + httpx
- **Type Safety**: MyPy + Pydantic
- **Code Quality**: Black + isort + Flake8
- **Docs**: OpenAPI 3.0 + AsyncAPI 2.4.0

#### Frontend
- **Framework**: Vue 3 + Composition API + TypeScript
- **Build**: Vite 7+
- **Package Mgmt**: npm (Node.js 20+)
- **State**: Pinia
- **Routing**: Vue Router 4
- **Testing**: Vitest + Vue Test Utils
- **Charts**: TradingView Advanced Charting Library
- **Code Quality**: ESLint + Prettier

#### Real-Time Infrastructure
- **Protocol**: WebSocket (ws/wss)
- **Framework**: FastWS with AsyncAPI docs
- **Pattern**: Topic-based pub/sub (`bars:SYMBOL:RESOLUTION`)
- **Operations**: Subscribe, Unsubscribe, Update messages
- **Features**: Heartbeat, connection lifespan, metrics

#### DevOps
- **CI/CD**: GitHub Actions (parallel jobs)
- **Testing**: Multi-tier (unit, integration, smoke, e2e)
- **Development**: VS Code multi-root workspace
- **Build**: Intelligent Makefile system

## Component Architecture

### Backend Structure

```
src/trading_api/
├── main.py              # App lifecycle, routing, specs
├── api/                 # REST endpoints
│   ├── broker.py        # Broker operations (orders, positions, leverage)
│   ├── datafeed.py      # Market data endpoints
│   ├── health.py        # Health checks
│   └── versions.py      # API versioning
├── ws/                  # WebSocket operations
│   └── datafeed.py      # Real-time bar data (subscribe/unsubscribe)
├── core/                # Business logic
│   ├── broker_service.py      # Broker operations
│   ├── datafeed_service.py    # Market data logic
│   ├── bar_broadcaster.py     # Background broadcasting
│   └── config.py              # Configuration models
├── models/              # Pydantic models
│   ├── common.py        # Shared types (BaseApiResponse, etc.)
│   ├── broker/          # Broker models (orders, positions)
│   └── market/          # Market data models (bars, quotes, symbols)
└── plugins/
    └── fastws_adapter.py  # FastWS integration

tests/
├── test_api_broker.py   # Broker API tests
├── test_api_health.py   # Health endpoint tests
├── test_ws_datafeed.py  # WebSocket tests
└── test_datafeed_broadcaster.py  # Broadcaster tests
```

### Frontend Structure

```
src/
├── main.ts             # App entry point
├── App.vue             # Root component
├── router/             # Vue Router config
├── stores/             # Pinia state management
├── services/           # API service layer
│   ├── brokerTerminalService.ts   # Broker adapter
│   └── datafeedService.ts         # Datafeed adapter
├── plugins/
│   └── apiAdapter.ts   # Consolidated backend client wrapper
├── clients/            # Auto-generated API clients
│   └── trader-client-generated/
├── components/         # Vue components
└── types/              # TypeScript type definitions

scripts/
├── generate-openapi-client.sh    # REST client generation
└── generate-asyncapi-types.sh    # WebSocket types generation
```

## Data Flow

### REST API Flow

```
Frontend → Generated Client → ApiAdapter → FastAPI Router
         ← Type-safe data  ← Pydantic    ← Business Logic
```

### WebSocket Flow

```
Frontend ═══► /api/v1/ws ═══► FastWS Adapter
    │ Subscribe(topic)        │
    │◄════ Response ══════════┤
    │                         │
    │◄═══ Updates ════════════┤ publish(topic, data)
         (topic subscribers)
```

## Client Generation

### Automated Workflow

1. **Backend Startup** → Generates `openapi.json` + `asyncapi.json`
2. **File Watchers** → Monitor spec files for changes
3. **Auto-Generation** → Regenerate clients on spec changes
4. **Type Safety** → Full TypeScript types from Pydantic models

**Benefits**:
- ✅ Automatic sync on backend changes
- ✅ Hot reload integration
- ✅ File-based (efficient, no server polling)
- ✅ One command startup: `make dev-fullstack`

## API Versioning

**Current**: `/api/v1/` (Stable)  
**Planned**: `/api/v2/` (Future breaking changes)

**Strategy**:
- URL-based versioning (`/api/v{major}/`)
- No breaking changes within versions
- 6-month deprecation period
- Version info in responses

**Lifecycle**: Development → Beta → Stable → Deprecated → Sunset

## Testing Strategy

### Testing Pyramid

```
┌────────────────────────────────────────┐
│ E2E (Playwright)    │ Full workflows   │
├────────────────────────────────────────┤
│ Integration         │ API contracts    │
├────────────────────────────────────────┤
│ Unit Tests          │ Isolated logic   │
│ • Backend (pytest)  │ • FastAPI Test   │
│ • Frontend (Vitest) │ • Vue Test Utils │
└────────────────────────────────────────┘
```

**Key Features**:
- Independent backend/frontend testing (no cross-dependencies)
- FastAPI TestClient for backend (no server needed)
- Mock services for frontend (offline testing)
- Parallel execution in CI/CD

## Real-Time Architecture

### WebSocket Implementation

**Endpoint**: `ws://localhost:8000/api/v1/ws`  
**Framework**: FastWS 0.1.7  
**Documentation**: AsyncAPI at `/api/v1/ws/asyncapi`

### Message Pattern

```json
{
  "type": "operation.name",
  "payload": { /* data */ }
}
```

### Operations

**Subscribe to Bars**:
```json
// Client → Server
{"type": "bars.subscribe", "payload": {"symbol": "AAPL", "resolution": "1"}}

// Server → Client
{"type": "bars.subscribe.response", "payload": {"status": "ok", "topic": "bars:AAPL:1"}}
```

**Receive Updates**:
```json
// Server → Client (Broadcast)
{"type": "bars.update", "payload": {"time": 1697097600000, "open": 150.0, ...}}
```

### Topic Format

`bars:{SYMBOL}:{RESOLUTION}` (e.g., `bars:AAPL:1`, `bars:GOOGL:D`)

**Features**:
- Multi-symbol subscriptions per client
- Topic-based filtering
- Broadcast only to subscribers
- Automatic cleanup on disconnect

### Connection Management

- **Heartbeat**: 30s interval (client must send messages)
- **Max Lifespan**: 1 hour per connection
- **Error Handling**: Graceful with WS status codes
- **Authentication**: Extensible (currently optional)

## Development Workflow

### Full-Stack Development

```bash
# Recommended: One command starts everything
make -f project.mk dev-fullstack

# What it does:
# 1. Port availability check
# 2. Start backend (generates specs)
# 3. Wait for backend ready
# 4. Generate API clients
# 5. Start file watchers (auto-regenerate on changes)
# 6. Start frontend
# 7. Monitor all processes
```

### Component Development

```bash
# Backend only
cd backend && make dev

# Frontend only (after backend ready)
cd frontend && make dev

# Run tests
make -f project.mk test-all

# Code quality
make -f project.mk lint-all format-all
```

## Design Patterns

### Backend Patterns
- **Dependency Injection** - FastAPI's DI system
- **Service Layer** - Business logic separation
- **Repository Pattern** - Data access abstraction
- **Response Models** - Consistent API responses

### Frontend Patterns
- **Composition API** - Vue 3 modern pattern
- **Store Pattern** - Pinia state management
- **Service Layer** - API abstraction with smart fallbacks
- **Dual-Client System** - Mock + Real backend adapters

### Cross-Cutting
- **Contract-First** - OpenAPI/AsyncAPI specifications
- **Test-Driven** - TDD workflow
- **Type-First** - TypeScript/Python type safety

## Performance Considerations

### Backend
- ASGI async/await for high concurrency
- In-memory caching for frequently accessed data
- Pydantic model optimization
- Efficient WebSocket broadcasting (topic-based)

### Frontend
- Vite for fast ES builds
- Code splitting and lazy loading
- Vue 3 Composition API optimizations
- Efficient state management with Pinia

### Real-Time
- Connection pooling
- Topic-based filtering (send only to subscribers)
- Heartbeat system for connection health
- Configurable rate limiting

## Security

### Current Measures
- CORS configuration
- Pydantic input validation
- MyPy + TypeScript static analysis
- Comprehensive test coverage

### Planned Enhancements
- JWT authentication
- Per-endpoint rate limiting
- HTTPS/WSS for production
- Enhanced input sanitization

## Monitoring & Observability

**Current**:
- Health endpoints (`/api/v1/health`)
- API version tracking
- WebSocket connection metrics
- Comprehensive test reporting

**Planned**:
- Application metrics (response times, error rates)
- WebSocket lifecycle tracking
- Centralized error logging
- Performance profiling

## Documentation Structure

### Core Documentation
- **ARCHITECTURE.md** - System architecture (this file)
- **BACKEND-BROKER-METHODOLOGY.md** - TDD implementation guide
- **docs/DEVELOPMENT.md** - Development workflows
- **docs/TESTING.md** - Testing strategies
- **docs/CLIENT-GENERATION.md** - API client generation
- **docs/WEBSOCKET-CLIENTS.md** - WebSocket implementation

### Configuration
- **WORKSPACE-SETUP.md** - VS Code workspace
- **ENVIRONMENT-CONFIG.md** - Environment variables
- **MAKEFILE-GUIDE.md** - Make commands reference
- **HOOKS-SETUP.md** - Git hooks

### Component Documentation
- **backend/docs/** - Backend-specific docs
- **frontend/** - Frontend implementation docs

## Deployment

### Development
```bash
make -f project.mk dev-fullstack  # All-in-one development
```

### Production (Planned)
- Load balancer (nginx) with SSL/TLS + WebSocket proxy
- Container orchestration (Docker/Kubernetes)
- Database layer (Redis + PostgreSQL)
- Monitoring and observability platform

## Future Roadmap

### Short Term (3 months)
- Complete JWT authentication
- Docker containerization
- Real market data integration
- E2E test suite completion

### Medium Term (6 months)
- Cloud deployment (Kubernetes)
- Production monitoring
- Performance analytics
- Enhanced security measures

### Long Term (12+ months)
- Mobile application
- AI-powered trading insights
- Advanced charting features
- Multi-region deployment

## Success Metrics

✅ **Independent Development** - Parallel team workflows  
✅ **Type Safety** - End-to-end type checking  
✅ **Real-Time Ready** - WebSocket infrastructure complete  
✅ **Test-Driven** - Comprehensive testing at all levels  
✅ **DevOps Friendly** - Automated CI/CD pipelines  
✅ **Developer Experience** - Zero-config setup with intelligent fallbacks  
✅ **Production Ready** - Scalable architecture for deployment

---

**Maintained by**: Development Team  
**Review Schedule**: Quarterly architecture reviews
