"""
Decorators and utilities for enforcing response model compliance
"""

import functools
from typing import Any, Callable, Union

from fastapi import APIRouter


class ResponseModelError(Exception):
    """Raised when a route is missing a response_model"""

    pass


def enforce_response_model(func: Callable) -> Callable:
    """
    Decorator that ensures the decorated route function has a response_model.
    This should be used on APIRouter methods like get, post, etc.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Check if response_model is provided
        if "response_model" not in kwargs or kwargs["response_model"] is None:
            # Try to extract function name from the decorator call
            if args and hasattr(args[0], "__name__"):
                func_name = args[0].__name__
            else:
                func_name = "unknown"

            raise ResponseModelError(
                f"Route function must have a response_model defined. "
                f"Missing response_model for function: {func_name}"
            )

        return func(*args, **kwargs)

    return wrapper


class StrictAPIRouter(APIRouter):
    """
    APIRouter that enforces response_model on all routes
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @enforce_response_model
    def get(self, *args: Any, **kwargs: Any) -> Any:
        return super().get(*args, **kwargs)

    @enforce_response_model
    def post(self, *args: Any, **kwargs: Any) -> Any:
        return super().post(*args, **kwargs)

    @enforce_response_model
    def put(self, *args: Any, **kwargs: Any) -> Any:
        return super().put(*args, **kwargs)

    @enforce_response_model
    def patch(self, *args: Any, **kwargs: Any) -> Any:
        return super().patch(*args, **kwargs)

    @enforce_response_model
    def delete(self, *args: Any, **kwargs: Any) -> Any:
        return super().delete(*args, **kwargs)


def validate_all_routes_have_response_models(
    app_or_router: Union[Any, APIRouter],
) -> None:
    """
    Validate that all routes in an app or router have response_models defined.
    Call this after all routes are registered.
    """
    routes = getattr(app_or_router, "routes", [])

    missing_models = []

    for route in routes:
        if hasattr(route, "endpoint") and hasattr(route, "response_model"):
            if route.response_model is None:
                endpoint_name = getattr(route.endpoint, "__name__", "unknown")
                path = getattr(route, "path", "unknown")
                methods: set[str] = getattr(route, "methods", set())
                missing_models.append(f"{methods} {path} -> {endpoint_name}")

    if missing_models:
        error_msg = "The following routes are missing response_model:\n" + "\n".join(
            f"  - {model}" for model in missing_models
        )
        raise ResponseModelError(error_msg)


def create_response_model_validator() -> Callable[[Any], None]:
    """
    Create a startup event handler that validates all routes have response models
    """

    def validate_response_models(app: Any) -> None:
        validate_all_routes_have_response_models(app)

    return validate_response_models
