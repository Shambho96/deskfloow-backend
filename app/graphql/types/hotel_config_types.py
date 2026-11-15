import strawberry
from typing import Optional, List


@strawberry.type
class HotelSpecialRequestType:
    id: int
    client_id: int
    outlet_id: Optional[int]
    code: str
    label: str
    category: str
    is_chargeable: bool
    price: float
    icon: str
    display_order: int
    is_active: bool


@strawberry.input
class HotelSpecialRequestInput:
    code: str
    label: str
    category: Optional[str] = "ROOM"
    is_chargeable: Optional[bool] = False
    price: Optional[float] = 0.0
    icon: Optional[str] = "Sparkles"
    display_order: Optional[int] = 0
    is_active: Optional[bool] = True


@strawberry.type
class HotelGuestTagType:
    id: int
    client_id: int
    outlet_id: Optional[int]
    name: str
    color: str
    category: str
    description: Optional[str] = None
    display_order: int
    is_active: bool


@strawberry.input
class HotelGuestTagInput:
    name: str
    color: Optional[str] = "primary"
    category: Optional[str] = "PROFILE"
    description: Optional[str] = None
    display_order: Optional[int] = 0
    is_active: Optional[bool] = True
