import os
import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

from mlcbakery.jwt import jwt_verification_strategy
from mlcbakery.api.access_level import AccessLevel

logging.basicConfig(level=logging.INFO)

# Define the bearer scheme
bearer_scheme = HTTPBearer()

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
    token = credentials.credentials

    parsed_token = verification_strategy.parse_token(token)

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

    if jwt_payload["access_level"].value < required_access_level.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access level {required_access_level.name} required.",
        )

    return jwt_payload  # Return the payload for further use if needed

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
        "identifier": "admin"
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
