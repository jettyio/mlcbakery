import json
from mlcbakery.auth.jwt_strategy import JWTStrategy, ADMIN_ROLE_NAME

class PassthroughStrategy(JWTStrategy):
    """
    A strategy that does not modify the JWT token.
    This is useful for testing purposes or when no specific JWT processing is required.
    """

    def decode_token(self, jwt_payload: str) -> dict:
        """
        Process the JWT payload without any modifications.
        """
        print(jwt_payload)
        return json.loads(jwt_payload)

def sample_user_token(user_sub: str = "user_12345") -> str:
  return json.dumps({
      "sub": user_sub,
      "org_id": None,
      "org_role": None
  })

def sample_org_token(org_role: str = ADMIN_ROLE_NAME, org_id: str = "org_12345", user_sub: str = "user_12345") -> str:
    return json.dumps({
        "sub": user_sub,
        "org_id": org_id,
        "org_role": org_role
    })

def authorization_headers(bearer_token: str):
    """
    Helper function to create authorization headers for testing.
    :param bearer_token: The JWT token to use in the Authorization header.
    :return: A dictionary with the Authorization header.
    """
    return {"Authorization": f"Bearer {bearer_token}"}
