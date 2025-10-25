import asyncio
import json
from typing import Any, Callable, Generic, Protocol, TypeVar

from pydantic import BaseModel

from external_packages.fastws import OperationRouter
from trading_api.plugins.fastws_adapter import FastWSAdapter


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


class WsRouteService:
    def __init__(self) -> None:
        super().__init__()
        self._topic_queues: dict[str, asyncio.Queue] = {}

    def get_topic_queue(self, topic: str) -> asyncio.Queue:
        return self._topic_queues.setdefault(topic, asyncio.Queue())

    def del_topic(self, topic: str) -> None:
        self._topic_queues.pop(topic, None)


class WsRouterProto(Protocol):
    route: str

    def topic_builder(self, params: BaseModel) -> str:
        ...

    def build_specs(self, wsUrl: str, wsApp: FastWSAdapter) -> dict:
        ...


class WsRouterInterface(OperationRouter, WsRouterProto):
    def topic_builder(self, params: BaseModel) -> str:
        return f"{self.route}:{buildTopicParams(params.model_dump())}"

    def build_specs(self, wsUrl: str, wsApp: FastWSAdapter) -> dict:
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


_TData = TypeVar("_TData", bound=BaseModel)


class topicTracker(Generic[_TData]):
    def __init__(
        self,
        topic: str,
        service: WsRouteService,
        send_update: Callable[[_TData], None],
    ) -> None:
        self.topic = topic
        self.service = service
        self.count = 1
        self.send_update = send_update
        self._task = asyncio.create_task(self.poll())

    async def poll(self) -> None:
        while self.count > 0:
            data = await self.service.get_topic_queue(self.topic).get()
            self.send_update(data)

    def inc(self) -> None:
        self.count += 1

    def dec(self) -> None:
        self.count -= 1
        if self.count <= 0:
            self.service.del_topic(self.topic)

    def __del__(self) -> None:
        """Destructor to clean up topic when tracker is garbage collected"""
        if self.count > 0:
            self.service.del_topic(self.topic)
