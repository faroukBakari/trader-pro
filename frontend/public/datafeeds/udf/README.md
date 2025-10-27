# UDF Compatible Datafeed (External Example - Not Used)

**Status**: ⚠️ **TradingView Example - Not Used in Project**  
**Last Reviewed**: October 25, 2025

## Important Notice

This is an **external example implementation** from TradingView. **Our project does NOT use this UDF datafeed adapter**. See below for our actual implementation.

## Project's Custom Datafeed

**Our Implementation**: `frontend/src/services/datafeedService.ts`

**Why Custom Instead of UDF?**

1. **Backend Control**: Our backend uses FastAPI, not UDF HTTP endpoints
2. **WebSocket Support**: Real-time bar updates via WebSocket (UDF uses HTTP polling)
3. **Type Safety**: Full TypeScript integration with backend OpenAPI spec
4. **Smart Fallback**: Mock mode for development without backend
5. **Unified API**: Single backend API for both datafeed and broker operations

**Our Backend Endpoints** (Not UDF):

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

**UDF Endpoints** (Standard):

```
GET /config
GET /symbol_info?symbol=AAPL
GET /search?query=AAPL
GET /history?symbol=AAPL&resolution=1D&from=...&to=...
GET /time
GET /marks?symbol=AAPL&from=...&to=...&resolution=1D
```

## About This UDF Implementation

This folder contains [UDF][udf-url] datafeed adapter. It implements [Datafeed API][datafeed-url] and makes HTTP requests using [UDF][udf-url] protocol.

**Original Purpose**: You can use this datafeed adapter to plug your data if you implement [UDF][udf-url] on your server.

**Our Use Case**: We keep this for reference only. Our backend does NOT implement UDF protocol.

This datafeed is implemented in [TypeScript](https://github.com/Microsoft/TypeScript/).

## Folders content

- `./src` folder contains the source code in TypeScript.

- `./lib` folder contains transpiled in es5 code. So, if you do not know how to use TypeScript - you can modify these files to change the result bundle later.

- `./dist` folder contains bundled JavaScript files which can be inlined into a page and used in the Widget Constructor.

## Build & bundle

Before building or bundling your code you need to run `npm install` to install dependencies.

`package.json` contains some handy scripts to build or generate the bundle:

- `npm run compile` to compile TypeScript source code into JavaScript files (output will be in `./lib` folder)
- `npm run bundle-js` to bundle multiple JavaScript files into one bundle (it also bundle polyfills)
- `npm run build` to compile and bundle (it is a combination of all above commands)

NOTE: if you want to minify the bundle code, you need to set `ENV` environment variable to a value different from `development`.

For example:

```bash
export ENV=prod
npm run bundle-js # or npm run build
```

or

```bash
ENV=prod npm run bundle-js
```

or

```bash
ENV=prod npm run build
```

## ⚠️ Usage Warning

**Do NOT use these files in our project**. They are:

- Excluded from Git (see `frontend/FRONTEND-EXCLUSIONS.md`)
- Excluded from linting and type-checking
- Not imported by any project code
- Only for reference and documentation

If you need to modify datafeed behavior, edit `frontend/src/services/datafeedService.ts` instead.

## Related Project Documentation

- **Our Datafeed Service**: `frontend/src/services/datafeedService.ts`
- **Datafeed Service Tests**: `frontend/src/services/__tests__/datafeedService.spec.ts`
- **Datafeed Service README**: `frontend/src/services/__tests__/README.md`
- **WebSocket Integration**: `frontend/WEBSOCKET-CLIENT-BASE.md`
- **Broker Integration**: `frontend/BROKER-TERMINAL-SERVICE.md`

## External TradingView Resources

[udf-url]: https://www.tradingview.com/charting-library-docs/latest/connecting_data/UDF
[datafeed-url]: https://www.tradingview.com/charting-library-docs/latest/connecting_data/Datafeed-API
