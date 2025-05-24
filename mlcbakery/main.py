from fastapi import FastAPI

from opentelemetry import trace # type: ignore
from opentelemetry.exporter.gcp.monitoring import GoogleCloudMonitoringMetricsExporter # type: ignore
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor # type: ignore
from opentelemetry.sdk.metrics import MeterProvider # type: ignore
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader # type: ignore
from opentelemetry.sdk.resources import Resource # type: ignore
# from opentelemetry.sdk.trace import TracerProvider
# from opentelemetry.sdk.trace.export import BatchSpanProcessor

from mlcbakery.api.endpoints import (
    datasets,
    collections,
    activities,
    agents,
    storage,
    entity_relationships,
)


# Re-enable OpenAPI docs after fixing schema issues
app = FastAPI(title="MLCBakery")

# Configure OpenTelemetry
# Set up a resource for your application
resource = Resource(attributes={
    "service.name": "mlcbakery", # Adjust if you like
})

# Metrics setup
reader = PeriodicExportingMetricReader(
    GoogleCloudMonitoringMetricsExporter(), # type: ignore
    export_interval_millis=5000, # Adjust export interval as needed
)
meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
# No need to set the global meter_provider for FastAPIInstrumentor if passing it directly

# Tracer setup (optional, but good practice if you want traces too)
# If you don't need traces, you can omit this part and not install trace related packages
# tracer_provider = TracerProvider(resource=resource)
# trace.set_tracer_provider(tracer_provider)
# For traces to be exported, you would need a span exporter, e.g., GoogleCloudTraceExporter
# from opentelemetry.exporter.gcp.trace import GoogleCloudTraceExporter
# tracer_provider.add_span_processor(BatchSpanProcessor(GoogleCloudTraceExporter()))


# Instrument FastAPI app
# Pass the meter_provider directly if you have a specific one,
# otherwise, the global one would be used if set.
FastAPIInstrumentor.instrument_app(app, meter_provider=meter_provider) # type: ignore
# If you also set up tracing:
# FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider, meter_provider=meter_provider)


@app.get("/api/v1/health")
async def health_check():
    return {"status": "healthy"}


app.include_router(collections.router, prefix="/api/v1", tags=["Collections"])
app.include_router(datasets.router, prefix="/api/v1", tags=["Datasets"])
app.include_router(activities.router, prefix="/api/v1", tags=["Activities"])
app.include_router(agents.router, prefix="/api/v1", tags=["Agents"])
app.include_router(storage.router, prefix="/api/v1", tags=["Storage"])
app.include_router(entity_relationships.router, prefix="/api/v1", tags=["Entity Relationships"])
