# TWS API - Setup & Installation Guide

<!-- METADATA: scope=installation, priority=critical, dependencies=[] -->

> **Source:** [TWS API Documentation](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/)  
> **Last Updated:** November 19, 2025

Complete guide for installing and configuring the TWS API for Python development.

**[CRITICAL]** This is your first step to working with TWS API. Complete setup before attempting connectivity.

---

## 📑 Quick Navigation - Cross-Reference Table

| Section       | Topic                                             | Jump To                                |
| ------------- | ------------------------------------------------- | -------------------------------------- |
| **1.0**       | Overview                                          | [§1.0](#10-overview)                   |
| **2.0**       | Prerequisites                                     | [§2.0](#20-prerequisites)              |
| **3.0**       | Installation Options                              | [§3.0](#30-installation-options)       |
| **4.0**       | Python Setup                                      | [§4.0](#40-python-setup)               |
| **5.0**       | TWS/Gateway Configuration                         | [§5.0](#50-twsgateway-configuration)   |
| **6.0**       | Verification                                      | [§6.0](#60-verification)               |
| **7.0**       | Common Issues                                     | [§7.0](#70-common-installation-issues) |
| **Related**   | [Main Navigation](./README.md)                    | Back to index                          |
| **Next**      | [Connectivity Guide](./07-CONNECTIVITY-GUIDE.md)  | Connection management                  |
| **Reference** | [Core API Classes](./01-API-REFERENCE-CLASSES.md) | EClient/EWrapper                       |

---

## 0.0 Installation Checklist

**[QUICK-REFERENCE]** Complete setup workflow:

- [ ] **Prerequisites:** Python 3.8+, Java 11+ (for TWS/Gateway)
- [ ] **Enable API Access:** Account Management → Trading Permissions → API Trading
- [ ] **Choose Installation:** Standalone API (pip) + TWS/Gateway
- [ ] **Install Python Client:** `pip install ibapi`
- [ ] **Install TWS or Gateway:** Download from IB website
- [ ] **Configure API Settings:** Enable socket clients, set port, add trusted IP
- [ ] **Verify Connection:** Run test script (see [§6.0](#60-verification))
- [ ] **Next Step:** [Connectivity Guide](./07-CONNECTIVITY-GUIDE.md)

---

## Table of Contents

- [1.0 Overview](#10-overview)
- [2.0 Prerequisites](#20-prerequisites)
- [3.0 Installation Options](#30-installation-options)
  - [3.1 Option 1: Standalone API (Recommended)](#31-option-1-standalone-api-recommended)
  - [3.2 Option 2: TWS Desktop](#32-option-2-tws-desktop)
  - [3.3 Option 3: IB Gateway](#33-option-3-ib-gateway)
- [4.0 Python Setup](#40-python-setup)
- [5.0 TWS/Gateway Configuration](#50-twsgateway-configuration)
- [6.0 Verification](#60-verification)
- [7.0 Common Installation Issues](#70-common-installation-issues)
- [8.0 Next Steps](#80-next-steps)

---

## 1.0 Overview

<!-- METADATA: scope=architecture-overview, priority=high, dependencies=[] -->

The Interactive Brokers TWS API allows you to programmatically connect to TWS (Trader Workstation) or IB Gateway to:

- **[MARKET-DATA]** Retrieve market data (real-time, historical, market depth)
- **[TRADING]** Place, modify, and cancel orders
- **[ACCOUNT]** Monitor account positions and balances
- **[EXECUTION]** Receive execution reports
- **[NEWS]** Access news and corporate events

**[ARCHITECTURE]** Client-server communication pattern:

```
Your Python Application
        ↓
   TWS API Client (ibapi)
        ↓
  Socket Connection (localhost:7496 or 7497)
        ↓
TWS Desktop / IB Gateway
        ↓
  IB Trading Servers
```

**[PATTERN]**: Socket-based client-server architecture [enables language-agnostic API design] [TWS API design]

---

## 2.0 Prerequisites

<!-- METADATA: scope=requirements, priority=critical, dependencies=[] -->

### 2.1 System Requirements

**[REQUIRED]** Software dependencies:

- **Operating System:** Windows, macOS, or Linux
- **Python:** 3.8 or higher recommended
- **Java:** Required for TWS Desktop or IB Gateway (Java 11+ recommended)
- **Internet:** Stable connection for market data and order routing

### 2.2 Account Requirements

**[REQUIRED]** IB account setup:

- **IB Account:** Live or paper trading account
- **API Access:** Must be enabled in Account Management

**[CRITICAL]** Enable API Access (required before first connection):

1. Log into Account Management: https://www.interactivebrokers.com/sso
2. Navigate to Settings → User Settings
3. Under Trading Experience & Permissions, enable "API Trading"
4. Accept API agreement if prompted

**[PITFALL]** Forgetting to enable API access causes Error 504 (Not connected). Enable this in Account Management before installing.

---

## 3.0 Installation Options

<!-- METADATA: scope=installation-choices, priority=critical, dependencies=[2.0] -->

**[DECISION]**: Recommend standalone API + separate TWS/Gateway [lighter footprint, pip-installable, production-ready] [rejected: bundled TWS install] [Nov 2025]

### 3.1 Option 1: Standalone API (Recommended)

**[RECOMMENDED]** Install only the API client library without TWS/Gateway. Requires separate TWS/Gateway installation.

**[INSTALLATION]** Python client:

```bash
# Install via pip (recommended)
pip install ibapi

# Or install from source (development)
git clone https://github.com/InteractiveBrokers/tws-api-public.git
cd tws-api-public/source/pythonclient
pip install -e .
```

**[PERFORMANCE]** Advantages:

- Minimal installation footprint
- Easy to include in requirements.txt
- No Java dependencies for client code
- Faster updates via pip

**[USE-CASE]** When to use:

- Production deployments
- Automated trading systems
- Cloud-based applications
- CI/CD pipelines

---

### 3.2 Option 2: TWS Desktop

**[PLATFORM]** Full trading platform with GUI and API capabilities.

**[DOWNLOAD]** Sources:

- Latest stable: https://www.interactivebrokers.com/en/trading/tws.php
- Latest beta: https://www.interactivebrokers.com/en/trading/tws-updateable-latest.php

**[INSTALLATION]** Steps:

1. Download installer for your OS (Windows .exe, macOS .dmg, Linux .sh)
2. Run installer and follow prompts
3. Choose installation directory (default recommended)
4. Launch TWS and log in with IB credentials

**[CONFIGURATION]** API settings:

- API settings: Edit → Global Configuration → API → Settings
- Socket port: 7496 (live), 7497 (paper)
- Enable ActiveX and Socket Clients
- Allow connections from localhost (127.0.0.1)

**[PERFORMANCE]** Advantages:

- Full GUI for manual trading
- Built-in charts and analytics
- Monitor API connections visually
- Easier debugging with log viewer

**[PITFALL]** Disadvantages:

- Requires desktop environment
- Higher memory usage (~500MB-1GB)
- Must keep GUI open for API connections

**[USE-CASE]** When to use:

- Development and testing
- Hybrid manual/automated trading
- Interactive market monitoring
- Learning API behavior

---

### 3.3 Option 3: IB Gateway

**[RECOMMENDED]** Lightweight headless API server without GUI (production environments).

**[DOWNLOAD]** Sources:

- Stable: https://www.interactivebrokers.com/en/trading/ibgateway-stable.php
- Latest: https://www.interactivebrokers.com/en/trading/ibgateway-latest.php

**[INSTALLATION]** Steps:

1. Download installer for your OS
2. Run installer (requires Java 11+)
3. Launch IB Gateway
4. Log in with IB credentials
5. Gateway runs in system tray (minimize to background)

**[CONFIGURATION]** Settings:

- Settings file: `jts.ini` in installation directory
- Socket port: 4001 (live), 4002 (paper)
- Enable API connections
- Set trusted IP addresses

**[PERFORMANCE]** Advantages:

- Low resource usage (~200MB)
- Designed for automated systems
- Can run headless (Linux servers)
- Faster startup than TWS

**[PITFALL]** Disadvantages:

- No GUI for troubleshooting
- Limited monitoring capabilities
- Requires manual restart if crashed

**[USE-CASE]** When to use:

- Production trading servers
- Cloud deployments (AWS, GCP, Azure)
- Dockerized applications
- High-uptime requirements

**[DECISION]**: Use IB Gateway for production deployments [minimal resource footprint, headless operation] [rejected: TWS Desktop] [Nov 2025]

---

## 4.0 Python Setup

<!-- METADATA: scope=python-client-installation, priority=critical, dependencies=[3.0] -->

### 4.1 Install TWS API

**[INSTALLATION]** From PyPI (Recommended):

```bash
pip install ibapi
```

**[DEVELOPMENT]** From Source (Development):

```bash
git clone https://github.com/InteractiveBrokers/tws-api-public.git
cd tws-api-public/source/pythonclient
pip install -e .
```

**[VERIFICATION]** Verify Installation:

```python
python -c "from ibapi.client import EClient; from ibapi.wrapper import EWrapper; print('TWS API imported successfully')"
```

**[REQUIRED]** Minimum Python version: 3.8+

### 4.2 Project Structure

**[PATTERN]** Recommended structure for TWS API projects:

```
your_project/
├── requirements.txt          # ibapi>=10.19.1
├── config.py                 # Connection settings
├── client.py                 # EClient/EWrapper implementation
├── strategies/               # Trading strategies
│   ├── __init__.py
│   └── example_strategy.py
└── tests/                    # Unit tests
    └── test_client.py
```

**[EXAMPLE]** requirements.txt:

```
ibapi>=10.19.1
pandas>=1.5.0
numpy>=1.24.0
```

---

## 5.0 TWS/Gateway Configuration

<!-- METADATA: scope=api-configuration, priority=critical, dependencies=[3.0, 4.0] -->

### 5.1 Enable API Connections

**[CRITICAL]** TWS Configuration:

1. File → Global Configuration → API → Settings
2. **Enable ActiveX and Socket Clients:** ✓
3. **Socket port:** 7496 (live) or 7497 (paper)
4. **Master API client ID:** 0 (or specific ID)
5. **Read-Only API:** ☐ (unchecked for trading)
6. **Download open orders on connection:** ✓ (recommended)
7. **Trusted IPs:** Add 127.0.0.1 (localhost)
8. Click OK and restart TWS

**[CRITICAL]** IB Gateway Configuration:

1. Configure → Settings → API → Settings
2. Same settings as TWS above
3. Restart Gateway after changes

**[SECURITY]** Always restrict trusted IPs to only necessary addresses. Use 127.0.0.1 for local development.

### 5.2 Port Configuration

**[REFERENCE]** Default ports:

| Application | Live Account | Paper Account |
| ----------- | ------------ | ------------- |
| TWS         | 7496         | 7497          |
| IB Gateway  | 4001         | 4002          |

**[CONFIGURATION]** Custom Ports:
You can configure custom ports in TWS/Gateway settings if defaults conflict with other applications.

**[PITFALL]** Port mismatch is the #1 cause of connection Error 502. Always verify the port matches your TWS/Gateway configuration.

### 5.3 Client ID

**[REQUIRED]** Client ID requirements:

- Each API connection requires a unique Client ID (integer)
- Client ID 0 can receive all manual TWS orders
- Client IDs 1-9999 recommended for API applications
- Multiple clients can connect simultaneously with different IDs

**[PITFALL]** Using the same Client ID for multiple connections causes Error 326 (Client ID already in use).

---

## 6.0 Verification

<!-- METADATA: scope=installation-verification, priority=critical, dependencies=[5.0] -->

### 6.1 Test Connection

**[VERIFICATION]** Simple Connection Test:

```python
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from threading import Thread
import time

class TestApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        print(f"Error {errorCode}: {errorString}")

    def nextValidId(self, orderId):
        print(f"Connected! Next valid order ID: {orderId}")
        self.disconnect()

def run_app():
    app = TestApp()
    app.connect("127.0.0.1", 7497, clientId=1)  # Paper trading port
    app.run()

if __name__ == "__main__":
    thread = Thread(target=run_app)
    thread.start()
    time.sleep(5)
```

**[SUCCESS]** Expected Output:

```
Connected! Next valid order ID: 1
```

**[ERROR]** Common Error Codes:

- **502:** Couldn't connect to TWS (TWS not running or wrong port)
- **504:** Not connected (TWS rejected connection)
- **326:** Unable connect as client ID already in use

For complete error reference, see [§7.0 Common Installation Issues](#70-common-installation-issues).

### 6.2 Verify Market Data

**[VERIFICATION]** Test market data subscription:

```python
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract

class DataApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)

    def nextValidId(self, orderId):
        # Create contract for AAPL stock
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"

        # Request market data
        self.reqMktData(1, contract, "", False, False, [])

    def tickPrice(self, reqId, tickType, price, attrib):
        print(f"Tick {tickType}: Price = {price}")

app = DataApp()
app.connect("127.0.0.1", 7497, clientId=1)
app.run()
```

---

## 7.0 Common Installation Issues

<!-- METADATA: scope=troubleshooting, priority=high, dependencies=[6.0] -->

### 7.1 Issue: "Couldn't connect to TWS" (Error 502)

**[ERROR]** Causes:

- TWS/Gateway not running
- Wrong port number
- Firewall blocking connection

**[SOLUTION]** Fixes:

1. Verify TWS/Gateway is running and logged in
2. Check port number matches configuration (7497 for paper, 7496 for live)
3. Disable firewall temporarily to test
4. Use `netstat -an | grep 7497` to verify port is listening

### 7.2 Issue: "Not connected" (Error 504)

**[ERROR]** Causes:

- API not enabled in TWS settings
- Client ID already in use
- IP address not trusted

**[SOLUTION]** Fixes:

1. Enable "ActiveX and Socket Clients" in TWS API settings
2. Use unique Client ID for each connection
3. Add 127.0.0.1 to trusted IPs
4. Restart TWS after configuration changes

### 7.3 Issue: "No market data permissions"

**[ERROR]** Causes:

- Missing market data subscriptions
- Paper account with limited data

**[SOLUTION]** Fixes:

1. Check Account Management → Market Data Subscriptions
2. Use paper trading account for testing (delayed data free)
3. Subscribe to required exchanges for live data

### 7.4 Issue: Import error - "No module named 'ibapi'"

**[ERROR]** Causes:

- TWS API not installed
- Wrong Python environment

**[SOLUTION]** Fixes:

```bash
# Verify pip installation
pip show ibapi

# Reinstall if needed
pip uninstall ibapi
pip install ibapi

# Check Python version
python --version  # Should be 3.8+
```

### 7.5 Issue: TWS/Gateway won't accept connections

**[ERROR]** Causes:

- Socket port setting incorrect
- Localhost not in trusted IPs
- API disabled in global configuration

**[SOLUTION]** Fixes:

1. TWS: Edit → Global Configuration → API → Settings
2. Verify "Enable ActiveX and Socket Clients" is checked
3. Socket port matches your connection code
4. Add 127.0.0.1 to "Trusted IPs" (or leave blank for localhost only)
5. Uncheck "Allow connections from localhost only" if connecting from network

---

## 8.0 Next Steps

**[WORKFLOW]** Continue to implementation guides:

- **[Connectivity Guide](./07-CONNECTIVITY-GUIDE.md)** - [CRITICAL] Learn connection patterns, threading, and event handling
- **[Market Data Guide](./08-MARKET-DATA-GUIDE.md)** - Request real-time and historical data _(Coming Soon)_
- **[Order Management Guide](./09-ORDER-MANAGEMENT-GUIDE.md)** - Place and manage orders _(Coming Soon)_
- **[API Reference](./01-API-REFERENCE-CLASSES.md)** - Complete class and method documentation

**[NAVIGATION]** Return to:

- **[Main Navigation](./README.md)** - TWS API documentation index

---

**[REFERENCE]** External resources:

- [TWS API Documentation](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/)
- [IB Knowledge Base](https://www.interactivebrokers.com/en/support/knowledge-base.php)
- [TWS API GitHub](https://github.com/InteractiveBrokers/tws-api-public)

---

**Referenced by:**

- [Main Navigation](./README.md#12-implementation-guides) - Setup Guide (Guide-06)
- [Connectivity Guide](./07-CONNECTIVITY-GUIDE.md) - Prerequisites for connection management
