"""Unified error responses and exception handlers."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.logging_config import request_id_var
from app.services.service import (
    DataUnavailableError,
    NotFoundError,
    OutOfRangeError,
    RefreshDisabledError,
)

logger = logging.getLogger("windiq.errors")


def _body(code: str, message: str, status: int, details: dict | None = None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": jsonable_encoder(details or {}),
            "request_id": request_id_var.get(),
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DataUnavailableError)
    async def data_unavailable(_request: Request, exc: DataUnavailableError):
        return JSONResponse(
            status_code=503,
            content=_body(
                "DATA_UNAVAILABLE",
                str(exc),
                503,
                exc.details,
            ),
        )

    @app.exception_handler(OutOfRangeError)
    async def out_of_range(_request: Request, exc: OutOfRangeError):
        return JSONResponse(
            status_code=422,
            content=_body("OUT_OF_RANGE", str(exc), 422, exc.details),
        )

    @app.exception_handler(NotFoundError)
    async def not_found(_request: Request, exc: NotFoundError):
        return JSONResponse(status_code=404, content=_body("NOT_FOUND", str(exc), 404))

    @app.exception_handler(RefreshDisabledError)
    async def refresh_disabled(_request: Request, exc: RefreshDisabledError):
        return JSONResponse(
            status_code=403, content=_body("REFRESH_DISABLED", str(exc), 403)
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=_body(
                "VALIDATION_ERROR",
                "One or more request parameters are invalid.",
                422,
                {"errors": jsonable_encoder(exc.errors())},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request: Request, exc: StarletteHTTPException):
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 403: "FORBIDDEN"}.get(
            exc.status_code, "HTTP_ERROR"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(code, str(exc.detail), exc.status_code),
        )

    @app.exception_handler(Exception)
    async def unhandled(_request: Request, exc: Exception):
        logger.exception("unhandled_error", extra={"error": str(exc)})
        return JSONResponse(
            status_code=500,
            content=_body(
                "INTERNAL_ERROR",
                "An unexpected error occurred. Check server logs with the request ID.",
                500,
            ),
        )
