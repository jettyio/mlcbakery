from enum import Enum

class AccessLevel(Enum):
  READ = 1
  # CONTRIBUTE = 2 Hypothetical access level, perhaps for those who can trigger actions, but not change metadata
  WRITE = 3
  ADMIN = 4
