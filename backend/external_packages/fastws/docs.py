# type: ignore
# mypy: ignore-errors
# pyright: reportGeneralTypeIssues=false
from dataclasses import dataclass
from typing import Any, Hashable, Literal, Sequence, get_args, get_origin

from pydantic import BaseModel
from pydantic.json_schema import GenerateJsonSchema
from pydantic_core import CoreSchema

from . import asyncapi
from .routing import Operation

REF_SCHEMAS_TEMPLATE = "#/components/schemas/{model}"
REF_MESSAGES_TEMPLATE = "#/components/messages/{message}"


@dataclass
class Field:
    key: Hashable
    json_mode: Literal["validation", "serialization"]
    core_schema: CoreSchema


def _extract_nested_request_types(model: type) -> list[type[BaseModel]]:
    """
    Extract nested BaseModel types from generic wrappers like SubscriptionRequest[T].

    Handles both standard Python generics and Pydantic generic models which use
    __pydantic_generic_metadata__ to store type args.
    """
    nested_types: list[type[BaseModel]] = []

    # Try Pydantic's generic metadata first (for Pydantic generic models)
    pydantic_meta = getattr(model, "__pydantic_generic_metadata__", None)
    if pydantic_meta is not None:
        args = pydantic_meta.get("args", ())
        for arg in args:
            if isinstance(arg, type) and issubclass(arg, BaseModel):
                nested_types.append(arg)
                # Recursively check for nested generics in this type too
                nested_types.extend(_extract_nested_request_types(arg))
        return nested_types

    # Fallback: Check if it's a standard generic type with arguments
    origin = get_origin(model)
    if origin is not None:
        args = get_args(model)
        for arg in args:
            if isinstance(arg, type) and issubclass(arg, BaseModel):
                nested_types.append(arg)
            elif get_origin(arg) is not None:
                nested_types.extend(_extract_nested_request_types(arg))

    # Also check field annotations for nested types
    if hasattr(model, "model_fields"):
        for field_info in model.model_fields.values():
            annotation = field_info.annotation
            if annotation is not None:
                # Check Pydantic generic metadata on the field annotation
                field_pydantic_meta = getattr(
                    annotation, "__pydantic_generic_metadata__", None
                )
                if field_pydantic_meta is not None:
                    field_args = field_pydantic_meta.get("args", ())
                    for arg in field_args:
                        if isinstance(arg, type) and issubclass(arg, BaseModel):
                            nested_types.append(arg)
                else:
                    # Standard generic check
                    field_origin = get_origin(annotation)
                    if field_origin is not None:
                        field_args = get_args(annotation)
                        for arg in field_args:
                            if isinstance(arg, type) and issubclass(arg, BaseModel):
                                nested_types.append(arg)

    return nested_types


def get_fields(
    routes: Sequence[Operation],
) -> list[Field]:
    fields: list[Field] = []
    seen_types: set[type] = set()

    for route in routes:
        if route.payload is not None and issubclass(route.payload, BaseModel):
            fields.append(
                Field(
                    key=route.operation,
                    json_mode="validation",
                    core_schema=route.payload.__pydantic_core_schema__,
                )
            )

            # Extract nested request types from ALL handler parameters (not just 'payload')
            for param in route.parameters.values():
                if param.annotation is not None:
                    nested_types = _extract_nested_request_types(param.annotation)
                    for nested_type in nested_types:
                        if nested_type not in seen_types:
                            seen_types.add(nested_type)
                            fields.append(
                                Field(
                                    key=nested_type.__name__,
                                    json_mode="validation",
                                    core_schema=nested_type.__pydantic_core_schema__,
                                )
                            )

        if route.reply_payload is not None and issubclass(
            route.reply_payload, BaseModel
        ):
            key = route.operation
            if route.method == "SEND":
                key = route.reply_operation
            fields.append(
                Field(
                    key=key,
                    json_mode="validation",
                    core_schema=route.reply_payload.__pydantic_core_schema__,
                )
            )
    return fields


