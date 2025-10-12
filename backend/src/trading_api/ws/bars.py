"""
WebSocket adapter for real-time bar (OHLC) data subscriptions
"""

from trading_api.models.market.bars import Bar
from trading_api.plugins.fastws_adapter import FastWSAdapter, TopicBuilder

# Topic builder for bars: bars:SYMBOL:RESOLUTION
bars_topic_builder: TopicBuilder = lambda symbol, params: (
    f"bars:{symbol}:{params.get('resolution', '1')}"
)

# Create bars adapter instance
bars_adapter = FastWSAdapter[Bar](
    route_prefix="bars",
    data_model=Bar,
    endpoint_path="/api/v1/ws/bars",
    topic_builder=bars_topic_builder,
    title="Bars WebSocket API",
    description=(
        "Real-time OHLC bar data streaming. "
        "Subscribe to specific symbol and resolution combinations."
    ),
    version="1.0.0",
    asyncapi_url="/api/v1/ws/bars/asyncapi.json",
    asyncapi_docs_url="/api/v1/ws/bars/asyncapi",
    heartbeat_interval=30.0,
    max_connection_lifespan=3600.0,
)
