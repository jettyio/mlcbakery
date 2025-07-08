import os
from mlcbakery.auth.jwks_strategy import JWKSStrategy

JWT_ISSUER_JWKS_URL = os.getenv("JWT_ISSUER_JWKS_URL")

def jwt_verification_strategy():
    return JWKSStrategy(JWT_ISSUER_JWKS_URL)
