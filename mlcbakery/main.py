import os
from fastapi import FastAPI

from opentelemetry import trace # type: ignore
from opentelemetry.exporter.cloud_monitoring import CloudMonitoringMetricsExporter # type: ignore
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor # type: ignore
from opentelemetry.sdk.metrics import MeterProvider # type: ignore
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader, ConsoleMetricExporter # type: ignore
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
# This section configures OpenTelemetry metrics.
# Metrics are exported to Google Cloud Monitoring if GOOGLE_CLOUD_PROJECT is set.
# Otherwise, you can uncomment the ConsoleMetricExporter to view them locally.
metric_readers = []

if os.getenv("GOOGLE_CLOUD_PROJECT"):
    print("GOOGLE_CLOUD_PROJECT is set. Initializing Google Cloud Monitoring exporter for metrics.") # Consider using logging
    cloud_monitoring_exporter = CloudMonitoringMetricsExporter() # type: ignore
    gcp_reader = PeriodicExportingMetricReader(
        exporter=cloud_monitoring_exporter,
        export_interval_millis=5000, # Adjust export interval as needed
    )
    metric_readers.append(gcp_reader)
else:
    print("GOOGLE_CLOUD_PROJECT not set. Metrics will be collected. To view them locally, uncomment ConsoleMetricExporter setup below.") # Consider using logging
    # To enable console exporting for local development (when GOOGLE_CLOUD_PROJECT is not set):
    # 1. Ensure 'ConsoleMetricExporter' is imported:
    #    from opentelemetry.sdk.metrics.export import ConsoleMetricExporter
    # 2. Uncomment the following lines:
    # console_exporter = ConsoleMetricExporter()
    # console_reader = PeriodicExportingMetricReader(
    #     exporter=console_exporter,
    #     export_interval_millis=5000, # Adjust export interval as needed
    # )
    # metric_readers.append(console_reader)
    # print("ConsoleMetricExporter has been enabled for local metrics viewing.") # Consider using logging

# Always initialize MeterProvider.
# FastAPIInstrumentor will use this meter_provider.
# If metric_readers is empty, metrics are collected by FastAPIInstrumentor but not exported by these readers.
meter_provider = MeterProvider(resource=resource, metric_readers=metric_readers)

# Instrument the FastAPI application for metrics.
# FastAPIInstrumentor automatically collects standard metrics like http.server.duration,
# http.server.active_requests, and errors, typically dimensioned by route, method, and status_code.
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
