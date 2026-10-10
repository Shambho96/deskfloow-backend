from pydantic import BaseModel
from typing import Optional, List, Union

class UserContext(BaseModel):
    user_id: Union[int, str]
    client_id: Union[int, str]
    outlet_id: Union[int, str]
    role: str
    email: Optional[str] = None
    name: Optional[str] = None
    allowed_outlets: List[Union[int, str]] = []

    @property
    def is_owner(self) -> bool:
        return self.role == "OWNER"

    @property
    def is_manager(self) -> bool:
        return self.role in ("OWNER", "MANAGER")
