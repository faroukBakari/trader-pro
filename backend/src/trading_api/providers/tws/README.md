# TWS Datafeed Provider Implementation Guide

**Status:** Implementation Guide (POC: search_symbols)
**Date:** November 25, 2025
**Architecture:** Provider Pattern (Three-Layer System)

---

## 1. Overview

### 1.1 System Flow

```
Frontend (TradingView)
        │ WebSocket
        ▼
DatafeedService (100% provider-agnostic)
        │ • Works with: Bar, SearchSymbolResultItem, TimeFrame (domain models)
        │ • Knows nothing about: Contract, TWS types
        │ requires capability="datafeed"
        ▼
ProviderRegistry
        │ injects
        ▼
TWSProvider (Layer 3 - implements DatafeedCapability)
        │ • Domain conversion: domain types ↔ TWS types
        │ • Delegates async requests to TWSClient
        │ • Error translation: TWSError → DatafeedError
        │ uses
        ▼
TWSClient (Layer 2 - AsyncIO Bridge + EWrapper)
        │ • Inherits EWrapper for TWS callbacks
        │ • asyncio.Future registry for request/response
        │ • Async methods: reqMatchingSymbols(), etc.
        │ • loop.call_soon_threadsafe() for thread-safe Future resolution
        │ uses
        ▼
IBSocket (Layer 1 - Raw TCP Protocol)
        │ • Pure socket management (connect, send, receive)
        │ • TWS handshake protocol (API version negotiation)
        │ • Message framing (length-prefix encoding)
        │ • Runs in daemon thread (_client_loop)
        ▼
TWS/IB Gateway (localhost:7497)
```

### 1.2 UML Class Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                   DatafeedCapability                         │
│                      <<interface>>                           │
├──────────────────────────────────────────────────────────────┤
│ + search_symbols(pattern) → List[SearchSymbolResultItem]    │
│ + get_symbol_info(symbol, exchange) → SymbolInfo            │
│ + get_historical_bars(...) → List[Bar]                      │
│ + subscribe_realtime_bars(symbol, callback) → int           │
│ + subscribe_market_data(symbol, callback) → int             │
│ + unsubscribe_realtime_bars(subscription_id)                │
│ + unsubscribe_market_data(subscription_id)                  │
└──────────────────────────────────────────────────────────────┘
                            △
                            │ implements
                            │
┌───────────────────────────┴──────────────────────────────────┐
│                      TWSProvider                             │
│              (Layer 3 - DatafeedCapability impl)             │
├──────────────────────────────────────────────────────────────┤
│ - _tws_client: TWSClient                                     │
│ - _config: TWSProviderConfig                                 │
├──────────────────────────────────────────────────────────────┤
│ + search_symbols(pattern) → List[SearchSymbolResultItem]    │
│   # Delegates to _tws_client.reqMatchingSymbols()           │
│   # Converts ContractDescription → SearchSymbolResultItem   │
│                                                              │
│ # Domain Mappers (in tws_mappers.py)                        │
│ - contract_description_to_search_result(desc) → ...         │
└──────────────────────────────────────────────────────────────┘
                            │
                            │ uses
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                       TWSClient                              │
│              (Layer 2 - AsyncIO Bridge)                      │
│                  extends TWSClientHelper                     │
├──────────────────────────────────────────────────────────────┤
│ - _ibsocket: IBSocket                                        │
│ - _loop: asyncio.AbstractEventLoop                           │
│ - _futures: dict[int, asyncio.Future]                        │
│ - _next_req_id: int                                          │
│ - _running: threading.Event                                  │
│ - _client_thread: threading.Thread                           │
├──────────────────────────────────────────────────────────────┤
│ # Async Request Methods                                      │
│ + reqMatchingSymbols(pattern) → List[ContractDescription]   │
│                                                              │
│ # EWrapper Callbacks (resolve futures)                       │
│ + symbolSamples(reqId, contractDescriptions)                │
│ + error(reqId, errorTime, errorCode, errorString)           │
│                                                              │
│ # Internal                                                   │
│ - _resolve_future(reqId, result)                            │
│ - _reject_future(reqId, exception)                          │
│ - _client_loop()  # runs in daemon thread                   │
└──────────────────────────────────────────────────────────────┘
                            │ extends
                            ▼
                    ┌──────────────────┐
                    │    EWrapper      │
                    │   <<ibapi>>      │
                    └──────────────────┘
                            │
                            │ uses
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                        IBSocket                              │
│              (Layer 1 - Raw TCP Protocol)                    │
├──────────────────────────────────────────────────────────────┤
│ - _host: str                                                 │
│ - _port: int                                                 │
│ - _client_id: int                                            │
│ - _socket: socket                                            │
│ - _server_version: int                                       │
│ - _lock: threading.Lock                                      │
├──────────────────────────────────────────────────────────────┤
│ + connect()  # TWS handshake                                │
│ + disconnect()                                               │
│ + isConnected() → bool                                       │
│ + send_message(msgId, values)                               │
│ + receive_data() → (msgId, data, buf, buf_siz)              │
└──────────────────────────────────────────────────────────────┘
                            │
                            │ TCP Socket
                            ▼
                 ┌─────────────────────┐
                 │   TWS/IB Gateway    │
                 │  (localhost:7497)   │
                 └─────────────────────┘


┌──────────────────────────────────────────────────────────────┐
│                   DatafeedService                            │
│              (100% Provider-Agnostic)                        │
├──────────────────────────────────────────────────────────────┤
│ - _providers: List[Provider]                                 │
│ - _topic_to_req_id: dict[str, int | List[int]]              │
├──────────────────────────────────────────────────────────────┤
│ + datafeed_provider → DatafeedCapability                    │
│                                                              │
│ # Business Logic (uses domain models only)                   │
│ + search_symbols(user_input, ...) → List[...]               │
│ + get_bars(symbol, resolution, ...) → List[Bar]             │
│ + create_topic(topic, topic_update)                         │
│ + remove_topic(topic)                                        │
│                                                              │
│ # Helper Methods                                             │
│ - _subscribe_bars(topic, symbol, callback)                  │
│ - _subscribe_quotes(topic, symbols, callback)               │
└──────────────────────────────────────────────────────────────┘
                            │
                            │ uses (via capability)
                            ▼
                  DatafeedCapability
                      (interface)


Domain Models (models/datafeed.py):
┌─────────────┐  ┌──────────────────┐  ┌──────────┐
│     Bar     │  │ SymbolSearchResult│  │SymbolInfo│
├─────────────┤  ├──────────────────┤  ├──────────┤
│ time: int   │  │ symbol: str      │  │name: str │
│ open: float │  │ exchange: str    │  │type: str │
│ high: float │  │ type: str        │  │...       │
│ low: float  │  │ ticker: str      │  │          │
│ close: float│  │ currency: str    │  │          │
│ volume: int │  └──────────────────┘  └──────────┘
└─────────────┘

TWS Models (ibapi package - used ONLY in TWSProvider):
┌──────────────┐  ┌───────────────────┐  ┌─────────────────┐
│  Contract    │  │ContractDescription│  │    BarData      │
├──────────────┤  ├───────────────────┤  ├─────────────────┤
│ symbol: str  │  │ contract: Contract│  │ date: str       │
│ secType: str │  │ derivativeSecTypes│  │ open: float     │
│ exchange: str│  └───────────────────┘  │ high: float     │
│ currency: str│                         │ low: float      │
└──────────────┘                         │ close: float    │
                                         │ volume: Decimal │
                                         └─────────────────┘
