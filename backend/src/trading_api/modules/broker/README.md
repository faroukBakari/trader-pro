# Broker Module

**Status**: ✅ Production Ready  
**Last Updated**: January 11, 2026  
**Related Files**: `backend/src/trading_api/modules/broker/`

---

## Overview

BFF (Backend-For-Frontend) module for trading operations. Provides REST API and WebSocket streaming for orders, positions, executions, account information, and leverage management.

**Key Responsibilities**:

- Translate frontend API requests to provider subscriptions
- Route WebSocket topics to appropriate `BrokerCapability` provider methods
- Handle error classification (recoverable vs non-recoverable)
- Delegate all business logic to the broker provider
- Pass enriched order data (with bracket relationships) to frontend for TradingView UI display

---

## Architecture

### Module Structure

```
modules/broker/
├── __init__.py           # BrokerModule class
├── service.py            # BrokerService (BFF layer, provider delegation)
├── api/v1.py             # REST endpoints (orders, positions, leverage)
├── ws/v1/__init__.py     # WebSocket routers (5 topics)
├── specs_generated/      # OpenAPI/AsyncAPI specs (auto-generated)
├── client_generated/     # Python client (auto-generated)
└── tests/                # Module tests
```

### Service Layer Pattern

The `BrokerService` follows the **WsRouteService** pattern:

```python
class BrokerService(WsRouteService):
    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        return [CapabilitySpec(name="broker")]

    @property
    def broker_provider(self) -> BrokerCapability:
        # Cached O(1) lookup - type-safe provider access
        provider = self.get_capability_provider("broker")
        return provider
```

**[DECISION]**: BrokerService is a thin BFF layer - all business logic lives in the `BrokerCapability` provider (e.g., `FakeBrokerProvider`, `TWSBrokerProvider`).

### Provider Delegation

```
┌─────────────────┐    ┌──────────────────┐    ┌───────────────────┐
│  BrokerApi      │───▶│  BrokerService   │───▶│  BrokerCapability │
│  (REST)         │    │  (BFF Layer)     │    │  (Provider)       │
└─────────────────┘    └──────────────────┘    └───────────────────┘
                              │
┌─────────────────┐           │
│  BrokerWsRouters│───────────┘
│  (WebSocket)    │
└─────────────────┘
```

---

## API Endpoints

All endpoints require authentication via JWT in HttpOnly cookie.

| Method | Path                                     | Operation ID           | Description                                    |
| ------ | ---------------------------------------- | ---------------------- | ---------------------------------------------- |
| POST   | `/api/broker/v1/orders`                  | `placeOrder`           | Place a new order (accepts `confirmId`¹)       |
| POST   | `/api/broker/v1/orders/preview`          | `previewOrder`         | Preview order costs/margin (returns confirmId) |
| PUT    | `/api/broker/v1/orders/{id}`             | `modifyOrder`          | Modify existing order                          |
| DELETE | `/api/broker/v1/orders/{id}`             | `cancelOrder`          | Cancel an order                                |
| GET    | `/api/broker/v1/orders`                  | `getOrders`            | Get all user orders                            |
| GET    | `/api/broker/v1/positions`               | `getPositions`         | Get all open positions                         |
| GET    | `/api/broker/v1/executions/{symbol}`     | `getExecutions`        | Get executions for symbol                      |
| DELETE | `/api/broker/v1/positions/{id}`          | `closePosition`        | Close position (full/partial)                  |
| PUT    | `/api/broker/v1/positions/{id}/brackets` | `editPositionBrackets` | Update SL/TP brackets                          |
| GET    | `/api/broker/v1/account`                 | `getAccountInfo`       | Get account metadata                           |
| GET    | `/api/broker/v1/leverage/info`           | `leverageInfo`         | Get leverage constraints                       |
| PUT    | `/api/broker/v1/leverage/set`            | `setLeverage`          | Set leverage for symbol                        |
| POST   | `/api/broker/v1/leverage/preview`        | `previewLeverage`      | Preview leverage changes                       |

¹ **Preview-to-Place Flow:** The `confirmId` returned by `previewOrder` can be passed as a query parameter to `placeOrder` for audit trail correlation. This links the preview and execution for logging/compliance purposes.

---

## WebSocket Topics

Real-time streaming via WebSocket with topic-based routing.

| Topic               | Request Model                         | Response Model           | Description                    |
| ------------------- | ------------------------------------- | ------------------------ | ------------------------------ |
| `orders`            | `OrderSubscriptionRequest`            | `PlacedOrder`            | Order status changes           |
| `positions`         | `PositionSubscriptionRequest`         | `Position`               | Position updates               |
| `executions`        | `ExecutionSubscriptionRequest`        | `Execution`              | Trade execution notifications  |
| `equity`            | `EquitySubscriptionRequest`           | `EquityData`             | Account balance/equity changes |
| `broker-connection` | `BrokerConnectionSubscriptionRequest` | `BrokerConnectionStatus` | Broker connection status       |

