from fastapi import FastAPI

from app.core.config import settings


def instrument_app(app: FastAPI) -> None:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.trace import set_tracer_provider

        set_tracer_provider(
            TracerProvider(resource=Resource.create({"service.name": settings.service_name}))
        )
        FastAPIInstrumentor.instrument_app(app)
    except Exception:
        # Observability must never stop the API from booting in local/dev.
        return