```

### 1.3 Threading Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Main Thread (FastAPI)                        │
│                                                                     │
│  ┌──────────────────┐         ┌──────────────────┐                 │
│  │ DatafeedService  │────────>│   TWSProvider    │                 │
│  │  (async/await)   │         │   (async/await)  │                 │
│  └──────────────────┘         └─────────┬────────┘                 │
│                                         │                           │
│                                         │ await reqMatchingSymbols()│
│                                         ▼                           │
│                               ┌──────────────────┐                  │
│                               │    TWSClient     │                  │
│                               │  (async methods) │                  │
│                               └─────────┬────────┘                  │
│                                         │                           │
│                                         │ asyncio.Future            │
│                                         │ (awaited in main thread)  │
└─────────────────────────────────────────┼───────────────────────────┘
                                          │
                                          │ loop.call_soon_threadsafe()
                                          │ (future.set_result/set_exception)
                                          │
┌─────────────────────────────────────────┼───────────────────────────┐
│                     Daemon Thread (_client_loop)                    │
│                                         │                           │
│                               ┌─────────▼────────┐                  │
│                               │    TWSClient     │                  │
│                               │ (EWrapper cbs)   │                  │
│                               │ symbolSamples()  │                  │
│                               │ error()          │                  │
│                               └─────────┬────────┘                  │
│                                         │                           │
│                                         │ Decoder.interpret()       │
│                                         │ (parses TWS messages)     │
│                                         ▼                           │
│                               ┌──────────────────┐                  │
│                               │     IBSocket     │                  │
│                               │  receive_data()  │                  │
│                               │  send_message()  │                  │
│                               └─────────┬────────┘                  │
│                                         │                           │
│                                         │ TCP Socket (blocking I/O) │
└─────────────────────────────────────────┼───────────────────────────┘
                                          │
                                 ┌────────┴────────┐
                                 │  TWS/IB Gateway │
                                 │ (localhost:7497)│
                                 └─────────────────┘


Data Flow (search_symbols Example):

1. Service calls             →  provider.search_symbols("AAPL")
                                        │
2. Provider delegates        →  _tws_client.reqMatchingSymbols("AAPL")
                                        │
3. TWSClient creates Future  →  future = loop.create_future()
                                        │
4. IBSocket sends request    →  send_message(REQ_MATCHING_SYMBOLS, [reqId, "AAPL"])
                                        │
5. TWS Gateway responds      →  TCP Socket (localhost:7497)
                                        │
6. IBSocket receives data    →  receive_data() in daemon thread
                                        │
7. Decoder parses message    →  Decoder.interpret() → symbolSamples()
                                        │
8. TWSClient resolves        →  loop.call_soon_threadsafe(future.set_result, data)
                                        │
9. Provider converts         →  contract_description_to_search_result()
                                        │
10. Service receives         →  List[SearchSymbolResultItem]


Thread Safety Boundaries:

┌────────────────────────────────────────────────────────────────────┐
│ Main Thread (AsyncIO)                                              │
│ • asyncio.Future created and awaited                               │
│ • Domain conversion (TWS → SearchSymbolResultItem)                 │
│ • NO direct socket operations                                      │
└────────────────────────────────────────────────────────────────────┘
                              │
                              │ loop.call_soon_threadsafe()
                              │ (thread-safe Future resolution)
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│ Daemon Thread (_client_loop)                                       │
│ • IBSocket.connect() - blocking socket operations                  │
│ • IBSocket.receive_data() - blocking recv()                        │
│ • Decoder.interpret() - parses TWS messages                        │
│ • EWrapper callbacks (symbolSamples, error, etc.)                  │
│ • _resolve_future() / _reject_future() - cross-thread signaling    │
└────────────────────────────────────────────────────────────────────┘
```

**Key Threading Principles:**

- **Single Daemon Thread**: One thread handles all socket I/O and message parsing
- **No EClient/EReader**: Custom IBSocket replaces complex ibapi threading
- **Future-Based Bridge**: `asyncio.Future` + `loop.call_soon_threadsafe()` for async/await
- **Testable Design**: `TWSClientHelper` accepts mock IBSocket for unit testing

### 1.4 Design Principles

- **Capability-Based**: TWSProvider implements DatafeedCapability interface
- **Auto-Discovery**: Provider registered via directory convention
- **Multi-Capability Ready**: Single provider can implement datafeed + broker capabilities
- **Configuration Auto-Loading**: BaseSettings pattern with TWS\_ prefix
- **100% Provider-Agnostic Service**: Service uses ONLY domain models
- **Zero TWS Knowledge in Service**: Service layer has NO imports from `ibapi` package
- **Three-Layer Separation**:
  - **TWSProvider** (Layer 3): Domain conversion, DatafeedCapability implementation
  - **TWSClient** (Layer 2): AsyncIO bridge, EWrapper callbacks, Future management
  - **IBSocket** (Layer 1): Raw TCP protocol, message framing, socket I/O
- **Testable Design**: `TWSClientHelper` base class allows mock injection for testing
- **Single Thread I/O**: One daemon thread for all socket operations (simpler than EClient/EReader)

### 1.5 File Structure

```
backend/src/trading_api/
├── models/
│   ├── market.py                            # Domain models (Bar, SearchSymbolResultItem, etc.)
│   ├── common.py                            # CapabilitySpec, DatafeedError
│   └── providers/
│       └── tws/
│           └── tws_configs.py               # TWSProviderConfig
│
├── providers/
│   ├── base.py                              # Provider base class
│   ├── capabilities/
│   │   └── datafeed.py                      # DatafeedCapability interface
│   └── tws/
│       ├── __init__.py                      # TWSProvider (Layer 3)
│       ├── tws_connection.py                # TWSClient, TWSClientHelper, IBSocket (Layers 1-2)
│       ├── tws_mappers.py                   # Domain mappers (ContractDescription → SearchSymbolResultItem)
│       └── tests/
│           ├── test_config.py               # TWSProviderConfig validation tests
│           ├── test_connection.py           # TWSClientHelper tests (mocked IBSocket)
│           └── test_provider.py             # TWSProvider tests (mocked TWSClient)
│
└── modules/
    └── datafeed/
        └── service.py                       # DatafeedService (provider-agnostic)
```

---

## 2. TWS Library Installation

### 2.1 Overview

The TWS API (`ibapi`) is Interactive Brokers' official Python client library for trading and market data. It's located in `backend/external_packages/tws/source/pythonclient/` and must be installed as a local package dependency.

**Key Requirements:**

- **Python**: 3.11.0+
- **Protobuf**: 5.29.3 (exact version required by TWS API)
- **TWS API Version**: 10.37.02

### 2.2 Installation Steps

#### Step 1: Add Dependencies to Poetry

Add the TWS API as a local editable package and the required protobuf version:

```bash
cd backend

# Install TWS API from local path
poetry add ./external_packages/tws/source/pythonclient

# Install exact protobuf version (critical - TWS API requires 5.29.3)
poetry add protobuf==5.29.3
```

**Alternative: Manual pyproject.toml Edit**

```toml
[tool.poetry.dependencies]
# ... existing dependencies ...
ibapi = {path = "external_packages/tws/source/pythonclient", develop = true}
protobuf = "5.29.3"
```

Then run:

```bash
poetry install
```

#### Step 2: Verify Installation

```bash
# Check installed packages
poetry show ibapi
poetry show protobuf

# Quick import test
poetry run python -c "from ibapi.client import EClient; from ibapi.wrapper import EWrapper; print('✓ TWS API installed')"
```

### 2.3 Validation Script

**File:** `backend/scripts/validate_tws_install.py`

