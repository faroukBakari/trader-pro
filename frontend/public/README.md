# TradingView Public Assets - Reference Material

**Version**: 1.0.0  
**Last Updated**: November 18, 2025  
**Status**: ✅ Current

> **Note**: This guide consolidates information from `datafeeds/README.md` and `datafeeds/udf/README.md` (archived November 18, 2025).

---

## ⚠️ Important: These Are Examples Only

This folder contains **TradingView's example implementations** from the Charting Library package. These are **reference materials only** and are **NOT used in our project**.

**Do NOT use these files in the project**. They are:

- Excluded from Git (see `frontend/docs/FRONTEND-EXCLUSIONS.md`)
- Excluded from linting and type-checking
- Not imported by any project code
- Only for reference and documentation purposes

---

## Project's Actual Implementation

### Our Custom Datafeed

**Implementation Location**: `frontend/src/services/datafeedService.ts`

### Why Custom Instead of UDF?

Our project uses a custom implementation instead of TradingView's UDF (Universal Data Feed) protocol for several important reasons:

1. **Backend Control**: Our backend uses FastAPI with custom endpoints, not UDF HTTP endpoints
2. **WebSocket Support**: Real-time bar updates via WebSocket (UDF uses HTTP polling)
3. **Type Safety**: Full TypeScript integration with backend OpenAPI spec
4. **Smart Fallback**: Mock mode for development without running backend
5. **Unified API**: Single backend API for both datafeed and broker operations
6. **Broker Integration**: Combined with BrokerTerminalService for trading features

### Our Backend Endpoints (Custom)

```typescript
// Historical bars
GET /api/v1/datafeed/history?symbol=AAPL&resolution=1D&from=...&to=...

// Symbol search
GET /api/v1/datafeed/search?query=AAPL

// Symbol info
GET /api/v1/datafeed/symbols?symbol=AAPL

// Real-time bars
WebSocket: ws://localhost:8000/ws
Topic: bars:SYMBOL:RESOLUTION
```

### UDF Endpoints (Standard - Not Used)

For reference, the standard UDF protocol uses these endpoints:

```
GET /config
GET /symbol_info?symbol=AAPL
GET /search?query=AAPL
GET /history?symbol=AAPL&resolution=1D&from=...&to=...
GET /time
GET /marks?symbol=AAPL&from=...&to=...&resolution=1D
```

**We do NOT implement these endpoints** - our backend uses the custom endpoints shown above.

---

## Public Folder Contents

### External Libraries

- `charting_library/` - TradingView Charting Library (minified external code)
- `trading_terminal/` - TradingView Trading Terminal library
- `advanced_charting_library/` - TradingView Advanced Chart library

### Example Implementations

- `datafeeds/` - TradingView datafeed example implementations
  - `udf/` - UDF (Universal Data Feed) compatible adapter implementation
  - Other example implementations

---

## Datafeed Examples Overview

### What's Included

The `datafeeds/` folder contains example datafeed implementations provided by TradingView, including:

- **UDF Adapter**: Reference implementation of the UDF protocol
- **Example Code**: TypeScript/JavaScript examples showing datafeed patterns
- **Build Scripts**: Tools for bundling and compiling the examples (not used by us)

### Why Keep These Examples?

We keep these TradingView examples for:

1. **Reference**: Understanding UDF protocol structure and patterns
2. **Documentation**: TradingView's official implementation examples
3. **Learning**: Comparing our custom approach vs. UDF standard
4. **Library Files**: Part of the TradingView library package distribution

---

## UDF Adapter Reference

### About the UDF Implementation

The `datafeeds/udf/` folder contains a [UDF][udf-url] datafeed adapter that implements the [Datafeed API][datafeed-url] and makes HTTP requests using the [UDF][udf-url] protocol.

**Original Purpose**: You can use this datafeed adapter to plug your data if you implement UDF on your server.

**Our Use Case**: We keep this for reference only. Our backend does **NOT** implement the UDF protocol.

