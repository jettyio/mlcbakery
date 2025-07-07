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
):
    """
    Dependency that verifies the provided admin token against the one stored
    in environment variables.

    This works over both HTTP and HTTPS as the Bearer token authentication
    is transport protocol agnostic. The token is sent in the Authorization header
    which is preserved by the reverse proxy as configured in Caddyfile.
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
    return credentials  # Or return True, or nothing if just validation is needed
