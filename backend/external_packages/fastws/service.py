"""Simple FastWS service used for local realtime streaming."""

from __future__ import annotations

import asyncio
import inspect
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional, Type, get_type_hints
from unittest.mock import Base

from fastapi import FastAPI, WebSocket
from pydantic import BaseModel

HandlerType = Callable[..., Awaitable[Optional[Any]]]


@dataclass
class Operation:
    """Registered operation metadata."""

    name: str
    handler: HandlerType
    reply: Optional[str]
    payload_model: BaseModel | None = None


class Client:
    """Represents an active WebSocket client connection."""

    def __init__(self, websocket: WebSocket, service: "FastWS") -> None:
        self.websocket = websocket
        self._service = service
        self.state: Dict[str, Any] = {}
        self._disconnect_callbacks: list[Callable[["Client"], Any]] = []

    async def send(self, message_type: str, payload: Any) -> None:
        """Send a JSON message to the connected client."""
        await self.websocket.send_text(
            json.dumps(
                {
                    "type": message_type,
                    "payload": payload,
                }
            )
        )

    async def close(self) -> None:
        await self.websocket.close()

    def add_disconnect_callback(self, callback: Callable[["Client"], Any]) -> None:
        self._disconnect_callbacks.append(callback)

    async def _run_disconnect_callbacks(self) -> None:
        for callback in self._disconnect_callbacks:
            result = callback(self)
            if inspect.isawaitable(result):
                await result


class FastWS:
    """Minimal FastWS-like service for message based WebSockets."""

    def __init__(self, *, heartbeat_interval: Optional[float] = None) -> None:
        self._operations: Dict[str, Operation] = {}
        self._heartbeat_interval = heartbeat_interval
        self._app: Optional[FastAPI] = None

    # Decorator -----------------------------------------------------------
    def send(
        self, name: str, *, reply: Optional[str] = None
    ) -> Callable[[HandlerType], HandlerType]:
        """Register a handler for an incoming message type."""

        def decorator(func: HandlerType) -> HandlerType:
            payload_model: BaseModel | None = None
            signature = inspect.signature(func)
            params = list(signature.parameters.values())
            type_hints = get_type_hints(func)
            if params:
                first_param = params[0]
                payload_model = type_hints.get(first_param.name)
            self._operations[name] = Operation(
                name=name,
                handler=func,
                reply=reply,
                payload_model=payload_model,
            )
            return func

        return decorator

    # Lifecycle -----------------------------------------------------------
    def setup(self, app: FastAPI) -> None:
        """Attach the FastWS service to a FastAPI application."""
        self._app = app

    async def manage(self, websocket: WebSocket) -> Client:
        await websocket.accept()
        return Client(websocket, self)

    async def serve(self, client: Client) -> None:
        websocket = client.websocket
        try:
            while True:
                if self._heartbeat_interval is not None:
                    message = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=self._heartbeat_interval,
                    )
                else:
                    message = await websocket.receive_text()
                data = json.loads(message)
                message_type = data.get("type")
                operation = self._operations.get(message_type)
                if not operation:
                    await client.send(
                        "error",
                        {
                            "message": "Unknown message type",
                            "type": message_type,
                        },
                    )
                    continue

                payload_data = data.get("payload")
                payload = payload_data
                if operation.payload_model is not None:
                    payload = operation.payload_model.model_validate(payload_data or {})
                try:
                    result = await self._call_handler(operation, client, payload)
                    if operation.reply:
                        await client.send(operation.reply, result or {})
                except Exception as exc:  # pragma: no cover - defensive
                    await client.send(
                        "error",
                        {
                            "message": str(exc),
                            "type": message_type,
                        },
                    )
        except asyncio.TimeoutError:
            await client.close()
        except RuntimeError:
            # Raised when connection closed by client; ignore
            pass
        except Exception:
            await client.close()
        finally:
            tasks = client.state.get("subscription_tasks")
            if isinstance(tasks, dict):
                for task in tasks.values():
                    task.cancel()
            await client._run_disconnect_callbacks()

    async def _call_handler(
        self,
        operation: Operation,
        client: Client,
        payload: Any,
    ) -> Optional[Any]:
        params = inspect.signature(operation.handler).parameters
        if len(params) == 0:
            return await operation.handler()  # type: ignore[misc]
        if len(params) == 1:
            return await operation.handler(payload)  # type: ignore[misc]
        return await operation.handler(payload, client)  # type: ignore[misc]

    # Documentation -------------------------------------------------------
    def generate_asyncapi(self) -> Dict[str, Any]:
        """Generate a minimal AsyncAPI schema."""
        channels = {}
        for name, _ in self._operations.items():
            channels[name] = {
                "description": f"Handler for {name}",
                "publish": {
                    "message": {
                        "name": name,
                    }
                },
            }
        return {
            "asyncapi": "2.6.0",
            "info": {
                "title": "FastWS Service",
                "version": "1.0.0",
            },
            "channels": channels,
        }
