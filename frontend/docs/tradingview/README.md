# TradingView Integration Documentation

This directory contains documentation specific to TradingView Trading Terminal integration.

---

## Documentation Files

### [BROKER-CONNECTION-ADAPTER.md](./BROKER-CONNECTION-ADAPTER.md)

**Purpose**: Complete reference for TradingView's `IBrokerConnectionAdapterHost` interface (Trading Host API).

**Contents**:

- Trading Host API overview
- Complete interface reference with all methods
- Event-driven architecture patterns
- Reactive values (`IWatchedValue`) usage
- UI update mechanisms
- Notification system
- Account manager configuration

**When to Read**: When implementing broker integration and understanding how to push updates to TradingView UI.

---

### [UI-USAGE-GUIDE.md](./UI-USAGE-GUIDE.md)

**Purpose**: Practical guide for interacting with TradingView Trading Terminal UI using Playwright MCP.

**Contents**:

- UI interaction patterns
- Order placement workflows
- Position management UI
- Account panel interactions
- Testing strategies
- Common UI patterns

**When to Read**: When writing UI tests or debugging TradingView Terminal interactions.

---

### [TYPE-DEFINITIONS.md](./TYPE-DEFINITIONS.md)

**Purpose**: Guide to TradingView TypeScript type definitions and how to use them.

**Contents**:

- Type definition file locations
- Core types reference (Order, Position, Execution, etc.)
- Enum definitions (OrderStatus, OrderType, Side, etc.)
- Type usage patterns
- Type safety best practices

**When to Read**: When writing TypeScript code that integrates with TradingView APIs.

---

## Quick Reference

### Key Interfaces

- **`IBrokerConnectionAdapterHost`**: Trading Host API for pushing updates to TradingView
- **`IBrokerWithoutRealtime`**: Broker API interface (what your service implements)
- **`IDatafeedQuotesApi`**: Market data provider interface

### Key Types

- **`Order`**: Order record with status, prices, quantities
- **`Position`**: Position record with side, quantity, average price
- **`Execution`**: Trade execution record
- **`PreOrder`**: Order placement request
- **`AccountMetainfo`**: Account metadata
- **`InstrumentInfo`**: Symbol trading constraints

### Key Enums

- **`OrderStatus`**: Canceled, Filled, Inactive, Placing, Rejected, Working
- **`OrderType`**: Limit, Market, Stop, StopLimit
- **`Side`**: Buy (1), Sell (-1)
- **`ConnectionStatus`**: Connected, Connecting, Disconnected, Error

---

## Related Documentation

- **[BROKER-INTEGRATION.md](../BROKER-INTEGRATION.md)**: Complete broker integration implementation guide
- **[WEBSOCKET-ARCHITECTURE.md](../WEBSOCKET-ARCHITECTURE.md)**: WebSocket integration patterns
- **[Frontend README](../../README.md)**: Frontend overview and setup
- **[Architecture](../../../ARCHITECTURE.md)**: System architecture overview

---

## External Resources

- **TradingView Docs**: https://www.tradingview.com/charting-library-docs/latest/trading_terminal/
- **Broker API**: https://www.tradingview.com/charting-library-docs/latest/api/interfaces/Charting_Library.IBrokerTerminal/
- **Trading Host**: https://www.tradingview.com/charting-library-docs/latest/api/interfaces/Charting_Library.IBrokerConnectionAdapterHost/

---

**Last Updated**: November 12, 2025  
**Maintained by**: Development Team
