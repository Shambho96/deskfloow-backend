import strawberry
from typing import Optional, List
from enum import Enum

@strawberry.enum
class RoomStatusEnum(Enum):
    AVAILABLE = "AVAILABLE"
    OCCUPIED = "OCCUPIED"
    CLEANING = "CLEANING"
    MAINTENANCE = "MAINTENANCE"

@strawberry.type
class RoomType:
    id: int
    room_number: str
    status: RoomStatusEnum
    floor_id: int
    floor_name: str
    category_id: int
    category_name: str
    base_price: float
    is_active: bool

@strawberry.type
class FloorType:
    id: int
    floor_number: int
    name: str
    is_active: bool
    room_count: int
    rooms: List[RoomType]

@strawberry.type
class RoomCategoryType:
    id: int
    name: str
    code: Optional[str] = None
    base_price: float
    max_adults: int
    max_children: int
    amenities: List[str]
    is_active: bool
    room_count: int

@strawberry.type
class HotelLayoutPayload:
    status: str
    total_floors: int
    total_rooms: int
    available_rooms: int
    occupied_rooms: int
    cleaning_rooms: int
    maintenance_rooms: int
    floors: List[FloorType]

@strawberry.input
class CreateFloorInput:
    floor_number: int
    name: str

@strawberry.input
class UpdateFloorInput:
    floor_number: Optional[int] = None
    name: Optional[str] = None
    is_active: Optional[bool] = None

@strawberry.input
class CreateRoomCategoryInput:
    name: str
    base_price: float
    code: Optional[str] = None
    max_adults: int = 2
    max_children: int = 1
    amenities: Optional[List[str]] = None

@strawberry.input
class UpdateRoomCategoryInput:
    name: Optional[str] = None
    code: Optional[str] = None
    base_price: Optional[float] = None
    max_adults: Optional[int] = None
    max_children: Optional[int] = None
    amenities: Optional[List[str]] = None
    is_active: Optional[bool] = None

@strawberry.input
class CreateRoomInput:
    floor_id: int
    category_id: int
    room_number: str

@strawberry.input
class UpdateRoomInput:
    floor_id: Optional[int] = None
    category_id: Optional[int] = None
    room_number: Optional[str] = None
    status: Optional[RoomStatusEnum] = None
    is_active: Optional[bool] = None
