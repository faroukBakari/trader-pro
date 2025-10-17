# Bar Data Broadcasting with Redis

## Overview

This document describes the implementation plan for offloading real-time bar data generation and broadcasting to a separate process using Redis Pub/Sub. This approach minimizes overhead on the main FastAPI application while providing scalable, resilient real-time data streaming.

## Architecture

```
┌──────────────────────┐         Redis          ┌──────────────────────┐
│  Bar Generator       │       Pub/Sub          │   FastAPI + WS       │
│  Process             │                        │   Main App           │
│  (Standalone)        │                        │                      │
│                      │                        │                      │
│  1. Generate bars    │  ──PUBLISH──►         │  1. SUBSCRIBE        │
│  2. Publish to       │   "bars:AAPL:1"       │  2. Receive bars     │
│     Redis channel    │   {bar data}          │  3. Broadcast via    │
│                      │                        │     wsApp.publish()  │
└──────────────────────┘                        └──────────────────────┘
     Separate process                               Existing app
     (CPU-intensive work)                           (minimal changes)
```

## Benefits

1. **Zero overhead on main app** - Bar generation runs in separate process
2. **Scalable** - Can run multiple generator processes for different symbols/markets
3. **Resilient** - Generator crash doesn't affect main API service
4. **Minimal refactoring** - Main app only needs Redis subscriber (< 100 lines)
5. **Easy to disable** - Just don't run the generator process
6. **Fast** - Redis pub/sub has sub-millisecond latency
7. **Production-ready** - Industry standard pattern for microservices

## Components

### 1. Bar Generator Process (NEW)

**File**: `backend/src/trading_api/services/bar_generator.py`

**Responsibilities**:
- Generate mocked bar data using `DatafeedService.mock_last_bar()`
- Publish bar data to Redis channels
- Run as standalone Python process
- Configurable symbols, resolutions, and intervals

**Redis Channel Format**: `bars:{SYMBOL}:{RESOLUTION}`
- Example: `bars:AAPL:1` for Apple 1-minute bars
- Example: `bars:GOOGL:D` for Google daily bars

**Message Format**:
```json
{
  "symbol": "AAPL",
  "resolution": "1",
  "bar": {
    "time": 1697097600000,
    "open": 150.0,
    "high": 151.0,
    "low": 149.5,
    "close": 150.5,
    "volume": 1000000
  }
}
```

**Configuration**:
```python
generator = BarGenerator(
    redis_url="redis://localhost:6379",
    interval=2.0,  # Generate every 2 seconds
    symbols=["AAPL", "GOOGL", "MSFT"],
    resolutions=["1", "5", "D"]
)
```

### 2. Bar Subscriber (NEW)

**File**: `backend/src/trading_api/services/bar_subscriber.py`

**Responsibilities**:
- Subscribe to Redis channels using pattern matching (`bars:*`)
- Receive bar data from Redis
- Check if WebSocket clients are subscribed to topic
- Broadcast to clients using `wsApp.publish()` only if subscribers exist
- Run within main FastAPI application lifecycle

**Integration**:
- Starts during FastAPI `lifespan` startup
- Stops gracefully during shutdown
- Uses existing `FastWSAdapter.publish()` method

### 3. Main App Changes (MINIMAL)

**File**: `backend/src/trading_api/main.py`

**Changes Required**:
1. Import `BarSubscriber`
2. Initialize subscriber in `lifespan` startup
3. Stop subscriber in `lifespan` shutdown

**Lines to add**: ~10 lines
**Existing functionality**: Unchanged

## Dependencies

### Add to `pyproject.toml`:
```toml
[tool.poetry.dependencies]
redis = "^5.0.0"  # Async Redis client
```

## Implementation Steps

### Step 1: Add Redis Dependency

```bash
cd backend
poetry add redis
```

### Step 2: Create Bar Generator

Create `backend/src/trading_api/services/bar_generator.py` with:
- `BarGenerator` class
- Async generation loop
- Redis publish logic
- CLI entry point for standalone execution

### Step 3: Create Bar Subscriber

Create `backend/src/trading_api/services/bar_subscriber.py` with:
- `BarSubscriber` class
- Redis pattern subscription
- Message handling and parsing
- Integration with `FastWSAdapter`

### Step 4: Update Main App

Modify `backend/src/trading_api/main.py`:
- Add subscriber to lifespan
- Configure Redis URL (from environment variable)

### Step 5: Update Configuration

Add to environment variables:
```bash
REDIS_URL=redis://localhost:6379
BAR_GENERATOR_INTERVAL=2.0
BAR_GENERATOR_SYMBOLS=AAPL,GOOGL,MSFT
BAR_GENERATOR_RESOLUTIONS=1,5,D
```

### Step 6: Update Documentation

- Update `backend/README.md` with Redis setup
- Update `ARCHITECTURE.md` with bar broadcasting flow
- Add examples to `backend/docs/websockets.md`

## Running the System

### Development Setup

**Terminal 1: Start Redis**
```bash
docker run -d -p 6379:6379 redis:alpine
# OR if Redis is already installed
redis-server
```

