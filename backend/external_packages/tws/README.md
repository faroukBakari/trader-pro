# TWS API - Interactive Brokers Python Client

## Overview

The TWS (Trader Workstation) API is Interactive Brokers' official programming interface for automating trading operations, accessing market data, and managing accounts. This is the Python implementation of the TWS API.

**Version**: 10.37.02  
**Protocol**: TCP Socket-based message protocol  
**License**: IB API Non-Commercial License or IB API Commercial License

## What is TWS API?

The TWS API is a **TCP Socket Protocol API** that connects to either:

- **Trader Workstation (TWS)**: Full-featured trading platform with GUI
- **IB Gateway (IBGW)**: Lightweight headless version (~40% fewer resources)

It allows you to programmatically:

- Place, modify, and cancel orders
- Subscribe to real-time and historical market data
- Monitor account balances, positions, and P&L
- Manage portfolios and executions
- Access news feeds and market scanners
- Handle Financial Advisor allocations

## Key Features

### Market Data

- **Real-time Streaming**: Tick-by-tick market data (L1 & L2)
- **Historical Data**: OHLCV bars with various time frames (1 sec to 1 year)
- **Market Depth**: Level 2 order book data
- **Real-time Bars**: 5-second OHLC bars
- **News Integration**: Multiple news providers (Briefing.com, Benzinga, Fly on the Wall, etc.)

### Order Management

- **Order Types**: Market, Limit, Stop, Stop-Limit, Trailing Stop, and 50+ advanced order types
- **Order Tracking**: Real-time order status updates and execution reports
- **Multi-Account**: Financial Advisor and IBroker account support
- **Bracket Orders**: Parent-child order relationships
- **Algorithmic Trading**: VWAP, TWAP, Adaptive, and other algos

### Account & Portfolio

- **Account Summary**: Real-time account values and balances
- **Positions**: Live position tracking across all accounts
- **P&L**: Real-time profit and loss (account-level and position-level)
- **Executions**: Complete trade history and commission reports

### Advanced Features

- **Options**: Greeks calculations, option chains, implied volatility
- **Combos**: Multi-leg strategies (spreads, straddles, etc.)
- **Market Scanners**: Custom market screening
- **Contract Search**: Symbol lookup and contract details
- **Wall Street Horizon**: Corporate events calendar

## Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                         TWS / IB Gateway                     │
│                      (Server on port 7496)                   │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ TCP Socket
                              │
┌─────────────────────────────▼─────────────────────────────┐
│                        Your Application                     │
│  ┌────────────┐              ┌──────────────┐             │
│  │  EClient   │  ─────────▶  │   EWrapper   │             │
│  │ (Requests) │              │  (Responses) │             │
│  └────────────┘              └──────────────┘             │
│         │                            ▲                      │
│         │                            │                      │
│         ▼                            │                      │
│  ┌─────────────────────────────────────┐                   │
│  │          Connection                  │                   │
│  │  ┌─────────┐      ┌────────────┐   │                   │
│  │  │ Reader  │      │  Decoder   │   │                   │
│  │  │ Thread  │ ───▶ │  (Parser)  │   │                   │
│  │  └─────────┘      └────────────┘   │                   │
│  └─────────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

### Message Flow

**Sending Requests** (Client → TWS):

1. Application calls `EClient` method (e.g., `reqMktData()`)
2. `EClient` encodes request into high-level message
3. `Connection` sends low-level message via TCP socket

**Receiving Responses** (TWS → Client):

1. `Reader` thread receives packets from socket
2. Packets assembled into low-level messages (size-prefixed)
3. `Decoder` parses into high-level messages (NULL-separated fields)
4. Corresponding `EWrapper` callback invoked with parsed data

### Key Classes

- **`EClient`**: Sends requests to TWS (place orders, request data, etc.)
- **`EWrapper`**: Receives callbacks from TWS (market data, order updates, errors)
- **`Connection`**: Manages TCP socket connection
- **`Reader`**: Background thread that reads incoming messages
- **`Decoder`**: Parses raw messages into structured data
- **`Contract`**: Represents financial instruments
- **`Order`**: Defines order parameters

## Installation

### Requirements

- **Python**: 3.11.0 or higher
- **TWS/IB Gateway**: Latest stable or offline version
- **Dependencies**: protobuf==5.29.3

### Install from Source

The TWS API is already included in this project at `backend/external_packages/tws/source/pythonclient/`.

To install in development mode:

```bash
cd backend/external_packages/tws/source/pythonclient
pip install -e .
```

To build and install wheel:

```bash
cd backend/external_packages/tws/source/pythonclient
python setup.py bdist_wheel
pip install dist/ibapi-10.37.2-py3-none-any.whl
```

### Protobuf Dependency

The API uses **Protocol Buffers 5.29.3** for efficient message serialization. It's automatically installed via `pip install`.

If you need to regenerate protobuf files:

```bash
cd backend/external_packages/tws/source
protoc --proto_path=./proto --python_out=./pythonclient/ibapi/protobuf proto/*.proto
```

## Quick Start