### Topic Format

Topics use the format `{topic_type}:{json_params}`:

```
orders:{"accountId":"DEMO-ACCOUNT"}
positions:{"accountId":"DEMO-ACCOUNT"}
executions:{"accountId":"DEMO-ACCOUNT","symbol":"AAPL"}
equity:{"accountId":"DEMO-ACCOUNT"}
broker-connection:{"accountId":"DEMO-ACCOUNT"}
```

### Topic Lifecycle

```python
# In BrokerService
async def create_topic(self, topic: str, topic_update: Callback, topic_error: Callback, user_id: str):
    """Parse topic, create provider subscription, track subscription ID."""
    topic_type, params_json = topic.split(":", 1)

    if topic_type == "orders":
        # For TWS provider: delegates to TWSClient.reqOrdersStream() → OrderTracker
        subscription_id = await self.broker_provider.subscribe_orders(
            callback=topic_update,
            on_error=on_provider_error,
        )
        self._topic_to_subscription_id[topic] = subscription_id

def remove_topic(self, topic: str):
    """Cleanup provider subscription on topic removal."""
    subscription_id = self._topic_to_subscription_id.pop(topic, None)
    if subscription_id:
        self.broker_provider.unsubscribe(subscription_id)
```

---

## Error Handling

### Recoverable vs Non-Recoverable Errors

The service classifies errors to determine WebSocket connection behavior:

```python
_RECOVERABLE_ERROR_CODES: frozenset[str] = frozenset({
    "PROVIDER_BROKER_TIMEOUT",
    "PROVIDER_BROKER_CONNECTION_LOST",
    "PROVIDER_BROKER_RATE_LIMIT",
})

def _is_error_recoverable(self, exc: TradingApiException) -> bool:
    """Default: ALL errors are non-recoverable (strict approach)."""
    return exc.code in _RECOVERABLE_ERROR_CODES
```

**[DECISION]**: Strict error handling - only explicitly whitelisted errors keep connections open. This prevents silent failures.

### Error Flow

1. Provider raises `ProviderException` or `TradingApiException`
2. `BrokerService.on_provider_error()` wraps with recoverable/retry_after_ms
3. For recoverable: `SubscriptionError` sent, connection stays open
4. For non-recoverable: `SubscriptionError` sent, connection closes

---

## Testing

### Running Tests

```bash
# Module tests only
cd backend && poetry run pytest src/trading_api/modules/broker/tests/ -v

# With coverage
cd backend && poetry run pytest src/trading_api/modules/broker/tests/ --cov=src/trading_api/modules/broker
```

### Mocking the Broker Provider

```python
@pytest.fixture
def mock_broker_provider():
    """Mock BrokerCapability for unit tests."""
    provider = AsyncMock(spec=BrokerCapability)
    provider.get_orders.return_value = [mock_order]
    provider.place_order.return_value = PlaceOrderResult(orderId="123")
    return provider
```

### WebSocket Testing

```python
async def test_orders_subscription(broker_ws_client):
    """Test orders topic subscription."""
    async with broker_ws_client.websocket_connect("/ws/broker/v1/orders") as ws:
        await ws.send_json({"action": "subscribe", "topic": "orders:{}"})
        response = await ws.receive_json()
        assert response["type"] == "subscribed"
```

---

## Models

Key Pydantic models used by this module (defined in `trading_api/models/broker/`):

| Model                    | Purpose                          |
| ------------------------ | -------------------------------- |
| `PreOrder`               | Order creation request           |
| `PlacedOrder`            | Order with status and timestamps |
| `PlaceOrderResult`       | Result of placing an order       |
| `Position`               | Open position with P&L           |
| `Execution`              | Trade execution record           |
| `Brackets`               | Stop-loss and take-profit levels |
| `AccountMetainfo`        | Account metadata (ID, name)      |
| `LeverageInfo`           | Leverage constraints for symbol  |
| `BrokerConnectionStatus` | Broker connection state          |
| `EquityData`             | Account balance and equity       |

---

## Related Documentation

- **[Provider System](../../../../docs/PROVIDER-SYSTEM.md)** - BrokerCapability interface
- **[Backend WebSockets](../../../../docs/BACKEND_WEBSOCKETS.md)** - WsRouteService pattern
- **[Broker Architecture](../../../../../docs/BROKER-ARCHITECTURE.md)** - Fakebroker execution simulator
- **[Error Management](../../../../docs/ERROR-MANAGEMENT.md)** - Exception hierarchy
- **[Modular Backend Architecture](../../../../docs/MODULAR_BACKEND_ARCHITECTURE.md)** - Module lifecycle

---

**Last Updated**: January 1, 2026
