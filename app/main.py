from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from time import perf_counter

from fastapi import FastAPI, Request

from app.api.routes import router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.init_db import initialize_database
from app.db.session import engine
from app.observability.metrics import REQUEST_LATENCY
from app.observability.telemetry import instrument_app


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await initialize_database(engine)
    yield


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="Agentic Document Intelligence Platform",
        version="0.1.0",
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.include_router(router)

    @app.middleware("http")
    async def record_request_latency(request: Request, call_next):
        started_at = perf_counter()
        response = await call_next(request)
        REQUEST_LATENCY.labels(endpoint=request.url.path).observe(perf_counter() - started_at)
        return response

    instrument_app(app)
    return app


app = create_app()