```python
"""TWS API Installation Validator"""
import sys
from pathlib import Path

def validate_tws_installation() -> bool:
    """Validate TWS API installation and dependencies"""
    errors = []
    warnings = []

    print("=" * 60)
    print("TWS API Installation Validation")
    print("=" * 60)

    # 1. Import check
    try:
        import ibapi
        print("✓ ibapi package imported successfully")
    except ImportError as e:
        errors.append(f"✗ Failed to import ibapi: {e}")
        return False

    # 2. Version check
    try:
        from ibapi import get_version_string
        version = get_version_string()
        expected = "10.37.02"
        if version == expected:
            print(f"✓ TWS API version: {version}")
        else:
            warnings.append(f"⚠ Version mismatch: {version} != {expected}")
    except Exception as e:
        errors.append(f"✗ Version check failed: {e}")

    # 3. Protobuf check
    try:
        import google.protobuf
        from google.protobuf import __version__ as pb_version
        expected_pb = "5.29.3"
        if pb_version == expected_pb:
            print(f"✓ Protobuf version: {pb_version}")
        elif pb_version.startswith("5.29"):
            warnings.append(f"⚠ Protobuf version: {pb_version} (expected {expected_pb})")
        else:
            errors.append(f"✗ Protobuf incompatible: {pb_version} (requires 5.29.x)")
    except ImportError as e:
        errors.append(f"✗ Protobuf not installed: {e}")

    # 4. Core components check
    try:
        from ibapi.client import EClient
        from ibapi.wrapper import EWrapper
        from ibapi.contract import Contract
        from ibapi.order import Order
        from ibapi.common import BarData
        print("✓ Core TWS classes imported successfully")
    except ImportError as e:
        errors.append(f"✗ Failed to import core classes: {e}")

    # 5. Protobuf files check
    try:
        from ibapi.protobuf import Order_pb2, Contract_pb2, Execution_pb2
        print("✓ Protobuf generated files available")
    except ImportError as e:
        errors.append(f"✗ Protobuf files missing or corrupted: {e}")
        errors.append("  → Regenerate: cd external_packages/tws/source && protoc ...")

    # 6. Path verification
    ibapi_path = Path(ibapi.__file__).parent
    expected_path_marker = "external_packages/tws/source/pythonclient/ibapi"
    if expected_path_marker in str(ibapi_path):
        print(f"✓ TWS API loaded from local package: {ibapi_path.parent.name}/")
    else:
        warnings.append(f"⚠ Unexpected install path: {ibapi_path}")
        warnings.append("  → Expected: .../external_packages/tws/source/pythonclient/ibapi")

    # 7. Test basic functionality
    try:
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"

        order = Order()
        order.action = "BUY"
        order.orderType = "LMT"
        order.totalQuantity = 100
        order.lmtPrice = 150.0

        print("✓ Contract and Order objects created successfully")
    except Exception as e:
        errors.append(f"✗ Failed to create TWS objects: {e}")

    # Summary
    print("\n" + "=" * 60)
    if warnings:
        print("WARNINGS:")
        for warning in warnings:
            print(f"  {warning}")
        print()

    if errors:
        print("❌ VALIDATION FAILED:")
        for error in errors:
            print(f"  {error}")
        print("=" * 60)
        return False
    else:
        print("✅ TWS API installation validated successfully!")
        print("=" * 60)
        return True

if __name__ == "__main__":
    success = validate_tws_installation()
    sys.exit(0 if success else 1)
```

**Run Validation:**

```bash
cd backend
poetry run python scripts/validate_tws_install.py
```

**Expected Output:**

```
============================================================
TWS API Installation Validation
============================================================
✓ ibapi package imported successfully
✓ TWS API version: 10.37.02
✓ Protobuf version: 5.29.3
✓ Core TWS classes imported successfully
✓ Protobuf generated files available
✓ TWS API loaded from local package: pythonclient/
✓ Contract and Order objects created successfully

============================================================
✅ TWS API installation validated successfully!
============================================================
```

### 2.4 Makefile Integration

Add TWS installation targets to `backend/Makefile`:

```makefile
.PHONY: install-tws validate-tws regenerate-tws-proto

install-tws:  ## Install TWS API and dependencies
	@echo "Installing TWS API from local package..."
	poetry add ./external_packages/tws/source/pythonclient
	poetry add protobuf==5.29.3
	@echo "\nValidating installation..."
	@$(MAKE) validate-tws

validate-tws:  ## Validate TWS API installation
	@poetry run python scripts/validate_tws_install.py

regenerate-tws-proto:  ## Regenerate protobuf files (advanced - only if needed)
	@echo "Regenerating TWS protobuf files..."
	@command -v protoc >/dev/null 2>&1 || { echo "Error: protoc not found. Install: pip install protobuf"; exit 1; }
	cd external_packages/tws/source && \
		protoc --proto_path=./proto --python_out=./pythonclient/ibapi/protobuf proto/*.proto
	@echo "Protobuf files regenerated. Run 'make validate-tws' to verify."
```

**Usage:**

```bash
# Install TWS API
make install-tws

# Validate existing installation
make validate-tws

# Regenerate protobuf (only if files corrupted or protoc version changed)
make regenerate-tws-proto
```

### 2.5 Troubleshooting

#### Issue: Import Error - "No module named 'ibapi'"

**Cause**: TWS API not installed or wrong virtual environment active

**Solution**:

```bash
cd backend
poetry install
source .venv/bin/activate  # or: poetry shell
poetry run python -c "import ibapi; print('OK')"
```

#### Issue: Protobuf Version Mismatch

**Cause**: Wrong protobuf version (TWS API requires exactly 5.29.3)

**Solution**:

```bash
poetry remove protobuf
poetry add protobuf==5.29.3
```

#### Issue: "ImportError: cannot import name 'Order_pb2'"

**Cause**: Protobuf files not generated or corrupted

**Solution**:

```bash
# Regenerate protobuf files
make regenerate-tws-proto

# Or manually:
cd backend/external_packages/tws/source
protoc --proto_path=./proto --python_out=./pythonclient/ibapi/protobuf proto/*.proto
```

#### Issue: Path Points to System ibapi Instead of Local Package

**Cause**: System-wide `ibapi` installed via pip conflicts with local package

**Solution**:

```bash
# Remove system-wide ibapi
pip uninstall ibapi

# Reinstall from local package
cd backend
poetry install
```

#### Issue: Protoc Not Found

**Cause**: Protocol buffer compiler not installed

**Solution**:

```bash
# Install protobuf compiler
pip install protobuf

# Or system package manager:
# Ubuntu/Debian: sudo apt-get install protobuf-compiler
# macOS: brew install protobuf
# Verify: protoc --version
```

### 2.6 Protobuf Files Reference

The TWS API uses Protocol Buffers for efficient message serialization. Generated Python files are pre-compiled and located in:

```
backend/external_packages/tws/source/pythonclient/ibapi/protobuf/
├── CancelOrderRequest_pb2.py
├── ComboLeg_pb2.py
├── Contract_pb2.py
├── DeltaNeutralContract_pb2.py
├── ErrorMessage_pb2.py
├── Execution_pb2.py
├── ExecutionDetails_pb2.py
├── ExecutionDetailsEnd_pb2.py
├── ExecutionFilter_pb2.py
├── ExecutionRequest_pb2.py
├── GlobalCancelRequest_pb2.py
├── OpenOrder_pb2.py
├── OpenOrdersEnd_pb2.py
├── Order_pb2.py
├── OrderAllocation_pb2.py
├── OrderCancel_pb2.py
├── OrderCondition_pb2.py
├── OrderState_pb2.py
├── OrderStatus_pb2.py
├── PlaceOrderRequest_pb2.py
└── SoftDollarTier_pb2.py
```

**Source `.proto` files** (used for regeneration):

```
backend/external_packages/tws/source/proto/*.proto
```

**Regeneration is only needed if:**

- Protobuf compiler version changes significantly
- Custom modifications to `.proto` files (not recommended)
- Files become corrupted

### 2.7 CI/CD Integration

Add TWS installation validation to your CI pipeline:

```yaml
# .github/workflows/backend-tests.yml
jobs:
  test:
    steps:
      - name: Install Dependencies
        run: |
          cd backend
          poetry install

      - name: Validate TWS API Installation
        run: |
          cd backend
          poetry run python scripts/validate_tws_install.py

      - name: Run Tests
        run: |
          cd backend
          poetry run pytest
```

### 2.8 Development Workflow

**First-Time Setup:**

```bash
# 1. Clone repository
git clone <repo>

# 2. Install backend dependencies (includes TWS API)
cd backend
poetry install

# 3. Validate TWS installation
make validate-tws

# 4. Start development
poetry shell
```

**Daily Workflow:**

```bash
# Activate environment
cd backend
poetry shell

# TWS API is already installed - just import and use
python -c "from ibapi.client import EClient; print('Ready!')"
```

**Updating TWS API Version:**

```bash
# Update local TWS source files in external_packages/tws/
# Then reinstall:
cd backend
poetry update ibapi
make validate-tws
```

---

## 3. Domain Models

### 3.1 Core Models

**File:** `backend/src/trading_api/models/datafeed.py`

