from fastapi import FastAPI

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


@app.get("/api/v1/health")
async def health_check():
    return {"status": "healthy"}


app.include_router(collections.router, prefix="/api/v1", tags=["Collections"])
app.include_router(datasets.router, prefix="/api/v1", tags=["Datasets"])
app.include_router(activities.router, prefix="/api/v1", tags=["Activities"])
app.include_router(agents.router, prefix="/api/v1", tags=["Agents"])
app.include_router(storage.router, prefix="/api/v1", tags=["Storage"])
app.include_router(entity_relationships.router, prefix="/api/v1", tags=["Entity Relationships"])
