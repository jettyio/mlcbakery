from fastapi import APIRouter
from .endpoints import collections, datasets, entities, trained_models, activities

api_router = APIRouter()

api_router.include_router(
    collections.router, prefix="/collections", tags=["collections"]
)
api_router.include_router(datasets.router, prefix="/datasets", tags=["datasets"])
api_router.include_router(entities.router, prefix="/entities", tags=["entities"])
api_router.include_router(
    trained_models.router, prefix="/trained_models", tags=["trained_models"]
)
api_router.include_router(activities.router, prefix="/activities", tags=["activities"])
