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

- Node.js (v16 or higher)
- npm or yarn
- Trading API backend running on http://localhost:8000

### Installation

1. Install dependencies:

```bash
npm install
```

2. Start the development server:

```bash
npm run dev
```

The application will be available at http://localhost:5173

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

## Recommended IDE Setup

[VS Code](https://code.visualstudio.com/) + [Vue (Official)](https://marketplace.visualstudio.com/items?itemName=Vue.volar) (and disable Vetur).

## Type Support for `.vue` Imports in TS

TypeScript cannot handle type information for `.vue` imports by default, so we replace the `tsc` CLI with `vue-tsc` for type checking. In editors, we need [Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar) to make the TypeScript language service aware of `.vue` types.
