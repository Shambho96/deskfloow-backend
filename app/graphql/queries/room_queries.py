import strawberry
from typing import Optional, List
from strawberry.types import Info

from app.db.session import AsyncSessionLocal
from app.services.room_service import (
    list_buildings,
    get_building_by_id,
    list_floors,
    get_floor_by_id,
    list_room_categories,
    get_room_category_by_id,
    list_rooms,
    get_room_by_id,
    list_utilities,
    get_campus_layout,
    get_hotel_layout,
)
from app.graphql.types.room_types import (
    BuildingPayloadType,
    CampusBuildingType,
    CampusLayoutPayload,
    FloorType,
    RoomCategoryType,
    RoomType,
    UtilityType,
    HotelLayoutPayload,
    RoomStatusEnum,
    UtilityStatusEnum,
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
        floor_number=r_dict.get("floor_number"),
        building_id=int(r_dict["building_id"]) if r_dict.get("building_id") else None,
        building_name=r_dict.get("building_name", "Main Tower"),
        category_id=int(r.category_id) if r.category_id else None,
        category_name=r_dict["category_name"],
        base_price=float(r_dict["base_price"]),
        amenities=r_dict.get("amenities", []),
        custom_name=r.custom_name,
        custom_price=float(r.custom_price) if r.custom_price is not None else None,
        custom_amenities=r_dict.get("custom_amenities", []),
        is_active=r.is_active,
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
        room_count=c_dict["room_count"],
    )


def map_utility(u) -> UtilityType:
    amenities_list = [a.strip() for a in u.amenities.split(",") if a.strip()] if u.amenities else []
    return UtilityType(
        id=int(u.id),
        name=u.name,
        utility_type=u.utility_type,
        status=UtilityStatusEnum(u.status),
        building_id=int(u.building_id),
        floor_id=int(u.floor_id) if u.floor_id else None,
        capacity=u.capacity,
        operating_hours=u.operating_hours,
        is_bookable=u.is_bookable,
        rental_price=float(u.rental_price) if u.rental_price is not None else None,
        amenities=amenities_list,
        is_active=u.is_active,
    )


def map_building(b_dict) -> BuildingPayloadType:
    b = b_dict["building"]
    return BuildingPayloadType(
        id=int(b.id),
        name=b.name,
        code=b.code,
        building_type=b.building_type,
        display_order=b.display_order,
        is_active=b.is_active,
        floor_count=b_dict.get("floor_count", 0),
        room_count=b_dict.get("room_count", 0),
        utility_count=b_dict.get("utility_count", 0),
    )


