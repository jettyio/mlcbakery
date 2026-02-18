import logging
import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWTError
from fastapi import HTTPException, status
from mlcbakery.auth.jwt_strategy import JWTStrategy

logger = logging.getLogger(__name__)

class JWKSStrategy(JWTStrategy):
    """
    Strategy for JWT authentication using JWKS (JSON Web Key Set).
    This strategy fetches the JWKS from a specified URL and uses it to verify JWT tokens.
    """

    def __init__(self, jwks_url: str):
        self.jwks_url = jwks_url
        self.jwks_client = PyJWKClient(jwks_url)

    def get_signing_key(self, token: str):
        """
        Get the signing key for the provided JWT token.
        """
        return self.jwks_client.get_signing_key_from_jwt(token).key

    def decode_token(self, token: str):
        """
        Decode the JWT token using the signing key.
        """
        try:
          signing_key = self.get_signing_key(token)
          return jwt.decode(
              token,
              signing_key,
              algorithms=["RS256"],
              options={"verify_aud": False}  # Adjust as needed
          )
        except Exception as e:
          if not isinstance(e, PyJWTError):
              logger.error(f"JWKS token validation error: {type(e).__name__}: {e}")
          return None
