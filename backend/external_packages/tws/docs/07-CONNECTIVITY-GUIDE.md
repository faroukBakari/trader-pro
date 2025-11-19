# TWS API - Connectivity & Threading Guide

<!-- METADATA: scope=connection-management, priority=critical, dependencies=[06-SETUP] -->

> **Source:** [TWS API Documentation](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/)  
> **Last Updated:** November 19, 2025

Complete guide for establishing connections, managing threads, and handling API events.

**[CRITICAL]** Master connection patterns and threading before building production applications.

---

## 📑 Quick Navigation - Cross-Reference Table

| Section       | Topic                                            | Jump To                                     |
| ------------- | ------------------------------------------------ | ------------------------------------------- |
| **1.0**       | Architecture Overview                            | [§1.0](#10-architecture-overview)           |
| **2.0**       | Basic Connection                                 | [§2.0](#20-basic-connection)                |
| **3.0**       | Threading Model                                  | [§3.0](#30-threading-model)                 |
| **4.0**       | Connection Management                            | [§4.0](#40-connection-management)           |
| **5.0**       | Error Handling                                   | [§5.0](#50-error-handling)                  |
| **6.0**       | Best Practices                                   | [§6.0](#60-best-practices)                  |
| **Related**   | [Main Navigation](./README.md)                   | Back to index                               |
| **Previous**  | [Setup Guide](./06-SETUP-GUIDE.md)               | Installation & configuration                |
| **Next**      | [Market Data Guide](./08-MARKET-DATA-GUIDE.md)   | Real-time & historical data _(Coming Soon)_ |
| **Reference** | [EClient Methods](./01-API-REFERENCE-CLASSES.md) | Core API classes                            |

---

## Table of Contents

- [1.0 Architecture Overview](#10-architecture-overview)
- [2.0 Basic Connection](#20-basic-connection)
- [3.0 Threading Model](#30-threading-model)
  - [3.1 Pattern 1: EClient.run() Thread (Simple)](#31-pattern-1-eclientrun-thread-simple)
  - [3.2 Pattern 2: EReader Thread (Production)](#32-pattern-2-ereader-thread-production)
  - [3.3 Pattern 3: Asyncio (Modern Python)](#33-pattern-3-asyncio-modern-python)
- [4.0 Connection Management](#40-connection-management)
- [5.0 Error Handling](#50-error-handling)
- [6.0 Best Practices](#60-best-practices)
- [7.0 Next Steps](#70-next-steps)

---

## 1.0 Architecture Overview

<!-- METADATA: scope=architecture-pattern, priority=high, dependencies=[] -->

### 1.1 Client-Server Pattern

**[ARCHITECTURE]** TWS API uses a **socket-based client-server architecture**:

```
┌─────────────────────────┐
│   Your Application      │
│  ┌─────────────────┐    │
│  │   EWrapper      │◄───── Callbacks (incoming data)
│  │  (Callbacks)    │    │
│  └─────────────────┘    │
│  ┌─────────────────┐    │
│  │   EClient       │───── Requests (outgoing commands)
│  │  (Requests)     │    │
│  └─────────────────┘    │
└───────────┬──────────────┘
           │ Socket (TCP)
           │ localhost:7496/7497
           ▼
┌─────────────────────────┐
│   TWS / IB Gateway      │
│  ┌─────────────────┐    │
│  │  Message Queue  │    │
│  └─────────────────┘    │
│  ┌─────────────────┐    │
│  │  Order Router   │    │
│  └─────────────────┘    │
│  ┌─────────────────┐    │
│  │  Market Data    │    │
│  └─────────────────┘    │
└─────────────────────────┘
```

**[DECISION]**: Socket-based architecture [language-agnostic, standard network protocol] [rejected: language-specific bindings] [TWS API design]

### 1.2 Key Components

**[REQUEST]** EClient:

- Sends requests to TWS/Gateway
- Methods like `reqMktData()`, `placeOrder()`, `reqAccountUpdates()`
- Non-blocking (returns immediately)

**[CALLBACK]** EWrapper:

- Receives callbacks from TWS/Gateway
- Methods like `tickPrice()`, `orderStatus()`, `error()`
- Called automatically when data arrives

**[PERFORMANCE]** EReader (optional):

- Manages incoming message queue
- Decouples network I/O from message processing
- Recommended for production applications

**[PATTERN]**: Callback-driven architecture [asynchronous event handling] [alternative: polling-based] [TWS API design]

---

## 2.0 Basic Connection

<!-- METADATA: scope=connection-basics, priority=critical, dependencies=[06-SETUP] -->

### 2.1 Minimal Example

**[EXAMPLE]** Basic connection pattern:

```python
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from threading import Thread
import time

class IBApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        print(f"Error {errorCode}: {errorString}")

    def nextValidId(self, orderId):
        print(f"Connected! Next Order ID: {orderId}")
        self.nextOrderId = orderId

# Create app instance
app = IBApp()

# Connect to TWS (host, port, clientId)
app.connect("127.0.0.1", 7497, clientId=1)

# Start message processing loop in separate thread
api_thread = Thread(target=app.run, daemon=True)
api_thread.start()

# Wait for connection
time.sleep(1)

# Your trading logic here
# ...

# Disconnect when done
app.disconnect()
```

### 2.2 Connection Parameters

**[REQUIRED]** Connection signature:

```python
app.connect(host, port, clientId)
```

**[PARAMETER]** host: IP address or hostname

- `"127.0.0.1"` or `"localhost"` for local TWS
- Remote IP if TWS on different machine (security risk)

**[PARAMETER]** port: TWS/Gateway listening port

- `7497` - TWS paper trading
- `7496` - TWS live trading
- `4002` - IB Gateway paper trading
- `4001` - IB Gateway live trading

**[PARAMETER]** clientId: Unique integer identifier (0-9999)

- Must be unique per connection
- `0` receives all manual TWS orders
- `1-9999` for API applications
- Different applications should use different IDs

**[PITFALL]** Using duplicate Client IDs causes Error 326. Always ensure unique IDs per connection.

**[SECURITY]** Remote connections require firewall configuration and expose trading access. Use SSH tunneling for remote access instead.

---

## 3.0 Threading Model

<!-- METADATA: scope=threading-patterns, priority=critical, dependencies=[2.0] -->

**[DECISION]**: TWS API requires threading [socket message loop must run separately from application logic] [rejected: blocking single-threaded design] [Nov 2025]

### 3.1 Pattern 1: EClient.run() Thread (Simple)

**[USE-CASE]** Basic applications, learning, prototyping

**[EXAMPLE]** Simple threading pattern:

```python
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from threading import Thread

class SimpleApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)

    def nextValidId(self, orderId):
        print("Connected!")
        # Make requests here
        self.reqCurrentTime()

    def currentTime(self, time):
        print(f"Server time: {time}")

app = SimpleApp()
app.connect("127.0.0.1", 7497, 1)

# Run message loop in separate thread
thread = Thread(target=app.run)
thread.start()

# Main thread continues
input("Press Enter to disconnect...")
app.disconnect()
thread.join()
```

**[PERFORMANCE]** Advantages:

- Simple to understand
- Minimal code
- Good for learning

**[PITFALL]** Disadvantages:

- `run()` blocks the calling thread
- Harder to coordinate with other threads
- Less control over message processing

---

### 3.2 Pattern 2: EReader Thread (Production)

**[RECOMMENDED]** **Use Case:** Production systems, high-frequency trading, complex applications

**[EXAMPLE]** Production-ready threading pattern:

```python
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.reader import EReader
from threading import Thread
import queue

class ProductionApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.msg_queue = queue.Queue()

    def nextValidId(self, orderId):
        print("Connected!")

    def currentTime(self, time):
        print(f"Server time: {time}")

app = ProductionApp()
app.connect("127.0.0.1", 7497, 1)

# Create and start EReader thread
reader = EReader(app.conn, app.msg_queue)
reader.start()

# Process messages in separate thread
def process_messages():
    while True:
        if not app.msg_queue.empty():
            msg = app.msg_queue.get()
            if msg is None:
                break
            reader.processMsgs()

msg_thread = Thread(target=process_messages, daemon=True)
msg_thread.start()

# Wait for connection
import time
time.sleep(1)

# Make requests
app.reqCurrentTime()

# Keep running
input("Press Enter to disconnect...")
app.disconnect()
```

**[PERFORMANCE]** Advantages:

- Decouples network I/O from processing
- Better performance under high message load
- More control over threading
- Can prioritize message types

**[PITFALL]** Disadvantages:

- More complex code
- Requires queue management
- Potential for queue overflow if not processed fast enough

**[DECISION]**: Use EReader for production apps [dedicated message processing thread, better performance] [rejected: simple threading] [Nov 2025]

---

### 3.3 Pattern 3: Asyncio (Modern Python)

**[USE-CASE]** Applications using async/await, integrating with other async libraries

**[EXAMPLE]** Async/await pattern:

```python
import asyncio
from ibapi.client import EClient
from ibapi.wrapper import EWrapper

class AsyncApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.connected_event = asyncio.Event()

    def nextValidId(self, orderId):
        print("Connected!")
        self.connected_event.set()

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        print(f"Error {errorCode}: {errorString}")

async def main():
    app = AsyncApp()
    app.connect("127.0.0.1", 7497, 1)

    # Run in executor to avoid blocking event loop
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, app.run)

    # Wait for connection
    await app.connected_event.wait()

    # Make async requests
    app.reqCurrentTime()

    # Keep running
    await asyncio.sleep(5)

    app.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

**[PERFORMANCE]** Advantages:

- Integrates with async frameworks (aiohttp, FastAPI)
- Efficient for I/O-bound operations
- Modern Python best practice

**[PITFALL]** Disadvantages:

- TWS API not natively async
- Requires careful executor management
- More complex error handling

---

## 4.0 Connection Management

<!-- METADATA: scope=connection-lifecycle, priority=critical, dependencies=[3.0] -->

### 4.1 Connection Lifecycle

**[ARCHITECTURE]** State diagram:

```
┌─────────────┐
│   Created   │
└──────┬──────┘
       │ connect()
       ▼
┌─────────────┐
│  Connecting │
└──────┬──────┘
       │ nextValidId()
       ▼
┌─────────────┐
│  Connected  │◄──┐
└──────┬──────┘   │
       │           │ Auto-reconnect
       │ error()   │ (if implemented)
       │ (502/504) │
       ▼           │
┌─────────────┐   │
│Disconnected │───┘
└─────────────┘
```

### 4.2 Detecting Connection State

**[PATTERN]** Track connection state in application:

```python
class ManagedApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.is_connected = False
        self.next_order_id = None

    def nextValidId(self, orderId):
        """Called when connection established"""
        self.is_connected = True
        self.next_order_id = orderId
        print("Connected successfully!")

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        """Called on errors"""
        if errorCode in [502, 504]:  # Connection errors
            self.is_connected = False
            print("Connection lost!")
        print(f"Error {errorCode}: {errorString}")

    def connectionClosed(self):
        """Called when connection closed"""
        self.is_connected = False
        print("Connection closed")
```

### 4.3 Auto-Reconnect

**[PATTERN]** Automatic reconnection with exponential backoff:

**[DECISION]**: Implement exponential backoff for reconnection [prevents server overload, graceful degradation] [rejected: fixed retry interval] [Nov 2025]

```python
import time
from threading import Thread, Event

class AutoReconnectApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.is_connected = False
        self.stop_event = Event()

    def nextValidId(self, orderId):
        self.is_connected = True
        print("Connected!")

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        if errorCode in [502, 504, 1100]:  # Connection errors
            self.is_connected = False

    def connectionClosed(self):
        self.is_connected = False

def maintain_connection(app, host, port, client_id):
    """Keep connection alive with auto-reconnect"""
    while not app.stop_event.is_set():
        if not app.is_connected:
            try:
                print(f"Connecting to {host}:{port}...")
                app.connect(host, port, client_id)

                # Start message loop
                Thread(target=app.run, daemon=True).start()

                # Wait for connection or timeout
                timeout = 0
                while not app.is_connected and timeout < 10:
                    time.sleep(1)
                    timeout += 1

                if app.is_connected:
                    print("Connected successfully!")
                else:
                    print("Connection timeout, retrying...")
                    app.disconnect()

            except Exception as e:
                print(f"Connection error: {e}")

        time.sleep(5)  # Check every 5 seconds

# Usage
app = AutoReconnectApp()
conn_thread = Thread(target=maintain_connection, args=(app, "127.0.0.1", 7497, 1))
conn_thread.start()

# Your application logic
try:
    while True:
        if app.is_connected:
            # Make requests when connected
            pass
        time.sleep(1)
except KeyboardInterrupt:
    app.stop_event.set()
    app.disconnect()
    conn_thread.join()
```

---

## 5.0 Error Handling

<!-- METADATA: scope=error-management, priority=critical, dependencies=[4.0] -->

### 5.1 Error Callback

**[CALLBACK]** Error handler signature:

```python
def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
    """
    reqId: Request ID that caused error (-1 if system-wide)
    errorCode: IB error code (see error codes table)
    errorString: Human-readable error description
    advancedOrderRejectJson: Additional rejection info (if applicable)
    """
    print(f"[{reqId}] Error {errorCode}: {errorString}")
```

### 5.2 Common Error Codes

**[REFERENCE]** Error code quick reference:

| Code     | Type                | Description                   | Action                            |
| -------- | ------------------- | ----------------------------- | --------------------------------- |
| **502**  | [ERROR] Connection  | Couldn't connect to TWS       | Check TWS is running, verify port |
| **504**  | [ERROR] Connection  | Not connected                 | Enable API in TWS settings        |
| **1100** | [ERROR] Connection  | Connectivity lost             | Auto-reconnect, check network     |
| **1101** | [INFO] Connection   | Restored data connection      | Resume normal operation           |
| **1102** | [INFO] Connection   | Restored data farm connection | Resume normal operation           |
| **2104** | [INFO] Data         | Market data farm connected    | Normal                            |
| **2106** | [INFO] Data         | HMDS data farm connected      | Normal                            |
| **2108** | [INFO] Data         | Market data farm disconnected | Temporary, usually recovers       |
| **200**  | [ERROR] Order       | No security definition found  | Invalid contract                  |
| **201**  | [ERROR] Order       | Order rejected                | Check order parameters            |
| **326**  | [ERROR] System      | Client ID already in use      | Use unique client ID              |
| **162**  | [ERROR] Market Data | Historical data error         | Check data subscription           |
| **354**  | [ERROR] Market Data | No market data permissions    | Subscribe to exchange data        |

**[PITFALL]** Errors 502, 504, 1100 indicate connection loss - implement auto-reconnect logic.

**[REFERENCE]** For complete error codes, see [TWS API Error Codes](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/#error-codes).

### 5.3 Error Handling Patterns

**[PATTERN]** Pattern 1: Log and Continue

```python
def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
    """Log all errors but don't crash"""
    import logging
    if errorCode >= 2000:  # Informational
        logging.info(f"[{reqId}] {errorCode}: {errorString}")
    elif errorCode >= 1000:  # Warnings
        logging.warning(f"[{reqId}] {errorCode}: {errorString}")
    else:  # Errors
        logging.error(f"[{reqId}] {errorCode}: {errorString}")
```

**[PATTERN]** Pattern 2: Specific Error Handling

```python
def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
    """Handle specific errors differently"""
    if errorCode in [502, 504]:
        # Connection errors - trigger reconnect
        self.handle_connection_error()
    elif errorCode == 200:
        # Invalid contract - notify caller
        self.handle_invalid_contract(reqId)
    elif errorCode in [1100, 1101, 1102]:
        # Connection state changes - update status
        self.update_connection_status(errorCode)
    else:
        print(f"Unhandled error {errorCode}: {errorString}")
```

---

## 6.0 Best Practices

<!-- METADATA: scope=best-practices, priority=high, dependencies=[5.0] -->

### 6.1 Always Use Threading

**[CRITICAL]** Threading is required:

```python
# ✓ CORRECT: Run in separate thread
thread = Thread(target=app.run, daemon=True)
thread.start()

# ✗ WRONG: Blocks main thread
app.run()
```

### 6.2 Wait for Connection Before Requests

**[PATTERN]** Use threading events for synchronization:

```python
class SafeApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.connected = threading.Event()

    def nextValidId(self, orderId):
        self.nextOrderId = orderId
        self.connected.set()  # Signal connection ready

app = SafeApp()
app.connect("127.0.0.1", 7497, 1)
Thread(target=app.run, daemon=True).start()

# Wait for connection (with timeout)
if app.connected.wait(timeout=10):
    # Safe to make requests
    app.reqCurrentTime()
else:
    print("Connection timeout!")
```

### 6.3 Handle Disconnections Gracefully

**[PATTERN]** Graceful degradation on connection loss:

```python
def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
    if errorCode == 1100:  # Connectivity lost
        # Pause order submissions
        self.pause_trading()
        # Cancel pending requests
        self.cancel_pending_requests()
    elif errorCode == 1102:  # Connection restored
        # Resume operations
        self.resume_trading()
        # Resubscribe to market data
        self.resubscribe_data()
```

### 6.4 Use Unique Request IDs

**[PATTERN]** Request tracking pattern:

```python
class RequestManager(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.next_req_id = 1
        self.pending_requests = {}

    def get_request_id(self):
        """Generate unique request ID"""
        req_id = self.next_req_id
        self.next_req_id += 1
        return req_id

    def track_request(self, req_id, callback):
        """Track pending requests"""
        self.pending_requests[req_id] = {
            'callback': callback,
            'timestamp': time.time()
        }
```

### 6.5 Implement Request Throttling

**[PERFORMANCE]** Rate limiting pattern (50 requests/second):

```python
import time
from collections import deque

class ThrottledApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.request_times = deque(maxlen=50)  # Last 50 requests

    def throttled_request(self, request_func, *args, **kwargs):
        """Limit to 50 requests per second"""
        now = time.time()

        # Remove requests older than 1 second
        while self.request_times and self.request_times[0] < now - 1:
            self.request_times.popleft()

        # Check if at limit
        if len(self.request_times) >= 50:
            sleep_time = 1 - (now - self.request_times[0])
            if sleep_time > 0:
                time.sleep(sleep_time)

        # Make request
        self.request_times.append(time.time())
        return request_func(*args, **kwargs)
```

### 6.6 Clean Shutdown

**[PATTERN]** Graceful shutdown sequence:

```python
def shutdown(app):
    """Graceful shutdown"""
    print("Shutting down...")

    # Cancel all active subscriptions
    app.cancelMktData(1)
    app.cancelMktDepth(2)

    # Wait for pending messages
    time.sleep(1)

    # Disconnect
    app.disconnect()

    # Wait for threads
    time.sleep(1)

    print("Shutdown complete")

# Register signal handler
import signal
signal.signal(signal.SIGINT, lambda sig, frame: shutdown(app))
```

---

## 📋 Quick Reference Cards

### Connection Error Codes & Solutions

| Error | Cause               | Solution                       |
| ----- | ------------------- | ------------------------------ |
| 502   | TWS not running     | Start TWS/Gateway, verify port |
| 504   | API disabled        | Enable API in TWS settings     |
| 326   | Duplicate Client ID | Use unique Client ID           |
| 1100  | Connection lost     | Implement auto-reconnect       |

### Threading Patterns Comparison

| Pattern       | Use Case             | Complexity | Performance |
| ------------- | -------------------- | ---------- | ----------- |
| EClient.run() | Learning, prototypes | Low        | Basic       |
| EReader       | Production systems   | Medium     | High        |
| Asyncio       | Async frameworks     | High       | Medium-High |

### Auto-Reconnect Implementation Checklist

- [ ] Track connection state (is_connected flag)
- [ ] Monitor error codes 502, 504, 1100
- [ ] Implement exponential backoff (5s, 10s, 20s, ...)
- [ ] Set maximum retry attempts
- [ ] Handle connection restored (errors 1101, 1102)
- [ ] Resubscribe to market data after reconnect
- [ ] Restore pending requests after reconnect
- [ ] Log connection state changes
- [ ] Notify application of connection status
- [ ] Implement connection timeout detection

---

## 7.0 Next Steps

**[WORKFLOW]** Continue to implementation guides:

- **[Market Data Guide](./08-MARKET-DATA-GUIDE.md)** - Request real-time and historical data _(Coming Soon)_
- **[Order Management Guide](./09-ORDER-MANAGEMENT-GUIDE.md)** - Place and manage orders _(Coming Soon)_
- **[Account & Portfolio Guide](./10-ACCOUNT-PORTFOLIO-GUIDE.md)** - Track positions and P&L _(Coming Soon)_
- **[API Reference - EClient](./01-API-REFERENCE-CLASSES.md)** - Complete method reference
- **[API Reference - EWrapper](./01-API-REFERENCE-CLASSES.md)** - Complete callback reference

**[NAVIGATION]** Return to:

- **[Main Navigation](./README.md)** - TWS API documentation index
- **[Setup Guide](./06-SETUP-GUIDE.md)** - Installation and configuration

---

**[REFERENCE]** External resources:

- [TWS API Documentation](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/)
- [IB Knowledge Base](https://www.interactivebrokers.com/en/support/knowledge-base.php)
- [TWS API GitHub](https://github.com/InteractiveBrokers/tws-api-public)

---

**Referenced by:**

- [Main Navigation](./README.md#12-implementation-guides) - Connectivity Guide (Guide-07)
- [Setup Guide](./06-SETUP-GUIDE.md#80-next-steps) - Next step after installation
