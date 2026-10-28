"""FastAPI application factory and middleware."""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app import __version__
from app.api.errors import register_exception_handlers
from app.api.v1.routes import router as api_v1_router
from app.config import Settings, get_settings
from app.logging_config import configure_logging, request_id_var
from app.services.cache import CacheStore
from app.services.dataset import DatasetStore
from app.services.service import WindIQService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    configure_logging(settings.log_level)
    cache = CacheStore(settings)
    datasets = DatasetStore(settings, cache)
    service = WindIQService(settings=settings, cache=cache, dataset_store=datasets)
    app.state.cache = cache
    app.state.datasets = datasets
    app.state.service = service
    if not service.dataset().loaded:
        import logging

        logging.getLogger("windiq.startup").warning(
            "dataset_not_loaded",
            extra={
                "detail": "No cached January 2026 dataset found. API will return 503 until data is loaded.",
                "command": "python -m app.cli load --start 2026-01-01 --end 2026-01-31",
            },
        )
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="WindIQ API",
        description=(
            "UK national wind generation forecast intelligence. Historical January 2026 "
            "analysis built on Elexon BMRS FUELHH and WINDFOR."
        ),
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Row-Count", "Content-Disposition"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.middleware("http")
    async def observability(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            import logging

            logging.getLogger("windiq.request").exception(
                "http_request_failed",
                extra={"method": request.method, "path": request.url.path},
            )
            raise
        finally:
            request_id_var.reset(token)
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        response.headers["X-Request-ID"] = request_id
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        import logging

        logging.getLogger("windiq.request").info(
            "http_request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "query": str(request.url.query)[:400],
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response

    register_exception_handlers(app)
    app.include_router(api_v1_router, prefix=settings.api_prefix)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "name": "WindIQ — Renewable Forecast Intelligence API",
            "version": __version__,
            "api": f"{settings.api_prefix}",
            "health": f"{settings.api_prefix}/health",
            "docs": "/docs",
        }

    return app


app = create_app()
