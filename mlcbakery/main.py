import os
from fastapi import FastAPI

from opentelemetry import trace # type: ignore
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor # type: ignore
from opentelemetry.sdk.metrics import MeterProvider # type: ignore
from opentelemetry.sdk.resources import Resource # type: ignore
from opentelemetry import metrics
import logging
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

from mlcbakery.metrics import init_metrics

_LOGGER = logging.getLogger(__name__)
from mlcbakery.api.endpoints import (
    datasets,
    collections,
    activities,
    agents,
    storage,
    entity_relationships,
)

# Define app early
app = FastAPI(title="MLCBakery")

# Configure OpenTelemetry
resource = Resource(attributes={
    "service.name": "mlcbakery",
})

OTLP_ENDPOINT = os.getenv("OTEL_COLLECTOR_ENDPOINT", "localhost:4317")

otlp_trace_exporter = None
otlp_metric_exporter = None

if os.getenv("OTLP_SECURE", "false").lower() == "true":
    _LOGGER.info(f"OTLP_SECURE is set. Configuring OTLP exporters for secure: {OTLP_ENDPOINT}")
    otlp_trace_exporter = OTLPSpanExporter(endpoint=OTLP_ENDPOINT, insecure=False)
    otlp_metric_exporter = OTLPMetricExporter(endpoint=OTLP_ENDPOINT, insecure=False)
else:
    _LOGGER.info(f"OTLP_SECURE not set. Configuring OTLP exporters for insecure: {OTLP_ENDPOINT}")
    otlp_trace_exporter = OTLPSpanExporter(endpoint=OTLP_ENDPOINT, insecure=True) # Local collector might not use TLS
    otlp_metric_exporter = OTLPMetricExporter(endpoint=OTLP_ENDPOINT, insecure=True) # Local collector might not use TLS

tracer_provider = TracerProvider(resource=resource)
if otlp_trace_exporter:
    span_processor = BatchSpanProcessor(otlp_trace_exporter)
    tracer_provider.add_span_processor(span_processor)
    _LOGGER.info("OTLP Trace Exporter configured.")
else:
    _LOGGER.warning("OTLP Trace Exporter not configured. Traces will not be exported via OTLP.")

meter_provider = MeterProvider(resource=resource)
metrics.set_meter_provider(meter_provider)

init_metrics()


FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider, meter_provider=meter_provider)



@app.get("/api/v1/health")
async def health_check():
    return {"status": "healthy"}

app.include_router(collections.router, prefix="/api/v1", tags=["Collections"])
app.include_router(datasets.router, prefix="/api/v1", tags=["Datasets"])
app.include_router(activities.router, prefix="/api/v1", tags=["Activities"])
app.include_router(agents.router, prefix="/api/v1", tags=["Agents"])
app.include_router(storage.router, prefix="/api/v1", tags=["Storage"])
app.include_router(entity_relationships.router, prefix="/api/v1", tags=["Entity Relationships"])
