from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Union
from datetime import datetime

class UserCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Full name of the team member")
    email: Optional[EmailStr] = Field(None, description="Email address (Required for Manager/Owner logins)")
    phone: Optional[str] = Field(None, description="Phone number")
    role: str = Field(..., description="Role: MANAGER or STAFF")
    assigned_outlet_ids: Optional[List[Union[int, str]]] = Field(None, description="List of outlet IDs assigned to this member (Defaults to active outlet if omitted)")
    password: Optional[str] = Field(None, min_length=6, description="Password for login (Required if Manager)")

class UserUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    assigned_outlet_ids: Optional[List[Union[int, str]]] = None
    password: Optional[str] = Field(None, min_length=6)

class UserMemberResponse(BaseModel):
    id: Union[int, str]
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str
    client_id: Union[int, str]
    can_login: bool
    is_active: bool
    assigned_outlet_ids: List[Union[int, str]] = []
    created_at: datetime

    class Config:
        from_attributes = True

class UserListResponse(BaseModel):
    status: str = "success"
    total: int
    users: List[UserMemberResponse]
