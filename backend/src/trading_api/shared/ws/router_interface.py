import asyncio
import json
from typing import Any, Callable, Protocol

from pydantic import BaseModel

from external_packages.fastws import FastWS, OperationRouter
from trading_api.models.common import SubscriptionUpdate


def buildTopicParams(obj: Any) -> str:
    """
    JSON stringify with sorted object keys for consistent serialization.
    Handles nested objects and arrays recursively.
    """

    def sort_recursive(item: Any) -> Any:
        if isinstance(item, dict):
            return {k: sort_recursive(v) for k, v in sorted(item.items())}
        elif isinstance(item, list):
            return [sort_recursive(element) for element in item]
        elif item is None:
            return ""
        else:
            return item

    sorted_obj = sort_recursive(obj)
    return json.dumps(sorted_obj, separators=(",", ":"))


class WsRouteService(Protocol):
    async def create_topic(self, topic: str, topic_update: Callable) -> None:
        ...

    def remove_topic(self, topic: str) -> None:
        ...


# TODO: add clear subscriptions method to use on FastWSAdapter when client disconnects
class WsRouteInterface(OperationRouter):
    def __init__(self, route: str, *args: Any, **kwargs: Any):
        super().__init__(prefix=f"{route}.", *args, **kwargs)
        self.route: str = route
        self.updates_queue = asyncio.Queue[SubscriptionUpdate[BaseModel]](maxsize=1000)

    def topic_builder(self, params: BaseModel) -> str:
        return f"{self.route}:{buildTopicParams(params.model_dump())}"

    def build_specs(self, wsUrl: str, wsApp: FastWS) -> dict:
        return {
            "endpoint": wsUrl,
            "docs": wsApp.asyncapi_docs_url,
            "spec": wsApp.asyncapi_url,
            "operations": [
                f"{self.route}.subscribe",
                f"{self.route}.unsubscribe",
                f"{self.route}.update",
            ],
            "note": "WebSocket endpoints use AsyncAPI spec, not OpenAPI/Swagger",
        }
