from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func
from typing import List

from mlcbakery.models import ApiKey, Collection
from mlcbakery.schemas.api_key import (
    ApiKeyCreate, 
    ApiKeyResponse, 
    ApiKeyCreatedResponse, 
    ApiKeyUpdate
)
from mlcbakery.database import get_async_db
from mlcbakery.api.dependencies import verify_auth_with_write_access

def _can_access_collection(collection: Collection, auth: dict) -> bool:
    if auth.get("org_id") == "*":
        return True
    return collection.auth_org_id == auth.get("org_id")

router = APIRouter()

@router.post("/api-keys/", response_model=ApiKeyCreatedResponse)
async def create_api_key(
    api_key_data: ApiKeyCreate,
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth_with_write_access)
):
    """Create a new API key for a collection."""
    
    # Find collection by name (case-insensitive)
    stmt = select(Collection).where(
        func.lower(Collection.name) == func.lower(api_key_data.collection_name)
    )
    result = await db.execute(stmt)
    collection = result.scalar_one_or_none()
    
    if not collection or not _can_access_collection(collection, auth):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection '{api_key_data.collection_name}' not found"
        )
    
    # Check for duplicate API key names within the same collection
    stmt_check = select(ApiKey).where(
        ApiKey.collection_id == collection.id,
        func.lower(ApiKey.name) == func.lower(api_key_data.name)
    )
    result_check = await db.execute(stmt_check)
    if result_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"API key with name '{api_key_data.name}' already exists in collection '{collection.name}'"
        )
    
    # Generate API key
    plaintext_key = ApiKey.generate_api_key()
    
    # Create API key record
    db_api_key = ApiKey.create_from_plaintext(
        api_key=plaintext_key,
        collection_id=collection.id,
        name=api_key_data.name
    )
    
    db.add(db_api_key)
    await db.commit()
    await db.refresh(db_api_key)
    
    # Return response with the plaintext key (only time it's shown)
    return ApiKeyCreatedResponse(
        id=db_api_key.id,
        collection_id=db_api_key.collection_id,
        collection_name=collection.name,
        name=db_api_key.name,
        key_prefix=db_api_key.key_prefix,
        created_at=db_api_key.created_at,
        created_by_agent_id=db_api_key.created_by_agent_id,
        is_active=db_api_key.is_active,
        api_key=plaintext_key
    )

@router.get("/api-keys/collection/{collection_name}", response_model=List[ApiKeyResponse])
async def list_api_keys_for_collection(
    collection_name: str,
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth_with_write_access)
):
    """List all API keys for a collection."""
    # Find collection by name
    stmt = select(Collection).where(
        func.lower(Collection.name) == func.lower(collection_name)
    )
    result = await db.execute(stmt)
    collection = result.scalar_one_or_none()
    
    if not collection or not _can_access_collection(collection, auth):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection '{collection_name}' not found"
        )
    
    # Get API keys with collection info
    stmt = (
        select(ApiKey)
        .options(selectinload(ApiKey.collection))
        .where(ApiKey.collection_id == collection.id)
        .order_by(ApiKey.created_at.desc())
    )
    result = await db.execute(stmt)
    api_keys = result.scalars().all()
    # Convert to response format
    return [
        ApiKeyResponse(
            id=key.id,
            collection_id=key.collection_id,
            collection_name=key.collection.name,
            name=key.name,
            key_prefix=key.key_prefix,
            created_at=key.created_at,
            created_by_agent_id=key.created_by_agent_id,
            is_active=key.is_active
        )
        for key in api_keys
    ]

@router.put("/api-keys/{api_key_id}", response_model=ApiKeyResponse)
async def update_api_key(
    api_key_id: int,
    update_data: ApiKeyUpdate,
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth_with_write_access)
):
    """Update an API key (name or active status)."""
    
    stmt = (
        select(ApiKey)
        .options(selectinload(ApiKey.collection))
        .where(ApiKey.id == api_key_id)
    )
    result = await db.execute(stmt)
    api_key = result.scalar_one_or_none()
    
    if not api_key or not _can_access_collection(api_key.collection, auth):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    # Check for name conflicts if updating name
    if update_data.name and update_data.name != api_key.name:
        stmt_check = select(ApiKey).where(
            ApiKey.collection_id == api_key.collection_id,
            func.lower(ApiKey.name) == func.lower(update_data.name),
            ApiKey.id != api_key_id
        )
        result_check = await db.execute(stmt_check)
        if result_check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"API key with name '{update_data.name}' already exists in collection '{api_key.collection.name}'"
            )
    
    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(api_key, field, value)
    
    await db.commit()
    await db.refresh(api_key)
    
    return ApiKeyResponse(
        id=api_key.id,
        collection_id=api_key.collection_id,
        collection_name=api_key.collection.name,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        created_at=api_key.created_at,
        created_by_agent_id=api_key.created_by_agent_id,
        is_active=api_key.is_active
    )

@router.delete("/api-keys/{api_key_id}")
async def delete_api_key(
    api_key_id: int,
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth_with_write_access)
):
    """Delete an API key."""
    
    stmt = (
        select(ApiKey)
        .options(selectinload(ApiKey.collection))
        .where(ApiKey.id == api_key_id)
    )
    result = await db.execute(stmt)
    api_key = result.scalar_one_or_none()
    
    if not api_key or not _can_access_collection(api_key.collection, auth):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    await db.delete(api_key)
    await db.commit()
    
    return {"message": "API key deleted successfully"}

@router.get("/api-keys/{api_key_id}", response_model=ApiKeyResponse)
async def get_api_key(
    api_key_id: int,
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth_with_write_access)
):
    """Get details of a specific API key."""
    
    stmt = (
        select(ApiKey)
        .options(selectinload(ApiKey.collection))
        .where(ApiKey.id == api_key_id)
    )
    result = await db.execute(stmt)
    api_key = result.scalar_one_or_none()
    
    if not api_key or not _can_access_collection(api_key.collection, auth):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    return ApiKeyResponse(
        id=api_key.id,
        collection_id=api_key.collection_id,
        collection_name=api_key.collection.name,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        created_at=api_key.created_at,
        created_by_agent_id=api_key.created_by_agent_id,
        is_active=api_key.is_active
    ) 
