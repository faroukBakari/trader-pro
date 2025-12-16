"""
Global exception handlers for FastAPI.

Converts TradingApiException hierarchy to HTTP responses and WebSocket close codes.
"""

import logging
import traceback
from http import HTTPStatus
from pathlib import Path
from typing import List

from fastapi import FastAPI, Request, WebSocket, WebSocketException
from fastapi import status as WebSocketStatus
from fastapi.exceptions import RequestValidationError, WebSocketRequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from trading_api.models.exceptions import TradingApiException

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _is_project_frame(frame: traceback.FrameSummary, project_root: Path) -> bool:
    """Check if a traceback frame is from project code."""
    try:
        return Path(frame.filename).resolve().is_relative_to(project_root.resolve())
    except AttributeError:
        # Python <3.9 fallback: simple substring check
        return str(project_root.resolve()) in str(frame.filename)
    except Exception:
        return False


def _filter_project_frames(
    frames: List[traceback.FrameSummary], project_root: Path
) -> tuple[List[traceback.FrameSummary], List[traceback.FrameSummary]]:
    """Filter frames to only project frames, return (project_frames, omitted_count)."""
    project_frames: list[traceback.FrameSummary] = []
    omitted_frames: list[traceback.FrameSummary] = []

    for f in frames:
        if _is_project_frame(f, project_root):
            project_frames.append(f)
        else:
            omitted_frames.append(f)

    return project_frames, omitted_frames


def _extract_project_backtrace(
    exc: BaseException, project_root: Path
) -> tuple[List[traceback.FrameSummary], List[traceback.FrameSummary]]:
    """Return a string containing only traceback frames whose filename is inside project_root.

    project_root: Path to your repo or package root (e.g., Path(__file__).resolve().parents[2])

    Handles multiple traceback sources in order:
    1. exc.__traceback__ (live traceback from raise)
    2. exc.__cause__.__traceback__ (chained exception via 'raise ... from ...')
    3. exc.backtrace (stored string in TradingApiException)
    """
    project_frames: List[traceback.FrameSummary] = []
    omitted_frames: List[traceback.FrameSummary] = []

    # 1. Try live traceback from exc.__traceback__
    frames: list[traceback.FrameSummary] | None = getattr(
        exc, "backtrace", traceback.extract_tb(exc.__traceback__)
    )
    if frames:
        project_frames, omitted_frames = _filter_project_frames(frames, project_root)

    # 2. If no project frames, try chained cause (__cause__ or __context__)
    if not project_frames:
        cause = exc.__cause__ or exc.__context__
        if cause and cause.__traceback__:
            cause_frames = traceback.extract_tb(cause.__traceback__)
            project_frames, new_omitted_frames = _filter_project_frames(
                cause_frames, project_root
            )
            omitted_frames.extend(new_omitted_frames)

    return project_frames, omitted_frames


def format_project_traceback(exc: BaseException, project_root: Path) -> str:
    """Return a string containing only traceback frames whose filename is inside project_root.

    project_root: Path to your repo or package root (e.g., Path(__file__).resolve().parents[2])

    Handles multiple traceback sources in order:
    1. exc.__traceback__ (live traceback from raise)
    2. exc.__cause__.__traceback__ (chained exception via 'raise ... from ...')
    3. exc.backtrace (stored string in TradingApiException)
    """

    project_frames, omitted_frames = _extract_project_backtrace(exc, project_root)
    parts: List[str] = traceback.format_list(project_frames or omitted_frames)
    # Format output
    if project_frames and omitted_frames:
        parts.insert(
            0,
            f"... omitted {len(omitted_frames)} frame(s) from external libraries ...\n",
        )
    return "".join(parts)


def _get_status_code_from_code(code: str) -> int:
    """
    Map error codes to HTTP status codes based on patterns.

    Convention:
        - *_NOT_FOUND -> 404
        - *_AUTH_INVALID_* -> 401 (authentication errors)
        - *_INVALID_* -> 400 (validation errors)
        - *_AUTH_* (with certain codes) -> 401/403
        - Default -> 500
    """
    code_upper = code.upper()

    # Not found errors
    if "NOT_FOUND" in code_upper:
        return 404

    # Authentication errors (check before general INVALID check)
    # Auth-related "invalid" is 401 (invalid token, invalid credentials)
    if "AUTH" in code_upper and any(
        pattern in code_upper
        for pattern in ["INVALID", "TOKEN_EXPIRED", "UNAUTHORIZED"]
    ):
        return 401

    # Forbidden
    if "FORBIDDEN" in code_upper or "EMAIL_NOT_VERIFIED" in code_upper:
        return 403

    # Validation / bad request errors (non-auth)
    if any(
        pattern in code_upper
        for pattern in [
            "INVALID",
            "BAD_REQUEST",
            "VALIDATION",
            "TOPIC_EXISTS",
            "NO_SYMBOLS",
        ]
    ):
        return 400

    # Default to internal server error
    return 500


