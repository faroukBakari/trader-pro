"""
Broker service - BFF layer for broker operations.

This service acts as a Backend-For-Frontend (BFF) layer that:
- Translates WebSocket topics to provider subscriptions
- Delegates all business logic to BrokerCapability provider
- Handles error classification (recoverable vs non-recoverable)

Pattern mirrors DatafeedService exactly.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from trading_api.capabilities.broker import BrokerCapability
from trading_api.models.broker import (
    AccountMetainfo,
    Brackets,
    BrokerConnectionStatus,
    Execution,
    LeverageInfo,
    LeverageInfoParams,
    LeveragePreviewResult,
    LeverageSetParams,
    LeverageSetResult,
    OrderPreviewResult,
    PlacedOrder,
    PlaceOrderResult,
    Position,
    PreOrder,
)
from trading_api.models.common import DatastoreCapabilitySpec, ProviderCapabilitySpec
from trading_api.models.exceptions import ServiceException, TradingApiException
from trading_api.modules.broker.order_manager import OrderManager
from trading_api.shared.ws.ws_router import (
    ProviderUpdateCallback,
    TopicErrorCallback,
    WsRouteService,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Recoverable Error Configuration
# ============================================================================
# Default behavior: ALL errors are non-recoverable (connection closes)
# Only exceptions in this set will keep the connection open and broadcast
# a SubscriptionError message instead.

_RECOVERABLE_ERROR_CODES: frozenset[str] = frozenset(
    {
        "PROVIDER_BROKER_TIMEOUT",
        "PROVIDER_BROKER_CONNECTION_LOST",
        "PROVIDER_BROKER_RATE_LIMIT",
    }
)

_DEFAULT_RETRY_AFTER_MS = 5000


class BrokerService(WsRouteService):
    """
    BFF layer for broker operations.

    Delegates all business logic to BrokerCapability provider.
    Handles WebSocket topic routing and error classification.

    Pattern matches DatafeedService exactly:
    - Capability declaration via capabilities() classmethod
    - Cached provider access via broker_provider property
    - Topic → subscription tracking via _topic_to_subscription_id
    - Error wrapping with recoverable/retry_after logic
    """

    @classmethod
    def provider_capabilities(cls) -> list[ProviderCapabilitySpec]:
        """Return required provider capabilities for broker service.

        Requires broker capability from provider (e.g., FakeBrokerProvider).

        Returns:
            List with broker capability requirement
        """
        return [ProviderCapabilitySpec(name="broker")]

    @classmethod
    def datastore_capabilities(cls) -> list[DatastoreCapabilitySpec]:
        """No specific capabilities — works with any datastore."""
        return []

    @property
    def broker_provider(self) -> BrokerCapability:
        """Cached O(1) lookup - type-safe provider access.

        Returns:
            BrokerCapability provider instance

        Raises:
            RuntimeError: If broker provider not available
        """
        provider = self.get_capability_provider("broker")  # , "fakebroker"
        # Type assertion: provider must implement BrokerCapability (validated at init)
        assert isinstance(provider, BrokerCapability)
        return provider

    def __init__(
        self,
        module_dir: Path,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize broker service.

        Args:
            module_dir: Path to the module directory
            providers: Provider instances for capabilities
            **kwargs: Additional arguments (includes datastore from ServiceInterface)
        """
        super().__init__(module_dir, *args, **kwargs)

        # Track provider subscription IDs for each topic (for cleanup)
        self._topic_to_subscription_id: dict[str, str] = {}

        self._order_manager = OrderManager(datastore=self.get_featured_datastore())

    # ================================ GETTERS (delegate to provider) =========

    async def get_orders(self, user_id: str) -> list[PlacedOrder]:
        """Get all orders for a user (bracket-enriched).

        Syncs provider state into OrderManager and returns enriched orders
        where parent orders carry bracket fields derived from their children.

        Args:
            user_id: User ID for scoping (unused for now)
        """
        raw_orders = await self.broker_provider.get_orders()
        await self._order_manager.sync(raw_orders)
        return await self._order_manager.get_all()

    async def get_positions(self, user_id: str) -> list[Position]:
        """Get all positions for a user.

        Args:
            user_id: User ID for scoping (unused for now)
        """
        return await self.broker_provider.get_positions()

    async def get_executions(self, symbol: str, user_id: str) -> list[Execution]:
        """Get execution history for a symbol.

        Args:
            symbol: Symbol to get executions for
            user_id: User ID for scoping (unused for now)
        """
        return await self.broker_provider.get_executions(symbol)

    async def get_all_executions(self, user_id: str) -> list[Execution]:
        """Get all execution history (across all symbols).

        Args:
            user_id: User ID for scoping (unused for now)
        """
        return await self.broker_provider.get_all_executions()

    async def get_account_info(self, user_id: str) -> AccountMetainfo:
        """Get account metadata for a user.

        Args:
            user_id: User ID for scoping (unused for now)
        """
        return await self.broker_provider.get_account_info()

    async def preview_order(self, order: PreOrder, user_id: str) -> OrderPreviewResult:
        """Preview order costs and requirements.

        Args:
            order: Order to preview
            user_id: User ID for scoping (unused for now)
        """
        return await self.broker_provider.preview_order(order)

    async def preview_leverage(
        self, params: LeverageSetParams, user_id: str
    ) -> LeveragePreviewResult:
        """Preview leverage changes.

        Args:
            params: Leverage parameters
            user_id: User ID for scoping (unused for now)
        """
        return await self.broker_provider.preview_leverage(params)

    async def leverage_info(
        self, params: LeverageInfoParams, user_id: str
    ) -> LeverageInfo:
        """Get leverage information for symbol.

        Args:
            params: Leverage info parameters
            user_id: User ID for scoping (unused for now)
        """
        return await self.broker_provider.get_leverage_info(params)

    # ================================ SETTERS (delegate to provider) =========

    async def place_order(
        self, order: PreOrder, user_id: str, confirm_id: str | None = None
    ) -> PlaceOrderResult:
        """Place a new order.

        Args:
            order: Order to place
            user_id: User ID for scoping (unused for now)
            confirm_id: Optional confirmation ID from preview_order (for audit trail)
        """
        return await self.broker_provider.place_order(order, confirm_id=confirm_id)

    async def modify_order(self, order_id: str, order: PreOrder, user_id: str) -> None:
        """Modify an existing order.

        Diffs bracket fields against current state to avoid re-submitting
        unchanged bracket legs to TWS (which rejects redundant child
        modifications while the parent is mid-modification).

        Args:
            order_id: ID of order to modify
            order: Updated order details
            user_id: User ID for scoping (unused for now)
        """
        order = await self._strip_unchanged_brackets(order_id, order)
        await self.broker_provider.modify_order(order_id, order)

    async def _strip_unchanged_brackets(
        self, order_id: str, order: PreOrder
    ) -> PreOrder:
        """Remove bracket fields from PreOrder if they match current state.

        Prevents redundant child order modifications that TWS rejects
        when the parent order is being modified simultaneously.
        """
        current = await self._order_manager.get(order_id)
        if current is None:
            return order  # Unknown order — pass through as-is

        updates: dict[str, None] = {}
        if order.takeProfit is not None and order.takeProfit == current.takeProfit:
            updates["takeProfit"] = None
        if order.stopLoss is not None and order.stopLoss == current.stopLoss:
            updates["stopLoss"] = None
        if (
            order.trailingStopPips is not None
            and order.trailingStopPips == current.trailingStopPips
        ):
            updates["trailingStopPips"] = None

        if not updates:
            return order  # All brackets changed (or none present)

        return order.model_copy(update=updates)

    async def cancel_order(self, order_id: str, user_id: str) -> None:
        """Cancel an order.

        Args:
            order_id: ID of order to cancel
            user_id: User ID for scoping (unused for now)
        """
        await self.broker_provider.cancel_order(order_id)

    async def close_position(
        self, position_id: str, user_id: str, amount: float | None = None
    ) -> None:
        """Close position (full or partial).

        Args:
            position_id: ID of position to close
            user_id: User ID for scoping (unused for now)
            amount: Amount to close (None for full close)
        """
        await self.broker_provider.close_position(position_id, amount)

    async def edit_position_brackets(
        self,
        position_id: str,
        brackets: Brackets,
        user_id: str,
        custom_fields: dict[str, Any] | None = None,
    ) -> None:
        """Update position brackets.

        Args:
            position_id: ID of position to update
            brackets: New bracket values
            user_id: User ID for scoping (unused for now)
            custom_fields: Optional custom fields (ignored)
        """
        # custom_fields ignored for now (provider doesn't use it)
        await self.broker_provider.edit_position_brackets(position_id, brackets)

    async def set_leverage(
        self, params: LeverageSetParams, user_id: str
    ) -> LeverageSetResult:
        """Set leverage for symbol.

        Args:
            params: Leverage parameters
            user_id: User ID for scoping (unused for now)
        """
        return await self.broker_provider.set_leverage(params)

    # ========================== WEBSOCKET STREAMING ==========================#

    async def create_topic(
        self,
        topic: str,
        topic_update: ProviderUpdateCallback,
        topic_error: TopicErrorCallback,
        user_id: str,
    ) -> None:
        """Parse topic and create appropriate provider subscription.

        Topic formats:
            - orders:{"accountId":"DEMO-ACCOUNT"}
            - positions:{"accountId":"DEMO-ACCOUNT"}
            - executions:{"accountId":"DEMO-ACCOUNT","symbol":"AAPL"}
            - equity:{"accountId":"DEMO-ACCOUNT"}
            - broker-connection:{"accountId":"DEMO-ACCOUNT"}

        Args:
            topic: Topic string in format "topic_type:{json_params}"
            topic_update: Callback to broadcast data updates to subscribers
            topic_error: Callback to broadcast errors to subscribers.
            user_id: Authenticated user ID for user-scoped data access (unused for now).

        Raises:
            ServiceException: If topic format is invalid or unknown
        """
        if topic in self._topic_to_subscription_id:
            raise ServiceException(
                code="SERVICE_BROKER_TOPIC_EXISTS",
                message=f"Topic already exists: {topic}",
                module="broker",
            )

        if ":" not in topic:
            raise ServiceException(
                code="SERVICE_BROKER_INVALID_TOPIC_FORMAT",
                message=f"Invalid topic format: {topic}",
                module="broker",
            )

        topic_type, params_json = topic.split(":", 1)

        # Wrap error callback to compute recoverable/retry at service level
        async def on_provider_error(exc: TradingApiException) -> None:
            """Handle provider errors - determine recoverable status and forward."""
            recoverable = self._is_error_recoverable(exc)
            if not recoverable:
                logger.error(f"Non-recoverable error on topic {topic}: {exc!r}")
                self._topic_to_subscription_id.pop(topic, None)

            retry_after_ms = _DEFAULT_RETRY_AFTER_MS if recoverable else None
            await topic_error(exc, recoverable, retry_after_ms)

        logger.info(f"Creating topic: {topic}")

        if topic_type == "orders":

            async def _order_update_callback(order: PlacedOrder) -> None:
                """Route order updates through OrderManager for bracket enrichment."""
                affected = await self._order_manager.upsert(order)
                for enriched_order in affected:
                    await topic_update(enriched_order)

            subscription_id = await self.broker_provider.subscribe_orders(
                callback=_order_update_callback,
                on_error=on_provider_error,
            )
            self._topic_to_subscription_id[topic] = subscription_id

        elif topic_type == "positions":
            subscription_id = await self.broker_provider.subscribe_positions(
                callback=topic_update,
                on_error=on_provider_error,
            )
            self._topic_to_subscription_id[topic] = subscription_id

        elif topic_type == "executions":
            params_dict = json.loads(params_json)
            symbol = params_dict.get("symbol", "")  # Empty = all symbols

            subscription_id = await self.broker_provider.subscribe_executions(
                symbol=symbol,
                callback=topic_update,
                on_error=on_provider_error,
            )
            self._topic_to_subscription_id[topic] = subscription_id

        elif topic_type == "equity":
            subscription_id = await self.broker_provider.subscribe_equity(
                callback=topic_update,
                on_error=on_provider_error,
            )
            self._topic_to_subscription_id[topic] = subscription_id

        elif topic_type == "broker-connection":
            # Special case: broker-connection sends immediate status
            # No provider subscription needed - just send connected status
            import asyncio

            status = BrokerConnectionStatus(
                status=1,  # 1 = Connected
                message="Connected to broker",
                disconnectType=None,
                timestamp=int(time.time() * 1000),
            )
            asyncio.create_task(topic_update(status))
            # Use placeholder subscription ID for broker-connection
            self._topic_to_subscription_id[topic] = "broker-connection-placeholder"

        else:
            raise ServiceException(
                code="SERVICE_BROKER_UNKNOWN_TOPIC_TYPE",
                message=f"Unknown topic type: {topic_type}",
                module="broker",
            )

    def _is_error_recoverable(self, exc: TradingApiException) -> bool:
        """Determine if error is transient and streaming should continue.

        Default: ALL errors are non-recoverable (strict approach).
        Only errors in _RECOVERABLE_ERROR_CODES will keep the connection open.

        Args:
            exc: The exception to check

        Returns:
            True if error is recoverable, False otherwise
        """
        return exc.code in _RECOVERABLE_ERROR_CODES

    def remove_topic(self, topic: str) -> None:
        """Remove topic and cleanup provider subscription.

        Args:
            topic: Topic to remove
        """
        logger.info(f"Removing topic: {topic}")

        subscription_id = self._topic_to_subscription_id.pop(topic, None)
        if subscription_id is not None:
            # Don't unsubscribe placeholder IDs
            if subscription_id != "broker-connection-placeholder":
                self.broker_provider.unsubscribe(subscription_id)
        else:
            logger.warning(f"No subscription_id found for topic: {topic}")
