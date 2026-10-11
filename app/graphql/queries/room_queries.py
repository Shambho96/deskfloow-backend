import strawberry
from typing import Optional, List
from strawberry.types import Info

from app.db.session import AsyncSessionLocal
from app.services.room_service import (
    list_floors,
    get_floor_by_id,
    list_room_categories,
    get_room_category_by_id,
    list_rooms,
    get_room_by_id,
    get_hotel_layout
)
from app.graphql.types.room_types import (
    FloorType,
    RoomCategoryType,
    RoomType,
    HotelLayoutPayload,
    RoomStatusEnum
)
from app.graphql.helpers import get_auth_context

def map_room(r_dict) -> RoomType:
    r = r_dict["room"]
    return RoomType(
        id=int(r.id),
        room_number=r.room_number,
        status=RoomStatusEnum(r.status),
        floor_id=int(r.floor_id),
        floor_name=r_dict["floor_name"],
        category_id=int(r.category_id),
        category_name=r_dict["category_name"],
        base_price=float(r_dict["base_price"]),
        is_active=r.is_active
    )

def map_category(c_dict) -> RoomCategoryType:
    c = c_dict["category"]
    amenities_list = [a.strip() for a in c.amenities.split(",") if a.strip()] if c.amenities else []
    return RoomCategoryType(
        id=int(c.id),
        name=c.name,
        code=c.code,
        base_price=float(c.base_price),
        max_adults=c.max_adults,
        max_children=c.max_children,
        amenities=amenities_list,
        is_active=c.is_active,
        room_count=c_dict["room_count"]
    )

@strawberry.type
class RoomQuery:
    @strawberry.field(description="Lists all floors in active property.")
    async def floors(self, info: Info, is_active: bool = True) -> List[FloorType]:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            data = await list_floors(db, ctx, is_active=is_active)
            result = []
            for item in data:
                f = item["floor"]
                result.append(FloorType(
                    id=int(f.id),
                    floor_number=f.floor_number,
                    name=f.name,
                    is_active=f.is_active,
                    room_count=item["room_count"],
                    rooms=[]
                ))
            return result

    @strawberry.field(description="Lists all room categories, base pricing, and amenities.")
    async def room_categories(self, info: Info, is_active: bool = True) -> List[RoomCategoryType]:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            data = await list_room_categories(db, ctx, is_active=is_active)
            return [map_category(item) for item in data]

    @strawberry.field(description="Lists rooms with optional filtering by floor, category, or status.")
    async def rooms(
        self,
        info: Info,
        floor_id: Optional[int] = None,
        category_id: Optional[int] = None,
        status: Optional[RoomStatusEnum] = None,
        is_active: bool = True
    ) -> List[RoomType]:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            status_str = status.value if status else None
            data = await list_rooms(db, ctx, floor_id=floor_id, category_id=category_id, status_val=status_str, is_active=is_active)
            return [map_room(item) for item in data]

    @strawberry.field(description="Fetches full Front-Desk layout: all floors with all their nested rooms & real-time room status statistics in 1 single query.")
    async def hotel_layout(self, info: Info) -> HotelLayoutPayload:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            data = await get_hotel_layout(db, ctx)
            floors_list = []
            for f_item in data["floors"]:
                f = f_item["floor"]
                mapped_rooms = [map_room(r) for r in f_item["rooms"]]
                floors_list.append(FloorType(
                    id=int(f.id),
                    floor_number=f.floor_number,
                    name=f.name,
                    is_active=f.is_active,
                    room_count=f_item["room_count"],
                    rooms=mapped_rooms
                ))
            return HotelLayoutPayload(
                status="success",
                total_floors=data["total_floors"],
                total_rooms=data["total_rooms"],
                available_rooms=data["available_rooms"],
                occupied_rooms=data["occupied_rooms"],
                cleaning_rooms=data["cleaning_rooms"],
                maintenance_rooms=data["maintenance_rooms"],
                floors=floors_list
            )