| Model                  | Fields                                                                                                                                                                                                                               | Purpose                  |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------ |
| **Bar**                | `time: int`<br>`open: float`<br>`high: float`<br>`low: float`<br>`close: float`<br>`volume: int`<br>`symbol: str \| None`                                                                                                            | OHLCV market data        |
| **SymbolSearchResult** | `symbol: str`<br>`exchange: str`<br>`type: str`<br>`description: str`<br>`ticker: str`<br>`currency: str`                                                                                                                            | Symbol search results    |
| **SymbolInfo**         | `name: str`<br>`description: str`<br>`type: str`<br>`session: str`<br>`timezone: str`<br>`ticker: str`<br>`exchange: str`<br>`minmov: int`<br>`pricescale: int`<br>`has_intraday: bool`<br>`has_daily: bool`<br>`currency_code: str` | Detailed symbol metadata |
| **QuoteData**          | `symbol: str`<br>`bid: float \| None`<br>`ask: float \| None`<br>`last: float \| None`<br>`volume: int \| None`<br>`timestamp: int`                                                                                                  | Real-time tick data      |
| **TimeFrame**          | `SEC_5 = "5"`<br>`SEC_10 = "10"`<br>`MIN_1 = "1"`<br>`MIN_5 = "5"`<br>`MIN_15 = "15"`<br>`MIN_30 = "30"`<br>`HOUR_1 = "60"`<br>`DAY_1 = "1D"`<br>`WEEK_1 = "1W"`<br>`MONTH_1 = "1M"`                                                 | Timeframe enum           |

### 3.2 TWS-Specific Models

**File:** TWS API (`ibapi` package) - used ONLY inside TWSProvider

| Model                   | Fields                                                                                               | Purpose                    |
| ----------------------- | ---------------------------------------------------------------------------------------------------- | -------------------------- |
| **Contract**            | `symbol: str`<br>`secType: str`<br>`exchange: str`<br>`currency: str`<br>`primaryExchange: str`      | TWS contract specification |
| **BarData**             | `date: str`<br>`open: float`<br>`high: float`<br>`low: float`<br>`close: float`<br>`volume: Decimal` | TWS historical bar         |
| **ContractDescription** | `contract: Contract`<br>`derivativeSecTypes: List[str]`                                              | TWS symbol search result   |
| **ContractDetails**     | `contract: Contract`<br>`longName: str`<br>`tradingHours: str`<br>`timeZoneId: str`                  | TWS detailed contract info |

### 3.3 Request Mappers (Core → TWS)

**Methods in TWSProvider** - Convert domain parameters to TWS API calls

| Method                      | Input (Domain)                                 | Output (TWS)     | Conversion                                 |
| --------------------------- | ---------------------------------------------- | ---------------- | ------------------------------------------ |
| `_build_tws_contract()`     | `symbol: str`<br>`exchange: str`               | `Contract`       | Create TWS Contract object                 |
| `_map_timeframe_to_tws()`   | `TimeFrame` enum                               | `str` (bar size) | `MIN_1` → `"1 min"`<br>`DAY_1` → `"1 day"` |
| `_calculate_tws_duration()` | `start_time: datetime`<br>`end_time: datetime` | `str` (duration) | Time delta → `"30 D"`, `"86400 S"`         |

### 3.4 Data Mappers (TWS → Core)

**Methods in TWSProvider** - Convert TWS responses to domain models

| Method                                       | Input (TWS)           | Output (Domain)      | Conversion                                                            |
| -------------------------------------------- | --------------------- | -------------------- | --------------------------------------------------------------------- |
| `_convert_tws_bar_to_domain()`               | `BarData`             | `Bar`                | `date` (str) → `time` (int ms)<br>`volume` (Decimal) → `int`          |
| `_convert_contract_desc_to_search_result()`  | `ContractDescription` | `SymbolSearchResult` | Extract contract fields<br>Format `ticker` as `"SYMBOL:EXCHANGE"`     |
| `_convert_contract_details_to_symbol_info()` | `ContractDetails`     | `SymbolInfo`         | Extract metadata<br>Parse `tradingHours`<br>Set `session`, `timezone` |

---

## 4. Layer 1: IBSocket (Raw TCP Protocol)

### 4.1 Purpose

Minimal TCP socket layer that handles raw TWS protocol communication. Manages socket connection, TWS handshake, and message framing without any EClient/EWrapper complexity. Designed for **maximum testability** by isolating socket operations.

### 4.2 Key Features

- **Raw Socket Management**: Pure Python `socket` operations
- **TWS Handshake**: API version negotiation during connect
- **Message Framing**: Length-prefix encoding for TWS messages
- **Thread-Safe Send**: `threading.Lock` protects concurrent writes
- **No Callback Logic**: Pure I/O layer - no business logic
- **Mockable**: Easily mocked for unit testing TWSClient

### 4.3 IBSocket Implementation

**File:** `backend/src/trading_api/providers/tws/tws_connection.py`

```python
import socket
import threading
from ibapi.common import UNSET_INTEGER, UNSET_DOUBLE

class IBSocket:
    """Raw TCP socket for TWS communication.

    Handles connection, handshake, and message framing.
    All I/O operations block - designed to run in daemon thread.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1):
        self._host = host
        self._port = port
        self._client_id = client_id
        self._socket: socket.socket | None = None
        self._server_version: int = 0
        self._lock = threading.Lock()

    def connect(self) -> tuple[int, str]:
        """Connect to TWS and perform handshake.

        Returns:
            Tuple of (server_version, server_time)
        """
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect((self._host, self._port))
        # TWS handshake: send API version, receive server version
        return self._perform_handshake()

    def disconnect(self):
        """Close socket connection."""
        if self._socket:
            self._socket.close()
            self._socket = None

    def isConnected(self) -> bool:
        """Check if socket is connected."""
        return self._socket is not None

    def send_message(self, msg_id: int, values: list) -> None:
        """Send TWS message with length-prefix framing.

        Thread-safe: protected by lock for concurrent writes.
        """
        with self._lock:
            # Build message: msg_id + values
            msg = self._encode_message(msg_id, values)
            self._socket.sendall(msg)

    def receive_data(self) -> tuple[int, bytes, bytes, int]:
        """Receive next TWS message from socket.

        Blocks until data available. Returns raw bytes for Decoder.
        """
        # Read length prefix (4 bytes)
        # Read message body
        # Return (msgId, data, buffer, buffer_size)
        ...

    @property
    def server_version(self) -> int:
        return self._server_version
```

**Key Design Notes:**

- **Blocking I/O**: All socket operations block - must run in dedicated thread
- **Handshake Protocol**: Negotiates API version with TWS Gateway
- **Message Framing**: 4-byte length prefix for all messages
- **Lock Scope**: Only protects `send_message()` - receive is single-threaded
- **No Callbacks**: Pure I/O - TWSClient handles message interpretation

### 4.4 TWSError Dataclass

**File:** `backend/src/trading_api/providers/tws/tws_connection.py`

```python
from dataclasses import dataclass

@dataclass
class TWSError:
    """Structured TWS error details for typed error handling."""
    req_id: int
    error_code: int
    error_string: str
    error_time: str
    advanced_order_reject_json: str = ""

    @property
    def is_warning(self) -> bool:
        """Warning codes are 2100-2199."""
        return 2100 <= self.error_code < 2200

    @property
    def is_data_error(self) -> bool:
        """Data-related errors (no data, invalid request)."""
        return self.error_code in (162, 200, 354, 10090)
```

**Common Error Codes:**

| Code    | Meaning                                         | Action                  |
| ------- | ----------------------------------------------- | ----------------------- |
| `162`   | Historical data request pacing violation        | Wait and retry          |
| `200`   | No security definition found                    | Invalid symbol          |
| `354`   | Requested market data not subscribed            | Missing subscription    |
| `504`   | Not connected                                   | Reconnect               |
| `10090` | Part of requested market data is not subscribed | Partial data available  |
| `2104`  | Market data farm connected                      | Informational (warning) |
| `2106`  | Historical data farm connected                  | Informational (warning) |

---

## 5. Layer 2: TWSClient (AsyncIO Bridge)

### 5.1 Purpose

AsyncIO bridge layer that inherits `EWrapper` for TWS callbacks and manages `asyncio.Future` objects for request/response patterns. Handles the critical **cross-thread communication** between the daemon socket thread and the main asyncio event loop.

