from abc import ABC, abstractmethod

from mlcbakery.api.access_level import AccessLevel

ADMIN_ROLE_NAME = "Admin"

class JWTStrategy(ABC):
    """
    Abstract base class for JWT strategies.
    """


    def parse_token(self, token: str):
      payload = self.decode_token(token)

      if not payload:
        return None
    
      user_id = payload.get("sub", None)
      org_id = payload.get("org_id", None)
      org_role = payload.get("org_role", None)

      identifier = org_id if org_id else user_id
      is_organization = org_id is not None
      access_level = AccessLevel.ADMIN if not is_organization or org_role == ADMIN_ROLE_NAME else AccessLevel.READ

      return {
        "verified": True,
        "organization": is_organization,
        "identifier": identifier,
        "access_level": access_level
      }

    @abstractmethod
    def decode_token(self, token: str) -> dict:
        """
        Decode a JWT token into a payload.
        """
        raise NotImplementedError("Subclasses must implement this method.")
