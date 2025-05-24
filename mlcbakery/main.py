import os
from fastapi import FastAPI

from opentelemetry import trace # type: ignore
from opentelemetry.exporter.cloud_monitoring import CloudMonitoringMetricsExporter # type: ignore
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

# if GOOGLE_CLOUD_PROJECT is set, use the GoogleCloudMonitoringMetricsExporter
if os.getenv("GOOGLE_CLOUD_PROJECT"):
    # Metrics setup
    reader = PeriodicExportingMetricReader(
        CloudMonitoringMetricsExporter(), # type: ignore
        export_interval_millis=5000, # Adjust export interval as needed
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
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
