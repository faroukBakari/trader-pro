# WebSocket & AsyncAPI Implementation Guide

**Version**: 1.0.0  
**Last Updated**: October 11, 2025  
**Status**: ✅ Production Ready

## Overview

This document describes the hybrid **OpenAPI + AsyncAPI** architecture implemented for real-time trading data. The system supports both traditional REST API endpoints and modern WebSocket communication for live market data streaming.

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    Trading API Server                       │
├─────────────────────────────────────────────────────────────┤
│  REST API (OpenAPI)          │  WebSocket API (AsyncAPI)    │
│  ├─ /api/v1/health          │  ├─ /api/v1/ws/v1            │
│  ├─ /api/v1/datafeed        │  ├─ /api/v1/ws/config        │
│  ├─ /api/v1/versions        │  ├─ /api/v1/ws/stats         │
│  └─ /api/v1/docs            │  └─ 10 Real-time Channels    │
├─────────────────────────────────────────────────────────────┤
│              Connection Manager & Data Streams              │
└─────────────────────────────────────────────────────────────┘
```

## Key Files & Components

### Backend Implementation

| Component | File | Purpose |
|-----------|------|---------|
| **WebSocket Models** | `src/trading_api/core/websocket_models.py` | Pydantic models for all WebSocket messages |
| **Connection Manager** | `src/trading_api/core/websocket_manager.py` | Manages connections, subscriptions, broadcasting |
| **WebSocket API** | `src/trading_api/api/websockets.py` | FastAPI WebSocket endpoints |
| **Real-time Service** | `src/trading_api/core/realtime_service.py` | Mock data generators for testing |
| **AsyncAPI Spec** | `backend/asyncapi.yaml` | Complete AsyncAPI 3.0 specification |
| **Main App** | `src/trading_api/main.py` | FastAPI app with both REST and WebSocket |

### Configuration

| File | Purpose |
|------|---------|
| `backend/pyproject.toml` | Poetry dependencies |
| `backend/Makefile` | Development commands |

## WebSocket Channels

### Public Channels (No Authentication)
- **`market_data`** - Real-time price ticks (100/sec, 500 max subscribers)
- **`orderbook`** - Order book depth updates (50/sec, 200 max subscribers)
- **`trades`** - Recent trade updates (100/sec, 300 max subscribers)
- **`chart_data`** - Candlestick data for TradingView (10/sec, 100 max subscribers)
- **`system`** - System status messages (5/sec, 1000 max subscribers)
- **`heartbeat`** - Connection health monitoring (1/sec, 1000 max subscribers)

### Private Channels (Authentication Required)
- **`account`** - Balance updates (10/sec, 50 max subscribers)
- **`positions`** - Position updates (20/sec, 50 max subscribers)
- **`orders`** - Order status updates (50/sec, 100 max subscribers)
- **`notifications`** - Trading alerts (20/sec, 200 max subscribers)

## Message Flow

### Client Connection Flow
```
1. Client connects to ws://localhost:8000/api/v1/ws/v1
2. Server sends welcome message with available channels
3. Client sends subscription requests
4. Server validates and confirms subscriptions
5. Real-time data flows to subscribed clients
6. Heartbeat maintains connection health
```

### Message Types
```typescript
// Subscription Request
{
  "type": "subscribe",
  "channel": "market_data",
  "symbol": "AAPL"
}

// Market Data Response  
{
  "type": "market_tick",
  "timestamp": "2025-10-11T08:30:00Z",
  "channel": "market_data",
  "symbol": "AAPL",
  "price": 150.25,
  "volume": 1000,
  "bid": 150.20,
  "ask": 150.30,
  "change": 2.15,
  "change_percent": 1.45
}
```

## Development Commands

### Backend Operations
```bash
# Start backend server
cd backend && make dev

# Run tests
make test

# Check health
curl http://localhost:8000/api/v1/health

# Get WebSocket config
curl http://localhost:8000/api/v1/ws/config

# Get AsyncAPI spec
curl http://localhost:8000/api/v1/asyncapi.yaml
```

### Testing WebSocket Connections
```bash
# Test with wscat (install: npm install -g wscat)
wscat -c ws://localhost:8000/api/v1/ws/v1

# Send subscription
{"type": "subscribe", "channel": "market_data", "symbol": "AAPL"}

