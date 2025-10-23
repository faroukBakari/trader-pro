import json
from typing import Any, Protocol

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