def get_messages(
    routes: Sequence[Operation],
    field_mapping: dict[tuple[Hashable, Literal["validation", "serialization"]], dict],
) -> tuple[dict[str, asyncapi.Message], list[str], list[str]]:
    messages = {}
    sub_messages = []
    pub_messages = []

    for route in routes:
        msg = asyncapi.Message(
            messageId=route.operation,
            name=route.name,
            title=" ".join(route.name.split("_")).title(),
            summary=route.summary,
            description=route.description,
            tags=[asyncapi.Tag(name=t) for t in route.tags],
        )
        if route.method == "SEND":
            key = route.operation
            pub_messages.append(key)

            to_update = {
                "messageId": key,
                "payload": field_mapping.get((key, "validation"), None),
            }
            if route.reply_operation is not None:
                to_update["x_response"] = {
                    "$ref": REF_MESSAGES_TEMPLATE.format(message=route.reply_operation)
                }
            messages[key] = msg.model_copy(update=to_update)
        if route.response_model or route.reply_operation or route.method == "RECEIVE":
            key = route.operation
            if route.method == "SEND":
                key = route.reply_operation
            sub_messages.append(key)
            messages[key] = msg.model_copy(
                update={
                    "messageId": key,
                    "payload": field_mapping.get((key, "validation"), None),
                }
            )
    return messages, sub_messages, pub_messages


def get_asyncapi(
    operations: Sequence[Operation],
    title: str = "Event Driven Broker",
    version: str = "1.0.0",
    asyncapi_version: str = "2.4.0",
    description: str | None = None,
    terms_of_service: str | None = None,
    contact: dict[str, str] | None = None,
    license_info: dict[str, str] | None = None,
    servers: dict | None = None,
) -> dict[str, Any]:
    output: dict[str, Any] = {"asyncapi": asyncapi_version}

    output["info"] = {
        "title": title,
        "version": version,
        "description": description or "",
        "termsOfService": terms_of_service,
        "contact": contact,
        "license": license_info,
    }
    if servers is not None:
        output["servers"] = servers

    schema_generator = GenerateJsonSchema(ref_template=REF_SCHEMAS_TEMPLATE)

    fields = get_fields(operations)
    field_mapping, definitions = schema_generator.generate_definitions(
        inputs=[(f.key, f.json_mode, f.core_schema) for f in fields]
    )
    messages, sub_messages, pub_messages = get_messages(operations, field_mapping)

    output["channels"] = {
        "/": {
            "publish": {
                "operationId": "sendMessage",
                "summary": "The API user can send a given message to the server.",
                "message": {
                    "oneOf": [
                        {"$ref": REF_MESSAGES_TEMPLATE.format(message=v)}
                        for v in pub_messages
                    ]
                },
            },
            "subscribe": {
                "operationId": "processMessage",
                "summary": "The API user can receive a given message from the server.",
                "message": {
                    "oneOf": [
                        {"$ref": REF_MESSAGES_TEMPLATE.format(message=v)}
                        for v in sub_messages
                    ]
                },
            },
        }
    }
    messages = {
        k: v.model_dump(by_alias=True, exclude_unset=True) for k, v in messages.items()
    }
    output["components"] = {"schemas": definitions, "messages": messages}
    return asyncapi.AsyncAPI(**output).model_dump(by_alias=True, exclude_none=True)


def get_asyncapi_html(
    *,
    title: str = "AsyncAPI",
    asyncapi_url: str = "/asyncapi.json",
    asyncapi_js_url: str = "https://unpkg.com/@asyncapi/react-component@1.0.0-next.39/browser/standalone/index.js",
    asyncapi_css_url: str = "https://unpkg.com/@asyncapi/react-component@1.0.0-next.39/styles/default.min.css",
) -> str:
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <link type="text/css" rel="stylesheet" href="{asyncapi_css_url}">
    <style>
    html,
    body {{
    font-family: ui-sans-serif, system-ui, Segoe UI, Roboto, Helvetica Neue, sans-serif,
    Apple Color Emoji, Segoe UI Emoji, Segoe UI Symbol, Noto Color Emoji
    }}
    </style>
    <title>{title}</title>
    </head>
    <body>
    <div id="asyncapi"></div>
    <script src="{asyncapi_js_url}"></script>
    <script>
    AsyncApiStandalone.render({{
    schema: {{
        url: '{asyncapi_url}',
        options: {{ method: "GET", mode: "cors" }},
    }},
    config: {{
        show: {{
        sidebar: true,
        }}
    }},
    }}, document.getElementById('asyncapi'));
    </script>
    </body>
    </html>"""
    return html