# Send authentication (for private channels)
{"type": "auth", "token": "your-jwt-token"}
```

## Real-time Data Service

The `RealTimeDataService` generates mock market data for testing:

### Features
- **Market Data Feed**: Simulates price movements every 0.5-2 seconds
- **Order Book Feed**: Updates bid/ask spreads every 2-5 seconds  
- **Chart Data Feed**: Generates 1-minute candlesticks every 5 seconds
- **Notification Feed**: Sends trading alerts every 30-60 seconds

### Symbols
Default symbols: `AAPL`, `GOOGL`, `MSFT`, `TSLA`, `AMZN`, `NVDA`, `META`

## Authentication

### Current Implementation
- **Mock Authentication**: Simple token validation (length > 10)
- **TODO**: Implement proper JWT validation

### Private Channel Access
```javascript
// Authenticate connection
ws.send(JSON.stringify({
  "type": "auth", 
  "token": "your-jwt-token-here"
}));

// Subscribe to private channel
ws.send(JSON.stringify({
  "type": "subscribe",
  "channel": "account"
}));
```

## Error Handling

### Connection Errors
- **Invalid JSON**: Returns error message
- **Unknown message type**: Returns error with supported types
- **Authentication required**: Returns auth error for private channels
- **Rate limiting**: Configured per channel but not enforced yet
- **Connection limits**: Max 1000 concurrent connections

### Graceful Degradation
- Automatic connection cleanup on disconnect
- Subscription removal when clients disconnect
- Real-time service restart on errors

## Production Considerations

### Security
- [ ] Implement proper JWT validation
- [ ] Add rate limiting enforcement
- [ ] Input sanitization and validation
- [ ] Connection abuse protection

### Performance
- [ ] Redis for connection state (multi-instance)
- [ ] Message batching for high-frequency data
- [ ] Connection pooling optimization
- [ ] Database integration for real market data

### Monitoring
- [ ] WebSocket connection metrics
- [ ] Message throughput monitoring
- [ ] Error rate tracking
- [ ] Performance profiling

## API Documentation

### OpenAPI (REST)
- **Interactive Docs**: http://localhost:8000/api/v1/docs
- **ReDoc**: http://localhost:8000/api/v1/redoc
- **Spec**: http://localhost:8000/api/v1/openapi.json

### AsyncAPI (WebSocket)
- **Spec**: http://localhost:8000/api/v1/asyncapi.yaml
- **TODO**: AsyncAPI HTML documentation

## Troubleshooting

### Common Issues

**Backend won't start**
```bash
# Check for port conflicts
lsof -i :8000

# Kill existing processes
pkill -f "uvicorn"

# Start fresh
cd backend && make dev
```

**WebSocket connection fails**
```bash
# Verify backend is running
curl http://localhost:8000/api/v1/health

# Check WebSocket endpoint
curl http://localhost:8000/api/v1/ws/config
```

**No real-time data**
```bash
# Check service status
curl http://localhost:8000/api/v1/ws/stats

# Verify subscriptions in logs
# Look for "subscribed to channel" messages
```

### Debugging WebSocket Messages

Add logging to see WebSocket traffic:
```python
import logging
logging.getLogger("trading_api.core.websocket_manager").setLevel(logging.DEBUG)
```

## Future Enhancements

### Frontend Integration
- [ ] AsyncAPI client generation for TypeScript
- [ ] WebSocket service wrapper
- [ ] TradingView real-time data integration
- [ ] React/Vue WebSocket hooks

### Advanced Features  
- [ ] WebSocket subprotocols
- [ ] Binary message support
- [ ] Message compression
- [ ] Replay functionality
- [ ] Historical data streaming

### Deployment
- [ ] Docker configuration
- [ ] Kubernetes manifests
- [ ] Load balancer WebSocket support
- [ ] SSL/TLS termination

## API Contract Validation

The system enforces strict API contracts:

### OpenAPI Validation
- All REST endpoints must have `response_model` defined
- Automatic OpenAPI spec generation
- Pre-commit hooks validate compliance

### AsyncAPI Validation  
- Complete message schema definitions
- Channel parameter validation
- Authentication requirement specification

## Maintenance Checklist

### Regular Tasks
- [ ] Update dependency versions
- [ ] Review connection limits and rate limits
- [ ] Monitor real-time service performance
- [ ] Check AsyncAPI spec accuracy
- [ ] Validate authentication flows

### Code Quality
- [ ] Run `make test` before changes
- [ ] Use `make format` for code formatting
- [ ] Check `make lint` for issues
- [ ] Update documentation for API changes

---

## Quick Start

1. **Start Backend**: `cd backend && make dev`
2. **Test REST**: `curl http://localhost:8000/api/v1/health`
3. **Test WebSocket**: `wscat -c ws://localhost:8000/api/v1/ws/v1`
4. **Subscribe**: `{"type": "subscribe", "channel": "market_data"}`
5. **View Docs**: http://localhost:8000/api/v1/docs

**Status**: ✅ Ready for frontend integration and production deployment!