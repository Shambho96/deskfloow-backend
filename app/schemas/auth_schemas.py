from pydantic import BaseModel, EmailStr
from typing import Optional, List

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    selected_outlet_id: Optional[str] = None

class SwitchOutletRequest(BaseModel):
    target_outlet_id: str

class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    client_id: str
    active_outlet_id: str
    allowed_outlets: List[str]

class AuthResponse(BaseModel):
    status: str
    message: str
    user: UserResponse