### 5.2 Key Features

- **EWrapper Inheritance**: Receives TWS callbacks (symbolSamples, error, etc.)
- **Future Registry**: Maps `reqId → asyncio.Future` for async/await
- **Thread-Safe Resolution**: `loop.call_soon_threadsafe()` for cross-thread Future completion
- **Request ID Generation**: Auto-incrementing IDs with locking
- **Daemon Thread**: Runs `_client_loop()` for socket I/O and message dispatch
- **Error Propagation**: TWSError → Future rejection with exception

### 5.3 TWSClientHelper Base Class

**Purpose:** Testable base class that accepts an IBSocket instance for mocking.

```python
class TWSClientHelper(EWrapper):
    """Base class for TWSClient - enables mock injection.

    Inherits EWrapper for callback methods.
    Accepts IBSocket dependency for testability.
    """

    def __init__(self, ibsocket: IBSocket, loop: asyncio.AbstractEventLoop | None = None):
        self._ibsocket = ibsocket
        self._loop = loop or asyncio.get_event_loop()
        self._futures: dict[int, asyncio.Future] = {}
        self._next_req_id = 1
        self._running = threading.Event()
        self._client_thread: threading.Thread | None = None

    def _resolve_future(self, req_id: int, result: Any) -> None:
        """Thread-safe Future resolution from daemon thread."""
        if future := self._futures.get(req_id):
            self._loop.call_soon_threadsafe(future.set_result, result)
            self._futures.pop(req_id, None)

    def _reject_future(self, req_id: int, exception: Exception) -> None:
        """Thread-safe Future rejection from daemon thread."""
        if future := self._futures.get(req_id):
            self._loop.call_soon_threadsafe(future.set_exception, exception)
            self._futures.pop(req_id, None)

    # EWrapper callbacks (implemented in TWSClient)
    def symbolSamples(self, reqId: int, contractDescriptions: list):
        raise NotImplementedError

    def error(self, reqId: int, errorTime: str, errorCode: int,
              errorString: str, advancedOrderRejectJson: str = ""):
        raise NotImplementedError
```

### 5.4 TWSClient Implementation

**File:** `backend/src/trading_api/providers/tws/tws_connection.py`

```python
from ibapi.wrapper import EWrapper
from ibapi.decoder import Decoder
from ibapi.contract import ContractDescription
import asyncio
import threading
import logging

logger = logging.getLogger(__name__)

class TWSClient(TWSClientHelper):
    """Full TWSClient with connection management.

    Creates IBSocket internally and manages daemon thread.
    Use TWSClientHelper with mock IBSocket for testing.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 1,
        loop: asyncio.AbstractEventLoop | None = None,
    ):
        ibsocket = IBSocket(host, port, client_id)
        super().__init__(ibsocket, loop)
        self._decoder = Decoder(wrapper=self, serverVersion=0)

    def connect(self) -> None:
        """Connect and start daemon thread for message processing."""
        server_version, _ = self._ibsocket.connect()
        self._decoder.serverVersion = server_version

        # Start daemon thread for socket reading and message dispatch
        self._running.set()
        self._client_thread = threading.Thread(target=self._client_loop, daemon=True)
        self._client_thread.start()

    def disconnect(self) -> None:
        """Stop daemon thread and disconnect socket."""
        self._running.clear()
        self._ibsocket.disconnect()
        if self._client_thread:
            self._client_thread.join(timeout=2.0)

    def _client_loop(self) -> None:
        """Daemon thread: read socket → decode → dispatch callbacks."""
        while self._running.is_set():
            try:
                msg_id, data, buf, buf_siz = self._ibsocket.receive_data()
                # Decoder interprets message and invokes EWrapper callbacks
                self._decoder.interpret(data)
            except Exception as e:
                if self._running.is_set():
                    logger.error(f"Client loop error: {e}")

    # === Async Request Methods ===

    async def reqMatchingSymbols(self, pattern: str) -> list[ContractDescription]:
        """Search for symbols matching pattern.

        Returns list of ContractDescription objects.
        """
        req_id = self._next_req_id
        self._next_req_id += 1

        future: asyncio.Future[list[ContractDescription]] = self._loop.create_future()
        self._futures[req_id] = future

        # Send request via IBSocket
        self._ibsocket.send_message(REQ_MATCHING_SYMBOLS, [req_id, pattern])

        return await future

    # === EWrapper Callbacks ===

    def symbolSamples(self, reqId: int, contractDescriptions: list) -> None:
        """Callback: symbol search results received."""
        self._resolve_future(reqId, contractDescriptions)

    def error(
        self,
        reqId: int,
        errorTime: str,
        errorCode: int,
        errorString: str,
        advancedOrderRejectJson: str = "",
    ) -> None:
        """Callback: error received from TWS."""
        tws_error = TWSError(
            req_id=reqId,
            error_code=errorCode,
            error_string=errorString,
            error_time=errorTime,
            advanced_order_reject_json=advancedOrderRejectJson,
        )

        if tws_error.is_warning:
            logger.warning(f"TWS warning [{errorCode}]: {errorString}")
            return

        logger.error(f"TWS error [{errorCode}]: {errorString}")
        self._reject_future(reqId, Exception(f"TWS error {errorCode}: {errorString}"))
```

**Key Design Notes:**

- **Single Daemon Thread**: `_client_loop()` handles all socket I/O
- **Decoder Integration**: ibapi `Decoder` parses messages and invokes EWrapper callbacks
- **Future-Based Async**: Each request gets an `asyncio.Future` for await
- **Thread-Safe Bridge**: `call_soon_threadsafe()` resolves futures from daemon thread
- **Testable**: `TWSClientHelper` base class accepts mock IBSocket

---

## 6. Layer 3: TWSProvider

### 6.1 Purpose

Top-level provider implementing `DatafeedCapability` interface. Delegates TWS communication to `TWSClient` and handles **domain model conversion** using mappers in `tws_mappers.py`.

### 6.2 Key Features

- **DatafeedCapability Implementation**: Async interface for market data operations
- **TWSClient Delegation**: All TWS communication via `_tws_client`
- **Domain Conversion**: TWS types ↔ domain models via `tws_mappers.py`
- **Error Translation**: TWSError → DatafeedError
- **Lifecycle Hooks**: `on_startup()` / `on_shutdown()` for connection management

### 6.3 TWSProvider Implementation

**File:** `backend/src/trading_api/providers/tws/__init__.py`

```python
from trading_api.models.providers.tws.tws_configs import TWSProviderConfig
from trading_api.models.common import CapabilitySpec
from trading_api.models.market import SearchSymbolResultItem
from trading_api.providers.base import Provider
from trading_api.providers.capabilities.datafeed import DatafeedCapability
from trading_api.providers.tws.tws_connection import TWSClient
from trading_api.providers.tws.tws_mappers import contract_description_to_search_result

class TWSProvider(Provider, DatafeedCapability):
    """TWS provider implementing DatafeedCapability.

    Delegates all TWS communication to TWSClient.
    Handles domain model conversion via tws_mappers.
    """

    def __init__(self, config: TWSProviderConfig | None = None) -> None:
        self._config = config or TWSProviderConfig()
        self._tws_client: TWSClient | None = None

    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        return [CapabilitySpec(name="datafeed")]

    # === Lifecycle Hooks ===

    async def on_startup(self) -> None:
        """Connect to TWS on provider startup."""
        self._tws_client = TWSClient(
            host=self._config.host,
            port=self._config.port,
            client_id=self._config.client_id,
        )
        self._tws_client.connect()

    async def on_shutdown(self) -> None:
        """Disconnect from TWS on provider shutdown."""
        if self._tws_client:
            self._tws_client.disconnect()
            self._tws_client = None

    # === DatafeedCapability Implementation ===

    async def search_symbols(self, pattern: str) -> list[SearchSymbolResultItem]:
        """Search symbols matching pattern.

        Delegates to TWSClient, converts TWS → domain models.
        """
        if not self._tws_client:
            raise RuntimeError("TWSClient not connected")

        # Delegate to TWSClient (async)
        tws_results = await self._tws_client.reqMatchingSymbols(pattern)

        # Convert TWS → domain using mapper
        return [
            contract_description_to_search_result(desc)
            for desc in tws_results
        ]
```

