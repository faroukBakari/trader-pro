"""
Tests for WebSocket bar subscriptions
"""

from typing import Callable

from trading_api.models.market.bars import Bar
from trading_api.plugins.fastws_adapter import FastWSAdapter

# Type alias for topic builder
TopicBuilder = Callable[[str, dict], str]


def bars_topic_builder(symbol: str, params: dict) -> str:
    """Topic builder for bars: bars:SYMBOL:RESOLUTION"""
    resolution = params.get("resolution", "1")
    return f"bars:{symbol}:{resolution}"


class TestFastWSAdapterInitialization:
    """Test FastWSAdapter initialization and configuration"""

    def test_adapter_creation_with_required_params(self):
        """Test creating adapter with all required parameters"""
        adapter = FastWSAdapter[Bar](
            route_prefix="bars",
            data_model=Bar,
            endpoint_path="/api/v1/ws/bars",
            topic_builder=bars_topic_builder,
            title="Bars WebSocket API",
            description="Real-time bar data",
        )

        assert adapter.route_prefix == "bars"
        assert adapter.data_model == Bar
        assert adapter.endpoint_path == "/api/v1/ws/bars"
        assert adapter.topic_builder == bars_topic_builder

    def test_adapter_service_initialized(self):
        """Test that FastWS service is initialized correctly"""
        adapter = FastWSAdapter[Bar](
            route_prefix="bars",
            data_model=Bar,
            endpoint_path="/api/v1/ws/bars",
            topic_builder=bars_topic_builder,
            title="Bars WebSocket API",
            description="Real-time bar data",
        )

        assert adapter.service is not None
        assert hasattr(adapter.service, "router")

    def test_adapter_router_created_with_prefix(self):
        """Test that router is created with correct prefix"""
        adapter = FastWSAdapter[Bar](
            route_prefix="bars",
            data_model=Bar,
            endpoint_path="/api/v1/ws/bars",
            topic_builder=bars_topic_builder,
            title="Bars WebSocket API",
            description="Real-time bar data",
        )

        assert adapter.router is not None
        assert adapter.router.prefix == "bars."

    def test_adapter_operations_registered(self):
        """Test that subscribe, unsubscribe, and update operations are registered"""
        adapter = FastWSAdapter[Bar](
            route_prefix="bars",
            data_model=Bar,
            endpoint_path="/api/v1/ws/bars",
            topic_builder=bars_topic_builder,
            title="Bars WebSocket API",
            description="Real-time bar data",
        )

        # Check that router has routes registered
        assert len(adapter.router.routes) == 3  # subscribe, unsubscribe, and update

        # Check operation names
        operation_names = [route.operation for route in adapter.router.routes]
        assert "subscribe" in operation_names
        assert "unsubscribe" in operation_names
        assert "update" in operation_names

    def test_adapter_with_custom_asyncapi_urls(self):
        """Test adapter with custom AsyncAPI documentation URLs"""
        adapter = FastWSAdapter[Bar](
            route_prefix="bars",
            data_model=Bar,
            endpoint_path="/api/v1/ws/bars",
            topic_builder=bars_topic_builder,
            title="Bars WebSocket API",
            description="Real-time bar data",
            asyncapi_url="/custom/asyncapi.json",
            asyncapi_docs_url="/custom/asyncapi",
        )

        assert adapter.service.asyncapi_url == "/custom/asyncapi.json"
        assert adapter.service.asyncapi_docs_url == "/custom/asyncapi"

    def test_adapter_with_custom_heartbeat(self):
        """Test adapter with custom heartbeat interval"""
        adapter = FastWSAdapter[Bar](
            route_prefix="bars",
            data_model=Bar,
            endpoint_path="/api/v1/ws/bars",
            topic_builder=bars_topic_builder,
            title="Bars WebSocket API",
            description="Real-time bar data",
            heartbeat_interval=60.0,
        )

        assert adapter.service.heartbeat_interval == 60.0

    def test_adapter_topic_builder_is_callable(self):
        """Test that topic_builder is properly assigned and callable"""
        adapter = FastWSAdapter[Bar](
            route_prefix="bars",
            data_model=Bar,
            endpoint_path="/api/v1/ws/bars",
            topic_builder=bars_topic_builder,
            title="Bars WebSocket API",
            description="Real-time bar data",
        )

        # Test topic builder functionality
        topic = adapter.topic_builder("AAPL", {"resolution": "1"})
        assert topic == "bars:AAPL:1"

        topic = adapter.topic_builder("GOOGL", {"resolution": "D"})
        assert topic == "bars:GOOGL:D"
