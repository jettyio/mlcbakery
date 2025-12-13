import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

from sqlalchemy import Select
from mlcbakery.database import get_async_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from mlcbakery.auth.jwks_strategy import JWKSStrategy
from mlcbakery.models import Collection, ApiKey
from mlcbakery.api.access_level import AccessLevel, AccessType
from mlcbakery.auth.admin_token_strategy import AdminTokenStrategy

ADMIN_AUTH_TOKEN = os.getenv("ADMIN_AUTH_TOKEN", "")
JWT_ISSUER_JWKS_URL = os.getenv("JWT_ISSUER_JWKS_URL", "")

def auth_strategies():
    return [
        AdminTokenStrategy(ADMIN_AUTH_TOKEN),
        JWKSStrategy(JWT_ISSUER_JWKS_URL)
    ]

logging.basicConfig(level=logging.INFO)

# Define the bearer scheme
bearer_scheme = HTTPBearer()
# Optional bearer scheme (doesn't require auth header)
optional_bearer_scheme = HTTPBearer(auto_error=False)

async def get_auth(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    auth_strategies = Depends(auth_strategies)
):
    """
    Parse the auth token based on provided auth strategies.
    """
    possible_auth_payloads = [
        strategy.parse_token(credentials.credentials)
        for strategy in auth_strategies
    ]

    return next((payload for payload in possible_auth_payloads if payload), None)

async def verify_auth(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    auth_strategies = Depends(auth_strategies),
) -> dict:
    """
    Verify bearer token based on provided auth strategies.
    Returns a standardized payload format for any auth methods.
    """

    return await verify_auth_with_access_level(AccessLevel.READ, credentials, auth_strategies)

async def optional_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer_scheme),
    auth_strategies = Depends(auth_strategies),
) -> dict | None:
    """
    Optionally verify bearer token. Returns None if no credentials provided.
    Use this for endpoints that should be publicly accessible but may have
    additional functionality for authenticated users (e.g., seeing private entities).
    """
    if credentials is None:
        return None

    auth_payload = await get_auth(credentials, auth_strategies)
    return auth_payload

async def verify_auth_with_write_access(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    auth_strategies = Depends(auth_strategies)
) -> dict:
    """
    Dependency that verifies any auth strategy has write access.
    For JWT tokens, requires WRITE access level or higher.
    """
    return await verify_auth_with_access_level(AccessLevel.WRITE, credentials, auth_strategies)

async def verify_auth_with_access_level(
    required_access_level: AccessLevel,
    credentials: HTTPAuthorizationCredentials,
    auth_strategies = Depends(auth_strategies)
) -> dict:
    """
    Dependency that verifies either admin token or JWT token with specific access level.
    Admin token supersedes JWT token access, granting maximum privileges.
    For JWT tokens, requires the specified access level or higher.
    """
    auth_payload = await get_auth(credentials, auth_strategies)

    if not auth_payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if auth_payload["access_level"].value < required_access_level.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access level {required_access_level.name} required.",
        )

    return auth_payload

async def verify_api_key_for_collection(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_async_db)
) -> tuple[Collection, ApiKey] | None:
    """
    Verify API key and return the associated collection and API key.
    For use with API key protected endpoints.
    """
    api_key = credentials.credentials

    # check if the api key is the admin api key
    if api_key == ADMIN_AUTH_TOKEN:
        # pass through the admin api key
        return None

    if not api_key or not api_key.startswith('mlc_'):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Hash the provided key
    key_hash = ApiKey.hash_key(api_key)

    # Look up the API key
    stmt = select(ApiKey).options(
        selectinload(ApiKey.collection)
    ).where(
        ApiKey.key_hash == key_hash,
        ApiKey.is_active == True
    )

    result = await db.execute(stmt)
    api_key_obj = result.scalar_one_or_none()

    if not api_key_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return api_key_obj.collection, api_key_obj

def apply_auth_to_stmt(stmt : Select, auth: dict) -> Select:
    if auth.get("access_type") == AccessType.ADMIN:
        return stmt
    else:
        return stmt.where(Collection.owner_identifier == auth["identifier"])

async def get_user_collection_id(
    auth: dict | None,
    db: AsyncSession = Depends(get_async_db)
) -> int | list[int] | None:
    """Get the collection ID(s) for the authenticated user.

    For admin tokens, returns None (no privacy filtering).
    For unauthenticated users (auth is None), returns an empty list to filter
    to only public entities.
    For regular users, returns their collection ID(s) - either a single int
    if they have one collection, or a list of ints if they have multiple.
    """
    # Unauthenticated: return empty list to show only public entities
    if auth is None:
        return []

    if auth.get("access_type") == AccessType.ADMIN:
        return None

    identifier = auth.get("identifier")
    if not identifier:
        return None

    stmt = select(Collection).where(Collection.owner_identifier == identifier)
    result = await db.execute(stmt)
    collections = result.scalars().all()

    if not collections:
        return None
    elif len(collections) == 1:
        return collections[0].id
    else:
        return [c.id for c in collections]
