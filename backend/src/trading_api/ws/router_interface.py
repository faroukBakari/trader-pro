from typing import Protocol

from pydantic import BaseModel

from external_packages.fastws import OperationRouter
from trading_api.plugins.fastws_adapter import FastWSAdapter


class WsRouterProto(Protocol):
    route: str

    def topic_builder(self, params: BaseModel) -> str:
        ...

    def build_specs(self, wsUrl: str, wsApp: FastWSAdapter) -> dict:
        ...


class WsRouterInterface(OperationRouter, WsRouterProto):
    def topic_builder(self, params: BaseModel) -> str:
        return ":".join(
            [self.route] + [str(getattr(params, attr)) for attr in sorted(vars(params))]
        )

    def build_specs(self, wsUrl: str, wsApp: FastWSAdapter) -> dict:
        return {
            "endpoint": wsUrl,
            "docs": wsApp.asyncapi_docs_url,
            "spec": wsApp.asyncapi_url,
            "operations": [
                "quotes.subscribe",
                "quotes.unsubscribe",
                "quotes.update",
            ],
            "note": "WebSocket endpoints use AsyncAPI spec, not OpenAPI/Swagger",
        }