**Terminal 2: Start Main API**
```bash
cd backend
make dev
```

**Terminal 3: Start Bar Generator**
```bash
cd backend
poetry run python -m trading_api.services.bar_generator
```

### Production Setup

**Docker Compose Example**:
```yaml
services:
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
  
  api:
    build: ./backend
    command: uvicorn trading_api.main:app --host 0.0.0.0
    depends_on:
      - redis
    environment:
      - REDIS_URL=redis://redis:6379
  
  bar-generator:
    build: ./backend
    command: python -m trading_api.services.bar_generator
    depends_on:
      - redis
    environment:
      - REDIS_URL=redis://redis:6379
      - BAR_GENERATOR_INTERVAL=2.0
```

## Testing

### Unit Tests

**Test Bar Generator** (`tests/test_bar_generator.py`):
- Mock Redis client
- Verify message format
- Test error handling

**Test Bar Subscriber** (`tests/test_bar_subscriber.py`):
- Mock Redis messages
- Verify `wsApp.publish()` is called
- Test subscriber lifecycle

### Integration Tests

**Test End-to-End Flow** (`tests/test_bar_broadcasting.py`):
1. Start Redis container
2. Start generator
3. Connect WebSocket client
4. Subscribe to topic
5. Verify bar updates are received
6. Cleanup

### Manual Testing

```python
# Test Redis publishing
import asyncio
import redis.asyncio as redis

async def test_publish():
    r = await redis.from_url("redis://localhost:6379")
    await r.publish("bars:AAPL:1", '{"symbol":"AAPL","bar":{...}}')
    await r.close()

asyncio.run(test_publish())
```

## Monitoring

### Redis Monitoring

```bash
# Monitor all Redis pub/sub activity
redis-cli MONITOR

# Check active channels
redis-cli PUBSUB CHANNELS bars:*

# Check number of subscribers per channel
redis-cli PUBSUB NUMSUB bars:AAPL:1
```

### Application Metrics

Add metrics to track:
- Messages published per second
- Messages received per second
- WebSocket broadcast count
- Active subscriber count per topic
- Redis connection health

### Logging

**Generator Logs**:
```
INFO: Bar generator started for symbols: ['AAPL', 'GOOGL', 'MSFT']
DEBUG: Published to bars:AAPL:1
DEBUG: Published to bars:GOOGL:1
```

**Subscriber Logs**:
```
INFO: Bar subscriber started for pattern: bars:*
DEBUG: Broadcasted bar for bars:AAPL:1
```

## Scaling Strategies

### Horizontal Scaling

1. **Multiple Generators**: Run separate generators for different symbol sets
   ```bash
   # Generator 1: US stocks
   BAR_GENERATOR_SYMBOLS=AAPL,GOOGL,MSFT python -m trading_api.services.bar_generator
   
   # Generator 2: Crypto
   BAR_GENERATOR_SYMBOLS=BTC,ETH,SOL python -m trading_api.services.bar_generator
   ```

2. **Multiple API Instances**: Redis pub/sub works with multiple subscribers
   ```bash
   # All API instances receive the same messages
   # Each broadcasts to its own WebSocket clients
   ```

### Performance Optimization

1. **Batch Publishing**: Publish multiple bars in single Redis message
2. **Connection Pooling**: Reuse Redis connections
3. **Message Compression**: Compress bar data for large volumes
4. **Selective Broadcasting**: Only broadcast to topics with active subscribers

## Migration Path

### Phase 1: Development (Current)
- No Redis, simple in-process broadcasting
- Good for testing and development

### Phase 2: Redis Integration (This Document)
- Add Redis pub/sub
- Separate generator process
- Production-ready architecture

### Phase 3: Real Data Integration (Future)
- Replace mock generator with real market data feed
- Keep Redis pub/sub infrastructure
- Minimal code changes needed

## Alternatives Considered

### 1. In-Process Background Task
- **Pros**: Simple, no dependencies
- **Cons**: CPU overhead on main app, not scalable

### 2. RabbitMQ/Kafka
- **Pros**: More features (queuing, persistence)
- **Cons**: Overkill for pub/sub, more complex setup

### 3. Python Multiprocessing
- **Pros**: No external dependencies
- **Cons**: Doesn't work across machines, harder to monitor

### Decision: Redis Pub/Sub
- Perfect balance of simplicity and scalability
- Widely used in production systems
- Easy to set up and monitor
- Fast enough for real-time data

## Future Enhancements

1. **Real Market Data**: Replace mock generator with actual market data feed
2. **Historical Replay**: Replay historical bars for backtesting
3. **Data Persistence**: Store bars in TimescaleDB/InfluxDB
4. **Multi-Asset Support**: Add support for options, futures, forex
5. **Smart Throttling**: Adjust broadcast rate based on client connections
6. **Health Checks**: Add health check endpoints for generator process

## References

- [Redis Pub/Sub Documentation](https://redis.io/docs/manual/pubsub/)
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)
- [Python Redis Async Client](https://redis.readthedocs.io/en/stable/examples/asyncio_examples.html)
- [WebSocket Real-Time Patterns](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)
