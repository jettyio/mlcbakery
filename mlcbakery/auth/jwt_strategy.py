from abc import ABC

from mlcbakery.api.access_level import AccessLevel, AccessType

ADMIN_ROLE_NAME = "org:admin"

class JWTStrategy(ABC):
    """
    Abstract base class for JWT strategies.
    """

    @abstractmethod
    def decode_token(self, token: str) -> dict:
        """
        Decode the JWT token using the signing key.
        """
        raise NotImplementedError("Subclasses must implement this method")

    def parse_token(self, token: str):
      try:
        payload = self.decode_token(token)
      except Exception as e:
        return None

      if not payload:
        return None
  
      user_id = payload.get("sub", None)
      org_id = payload.get("org_id", None)
      org_role = payload.get("org_role", None)

      identifier = org_id if org_id else user_id
      access_type = AccessType.ORG if org_id else AccessType.PERSONAL

      # Map org_role to access level
      if org_role == ADMIN_ROLE_NAME:
          access_level = AccessLevel.ADMIN
      elif org_role == "org:admin":
          access_level = AccessLevel.WRITE
      elif org_role == "org:member":
          access_level = AccessLevel.READ
      else:
          access_level = AccessLevel.READ

      return {
        "verified": True,
        "org_id": org_id,
        "identifier": identifier,
        "access_level": access_level,
        "access_type": access_type,
        "auth_type": "jwt",
        "claims": payload  # Include all JWT claims
      }
