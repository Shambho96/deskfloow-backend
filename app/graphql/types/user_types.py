import strawberry
from typing import Optional, List
from datetime import datetime

@strawberry.type
class UserType:
    id: int
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str
    client_id: int
    can_login: bool
    is_active: bool
    assigned_outlet_ids: List[int]
    created_at: str

@strawberry.type
class UserListPayload:
    status: str
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool
    users: List[UserType]

@strawberry.type
class StatusPayload:
    status: str
    message: str

@strawberry.input
class CreateUserInput:
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str
    assigned_outlet_ids: Optional[List[int]] = None
    password: Optional[str] = None

@strawberry.input
class UpdateUserInput:
    user_id: int
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    assigned_outlet_ids: Optional[List[int]] = None
    password: Optional[str] = None
