# TradingView Integration Documentation

This directory contains documentation specific to TradingView Trading Terminal integration.

> **⚠️ Important**: We use a **forked semi-bundled version** of TradingView Trading Terminal with **no official support**. All customizations require reverse engineering. See [public/README.md](../../public/README.md) for maintenance overview.

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

### [BUNDLE-MAINTENANCE.md](./BUNDLE-MAINTENANCE.md)

**Purpose**: ⭐ **PRIMARY MAINTENANCE GUIDE** - Comprehensive guide for maintaining and debugging TradingView Trading Terminal bundles.

**Contents**:

- Bundle architecture and obfuscation patterns
- Debugging methodology (unobfuscation, console logging strategies)
- Case study 1: Position bracket pre-population bug
- Case study 2: Position dialog field sync bug
- RxJS patterns in TradingView bundles (combineLatest, startWith, observables)
- Common bundle issues and solutions
- Maintenance best practices (preserve original code, document changes)
- Reference: Key classes (Pt, bt, ie, gt)
- Appendix: Tick value calculation

**When to Read**: ⭐ **START HERE** for any bundle modification work, debugging dialog issues, investigating field sync problems, or understanding obfuscated code.

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

- **[public/README.md](../../public/README.md)** - ⭐ Bundle maintenance overview, upgrade strategy, known issues
- **[BROKER-INTEGRATION.md](../BROKER-INTEGRATION.md)** - Complete broker integration implementation guide
- **[WEBSOCKET-ARCHITECTURE.md](../WEBSOCKET-ARCHITECTURE.md)** - WebSocket integration patterns
- **[Frontend README](../../README.md)** - Frontend overview and setup
- **[Architecture](../../../docs/ARCHITECTURE.md)** - System architecture overview

---

## Forked Bundle Reality

We maintain a **forked, patched, reverse-engineered** TradingView Trading Terminal:

- ⚠️ **No official support** - All customizations via reverse engineering
- ⚠️ **Bundle modifications** - Direct JavaScript patches to obfuscated code
- ✅ **Comprehensive docs** - Every patch documented in BUNDLE-MAINTENANCE.md
- ✅ **Known issues** - Solutions for Position dialog, bracket orders, field sync
- ⚠️ **Upgrade risk** - Version updates break our patches

**For maintenance work, always start with**:

1. [BUNDLE-MAINTENANCE.md](./BUNDLE-MAINTENANCE.md) - Debugging & case studies
2. [public/README.md](../../public/README.md) - Maintenance workflow & upgrade strategy

---

## External Resources

- **TradingView Docs Portal**: https://www.tradingview.com/charting-library-docs/latest/trading_terminal/
- **Full API Reference**: https://www.tradingview.com/charting-library-docs/latest/api/
- **Broker API**: https://www.tradingview.com/charting-library-docs/latest/api/interfaces/Charting_Library.IBrokerTerminal/
- **Trading Host**: https://www.tradingview.com/charting-library-docs/latest/api/interfaces/Charting_Library.IBrokerConnectionAdapterHost/
- **Datafeed API**: https://www.tradingview.com/charting-library-docs/latest/connecting_data/datafeed-api/
- **Tutorials**: https://www.tradingview.com/charting-library-docs/latest/tutorials/
- **Getting Started**: https://www.tradingview.com/charting-library-docs/latest/getting_started/
- **GitHub Examples**: https://github.com/tradingview/charting-library-examples
- **GitHub Tutorial Code**: https://github.com/tradingview/charting-library-tutorial

---

**Last Updated**: November 30, 2025  
**Maintained by**: Development Team