### 1. Configure TWS/IB Gateway

Before using the API, configure TWS:

1. **Enable API**:

   - Go to `File` → `Global Configuration` → `API` → `Settings`
   - Check "Enable ActiveX and Socket Clients"
   - Uncheck "Read-Only API"
   - Note the "Socket Port" (default: 7496 for TWS Live, 7497 for Paper)

2. **Allow Connections**:

   - For localhost: Keep "Allow connections from localhost only" checked
   - For remote: Add your IP to "Trusted IPs"

3. **Recommended Settings**:
   - Memory Allocation: 4000 MB
   - Lock and Exit: "Never lock" and "Auto restart"
   - API Precautions: Enable all bypass options
   - Create API message log file: Enable (for debugging)

### 2. Basic Connection Example

```python
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
import threading
import time

class TradingApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        print(f"Error {errorCode}: {errorString}")

    def nextValidId(self, orderId):
        """Called after successful connection"""
        print(f"Connected! Next valid order ID: {orderId}")
        self.nextOrderId = orderId
        # Start your trading logic here

def run_loop():
    app.run()

# Initialize and connect
app = TradingApp()
app.connect("127.0.0.1", 7496, clientId=0)

# Start message processing loop in separate thread
api_thread = threading.Thread(target=run_loop, daemon=True)
api_thread.start()

# Wait for connection
time.sleep(1)

# Keep application running
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    app.disconnect()
```

### 3. Request Market Data

```python
def tickPrice(self, reqId, tickType, price, attrib):
    print(f"Tick Price - ID: {reqId}, Type: {tickType}, Price: {price}")

def tickSize(self, reqId, tickType, size):
    print(f"Tick Size - ID: {reqId}, Type: {tickType}, Size: {size}")

# Create contract
contract = Contract()
contract.symbol = "AAPL"
contract.secType = "STK"
contract.exchange = "SMART"
contract.currency = "USD"

# Request market data
app.reqMktData(1001, contract, "", False, False, [])
```

### 4. Place an Order

```python
from ibapi.order import Order

def orderStatus(self, orderId, status, filled, remaining, avgFillPrice,
                permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice):
    print(f"Order {orderId}: {status}")

# Create order
order = Order()
order.action = "BUY"
order.orderType = "LMT"
order.totalQuantity = 100
order.lmtPrice = 150.00

# Place order
app.placeOrder(app.nextOrderId, contract, order)
app.nextOrderId += 1
```

## Project Integration

This TWS API library is located in your project at:

```
backend/external_packages/tws/
├── API_VersionNum.txt          # Version file
├── samples/                    # Example code
│   └── Python/Testbed/        # Full test application
└── source/
    ├── pythonclient/          # Python API source
    │   ├── ibapi/            # Main package
    │   │   ├── client.py     # EClient class
    │   │   ├── wrapper.py    # EWrapper class
    │   │   ├── contract.py   # Contract definitions
    │   │   ├── order.py      # Order definitions
    │   │   └── protobuf/     # Protobuf message types
    │   ├── setup.py          # Installation script
    │   └── tests/            # Unit tests
    └── proto/                 # Protobuf definitions
```

### Sample Code

Explore the comprehensive samples in `samples/Python/Testbed/`:

- **`Program.py`**: Main test application with all API features
- **`ContractSamples.py`**: Contract creation examples
- **`OrderSamples.py`**: Various order type examples
- **`AvailableAlgoParams.py`**: Algorithmic order parameters
- **`ScannerSubscriptionSamples.py`**: Market scanner configurations
- **`FaAllocationSamples.py`**: Financial Advisor allocations

## Common Use Cases

### Historical Data

```python
def historicalData(self, reqId, bar):
    print(f"{bar.date} - O:{bar.open} H:{bar.high} L:{bar.low} C:{bar.close} V:{bar.volume}")

app.reqHistoricalData(
    reqId=2001,
    contract=contract,
    endDateTime="",                    # Empty = now
    durationStr="1 D",                 # 1 day of data
    barSizeSetting="1 min",            # 1-minute bars
    whatToShow="TRADES",               # Trade data
    useRTH=1,                          # Regular trading hours only
    formatDate=1,                      # Date as string
    keepUpToDate=False,                # Snapshot only
    chartOptions=[]
)
```

### Account Information

```python
def updateAccountValue(self, key, val, currency, accountName):
    print(f"{accountName} - {key}: {val} {currency}")

def updatePortfolio(self, contract, position, marketPrice, marketValue,
                    averageCost, unrealizedPNL, realizedPNL, accountName):
    print(f"{contract.symbol}: Pos={position}, Mkt={marketPrice}, PnL={unrealizedPNL}")

app.reqAccountUpdates(True, "DU123456")  # Your account ID
```

### Real-time Positions

```python
def position(self, account, contract, position, avgCost):
    print(f"{account}: {contract.symbol} - {position} @ {avgCost}")

def positionEnd(self):
    print("All positions received")

app.reqPositions()  # Request all positions
```

## Error Handling

### Error Codes

