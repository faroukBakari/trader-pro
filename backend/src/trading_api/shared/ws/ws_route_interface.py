import asyncio
import json
import logging
from typing import Any, Callable

from pydantic import BaseModel

from external_packages.fastws import FastWS, OperationRouter
from trading_api.models.common import SubscriptionUpdate
from trading_api.shared.service_interface import ServiceInterface
from trading_api.shared.ws.module_router_generator import generate_ws_routers

# Module logger for app_factory
logger = logging.getLogger(__name__)


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


class WsRouteService(ServiceInterface):
    async def create_topic(self, topic: str, topic_update: Callable) -> None:
        ...

    def remove_topic(self, topic: str) -> None:
        ...


# TODO: add clear subscriptions method to use on FastWSAdapter when client disconnects
class WsRouteInterface(OperationRouter):
    def __init__(self, route: str, *args: Any, **kwargs: Any):
        # Validate route parameter
        if not route or not isinstance(route, str):
            raise ValueError(
                f"Router 'route' must be a non-empty string. Got: {route!r}"
            )

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


class WsRouterInterface(list[WsRouteInterface]):
    def __init__(self, *args: Any, service: ServiceInterface, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._service = service

    def generate_routers(self, ws_file: str) -> None:
        """Generate WebSocket routers from the ws file path.

        Args:
            ws_file: Path to the WebSocket router definition file
                     (typically __file__ from the calling module)
                     Expected pattern: modules/{module_name}/ws/{version}/__init__.py

        Raises:
            RuntimeError: If router generation fails
            ValueError: If ws_file path doesn't match expected pattern
        """
        try:
            generated = generate_ws_routers(ws_file)
            if generated:
                # Extract module info for logging (best effort)
                from pathlib import Path

                ws_path = Path(ws_file)
                parts = ws_path.parts
                try:
                    modules_idx = parts.index("modules")
                    module_name = parts[modules_idx + 1]
                    version = parts[modules_idx + 3]
                    logger.info(
                        f"Generated WS routers for module '{module_name}' version '{version}'"
                    )
                except (ValueError, IndexError):
                    logger.info(f"Generated WS routers from {ws_file}")
        except RuntimeError as e:
            # Fail loudly with context
            logger.error(f"WebSocket router generation failed for '{ws_file}'!")
            logger.error(str(e))
            raise