### 6.4 Domain Mappers

**File:** `backend/src/trading_api/providers/tws/tws_mappers.py`

```python
from trading_api.models.market import SearchSymbolResultItem
from ibapi.contract import ContractDescription

# TWS secType → domain type mapping
SEC_TYPE_MAP: dict[str, str] = {
    "STK": "stock",
    "OPT": "option",
    "FUT": "futures",
    "CASH": "forex",
    "IND": "index",
    "CFD": "cfd",
    "CRYPTO": "crypto",
}

def contract_description_to_search_result(
    desc: ContractDescription,
) -> SearchSymbolResultItem:
    """Convert TWS ContractDescription → domain SearchSymbolResultItem."""
    contract = desc.contract
    return SearchSymbolResultItem(
        symbol=contract.symbol,
        full_name=contract.symbol,  # TWS doesn't provide full name
        description=f"{contract.symbol} ({contract.primaryExchange or contract.exchange})",
        exchange=contract.primaryExchange or contract.exchange,
        ticker=f"{contract.symbol}:{contract.primaryExchange or contract.exchange}",
        type=SEC_TYPE_MAP.get(contract.secType, contract.secType.lower()),
    )
```

---

## 7. Configuration

### 7.1 TWSProviderConfig

**File:** `backend/src/trading_api/models/providers/tws/tws_configs.py`

**Pattern:** Pydantic `BaseSettings` with `TWS_` prefix for auto-loading from environment

| Parameter            | Type    | Default       | Environment Variable     | Description                                   |
| -------------------- | ------- | ------------- | ------------------------ | --------------------------------------------- |
| `enabled`            | `bool`  | `True`        | `TWS_ENABLED`            | Enable/disable TWS provider                   |
| `host`               | `str`   | `"127.0.0.1"` | `TWS_HOST`               | TWS/Gateway hostname                          |
| `port`               | `int`   | `7497`        | `TWS_PORT`               | TWS/Gateway port (see Port Reference)         |
| `client_id`          | `int`   | `1`           | `TWS_CLIENT_ID`          | Client ID for TWS connection (1-32)           |
| `connection_timeout` | `float` | `10.0`        | `TWS_CONNECTION_TIMEOUT` | Connection timeout in seconds                 |
| `realtime_bar_size`  | `int`   | `5`           | `TWS_REALTIME_BAR_SIZE`  | Real-time bar size in seconds (5 or 10 only)  |
| `market_data_type`   | `int`   | `1`           | `TWS_MARKET_DATA_TYPE`   | Market data type (see Market Data Type table) |

**Configuration File:** `.env.local` (optional - fallback to system environment)

```bash
TWS_ENABLED=true
TWS_HOST=127.0.0.1
TWS_PORT=7497
TWS_CLIENT_ID=1
TWS_CONNECTION_TIMEOUT=10.0
TWS_REALTIME_BAR_SIZE=5
TWS_MARKET_DATA_TYPE=1
```

### 6.2 Port Reference

| Port   | Environment   | Application | Usage                    |
| ------ | ------------- | ----------- | ------------------------ |
| `7497` | Paper Trading | TWS         | Default for development  |
| `7496` | Live Trading  | TWS         | Production with TWS      |
| `4002` | Paper Trading | IB Gateway  | Development with Gateway |
| `4001` | Live Trading  | IB Gateway  | Production with Gateway  |

**Recommendation:** Use `7497` (TWS paper) or `4002` (Gateway paper) for development

### 6.3 Market Data Type Reference

| Value | Type           | Description                            | Subscription Required |
| ----- | -------------- | -------------------------------------- | --------------------- |
| `1`   | Real-time      | Live streaming data                    | Yes                   |
| `2`   | Frozen         | Last recorded data before market close | No                    |
| `3`   | Delayed        | 15-20 minute delayed data              | No                    |
| `4`   | Delayed Frozen | Delayed data before market close       | No                    |

**Default:** `1` (real-time) - requires active market data subscription with Interactive Brokers

### 6.4 Validation Rules

- **Port Validation:** Must be valid TWS/Gateway port (see Port Reference)
- **Client ID Range:** 1-32 (TWS limitation)
- **Bar Size Constraint:** Real-time bars only support 5 or 10 seconds
- **Market Data Type:** Valid values 1-4 only
- **Connection Timeout:** Minimum 5.0 seconds recommended

---

## 7. DatafeedService Integration

**File:** `backend/src/trading_api/modules/datafeed/service.py`

### 7.1 Provider Injection Pattern

```
AppFactory (startup)
        │
        ├─ ProviderRegistry.auto_discover()  # Finds TWSProvider
        │       └─ Scans providers/tws/__init__.py
        │       └─ Registers: name="tws", capabilities=["datafeed"]
        │
        ├─ Create DatafeedService(providers=[tws_provider])
        │       └─ Validates: requires capability="datafeed" ✓
        │
        └─ Service ready
                │
                ▼
        self.datafeed_provider → TWSProvider (cached O(1) lookup)
                │
                ▼ (all methods return domain models)
        search_symbols() → List[SymbolSearchResult]
        get_historical_bars() → List[Bar]
        subscribe_realtime_bars() → int
```

**Key Code Pattern:**

```python
class DatafeedService(WsRouteService):
    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        return [CapabilitySpec(name="datafeed")]  # Require datafeed provider

    @property
    def datafeed_provider(self) -> DatafeedCapability:
        """Cached O(1) lookup - type-safe provider access"""
        return self._get_capability_provider("datafeed")

    async def get_bars(...) -> List[Bar]:
        # Provider returns domain models directly!
        bars = await self.datafeed_provider.get_historical_bars(...)
        return bars  # Already domain models
```

### 7.2 Business Logic Responsibilities

**Service Layer** (100% provider-agnostic business logic):

- **Ticker Format Parsing**: `"AAPL:NASDAQ"` → `symbol="AAPL"`, `exchange="NASDAQ"`
- **Resolution Conversion**: TradingView resolution strings → `TimeFrame` enum
- **Timestamp Conversion**: Unix milliseconds → Python `datetime` objects
- **Filtering**: Apply exchange/type filters to search results
- **Pagination**: `count_back` parameter, `max_results` limiting
- **WebSocket Topic Management**: Map topics to subscription IDs
- **API Model Conversion**: Domain models → API response models (DTO pattern)
- **Error Handling**: Business-level errors (e.g., "Invalid symbol format")

**Provider Layer** (TWS-specific integration):

- **TWS Protocol**: All EClient/EWrapper operations
- **Domain Conversion**: TWS types ↔ domain models
- **AsyncIO Bridge**: Sync callbacks → async/await
- **Connection Management**: Connect, disconnect, reconnect
- **Request ID Management**: Thread-safe ID generation
- **TWS Error Translation**: TWS error codes → domain exceptions

**Clear Boundary**: Service never imports `ibapi` package, provider never handles business rules

### 7.3 Zero TWS Knowledge Rule

**❌ WRONG - Service with TWS Knowledge:**

```python
# NEVER do this in DatafeedService!
from ibapi.contract import Contract  # ❌ Service imports TWS types

async def get_bars(self, symbol: str, ...):
    contract = Contract()  # ❌ Service creates TWS objects
    contract.symbol = symbol
    contract.secType = "STK"
    # ...
```

**✅ CORRECT - Provider-Agnostic Service:**

```python
# Service uses domain models ONLY
from trading_api.models.datafeed import Bar, TimeFrame  # ✓ Domain types

async def get_bars(
    self, symbol: str, resolution: str, from_time: int, to_time: int
) -> List[Bar]:
    # Business logic: parse input
    start_dt = datetime.fromtimestamp(from_time / 1000)
    timeframe = TimeFrame(resolution)

    # Provider delegation: domain params → domain results
    bars: List[Bar] = await self.datafeed_provider.get_historical_bars(
        symbol=symbol,
        start_time=start_dt,
        resolution=timeframe
    )

    return bars  # Already domain models - no conversion needed
```

**Benefits:**

