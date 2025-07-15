from abc import ABC
from gzip import READ

from mlcbakery.api.access_level import AccessLevel

ADMIN_ROLE_NAME = "Admin"

class JWTStrategy(ABC):
    """
    Abstract base class for JWT strategies.
    """


    def parse_token(self, token: str, required_access_level: AccessLevel = AccessLevel.READ):
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
      is_organization_scope = org_id is not None
      is_personal_scope = org_id is None

      # Map org_role to access level
      if org_role == ADMIN_ROLE_NAME:
          access_level = AccessLevel.ADMIN
      elif org_role == "Writer":
          access_level = AccessLevel.WRITE
      elif org_role == "Member":
          access_level = AccessLevel.READ
      else:
          access_level = AccessLevel.READ

      has_access = is_personal_scope or access_level.value >= required_access_level.value

      print(f"JWTStrategy.parse_token: returning payload")
      return {
        "verified": True,
        "has_access": has_access,
        "organization": is_organization_scope,
        "org_id": org_id,
        "identifier": identifier,
        "access_level": access_level,
        "claims": payload  # Include all JWT claims
      }