@strawberry.type
class RoomQuery:
    @strawberry.field(description="Lists all property buildings/wings in display order.")
    async def buildings(self, info: Info, is_active: bool = True) -> List[BuildingPayloadType]:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            data = await list_buildings(db, ctx, is_active=is_active)
            return [map_building(b) for b in data]

    @strawberry.field(description="Lists all floors with optional building filtering.")
    async def floors(self, info: Info, building_id: Optional[int] = None, is_active: bool = True) -> List[FloorType]:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            data = await list_floors(db, ctx, building_id=building_id, is_active=is_active)
            result = []
            for item in data:
                f = item["floor"]
                result.append(
                    FloorType(
                        id=int(f.id),
                        floor_number=f.floor_number,
                        name=f.name,
                        building_id=int(f.building_id) if f.building_id else None,
                        building_name=item.get("building_name", "Main Tower"),
                        is_active=f.is_active,
                        room_count=item["room_count"],
                        rooms=[],
                        utilities=[],
                    )
                )
            return result

    @strawberry.field(description="Lists all room categories, base pricing, and amenities.")
    async def room_categories(self, info: Info, is_active: bool = True) -> List[RoomCategoryType]:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            data = await list_room_categories(db, ctx, is_active=is_active)
            return [map_category(item) for item in data]

    @strawberry.field(description="Lists rooms with optional filtering by building, floor, category, or status.")
    async def rooms(
        self,
        info: Info,
        building_id: Optional[int] = None,
        floor_id: Optional[int] = None,
        category_id: Optional[int] = None,
        status: Optional[RoomStatusEnum] = None,
        is_active: bool = True,
    ) -> List[RoomType]:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            status_str = status.value if status else None
            data = await list_rooms(
                db,
                ctx,
                building_id=building_id,
                floor_id=floor_id,
                category_id=category_id,
                status_val=status_str,
                is_active=is_active,
            )
            return [map_room(item) for item in data]

    @strawberry.field(description="Lists utilities (pools, lawns, gyms, etc.) with optional filtering.")
    async def utilities(
        self,
        info: Info,
        building_id: Optional[int] = None,
        floor_id: Optional[int] = None,
        is_active: bool = True,
    ) -> List[UtilityType]:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            data = await list_utilities(db, ctx, building_id=building_id, floor_id=floor_id, is_active=is_active)
            return [map_utility(u) for u in data]

    @strawberry.field(
        description="Fetches full Hierarchical Campus Architecture: Buildings -> Floors -> Rooms + Utilities."
    )
    async def campus_layout(self, info: Info) -> CampusLayoutPayload:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            data = await get_campus_layout(db, ctx)

            campus_buildings = []
            for b_info in data["buildings"]:
                b = b_info["building"]
                b_payload = BuildingPayloadType(
                    id=int(b.id),
                    name=b.name,
                    code=b.code,
                    building_type=b.building_type,
                    display_order=b.display_order,
                    is_active=b.is_active,
                    floor_count=b_info["total_floors"],
                    room_count=b_info["total_rooms"],
                    utility_count=len(b_info.get("utilities", [])),
                )

                floors_list = []
                for f_info in b_info["floors"]:
                    f = f_info["floor"]
                    floor_rooms = [map_room(r) for r in f_info["rooms"]]
                    floor_utils = [map_utility(u) for u in f_info.get("utilities", [])]
                    floors_list.append(
                        FloorType(
                            id=int(f.id),
                            floor_number=f.floor_number,
                            name=f.name,
                            building_id=int(f.building_id) if f.building_id else None,
                            building_name=b.name,
                            is_active=f.is_active,
                            room_count=f_info["room_count"],
                            rooms=floor_rooms,
                            utilities=floor_utils,
                        )
                    )

                b_utilities = [map_utility(u) for u in b_info.get("utilities", [])]

                campus_buildings.append(
                    CampusBuildingType(
                        building=b_payload,
                        total_floors=b_info["total_floors"],
                        total_rooms=b_info["total_rooms"],
                        floors=floors_list,
                        utilities=b_utilities,
                    )
                )

            return CampusLayoutPayload(
                status=data["status"],
                total_buildings=data["total_buildings"],
                total_floors=data["total_floors"],
                total_rooms=data["total_rooms"],
                available_rooms=data["available_rooms"],
                occupied_rooms=data["occupied_rooms"],
                cleaning_rooms=data["cleaning_rooms"],
                maintenance_rooms=data["maintenance_rooms"],
                total_utilities=data["total_utilities"],
                buildings=campus_buildings,
            )

    @strawberry.field(description="Fetches legacy Front-Desk layout.")
    async def hotel_layout(self, info: Info) -> HotelLayoutPayload:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            data = await get_hotel_layout(db, ctx)
            floors_list = []
            for f_info in data["floors"]:
                f = f_info["floor"]
                floor_rooms = [map_room(r) for r in f_info["rooms"]]
                floors_list.append(
                    FloorType(
                        id=int(f.id),
                        floor_number=f.floor_number,
                        name=f.name,
                        building_id=int(f.building_id) if f.building_id else None,
                        building_name="Main Tower",
                        is_active=f.is_active,
                        room_count=f_info["room_count"],
                        rooms=floor_rooms,
                        utilities=[],
                    )
                )

            return HotelLayoutPayload(
                status=data["status"],
                total_floors=data["total_floors"],
                total_rooms=data["total_rooms"],
                available_rooms=data["available_rooms"],
                occupied_rooms=data["occupied_rooms"],
                cleaning_rooms=data["cleaning_rooms"],
                maintenance_rooms=data["maintenance_rooms"],
                floors=floors_list,
            )
