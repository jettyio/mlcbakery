import os
import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWTError

logging.basicConfig(level=logging.INFO)

# Define the bearer scheme
bearer_scheme = HTTPBearer()

JWT_ISSUER_JWKS_URL = os.getenv("JWT_ISSUER_JWKS_URL")

async def verify_jwt_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    """
    Dependency that verifies the provided JWT token.

    This works over both HTTP and HTTPS as the Bearer token authentication
    is transport protocol agnostic. The token is sent in the Authorization header
    which is preserved by the reverse proxy as configured in Caddyfile.
    """
    print(credentials)
    print(credentials.credentials)

    token = credentials.credentials
    jwks_client = PyJWKClient(JWT_ISSUER_JWKS_URL)

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={
                "verify_aud": False,  # Adjust as needed
            }
        )
        print(f"JWT payload: {payload}")
        org_id = payload.get("org_id", None)
        user_id = payload.get("sub", None)

        return {
            "verified": True,
            "organization": org_id is not None,
            "identifier": org_id if org_id else user_id
        }
    except PyJWTError as e:
        print(f"JWT verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired JWT token"
        )

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
    print(credentials)
    print(credentials.credentials)
    # Read the token *inside* the function
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