- Service works with ANY datafeed provider (TWS, Alpaca, Polygon)
- Swap providers via config: `TWS_ENABLED=false` + `ALPACA_ENABLED=true`
- Service tests use mocked `DatafeedCapability` - no TWS dependency
- Type safety: IDE autocomplete on domain model attributes

---

## 8. Implementation Patterns

### 8.1 Request/Response Pattern

**Used by:** `search_symbols()` - Single response with complete data

```python
# TWSProvider implementation
async def search_symbols(self, pattern: str, timeout: float = 5.0) -> List[SymbolSearchResult]:
    req_id = await self._get_next_req_id()
    future: Future[List[ContractDescription]] = Future()
    self._pending_requests[req_id] = future

    # Register callback wrapper
    def callback(contract_descriptions):
        # Single response - complete data arrives in one call
        loop = asyncio.get_event_loop()
        loop.call_soon_threadsafe(future.set_result, contract_descriptions)

    self.tws.callbacks[req_id] = callback

    try:
        self.tws.reqMatchingSymbols(req_id, pattern)
        tws_results = await asyncio.wait_for(asyncio.wrap_future(future), timeout)
        # Convert TWS → domain models
        return [self._convert_contract_desc_to_search_result(desc) for desc in tws_results]
    finally:
        self._pending_requests.pop(req_id, None)
        self.tws.callbacks.pop(req_id, None)
```

**Characteristics:**

- Single callback invocation with complete data
- Future resolves immediately after callback
- Simple pattern - no accumulation needed

### 8.2 Streaming Accumulation Pattern

**Used by:** `get_historical_bars()`, `get_symbol_info()` - Multiple responses → single result

```python
# TWSProvider implementation
async def get_historical_bars(
    self, symbol: str, start_time: datetime, end_time: datetime,
    resolution: TimeFrame, exchange: str | None = None, timeout: float = 30.0
) -> List[Bar]:
    req_id = await self._get_next_req_id()
    future: Future[List[Bar]] = Future()
    bars_accumulated = []  # Closure variable for accumulation

    # Register callback wrapper with accumulation logic
    def callback(bar):
        if bar is None:
            # End-of-stream signal (from historicalDataEnd callback)
            loop = asyncio.get_event_loop()
            loop.call_soon_threadsafe(future.set_result, bars_accumulated)
        else:
            # Accumulate bar (from historicalData callback - called multiple times)
            domain_bar = self._convert_tws_bar_to_domain(bar)
            bars_accumulated.append(domain_bar)

    self.tws.callbacks[req_id] = callback

    try:
        # Build TWS parameters
        contract = self._build_tws_contract(symbol, exchange or "SMART")
        end_dt_str = end_time.strftime("%Y%m%d %H:%M:%S")
        duration_str = self._calculate_tws_duration(start_time, end_time)
        bar_size_str = self._map_timeframe_to_tws(resolution)

        self.tws.reqHistoricalData(req_id, contract, end_dt_str, duration_str, bar_size_str, "TRADES", 1, 1, False, [])
        return await asyncio.wait_for(asyncio.wrap_future(future), timeout)
    finally:
        self._pending_requests.pop(req_id, None)
        self.tws.callbacks.pop(req_id, None)
```

**Characteristics:**

- Multiple callback invocations (one per bar/item)
- Accumulate results in closure variable
- `None` signals end-of-stream → resolve Future
- Performance: No string comparisons (`None` check is faster)

### 8.3 Continuous Subscription Pattern

**Used by:** `subscribe_realtime_bars()`, `subscribe_market_data()` - Indefinite streaming

```python
# TWSProvider implementation
def subscribe_realtime_bars(
    self, symbol: str, callback: Callable[[Bar], None],
    exchange: str | None = None, resolution: TimeFrame = TimeFrame.SEC_5
) -> int:
    """Subscribe to real-time bars - returns subscription ID for cleanup"""
    req_id = self._get_next_req_id_sync()
    contract = self._build_tws_contract(symbol, exchange or "SMART")

    # Wrapper converts TWS data → domain model → user callback
    def tws_callback(time, open_, high, low, close, volume, wap, count):
        # Convert TWS parameters → domain model
        bar = Bar(
            time=time * 1000,
            open=open_,
            high=high,
            low=low,
            close=close,
            volume=volume,
            symbol=symbol
        )
        # Invoke user callback with domain model
        callback(bar)

    # Register callback (no Future - continuous stream)
    self._subscriptions[req_id] = tws_callback
    self.tws.callbacks[req_id] = tws_callback

    # Start subscription
    self.tws.reqRealTimeBars(req_id, contract, 5, "TRADES", False, [])
    return req_id  # Return ID for unsubscribe

def unsubscribe_realtime_bars(self, subscription_id: int):
    """Cancel subscription and cleanup"""
    self.tws.cancelRealTimeBars(subscription_id)
    self._subscriptions.pop(subscription_id, None)
    self.tws.callbacks.pop(subscription_id, None)
```

**Characteristics:**

- No Future - indefinite streaming
- Callback invoked on every update
- Returns subscription ID for later cleanup
- Must explicitly unsubscribe to stop
- Performance: Direct parameter unpacking, zero string operations

---

## 9. Threading Model

### 9.1 Thread Architecture

**See section 1.3 for complete threading diagrams**

```
Main Thread (AsyncIO)              TWS Reader Thread (Blocking)
─────────────────────              ────────────────────────────
TWSProvider (async/await)          TWSConnection (sync callbacks)
        │                                      │
        │ asyncio.Future                      │
        │ asyncio.Lock                        │ threading.Lock
        │                                      │ threading.Event
        │                                      │
        ├─ _get_next_req_id()                 ├─ get_req_id()
        │  (async with lock)                  │  (with lock)
        │                                      │
        ├─ _register_callbacks()               ├─ callbacks[reqId](data)
        │  ↓                                   │  (direct dispatch)
        │  loop.call_soon_threadsafe()  ←──────┤
        │  ↓                                   │
        │  future.set_result(data)             │
        │                                      │
        └─ await future ✓                     └─ No AsyncIO knowledge
```

**Three Threads in System:**

1. **Main Thread**: FastAPI event loop, async/await, TWSProvider, DatafeedService
2. **TWS Reader Thread**: Created by `EReader.start()`, reads TCP socket, deserializes TWS messages
3. **TWS Message Thread**: Runs `connect_and_run()`, processes message queue, invokes EWrapper callbacks

### 9.2 Thread Safety Rules

**TWSConnection (Layer 1 - TWS Thread):**

- ✅ Use `threading.Lock` for request ID generation
- ✅ Use `threading.Event` for connection ready signal
- ✅ Callbacks execute in TWS thread - no AsyncIO allowed
- ✅ Pass data by reference (zero-copy) - conversion happens in main thread
- ❌ Never use `asyncio.Lock` or `asyncio.Event` - not thread-safe across threads

**TWSProvider (Layer 2 - Main Thread):**

- ✅ Use `asyncio.Lock` for async request ID generation
- ✅ Use `loop.call_soon_threadsafe()` for cross-thread Future resolution
- ✅ All expensive operations (conversion, validation) happen in main thread
- ✅ Register callback wrappers that bridge to AsyncIO
- ❌ Never call TWS API directly from async methods - use TWSConnection

**Cross-Thread Communication:**

- ✅ `asyncio.Future` with `loop.call_soon_threadsafe()` - thread-safe bridge
- ✅ `threading.Event.set()` can be called from any thread
- ✅ Await `run_in_executor(lambda: event.wait(timeout))` to bridge threading.Event to AsyncIO
- ❌ Never share mutable state between threads without synchronization
- ❌ Never use `asyncio.Event.set()` from TWS thread - race condition

**Why Separate Thread for `connect_and_run()`:**

- TWS `run()` method blocks indefinitely in message loop
- Cannot run in AsyncIO event loop - would freeze entire application
- Must run in dedicated thread spawned via `threading.Thread`
- Non-daemon thread allows clean shutdown on disconnect

**Why `threading.Event` not `asyncio.Event`:**

- `asyncio.Event` is NOT thread-safe for cross-thread signaling
- `threading.Event.set()` is thread-safe - can be called from TWS thread
- Bridge to AsyncIO via `run_in_executor(lambda: event.wait(timeout))`

---

## 10. Testing Strategy

