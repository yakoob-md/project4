"""Export content-free M0 spans using W3C trace context and OTLP."""
import base64
import os
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

propagator = TraceContextTextMapPropagator()


def tracer(service):
    provider = TracerProvider(resource=Resource.create({"service.name": service}))
    if endpoint := os.getenv("M0_OTLP_TRACES_ENDPOINT"):
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    host = os.getenv("LANGFUSE_HOST", "").rstrip("/")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    if host and public_key and secret_key:
        auth = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
        exporter = OTLPSpanExporter(
            endpoint=f"{host}/api/public/otel/v1/traces",
            headers={"Authorization": f"Basic {auth}", "x-langfuse-ingestion-version": "4"},
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
    return provider.get_tracer(service)


def traceparent():
    carrier = {}
    propagator.inject(carrier)
    return carrier.get("traceparent", "")


@contextmanager
def stage(tracer, name, run_id, parent=None):
    context = propagator.extract({"traceparent": parent}) if parent else None
    with tracer.start_as_current_span(
        name, context=context, record_exception=False, set_status_on_exception=False,
        attributes={"paperlens.run_id": str(run_id)},
    ) as span:
        try:
            yield span
        except Exception:
            span.set_status(trace.StatusCode.ERROR)
            span.set_attribute("paperlens.outcome", "failed")
            raise
        else:
            span.set_attribute("paperlens.outcome", "ok")
