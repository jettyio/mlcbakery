import os
from fastapi import FastAPI

from opentelemetry import trace # type: ignore
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor # type: ignore
from opentelemetry.sdk.metrics import MeterProvider # type: ignore
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader # type: ignore
from opentelemetry.sdk.resources import Resource # type: ignore
from opentelemetry import metrics
import logging
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
# Use HTTP exporters instead of gRPC for Cloud Run compatibility
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

# GCP direct exporters
from opentelemetry.exporter.cloud_monitoring import CloudMonitoringMetricsExporter # type: ignore
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter # type: ignore

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

# Check if we should use GCP direct exporters
USE_GCP_METRICS = os.getenv("IS_GCP_METRICS", "false").lower() == "true"

trace_exporter = None
metric_exporter = None

if USE_GCP_METRICS:
    _LOGGER.info("Using direct GCP exporters for metrics and traces")
    # Use direct GCP exporters
    trace_exporter = CloudTraceSpanExporter()
    metric_exporter = CloudMonitoringMetricsExporter()
else:
    _LOGGER.info("Using OTLP exporters for metrics and traces")
    # Use OTLP exporters to collector
    OTLP_HTTP_ENDPOINT = os.getenv("OTLP_HTTP_ENDPOINT", "http://localhost:4318")
    
    # Cloud Run services communicate over HTTPS, so we use HTTP exporters
    _LOGGER.info(f"Configuring OTLP HTTP exporters for: {OTLP_HTTP_ENDPOINT}")
    trace_exporter = OTLPSpanExporter(
        endpoint=f"{OTLP_HTTP_ENDPOINT}/v1/traces",
        headers={}  # Add any required headers here
    )
    metric_exporter = OTLPMetricExporter(
        endpoint=f"{OTLP_HTTP_ENDPOINT}/v1/metrics",
        headers={}  # Add any required headers here
    )

# Configure metric readers
metric_readers = []
if metric_exporter:
    metric_reader = PeriodicExportingMetricReader(
        exporter=metric_exporter,
        export_interval_millis=5000,
    )
    metric_readers.append(metric_reader)
    _LOGGER.info("Metric Exporter configured.")

# Configure tracer
tracer_provider = TracerProvider(resource=resource)
if trace_exporter:
    span_processor = BatchSpanProcessor(trace_exporter)
    tracer_provider.add_span_processor(span_processor)
    _LOGGER.info("Trace Exporter configured.")
else:
    _LOGGER.warning("Trace Exporter not configured.")

# Configure meter provider with readers
meter_provider = MeterProvider(resource=resource, metric_readers=metric_readers)
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
