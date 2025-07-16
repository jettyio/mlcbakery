import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

from mlcbakery.auth.jwks_strategy import JWKSStrategy
from mlcbakery.models import Collection
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

def apply_auth_to_stmt(stmt, auth):
    if auth.get("access_type") == AccessType.ADMIN:
        return stmt
    else:
        return stmt.where(Collection.owner_identifier == auth["identifier"])