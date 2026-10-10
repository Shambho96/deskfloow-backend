from pydantic import BaseModel, EmailStr
from typing import Optional, List, Union

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    selected_outlet_id: Optional[Union[int, str]] = None

class SwitchOutletRequest(BaseModel):
    target_outlet_id: Union[int, str]

class UserResponse(BaseModel):
    id: Union[int, str]
    name: str
    email: str
    role: str
    client_id: Union[int, str]
    active_outlet_id: Union[int, str]
    allowed_outlets: List[Union[int, str]]

class AuthResponse(BaseModel):
    status: str
    message: str
    access_token: Optional[str] = None
    user: UserResponse
