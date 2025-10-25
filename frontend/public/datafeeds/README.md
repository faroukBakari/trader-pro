# Advanced Charts Datafeeds (External Examples - Not Used)

**Status**: ⚠️ **External TradingView Examples - Not Used in Project**  
**Last Reviewed**: October 25, 2025

## Overview

This folder contains **TradingView's example datafeed implementations** from the Charting Library package. These are **reference implementations** provided by TradingView, but **our project uses a custom datafeed implementation**.

## Project's Actual Datafeed

**Our Implementation**: `frontend/src/services/datafeedService.ts`

**Key Differences**:

- **Custom REST API**: Uses our backend API (`/api/v1/datafeed/*`) instead of UDF protocol
- **WebSocket Integration**: Real-time bar updates via WebSocket (not HTTP polling)
- **Smart Client Selection**: Supports both mock fallback and real backend
- **Type Safety**: Full TypeScript integration with TradingView types
- **Broker Integration**: Combined with BrokerTerminalService for trading features

## Why Keep These Examples?

These TradingView examples are kept for:

1. **Reference**: Understanding UDF protocol structure
2. **Documentation**: TradingView's official implementation patterns
3. **Learning**: Comparing our custom approach vs. UDF standard
4. **Library Files**: Part of the TradingView library package

## Contents

- `udf/` - UDF (Universal Data Feed) compatible adapter implementation
- Other example implementations may be present

## Usage Warning

⚠️ **Do NOT use these files in the project**

These files are:

- Excluded from Git (see `FRONTEND-EXCLUSIONS.md`)
- Excluded from linting and type-checking
- Not imported by any project code
- Only for reference and documentation

## Related Documentation

- **Our Datafeed**: `frontend/src/services/datafeedService.ts`
- **UDF vs Custom**: See our implementation comments in DatafeedService
- **WebSocket Integration**: `frontend/WEBSOCKET-CLIENT-BASE.md`
- **Exclusions**: `frontend/FRONTEND-EXCLUSIONS.md`

---

**Note**: If you need to implement a UDF-compatible datafeed, refer to TradingView's official documentation:

- [UDF Protocol](https://www.tradingview.com/charting-library-docs/latest/connecting_data/UDF)
- [Datafeed API](https://www.tradingview.com/charting-library-docs/latest/connecting_data/Datafeed-API)