- **1xxx**: System messages (connectivity, server status)
- **2xxx**: Warnings (market data farm status)
- **100-999**: Client errors (validation, permissions)
- **1000+**: Order-related errors

### Important Error Codes

| Code  | Message                                     | Solution                                     |
| ----- | ------------------------------------------- | -------------------------------------------- |
| 502   | Couldn't connect to TWS                     | Enable API in TWS settings, check port       |
| 1100  | Connectivity lost                           | Temporary disconnect, wait for 1102          |
| 1102  | Connection restored                         | Resume operations                            |
| 2104  | Market data farm is OK                      | Normal status message                        |
| 2106  | HMDS data farm is OK                        | Normal status message                        |
| 10167 | Requested market data requires subscription | Subscribe to market data or use delayed data |

### Best Practices

```python
def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
    if errorCode >= 2000:
        # Warnings - informational only
        print(f"INFO {errorCode}: {errorString}")
    elif errorCode >= 1000:
        # System messages
        print(f"SYSTEM {errorCode}: {errorString}")
        if errorCode == 1100:
            # Connection lost - pause operations
            self.is_connected = False
        elif errorCode == 1102:
            # Connection restored
            self.is_connected = True
    else:
        # Real errors
        print(f"ERROR {errorCode}: {errorString}")
```

## Pacing Limits

The API enforces pacing limits to prevent overload:

- **Market Data**: 50 messages/second (= max market data lines / 2)
- **Default Lines**: 100 (= 50 req/sec max)
- **Breaking Limit**: Error 100, 3 violations = disconnect

**Tip**: Use `time.sleep()` between requests or implement request queuing.

## Important Notes

### Threading Model

The TWS API uses **at least 2 threads**:

1. **Main thread**: Sends requests via `EClient`
2. **Reader thread**: Receives messages, calls `EWrapper` callbacks

⚠️ **All `EWrapper` callbacks run in the reader thread!** Use thread-safe patterns when accessing shared data.

### Client ID

- **Client ID 0**: Special "master" client that can see all orders
- **Other IDs**: Only see their own orders
- **Max connections**: 32 simultaneous clients per TWS session

### Market Data Subscriptions

- Market data requires **separate subscriptions** from IB
- Different in TWS vs API (TWS snapshots may not be available via API)
- Use `reqMarketDataType(4)` for delayed data (free, 15-min delay)
- Check [IB Market Data](https://www.interactivebrokers.com/en/trading/market-data-subscriptions.php)

### Order Management

- Orders are **bound to the client ID** that placed them
- Only the originating client can modify its orders
- Client ID 0 can bind manual TWS orders (use `reqAutoOpenOrders(True)`)
- Order IDs must be **unique and sequential**

## Resources

### Official Documentation

- **Main Documentation**: https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/
- **API Reference**: https://ibkrcampus.com/campus/ibkr-api-page/twsapi-ref/
- **Download Page**: https://interactivebrokers.github.io/
- **Video Tutorials**: https://www.interactivebrokers.com/campus/trading-course/python-tws-api/

### Interactive Brokers Links

- **Account Management**: https://www.interactivebrokers.com/portal
- **Market Data Subscriptions**: https://www.interactivebrokers.com/en/trading/market-data-subscriptions.php
- **System Status**: https://www.interactivebrokers.com/en/software/systemStatus.php
- **Support**: https://www.interactivebrokers.com/en/support/customer-service.php

### Community

- **GitHub**: https://github.com/InteractiveBrokers/tws-api
- **Forums**: https://www.interactivebrokers.com/en/software/api/forums.php

## Troubleshooting

### Connection Issues

```python
# Problem: Error 502 - Can't connect
# Solution:
1. Check TWS API settings are enabled
2. Verify correct port (7496 live, 7497 paper)
3. For remote: Add IP to Trusted IPs
4. Disable firewall/antivirus temporarily
```

### No Market Data

```python
# Problem: No data after reqMktData
# Solution:
1. Subscribe to market data in Account Management
2. Use delayed data: app.reqMarketDataType(4)
3. Check you're using the right exchange
4. Verify contract details: app.reqContractDetails()
```

### API Logs

Enable detailed logging in TWS:

1. `Global Configuration` → `API` → `Settings`
2. Check "Create API message log file"
3. Set "Logging Level" to "Detail"
4. Logs saved to: `C:\Jts\` (Windows) or `~/Jts/` (Unix)

### Debug Mode

```python
# Enable TWS debug mode for conId lookup
# Edit jts.ini: [Communication] debug=1
# Then in TWS watchlist: type "265598|C" and press Enter
# to resolve conId to symbol
```

## License

This software is subject to the terms and conditions of either:

- **IB API Non-Commercial License**, or
- **IB API Commercial License**

See the license files in the source distribution for details.

## Version Information

- **API Version**: 10.37.02
- **Python Requirement**: 3.11.0+
- **Protobuf Version**: 5.29.3
- **Last Updated**: January 2025

---

**Note**: Always test with **Paper Trading** account before using live trading!

For questions specific to Trader Pro integration, see project documentation in `/docs/`.
