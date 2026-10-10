from pydantic import BaseModel
from typing import Optional, List

class UserContext(BaseModel):
    user_id: str
    client_id: str
    outlet_id: str
    role: str
    email: Optional[str] = None
    name: Optional[str] = None
    allowed_outlets: List[str] = []

    @property
    def is_owner(self) -> bool:
        return self.role == "OWNER"

    @property
    def is_manager(self) -> bool:
        return self.role in ("OWNER", "MANAGER")
