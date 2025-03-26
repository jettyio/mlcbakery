from fastapi import FastAPI
from mlcbakery.api.endpoints import entities, datasets, collections

app = FastAPI()


@app.get("/api/v1/health")
async def health_check():
    return {"status": "healthy"}


app.include_router(entities.router, prefix="/api/v1")
app.include_router(datasets.router, prefix="/api/v1")
app.include_router(collections.router, prefix="/api/v1")
