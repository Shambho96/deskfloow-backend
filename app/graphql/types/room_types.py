import strawberry
from typing import Optional, List
from enum import Enum


@strawberry.enum
class RoomStatusEnum(Enum):
    AVAILABLE = "AVAILABLE"
    OCCUPIED = "OCCUPIED"
    CLEANING = "CLEANING"
    MAINTENANCE = "MAINTENANCE"


@strawberry.enum
class UtilityStatusEnum(Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CLEANING = "CLEANING"
    MAINTENANCE = "MAINTENANCE"


@strawberry.type
class UtilityType:
    id: int
    name: str
    utility_type: str
    status: UtilityStatusEnum
    building_id: int
    floor_id: Optional[int] = None
    capacity: Optional[int] = None
    operating_hours: Optional[str] = None
    is_bookable: bool = False
    rental_price: Optional[float] = None
    amenities: List[str] = strawberry.field(default_factory=list)
    is_active: bool = True


@strawberry.type
class RoomType:
    id: int
    room_number: str
    status: RoomStatusEnum
    floor_id: int
    floor_name: str
    floor_number: Optional[int] = None
    building_id: Optional[int] = None
    building_name: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    base_price: float
    amenities: List[str] = strawberry.field(default_factory=list)
    custom_name: Optional[str] = None
    custom_price: Optional[float] = None
    custom_amenities: List[str] = strawberry.field(default_factory=list)
    is_active: bool = True


@strawberry.type
class FloorType:
    id: int
    floor_number: int
    name: str
    building_id: Optional[int] = None
    building_name: Optional[str] = None
    is_active: bool
    room_count: int
    rooms: List[RoomType] = strawberry.field(default_factory=list)
    utilities: List[UtilityType] = strawberry.field(default_factory=list)


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
class BuildingPayloadType:
    id: int
    name: str
    code: Optional[str] = None
    building_type: str
    display_order: int
    is_active: bool
    floor_count: int = 0
    room_count: int = 0
    utility_count: int = 0


@strawberry.type
class CampusBuildingType:
    building: BuildingPayloadType
    total_floors: int
    total_rooms: int
    floors: List[FloorType] = strawberry.field(default_factory=list)
    utilities: List[UtilityType] = strawberry.field(default_factory=list)


@strawberry.type
class CampusLayoutPayload:
    status: str
    total_buildings: int
    total_floors: int
    total_rooms: int
    available_rooms: int
    occupied_rooms: int
    cleaning_rooms: int
    maintenance_rooms: int
    total_utilities: int
    buildings: List[CampusBuildingType]


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


# =========================================================================
# Inputs
# =========================================================================


@strawberry.input
class CreateBuildingInput:
    name: str
    code: Optional[str] = None
    building_type: Optional[str] = "HOTEL_TOWER"
    display_order: Optional[int] = None


@strawberry.input
class UpdateBuildingInput:
    name: Optional[str] = None
    code: Optional[str] = None
    building_type: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


@strawberry.input
class ReorderBuildingsInput:
    building_ids: List[int]


@strawberry.input
class CreateFloorInput:
    floor_number: int
    name: str
    building_id: Optional[int] = None


@strawberry.input
class UpdateFloorInput:
    floor_number: Optional[int] = None
    name: Optional[str] = None
    building_id: Optional[int] = None
    is_active: Optional[bool] = None


@strawberry.input
class ReorderFloorsInput:
    building_id: int
    floor_ids_bottom_to_top: List[int]


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
    room_number: str
    category_id: Optional[int] = None
    custom_name: Optional[str] = None
    custom_price: Optional[float] = None
    custom_amenities: Optional[List[str]] = None


@strawberry.input
class UpdateRoomInput:
    floor_id: Optional[int] = None
    category_id: Optional[int] = None
    room_number: Optional[str] = None
    custom_name: Optional[str] = None
    custom_price: Optional[float] = None
    custom_amenities: Optional[List[str]] = None
    status: Optional[RoomStatusEnum] = None
    is_active: Optional[bool] = None


@strawberry.input
class CreateBulkRoomsInput:
    floor_id: int
    start_number: int
    end_number: int
    category_id: Optional[int] = None
    prefix: Optional[str] = None
    custom_price: Optional[float] = None


@strawberry.type
class BulkRoomsPayload:
    status: str
    message: str
    created_count: int
    rooms: List[RoomType]


@strawberry.input
class CreateUtilityInput:
    building_id: int
    name: str
    utility_type: str
    floor_id: Optional[int] = None
    status: Optional[UtilityStatusEnum] = UtilityStatusEnum.OPEN
    capacity: Optional[int] = None
    operating_hours: Optional[str] = None
    is_bookable: bool = False
    rental_price: Optional[float] = None
    amenities: Optional[List[str]] = None


@strawberry.input
class UpdateUtilityInput:
    name: Optional[str] = None
    utility_type: Optional[str] = None
    building_id: Optional[int] = None
    floor_id: Optional[int] = None
    status: Optional[UtilityStatusEnum] = None
    capacity: Optional[int] = None
    operating_hours: Optional[str] = None
    is_bookable: Optional[bool] = None
    rental_price: Optional[float] = None
    amenities: Optional[List[str]] = None
    is_active: Optional[bool] = None
