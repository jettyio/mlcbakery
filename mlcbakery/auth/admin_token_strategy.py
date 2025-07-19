import os
import secrets
from mlcbakery.api.access_level import AccessLevel, AccessType

class AdminTokenStrategy:
    """
    Strategy for authenticating using the admin token.
    """
    def __init__(self, admin_token: str):
        self.admin_token = admin_token

    def parse_token(self, token: str, _required_access_level: AccessLevel = AccessLevel.READ):
        if not self.admin_token or self.admin_token == "":
            return None

        is_token_valid = secrets.compare_digest(token, self.admin_token)
        if not is_token_valid:
            return None

        return {
            "verified": True,
            "access_type": AccessType.ADMIN,
            "auth_type": "admin",
            "access_level": AccessLevel.ADMIN,
            "identifier": "admin",
        } 
