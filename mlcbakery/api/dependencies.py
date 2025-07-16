import os
import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from mlcbakery.auth.jwks_strategy import JWKSStrategy
from mlcbakery.models import Collection, ApiKey
from mlcbakery.database import get_async_db

JWT_ISSUER_JWKS_URL = os.getenv("JWT_ISSUER_JWKS_URL", "")

def jwt_verification_strategy():
    return JWKSStrategy(JWT_ISSUER_JWKS_URL)

from mlcbakery.api.access_level import AccessLevel

logging.basicConfig(level=logging.INFO)

# Define the bearer scheme
bearer_scheme = HTTPBearer()

def _get_access_level_from_token(jwt_payload: dict) -> AccessLevel:
    """
    Extract access level from JWT payload.
    Handles both direct access_level field and org_role field.
    """
    # If access_level is directly available, use it
    if "access_level" in jwt_payload:
        return jwt_payload["access_level"]
    
    # Map org_role to access level
    org_role = jwt_payload.get("org_role")
    if org_role == "org:admin":
        return AccessLevel.ADMIN
    elif org_role == "org:member":
        return AccessLevel.READ
    else:
        # Default to read access for authenticated users
        return AccessLevel.READ

async def verify_jwt_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    verification_strategy = Depends(jwt_verification_strategy)
):
    """
    Dependency that verifies the provided JWT token.

    This works over both HTTP and HTTPS as the Bearer token authentication
    is transport protocol agnostic. The token is sent in the Authorization header
    which is preserved by the reverse proxy as configured in Caddyfile.
    """
    parsed_token = verification_strategy.parse_token(credentials.credentials)
    if not parsed_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired JWT token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return parsed_token

async def verify_jwt_with_write_access(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    jwt_verification_strategy = Depends(jwt_verification_strategy)
):
    return await verify_access_level(AccessLevel.WRITE, credentials, jwt_verification_strategy)

async def verify_access_level(
    required_access_level: AccessLevel,
    credentials: HTTPAuthorizationCredentials,
    jwt_verification_strategy
) -> dict:
    """
    Dependency that verifies the access level of the user based on the JWT token.

    This works over both HTTP and HTTPS as the Bearer token authentication
    is transport protocol agnostic. The token is sent in the Authorization header
    which is preserved by the reverse proxy as configured in Caddyfile.
    """
    jwt_payload = await verify_jwt_token(credentials, jwt_verification_strategy)
    user_access_level = _get_access_level_from_token(jwt_payload)
    logging.info(f"verify_access_level: user_access_level={user_access_level}, required_access_level={required_access_level}, payload={jwt_payload}")
    if user_access_level.value < required_access_level.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access level {required_access_level.name} required.",
        )
    return jwt_payload

async def verify_admin_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """
    Dependency that verifies the provided admin token against the one stored
    in environment variables.

    This works over both HTTP and HTTPS as the Bearer token authentication
    is transport protocol agnostic. The token is sent in the Authorization header
    which is preserved by the reverse proxy as configured in Caddyfile.
    
    Returns a standardized payload format compatible with JWT tokens.
    """
    admin_auth_token = os.environ.get("ADMIN_AUTH_TOKEN")
    if not admin_auth_token:  # Check the locally read token
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin token not configured on the server.",
        )
    is_token_valid = secrets.compare_digest(
        credentials.credentials,
        admin_auth_token,  # Compare against the locally read token
    )

    if not is_token_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Return standardized payload format for consistency with JWT tokens
    return {
        "auth_type": "admin",
        "access_level": AccessLevel.ADMIN,
        "identifier": "admin",
        "org_id": "*"
    }

# New hybrid dependency functions that allow admin token to supersede JWT access

async def verify_admin_or_jwt_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    verification_strategy = Depends(jwt_verification_strategy)
) -> dict:
    """
    Dependency that verifies either admin token or JWT token.
    Admin token supersedes JWT token access, granting maximum privileges.
    
    Returns a standardized payload format for both auth methods.
    """
    try:
        # Try admin token first
        admin_payload = await verify_admin_token(credentials)
        return admin_payload
    except HTTPException:
        # Fall back to JWT verification if admin token fails
        jwt_payload = await verify_jwt_token(credentials, verification_strategy)
        # Add auth_type for consistency
        jwt_payload["auth_type"] = "jwt"
        return jwt_payload

async def verify_admin_or_jwt_with_write_access(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    verification_strategy = Depends(jwt_verification_strategy)
) -> dict:
    """
    Dependency that verifies either admin token or JWT token with write access.
    Admin token supersedes JWT token access, granting maximum privileges.
    
    For JWT tokens, requires WRITE access level or higher.
    """
    try:
        # Try admin token first - admin always has write access
        admin_payload = await verify_admin_token(credentials)
        return admin_payload
    except HTTPException:
        # Fall back to JWT verification with write access requirement
        jwt_payload = await verify_access_level(AccessLevel.WRITE, credentials, verification_strategy)
        # Add auth_type for consistency
        jwt_payload["auth_type"] = "jwt"
        return jwt_payload

async def verify_admin_or_jwt_with_access_level(
    required_access_level: AccessLevel,
    credentials: HTTPAuthorizationCredentials,
    verification_strategy
) -> dict:
    """
    Dependency that verifies either admin token or JWT token with specific access level.
    Admin token supersedes JWT token access, granting maximum privileges.
    
    For JWT tokens, requires the specified access level or higher.
    """
    try:
        # Try admin token first - admin always has maximum access
        admin_payload = await verify_admin_token(credentials)
        return admin_payload
    except HTTPException:
        # Fall back to JWT verification with access level requirement
        jwt_payload = await verify_access_level(required_access_level, credentials, verification_strategy)
        # Add auth_type for consistency
        jwt_payload["auth_type"] = "jwt"
        return jwt_payload

# Convenience wrapper for commonly used access levels
async def verify_admin_or_jwt_with_read_access(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    verification_strategy = Depends(jwt_verification_strategy)
) -> dict:
    """
    Dependency that verifies either admin token or JWT token with read access.
    This is equivalent to verify_admin_or_jwt_token since READ is the base level.
    """
    return await verify_admin_or_jwt_with_access_level(AccessLevel.READ, credentials, verification_strategy)


def user_auth_org_ids(auth: dict) -> list[str]:
    """
    Get the organization IDs for the authenticated user.
    """
    # Handle both new format (claims.organizations) and old format (org_id)
    if "claims" in auth and "organizations" in auth["claims"]:
        return list(auth["claims"]["organizations"].keys())
    elif "org_id" in auth and auth["org_id"]:
        return [auth["org_id"]]
    else:
        return []

def user_has_collection_access(collection: Collection, auth: dict) -> bool:
    """
    Check if the authenticated user has access to the collection.
    Global admin users (auth_type="admin") have access to all collections.
    Organization users (including org admins) only have access to collections in their org.
    """
    # Global admin users have access to all collections
    if auth.get("auth_type") == "admin":
        return True
    
    # Organization users (including org admins) only have access to collections in their org
    user_org_ids = user_auth_org_ids(auth)
    return collection.auth_org_id in user_org_ids


async def verify_api_key_for_collection(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_async_db)
) -> tuple[Collection, ApiKey]:
    """
    Verify API key and return the associated collection and API key.
    For use with API key protected endpoints.
    """
    api_key = credentials.credentials
    
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