This datafeed example is implemented in [TypeScript](https://github.com/Microsoft/TypeScript/).

### Folder Structure

- `./src` - TypeScript source code
- `./lib` - Transpiled ES5 code
- `./dist` - Bundled JavaScript files for browser use

---

## Build Instructions (Reference Only)

**Note**: These build instructions are for the example UDF adapter only. You do NOT need to run these commands for our project.

### Prerequisites

```bash
cd datafeeds/udf
npm install
```

### Build Commands

```bash
# Compile TypeScript to JavaScript
npm run compile

# Bundle JavaScript files
npm run bundle-js

# Compile and bundle
npm run build
```

### Production Build

To minify the bundle code, set the `ENV` environment variable:

```bash
# Option 1
export ENV=prod
npm run build

# Option 2
ENV=prod npm run build
```

**Again**: These commands are for reference only. Our project uses the custom datafeed implementation in `frontend/src/services/datafeedService.ts`.

---

## Related Project Documentation

### Our Implementation

- **[Datafeed Service](../src/services/datafeedService.ts)** - Our custom datafeed implementation
- **[Datafeed Tests](../src/services/__tests__/datafeedService.spec.ts)** - Test coverage
- **[Services README](../src/services/README.md)** - Service layer architecture
- **[Services Testing](../src/services/__tests__/README.md)** - Testing strategies

### Architecture & Integration

- **[WebSocket Architecture](../docs/WEBSOCKET-ARCHITECTURE.md)** - WebSocket client patterns
- **[Broker Integration](../docs/BROKER-INTEGRATION.md)** - TradingView broker integration
- **[Frontend README](../README.md)** - Frontend overview
- **[Frontend Exclusions](../docs/FRONTEND-EXCLUSIONS.md)** - Configuration exclusions

### Project-Wide Documentation

- **[Client Generation](../../docs/CLIENT-GENERATION.md)** - API client generation
- **[WebSocket Architecture](../docs/WEBSOCKET-ARCHITECTURE.md)** - WebSocket implementation overview
- **[Makefile Guide](../../docs/MAKEFILE-GUIDE.md)** - Build commands

---

## External TradingView Resources

If you need to understand the UDF protocol or implement a UDF-compatible datafeed, refer to TradingView's official documentation:

- **[UDF Protocol][udf-url]** - Universal Data Feed specification
- **[Datafeed API][datafeed-url]** - TradingView Datafeed API reference
- **[Charting Library Docs](https://www.tradingview.com/charting-library-docs/)** - Complete documentation

[udf-url]: https://www.tradingview.com/charting-library-docs/latest/connecting_data/UDF
[datafeed-url]: https://www.tradingview.com/charting-library-docs/latest/connecting_data/Datafeed-API

---

## Key Differences: Our Implementation vs. UDF

| Aspect                 | UDF Standard    | Our Implementation      |
| ---------------------- | --------------- | ----------------------- |
| **Protocol**           | HTTP REST only  | HTTP REST + WebSocket   |
| **Endpoints**          | Fixed UDF paths | Custom FastAPI routes   |
| **Real-time**          | HTTP polling    | WebSocket push          |
| **Type Safety**        | JavaScript      | TypeScript with OpenAPI |
| **Backend**            | Any UDF server  | FastAPI Python backend  |
| **Mock Support**       | No              | Yes (fallback mode)     |
| **Broker Integration** | Separate        | Unified service         |

---

## Usage Warning

⚠️ **IMPORTANT**: These example files are reference material only.

**Do NOT**:

- Import these files in project code
- Modify these files for project features
- Use these files in production
- Commit changes to these files

**DO**:

- Use our custom datafeed implementation
- Refer to these examples for learning
- Consult TradingView documentation
- Edit `frontend/src/services/datafeedService.ts` for datafeed changes

---

**Last Updated**: November 18, 2025  
**Maintained by**: Development Team  
**Status**: ✅ Current (Consolidated from datafeeds/README.md and datafeeds/udf/README.md)
