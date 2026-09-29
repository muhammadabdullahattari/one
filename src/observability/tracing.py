from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.trace import Span, Tracer

from src.core.config import get_settings

_TRACER_PROVIDER: TracerProvider | None = None
_TRACER: Tracer | None = None


def init_tracer(service_name: str = "task-engine") -> Tracer:
    global _TRACER_PROVIDER, _TRACER
    if _TRACER is not None:
        return _TRACER

    settings = get_settings()
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": settings.app_version,
            "deployment.environment": settings.app_env.value,
        }
    )
    provider = TracerProvider(resource=resource)

    if settings.otel_exporter_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            otlp_exporter = OTLPSpanExporter(
                endpoint=settings.otel_exporter_endpoint, insecure=True
            )
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        except Exception:
            provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    else:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _TRACER_PROVIDER = provider
    _TRACER = trace.get_tracer(service_name, settings.app_version)
    return _TRACER


def get_tracer() -> Tracer:
    global _TRACER
    if _TRACER is None:
        return init_tracer()
    return _TRACER


@asynccontextmanager
async def trace_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    task_id: str | None = None,
    attempt_id: str | None = None,
    queue: str | None = None,
    worker_id: str | None = None,
) -> AsyncGenerator[Span]:
    tracer = get_tracer()
    attrs: dict[str, Any] = attributes.copy() if attributes else {}
    if task_id:
        attrs["task.id"] = task_id
    if attempt_id:
        attrs["task.attempt_id"] = attempt_id
    if queue:
        attrs["task.queue"] = queue
    if worker_id:
        attrs["worker.id"] = worker_id

    with tracer.start_as_current_span(name, attributes=attrs) as span:
        yield span


def get_current_trace_id() -> str | None:
    current_span = trace.get_current_span()
    ctx = current_span.get_span_context()
    if ctx.is_valid:
        return f"{ctx.trace_id:032x}"
    return None
