from fastapi import FastAPI
from mlcbakery.api.endpoints import entities, datasets

app = FastAPI()

app.include_router(entities.router, prefix="/api/v1")
app.include_router(datasets.router, prefix="/api/v1")
