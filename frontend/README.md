# Trading API Frontend

A Vue.js frontend application for the Trading API built with TypeScript, Vue Router, Pinia, and Vite.

## Features

- ✅ Vue 3 with Composition API
- ✅ TypeScript support
- ✅ Vue Router for navigation
- ✅ Pinia for state management
- ✅ Vitest for testing
- ✅ ESLint + Prettier for code quality
- ✅ API service integration with FastAPI backend
- ✅ Real-time API status monitoring

## Development Setup

### Prerequisites

- **Node.js 20.19+ or 22.12+** (required by Vite)
  - Will be **automatically installed** if you have [nvm](https://github.com/nvm-sh/nvm)
  - Or check version: `node --version`
  - Manual install: `nvm install 20.19.0 && nvm use 20.19.0`
- npm (comes with Node.js)

## Quick Start

### Install dependencies

```bash
cd frontend
make install       # Validates Node.js version, offers to install if needed, then installs dependencies
```

The `make install` command will:
1. **Check Node.js version** - Validates Node.js 20.19+ or 22.12+ is available
2. **Auto-install Node.js** - If wrong version and nvm is available, **offers to install Node.js 20.19.0** (with confirmation)
3. **Install dependencies** - Runs `npm install` to set up the project

**Interactive prompts:**
- If Node.js version is incompatible and nvm is available, you'll be asked: `"Would you like to install Node.js 20.19.0 via nvm? [y/N]"`
- Type `y` and press Enter to automatically install and activate Node.js 20.19.0
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

The frontend connects to the FastAPI backend through the API service located in `src/services/api.ts`.

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

The frontend includes a robust WebSocket client implementation for real-time data streaming.

### 📚 Documentation

**Complete Documentation Package**: See [`WEBSOCKET-DOCUMENTATION-INDEX.md`](./WEBSOCKET-DOCUMENTATION-INDEX.md) for complete index

**Quick Start**:
- **New Developers**: Start with [`WEBSOCKET-IMPLEMENTATION-SUMMARY.md`](./WEBSOCKET-IMPLEMENTATION-SUMMARY.md)
- **Quick Reference**: Use [`WEBSOCKET-QUICK-REFERENCE.md`](./WEBSOCKET-QUICK-REFERENCE.md) for daily coding
- **Complete Pattern**: Read [`WEBSOCKET-CLIENT-PATTERN.md`](./WEBSOCKET-CLIENT-PATTERN.md) for deep dive
- **Visual Diagrams**: See [`WEBSOCKET-ARCHITECTURE-DIAGRAMS.md`](./WEBSOCKET-ARCHITECTURE-DIAGRAMS.md)

### 🔑 Key Files

- **Base Client**: `src/plugins/wsClientBase.ts` - Generic WebSocket client foundation
- **Bars Client**: `src/plugins/barsClient.ts` - Domain-specific bars data client
- **Types**: `src/plugins/ws-types.ts` - Type definitions
- **Integration**: `src/services/datafeedService.ts` - TradingView integration example

### ⭐ Key Features

- ✅ **Singleton pattern** - One connection per URL
- ✅ **Auto-connection** - Automatic connection with exponential backoff retry
- ✅ **Type safety** - Full TypeScript generics support
- ✅ **Server confirmation** - Waits for subscription acknowledgment
- ✅ **Topic-based routing** - Filters messages to relevant subscribers
- ✅ **Reference counting** - Automatic cleanup when no longer needed
- ✅ **Reconnection logic** - Automatic resubscription on reconnect
- ✅ **Zero dependencies** - Uses native WebSocket API

## Recommended IDE Setup

[VS Code](https://code.visualstudio.com/) + [Vue (Official)](https://marketplace.visualstudio.com/items?itemName=Vue.volar) (and disable Vetur).

## Type Support for `.vue` Imports in TS

TypeScript cannot handle type information for `.vue` imports by default, so we replace the `tsc` CLI with `vue-tsc` for type checking. In editors, we need [Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar) to make the TypeScript language service aware of `.vue` types.