def _get_ws_close_code_from_code(code: str) -> int:
    """
    Map error codes to WebSocket close codes based on patterns.

    Convention:
        - *_AUTH_* -> 1008 (Policy Violation - auth required)
        - *_INVALID_* / validation -> 1003 (Unsupported Data)
        - *_NOT_FOUND -> 1003 (Unsupported Data)
        - Default -> 1011 (Internal Error)
    """
    code_upper = code.upper()

    # Authentication errors -> Policy Violation
    if "AUTH" in code_upper:
        return WebSocketStatus.WS_1008_POLICY_VIOLATION

    # Validation / bad request / not found -> Unsupported Data
    if any(
        pattern in code_upper
        for pattern in [
            "INVALID",
            "BAD_REQUEST",
            "VALIDATION",
            "NOT_FOUND",
            "NO_SYMBOLS",
        ]
    ):
        return WebSocketStatus.WS_1003_UNSUPPORTED_DATA

    # Default to internal error
    return WebSocketStatus.WS_1011_INTERNAL_ERROR


def _log_exception(
    exc: TradingApiException, status_code: int, request: Request | WebSocket
) -> None:
    """
    Log exception once with predefined format: request info / code / message / backtrace.

    Server errors (5xx) logged as ERROR, client errors (4xx) as WARNING.
    Uses request state to prevent duplicate logging in nested app scenarios.
    """
    # Check if already logged (nested FastAPI apps can trigger handlers multiple times)
    state = request.state
    if getattr(state, "_exception_logged", False):
        return
    setattr(state, "_exception_logged", True)

    # Build request info: method, URL, and query params
    if isinstance(request, WebSocket):
        request_info = f"WS {request.url.path}"
    else:
        request_info = f"{request.method} {request.url.path}"
    if request.query_params:
        request_info += f"?{request.query_params}"

    log_message = (
        f"[{request_info} --> {status_code}: {HTTPStatus(status_code).name}]"
        + f"\n{format_project_traceback(exc, PROJECT_ROOT)}"
        + f"\n{''.join(traceback.format_exception_only(type(exc), exc))}"
        + f"\n{exc}"
    )

    if status_code >= 500:
        logger.error(log_message)
    else:
        logger.warning(log_message)


def _api_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle all exceptions for HTTP requests.

    - Logs once with format: request info / code / message / backtrace
    - Returns only code + message to client (no backtrace in response)
    """
    # Handle validation errors specially (422 Unprocessable Entity)
    if isinstance(exc, RequestValidationError):
        api_exc = TradingApiException(
            code="VALIDATION_ERROR",
            message=str(exc.errors()),
            backtrace=exc.__traceback__,
        )
        status_code = 422
    # Handle HTTPException (FastAPI/Starlette standard exceptions, including 404)
    elif isinstance(exc, StarletteHTTPException):
        api_exc = TradingApiException(
            code=HTTPStatus(exc.status_code).name.upper(),
            message=str(exc.detail),
            backtrace=exc.__traceback__,
        )
        status_code = exc.status_code
    elif isinstance(exc, TradingApiException):
        api_exc = exc
        status_code = _get_status_code_from_code(api_exc.code)
    else:
        api_exc = TradingApiException(
            code="UNHANDLED_EXCEPTION",
            message=str(exc),
            backtrace=exc.__traceback__,
        )
        status_code = _get_status_code_from_code(api_exc.code)

    _log_exception(api_exc, status_code, request)

    return JSONResponse(
        status_code=status_code,
        content={"code": api_exc.code, "message": api_exc.message},
    )


async def _ws_exception_handler(websocket: WebSocket, exc: Exception) -> None:
    """
    Handle all exceptions for WebSocket connections.

    - Logs once with format: request info / code / message / backtrace
    - Closes WebSocket with appropriate close code and reason
    """
    if isinstance(exc, TradingApiException):
        ws_exc = exc
    else:
        project_frames, omitted_frames = _extract_project_backtrace(exc, PROJECT_ROOT)
        ws_exc = TradingApiException(
            code="UNHANDLED_EXCEPTION",
            message=str(exc),
            backtrace=project_frames or omitted_frames,
        )

    close_code = _get_ws_close_code_from_code(ws_exc.code)
    http_status = _get_status_code_from_code(ws_exc.code)
    _log_exception(ws_exc, http_status, websocket)

    # Close WebSocket with code and reason (truncate reason to 123 bytes per RFC 6455)
    reason = f"{ws_exc.code}: {ws_exc.message}"
    if len(reason.encode("utf-8")) > 123:
        reason = reason.encode("utf-8")[:120].decode("utf-8", errors="ignore") + "..."
    await websocket.close(code=close_code, reason=reason)


async def exception_handler(
    conn: Request | WebSocket, exc: Exception
) -> JSONResponse | None:
    """
    Unified exception handler for both HTTP and WebSocket connections.

    Detects connection type from scope and delegates to appropriate handler.
    """
    if isinstance(conn, WebSocket):
        await _ws_exception_handler(conn, exc)
        return None
    else:
        return _api_exception_handler(conn, exc)


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register all exception handlers on the FastAPI app.

    Call this during app initialization.
    """
    # Single unified handler for both HTTP and WebSocket
    for key in app.exception_handlers.keys():
        app.add_exception_handler(key, exception_handler)  # type: ignore[arg-type]

    must_have_exceptions = [
        Exception,
        StarletteHTTPException,  # Includes FastAPI HTTPException (subclass)
        WebSocketException,
        RequestValidationError,
        WebSocketRequestValidationError,
        500,
    ]
    for exc in must_have_exceptions:
        app.add_exception_handler(exc, exception_handler)  # type: ignore[arg-type]
