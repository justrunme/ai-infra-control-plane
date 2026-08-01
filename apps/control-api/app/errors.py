"""Unified API error envelope helpers."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def error_body(
    *,
    code: str,
    message: str,
    request_id: str = "",
    retryable: bool = False,
    details: Any = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
            "retryable": retryable,
        }
    }
    if details is not None:
        payload["error"]["details"] = details
    return payload


def _request_id(request: Request) -> str:
    return request.headers.get("x-request-id", "") or ""


def _code_from_status(status_code: int, detail: Any) -> str:
    if isinstance(detail, dict) and isinstance(detail.get("error"), str):
        raw = detail["error"].strip().lower().replace(" ", "_")
        if raw:
            return raw[:64]
    mapping = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
        503: "service_unavailable",
    }
    return mapping.get(status_code, f"http_{status_code}")


def _message_from_detail(detail: Any) -> str:
    if isinstance(detail, dict):
        if isinstance(detail.get("error"), str):
            return detail["error"]
        if isinstance(detail.get("message"), str):
            return detail["message"]
        return "request failed"
    if isinstance(detail, list):
        return "validation failed"
    return str(detail)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        detail = exc.detail
        body = error_body(
            code=_code_from_status(exc.status_code, detail),
            message=_message_from_detail(detail),
            request_id=_request_id(request),
            retryable=exc.status_code >= 500,
            details=detail if isinstance(detail, (dict, list)) else None,
        )
        # Keep FastAPI-compatible `detail` for existing clients/tests.
        body["detail"] = detail
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        body = error_body(
            code="validation_error",
            message="request validation failed",
            request_id=_request_id(request),
            retryable=False,
            details=exc.errors(),
        )
        body["detail"] = exc.errors()
        return JSONResponse(status_code=422, content=body)
