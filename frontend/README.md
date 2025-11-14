# Trading API Frontend

A Vue.js frontend application for the Trading API built with TypeScript, Vue Router, Pinia, and Vite.

## Features

- ✅ Vue 3 with Composition API
- ✅ TypeScript support
- ✅ Vue Router for navigation
- ✅ Pinia for state management
- ✅ JWT-based authentication with Google OAuth
- ✅ Cookie-based session management
- ✅ Service-based auth architecture (no Pinia store)
- ✅ Protected routes with stateless guards
- ✅ Vitest for testing
- ✅ ESLint + Prettier for code quality
- ✅ API service integration with FastAPI backend
- ✅ Real-time API status monitoring
- ✅ WebSocket authentication via cookies

## Development Setup

### Prerequisites

- **Node.js 22.20+** (required by Vite)
  - Will be **automatically installed** if you have [nvm](https://github.com/nvm-sh/nvm)
  - Or check version: `node --version`
  - Manual install: `nvm install 22.20.0 && nvm use 22.20.0`
- npm (comes with Node.js)

### Authentication Setup

The application requires authentication to access protected routes.

**Quick Start:**

1. Start the backend (includes auth module): `cd ../backend && make dev`
2. Navigate to http://localhost:5173/login
3. Sign in with Google OAuth
4. Access protected routes (all routes except `/login` require authentication)

**Architecture:**

The frontend uses a **service-based authentication architecture**:

- **Service Layer**: `authService.ts` singleton with composable interface
- **Cookie-Based**: HttpOnly cookies for access tokens (XSS protection)
- **Stateless Guards**: Router guards use direct API introspection
- **Google OAuth**: Integration via `vue3-google-signin`
- **No Store**: Authentication managed entirely through service + cookies

**Key Features:**

- ✅ JWT access tokens in HttpOnly cookies (5-minute expiry)
- ✅ Refresh token rotation with device fingerprinting
- ✅ Automatic cookie handling (no manual token management)
- ✅ Stateless router guards (API introspection with 30s cache)
- ✅ WebSocket authentication via cookies (automatic)
- ✅ Protected routes with redirect preservation

**Documentation:**

- **Auth Service**: See `src/services/README.md` for service layer details
- **Router Guards**: See `src/router/README.md` for authentication guards
- **Authentication Guide**: See `../docs/AUTHENTICATION.md` for complete system documentation

## Quick Start

### Install dependencies

```bash
cd frontend
make install       # Validates Node.js version, offers to install if needed, then installs dependencies
```

The `make install` command will:

1. **Check Node.js version** - Validates Node.js 22.20+ is available
2. **Auto-install Node.js** - If wrong version and nvm is available, **offers to install Node.js 22.20.0** (with confirmation)
3. **Install dependencies** - Runs `npm install` to set up the project

**Interactive prompts:**

- If Node.js version is incompatible and nvm is available, you'll be asked: `"Would you like to install Node.js 22.20.0 via nvm? [y/N]"`
- Type `y` and press Enter to automatically install and activate Node.js 22.20.0
- Type `n` to skip and see manual installation instructions

Alternatively, check prerequisites manually:

```bash
make ensure-node   # Check Node.js version
npm install        # Install dependencies
```

### Available Scripts

- `npm run dev` - Start development server with hot reload
- `npm run build` - Build for production
- `npm run preview` - Preview production build locally
- `npm run test:unit` - Run unit tests with Vitest
- `npm run lint` - Run ESLint
- `npm run format` - Format code with Prettier

## API Integration

The frontend connects to the FastAPI backend through auto-generated TypeScript clients.

### Client Generation

**Automatic Generation**: Both REST and WebSocket clients are automatically generated before development and build:

```bash
npm run dev    # Auto-generates clients, then starts dev server
npm run build  # Auto-generates clients, then builds for production
```

**Manual Generation**:

```bash
# Generate REST API client and WebSocket types
make generate-openapi-client
make generate-asyncapi-types

# Or use Makefile
make generate
```

**Documentation**:

- **Development Guide**: See `../docs/DEVELOPMENT.md`
- **Client Generation**: See `../docs/CLIENT-GENERATION.md`
- **WebSocket Clients**: See `../docs/WEBSOCKET-CLIENTS.md`
- **Testing**: See `../docs/TESTING.md`

### Frontend-Specific Docs

- **WebSocket Pattern**: See `WEBSOCKET-CLIENT-PATTERN.md`
- **Plugin Usage**: See `src/plugins/ws-plugin-usage.md`

### Generated Files

The following directories are auto-generated (gitignored):

- `src/clients_generated/trader-client-generated/` - REST API client
- `src/clients_generated/ws-types-generated/` - WebSocket type definitions

### Environment Configuration

Configure the API base URL in `.env`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

### Available API Endpoints

- **Health Check**: `GET /api/v1/health`
- **API Versions**: `GET /api/v1/versions`
- **Current Version**: `GET /api/v1/versions/current`

## Pages

- **Home** (`/`) - Welcome page with basic information
- **About** (`/about`) - Information about the application
- **API Status** (`/api-status`) - Real-time monitoring of backend API status

### API Status Component

The API Status component displays health and version information for all integrated backend modules in a responsive grid layout.

#### Features

- **Per-Module Monitoring**: Displays health status for each module independently (broker, datafeed, etc.)
- **Response Time Tracking**: Shows response time for each module's health check
- **Documentation Links**: Direct links to OpenAPI docs for each module
- **AsyncAPI Support**: Automatically detects and shows AsyncAPI spec links for modules with WebSocket support
- **Error Visibility**: Displays error states for individual module failures (partial failure support)
- **Mock Support**: Works with fallback client when backend is unavailable
- **Client Type Indicator**: Shows whether using real backend or mock data

#### Architecture

The component uses a modular multi-module architecture:

- **`ApiAdapter.getIntegratedModules()`** - Provides module registry with metadata (name, docs URL, WebSocket support)
- **`WsAdapter.getModules()`** - Detects which modules have WebSocket/AsyncAPI support
- **`ApiService.getAllModulesHealth()`** - Parallel health checks for all modules with error handling
- **`ApiService.getAllModulesVersions()`** - Retrieves version information for all modules

**For detailed API method documentation**, see [Services README](src/services/README.md#multi-module-api-architecture).

**Type System:**

```typescript
interface ModuleHealth {
  moduleName: string
  health: HealthResponse | null
  loading: boolean
  error: string | null
  responseTime?: number
}

interface ModuleVersions {
  moduleName: string
  versions: APIMetadata | null
  loading: boolean
  error: string | null
}
```

#### Adding New Modules

When integrating a new backend module into the API Status display:

1. **Add to ApiAdapter registry** - Update `ApiAdapter.getIntegratedModules()` array with new module metadata
2. **Add routing** - Add switch case in `ApiAdapter.getModuleHealth()` and `getModuleVersions()` for the new module
3. **WebSocket support** (optional) - If module has WebSocket endpoints, update `WsAdapter.getModules()` to include it

The API Status component will automatically detect and display the new module without requiring component-level changes.

## Development Workflow

1. Start the FastAPI backend server:

```bash
cd ../backend
make dev
```

2. Start the Vue.js frontend server:

```bash
npm run dev
```

3. Navigate to http://localhost:5173/api-status to verify the connection between frontend and backend

## Building for Production

1. Build the frontend:

```bash
npm run build
```

2. The built files will be in the `dist/` directory

3. Preview the production build:

```bash
npm run preview
```

## Testing

Run unit tests:

```bash
npm run test:unit
```

## Code Quality

The project uses ESLint and Prettier for code quality:

```bash
# Check linting
npm run lint

# Format code
npm run format
```

## WebSocket Integration

The frontend includes real-time WebSocket clients for streaming market data.

### Documentation

- **WebSocket Clients**: See `../docs/WEBSOCKET-CLIENTS.md` for overview
- **WebSocket Pattern**: See `WEBSOCKET-CLIENT-PATTERN.md` for implementation details
- **Plugin Usage**: See `src/plugins/ws-plugin-usage.md` for integration patterns

### Basic Usage

```typescript
import { WebSocketClientBase } from '@/plugins/wsClientBase'
import type { Bar, BarsSubscriptionRequest } from '@/clients/ws-types-generated'

const client = new WebSocketClientBase<BarsSubscriptionRequest, Bar>('bars')
await client.subscribe({ symbol: 'AAPL', resolution: '1' }, (bar: Bar) =>
  console.log('New bar:', bar),
)
```

### Key Files

- **Base Client**: `src/plugins/wsClientBase.ts` - Core WebSocket implementation
- **WebSocket Adapter**: `src/plugins/wsAdapter.ts` - High-level WebSocket clients wrapper
- **Data Mappers**: `src/plugins/mappers.ts` - Type-safe data transformations between backend/frontend types
  - **⚠️ STRICT NAMING**: All type imports must follow `<TYPE>_Api_Backend`, `<TYPE>_Ws_Backend`, and `<TYPE>` pattern
- **Generated Types**: `src/clients_generated/ws-types-generated/index.ts` - Auto-generated type definitions (from AsyncAPI)
- **Integration**: `src/services/datafeedService.ts` - TradingView integration example
- **Type Generator**: `scripts/generate-ws-types.mjs` - AsyncAPI → TypeScript types

### ⭐ Key Features

- ✅ **Automatic type generation** - Types generated from AsyncAPI spec
- ✅ **No hardcoded lists** - All types auto-discovered
- ✅ **Singleton pattern** - One connection per URL
- ✅ **Auto-connection** - Automatic connection with exponential backoff retry
- ✅ **Full type safety** - TypeScript generics throughout
- ✅ **Server confirmation** - Waits for subscription acknowledgment
- ✅ **Topic-based routing** - Filters messages to relevant subscribers
- ✅ **Reference counting** - Automatic cleanup when no longer needed
- ✅ **Reconnection logic** - Automatic resubscription on reconnect
- ✅ **Zero dependencies** - Uses native WebSocket API

## Recommended IDE Setup

[VS Code](https://code.visualstudio.com/) + [Vue (Official)](https://marketplace.visualstudio.com/items?itemName=Vue.volar) (and disable Vetur).

## Type Support for `.vue` Imports in TS

TypeScript cannot handle type information for `.vue` imports by default, so we replace the `tsc` CLI with `vue-tsc` for type checking. In editors, we need [Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar) to make the TypeScript language service aware of `.vue` types.
