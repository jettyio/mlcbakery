from abc import ABC, abstractmethod

from mlcbakery.api.access_level import AccessLevel

ADMIN_ROLE_NAME = "Admin"

class JWTStrategy(ABC):
    """
    Abstract base class for JWT strategies.
    """


    def parse_token(self, token: str, auth_org_id: str | None = None):
      payload = self.decode_token(token)

      if not payload:
        return None
    
      user_id = payload.get("sub", None)
      org_id = payload.get("org_id", None)
      org_slug = payload.get("org_slug", None)
      org_role = payload.get("org_role", None)

      identifier = org_id if org_id else user_id
      is_organization = org_id is not None
      # TODO(jon): we need to fix this by using the permissions available in the claims of the JWT token
      access_level = AccessLevel.ADMIN if not is_organization or org_role == ADMIN_ROLE_NAME else AccessLevel.WRITE

      return {
        "verified": True,
        "organization": is_organization,
        "org_name": org_slug,
        "org_id": org_id,
        "identifier": identifier,
        "access_level": access_level,
        "claims": payload  # Include all JWT claims
      }