### 10.1 Layer Testing Approach

**Aligned with**: `backend/docs/BACKEND_TESTING.md` and TDD methodology from `.github/prompts/tdd-plan.prompt.md`

| Layer               | Test Type   | Mock Strategy                            | Test Location                                     | Focus                                    |
| ------------------- | ----------- | ---------------------------------------- | ------------------------------------------------- | ---------------------------------------- |
| **DatafeedService** | Unit        | Mock `DatafeedCapability` interface      | `modules/datafeed/tests/test_service.py`          | Business logic, ticker parsing, filters  |
| **TWSProvider**     | Unit        | Mock `TWSConnection` (Layer 1)           | `providers/tws/tests/test_provider.py`            | AsyncIO bridge, domain conversion        |
| **TWSConnection**   | Unit        | Mock TWS API (no real connection)        | `providers/tws/tests/test_connection.py`          | Callback dispatch, request ID generation |
| **Integration**     | Integration | Mock TWS Gateway (test server)           | `tests/integration/test_tws_provider.py`          | Full stack: Service → Provider → TWS     |
| **Contract**        | Contract    | Real TWS paper trading (CI: conditional) | `tests/integration/test_tws_contract.py` (manual) | Verify TWS API compatibility             |

### 10.2 Mock Patterns

**Service Layer Mock (Unit Test):**

```python
# modules/datafeed/tests/test_service.py
from unittest.mock import AsyncMock
import pytest
from trading_api.models.datafeed import Bar, TimeFrame
from trading_api.modules.datafeed.service import DatafeedService

@pytest.mark.asyncio
async def test_get_bars_parses_ticker_format():
    """Test service parses 'SYMBOL:EXCHANGE' format."""
    # Mock provider
    mock_provider = AsyncMock()
    mock_provider.get_historical_bars.return_value = [
        Bar(time=1000, open=100.0, high=101.0, low=99.0, close=100.5, volume=1000)
    ]

    service = DatafeedService(providers=[mock_provider])

    # Service should parse "AAPL:NASDAQ" → symbol="AAPL", exchange="NASDAQ"
    bars = await service.get_bars(
        symbol="AAPL:NASDAQ",
        resolution="1",
        from_time=1000,
        to_time=2000
    )

    # Verify provider called with parsed values
    mock_provider.get_historical_bars.assert_called_once()
    call_args = mock_provider.get_historical_bars.call_args
    assert call_args.kwargs["symbol"] == "AAPL"
    assert call_args.kwargs["exchange"] == "NASDAQ"
    assert len(bars) == 1
```

**Provider Layer Mock (Unit Test):**

```python
# providers/tws/tests/test_provider.py
from unittest.mock import Mock, MagicMock
import pytest
from trading_api.providers.tws import TWSProvider
from trading_api.models.datafeed import Bar, TimeFrame
from ibapi.common import BarData
from decimal import Decimal

@pytest.mark.asyncio
async def test_provider_converts_tws_bar_to_domain():
    """Test TWSProvider converts TWS BarData → domain Bar."""
    # Mock TWSConnection (Layer 1)
    mock_tws = Mock()
    mock_tws.get_req_id.return_value = 1

    provider = TWSProvider()
    provider.tws = mock_tws

    # Simulate TWS callback with BarData
    tws_bar = BarData()
    tws_bar.date = "1609459200"  # Unix timestamp as string
    tws_bar.open = 100.0
    tws_bar.high = 101.0
    tws_bar.low = 99.0
    tws_bar.close = 100.5
    tws_bar.volume = Decimal("1000")

    # Test conversion
    domain_bar = provider._convert_tws_bar_to_domain(tws_bar)

    assert domain_bar.time == 1609459200000  # ms
    assert domain_bar.open == 100.0
    assert domain_bar.volume == 1000  # int, not Decimal
```

**Connection Layer Mock (Unit Test):**

```python
# providers/tws/tests/test_connection.py
import pytest
from unittest.mock import Mock
from trading_api.providers.tws.tws_connection import TWSConnection

def test_connection_dispatches_callback():
    """Test TWSConnection dispatches callbacks by reqId."""
    connection = TWSConnection()

    # Register callback
    callback_invoked = False
    received_data = None

    def test_callback(data):
        nonlocal callback_invoked, received_data
        callback_invoked = True
        received_data = data

    req_id = 1
    connection.callbacks[req_id] = test_callback

    # Simulate TWS callback
    test_data = [Mock(symbol="AAPL", exchange="SMART")]
    connection.symbolSamples(req_id, test_data)

    # Verify callback invoked with correct data
    assert callback_invoked
    assert received_data == test_data

def test_connection_signals_end_with_none():
    """Test TWSConnection signals end-of-stream with None."""
    connection = TWSConnection()

    received_signal = False

    def test_callback(data):
        nonlocal received_signal
        if data is None:
            received_signal = True

    connection.callbacks[1] = test_callback
    connection.contractDetailsEnd(1)

    assert received_signal
```

### 10.3 TDD Workflow (6-Phase)

**For provider implementation, follow `API-METHODOLOGY.md` 6-phase approach:**

**Phase 1: Domain Models (Red → Green)**

- Define domain models (`Bar`, `SymbolSearchResult`)
- Write model validation tests
- Implement models with Pydantic

**Phase 2: Capability Interface (Red → Green)**

- Define `DatafeedCapability` interface
- Write interface contract tests
- Document method signatures

**Phase 3: Provider Implementation (Red → Green)**

- Write provider unit tests (mock TWSConnection)
- Implement TWSProvider with AsyncIO bridge
- Verify domain conversion

**Phase 4: Connection Layer (Red → Green)**

- Write connection unit tests (mock TWS API)
- Implement TWSConnection callbacks
- Verify zero-copy dispatch

**Phase 5: Integration Tests (Red → Green)**

- Write full-stack integration test
- Mock TWS Gateway or use paper trading
- Verify end-to-end flow

**Phase 6: Refactor & Optimize**

- Performance profiling (callback latency)
- Error handling edge cases
- Documentation updates

### 10.4 Performance Testing

**Latency Targets** (from section 3.3):

| Operation            | Target   | Measurement                    |
| -------------------- | -------- | ------------------------------ |
| Callback dispatch    | < 2 µs   | Dict lookup + function call    |
| Data conversion      | < 10 µs  | TWS types → domain models      |
| AsyncIO bridge       | < 50 µs  | `loop.call_soon_threadsafe()`  |
| Historical bar fetch | < 500 ms | Full request/response cycle    |
| Real-time tick       | < 1 ms   | Tick arrival → callback invoke |

**Performance Test Example:**

```python
import time
import pytest
from trading_api.providers.tws.tws_connection import TWSConnection

def test_callback_dispatch_latency():
    """Verify callback dispatch meets <2µs target."""
    connection = TWSConnection()

    dispatch_times = []

    def measure_callback(data):
        pass  # Minimal callback

    connection.callbacks[1] = measure_callback

    # Warm up
    for _ in range(100):
        connection.symbolSamples(1, [])

    # Measure 1000 dispatches
    for _ in range(1000):
        start = time.perf_counter()
        connection.symbolSamples(1, [])
        dispatch_times.append((time.perf_counter() - start) * 1_000_000)  # µs

    avg_latency = sum(dispatch_times) / len(dispatch_times)
    p99_latency = sorted(dispatch_times)[int(len(dispatch_times) * 0.99)]

    assert avg_latency < 2.0, f"Average: {avg_latency:.2f}µs"
    assert p99_latency < 5.0, f"P99: {p99_latency:.2f}µs"
```

### 10.5 CI/CD Integration

**Test Execution in CI:**

```yaml
# .github/workflows/backend-tests.yml
- name: Run Provider Tests
  run: |
    make test-module-datafeed
    make test-providers

- name: Run Integration Tests (Mock TWS)
  run: |
    make test-integration

- name: Contract Tests (Paper Trading - Nightly)
  if: github.event_name == 'schedule'
  run: |
    TWS_HOST=paper.interactivebrokers.com make test-contract
```

**Coverage Targets:**

- Unit tests: > 90% coverage
- Integration tests: All critical paths
- Contract tests: TWS API compatibility (nightly)

---
