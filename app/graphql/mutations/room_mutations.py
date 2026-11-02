import strawberry
from strawberry.types import Info
from typing import List, Optional

from app.db.session import AsyncSessionLocal
from app.services.room_service import (
    create_building,
    update_building,
    delete_building,
    reorder_buildings,
    create_floor,
    update_floor,
    delete_floor,
    reorder_floors,
    create_room_category,
    update_room_category,
    delete_room_category,
    create_room,
    create_bulk_rooms,
    update_room,
    update_room_status,
    delete_room,
    create_utility,
    update_utility,
    update_utility_status,
    delete_utility,
    list_rooms,
)
from app.graphql.types.room_types import (
    BuildingPayloadType,
    FloorType,
    RoomCategoryType,
    RoomType,
    UtilityType,
    RoomStatusEnum,
    UtilityStatusEnum,
    CreateBuildingInput,
    UpdateBuildingInput,
    ReorderBuildingsInput,
    CreateFloorInput,
    UpdateFloorInput,
    ReorderFloorsInput,
    CreateRoomCategoryInput,
    UpdateRoomCategoryInput,
    CreateRoomInput,
    CreateBulkRoomsInput,
    BulkRoomsPayload,
    UpdateRoomInput,
    CreateUtilityInput,
    UpdateUtilityInput,
)
from app.graphql.types.user_types import StatusPayload
from app.graphql.helpers import get_auth_context
from app.graphql.queries.room_queries import map_room, map_utility


@strawberry.type
class RoomMutation:
    # =========================================================================
    # Building Mutations
    # =========================================================================

    @strawberry.field(description="Creates a new building/wing in the property.")
    async def create_building(self, info: Info, input: CreateBuildingInput) -> BuildingPayloadType:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            b = await create_building(
                db,
                ctx,
                name=input.name,
                code=input.code,
                building_type=input.building_type or "HOTEL_TOWER",
                display_order=input.display_order,
            )
            return BuildingPayloadType(
                id=int(b.id),
                name=b.name,
                code=b.code,
                building_type=b.building_type,
                display_order=b.display_order,
                is_active=b.is_active,
                floor_count=0,
                room_count=0,
                utility_count=0,
            )

    @strawberry.field(description="Updates an existing building/wing.")
    async def update_building(self, info: Info, id: int, input: UpdateBuildingInput) -> BuildingPayloadType:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            b = await update_building(
                db,
                ctx,
                building_id=id,
                name=input.name,
                code=input.code,
                building_type=input.building_type,
                display_order=input.display_order,
                is_active=input.is_active,
            )
            return BuildingPayloadType(
                id=int(b.id),
                name=b.name,
                code=b.code,
                building_type=b.building_type,
                display_order=b.display_order,
                is_active=b.is_active,
            )

    @strawberry.field(description="Deletes (deactivates) a building if no active rooms exist in it.")
    async def delete_building(self, info: Info, id: int) -> StatusPayload:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            res = await delete_building(db, ctx, building_id=id)
            return StatusPayload(status=res["status"], message=res["message"])

    @strawberry.field(description="Reorders building tabs/cards across the property.")
    async def reorder_buildings(self, info: Info, input: ReorderBuildingsInput) -> List[BuildingPayloadType]:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            ordered = await reorder_buildings(db, ctx, building_ids=input.building_ids)
            return [
                BuildingPayloadType(
                    id=int(b.id),
                    name=b.name,
                    code=b.code,
                    building_type=b.building_type,
                    display_order=b.display_order,
                    is_active=b.is_active,
                )
                for b in ordered
            ]

    # =========================================================================
    # Floor Mutations
    # =========================================================================

    @strawberry.field(description="Creates a new floor in a specific building.")
    async def create_floor(self, info: Info, input: CreateFloorInput) -> FloorType:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            f = await create_floor(
                db,
                ctx,
                floor_number=input.floor_number,
                name=input.name,
                building_id=input.building_id,
            )
            return FloorType(
                id=int(f.id),
                floor_number=f.floor_number,
                name=f.name,
                building_id=int(f.building_id) if f.building_id else None,
                is_active=f.is_active,
                room_count=0,
                rooms=[],
                utilities=[],
            )

    @strawberry.field(description="Updates an existing floor, with optional building reassignment.")
    async def update_floor(self, info: Info, id: int, input: UpdateFloorInput) -> FloorType:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            f = await update_floor(
                db,
                ctx,
                floor_id=id,
                floor_number=input.floor_number,
                name=input.name,
                building_id=input.building_id,
                is_active=input.is_active,
            )
            return FloorType(
                id=int(f.id),
                floor_number=f.floor_number,
                name=f.name,
                building_id=int(f.building_id) if f.building_id else None,
                is_active=f.is_active,
                room_count=0,
                rooms=[],
                utilities=[],
            )

    @strawberry.field(description="Deletes (deactivates) a floor if no rooms exist on it.")
    async def delete_floor(self, info: Info, id: int) -> StatusPayload:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            res = await delete_floor(db, ctx, floor_id=id)
            return StatusPayload(status=res["status"], message=res["message"])

    @strawberry.field(description="Reorders floors vertically (Option 1: Lowest floor at bottom, highest on top).")
    async def reorder_floors(self, info: Info, input: ReorderFloorsInput) -> List[FloorType]:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            floors = await reorder_floors(
                db,
                ctx,
                building_id=input.building_id,
                floor_ids_bottom_to_top=input.floor_ids_bottom_to_top,
            )
            return [
                FloorType(
                    id=int(f.id),
                    floor_number=f.floor_number,
                    name=f.name,
                    building_id=int(f.building_id) if f.building_id else None,
                    is_active=f.is_active,
                    room_count=0,
                    rooms=[],
                    utilities=[],
                )
                for f in floors
            ]

    # =========================================================================
    # Room Category Mutations
    # =========================================================================

    @strawberry.field(description="Creates a room category with pricing and amenities.")
    async def create_room_category(self, info: Info, input: CreateRoomCategoryInput) -> RoomCategoryType:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            c = await create_room_category(
                db,
                ctx,
                name=input.name,
                base_price=input.base_price,
                code=input.code,
                max_adults=input.max_adults,
                max_children=input.max_children,
                amenities=input.amenities,
            )
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
                room_count=0,
            )

    @strawberry.field(description="Updates a room category.")
    async def update_room_category(self, info: Info, id: int, input: UpdateRoomCategoryInput) -> RoomCategoryType:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            c = await update_room_category(
                db,
                ctx,
                category_id=id,
                name=input.name,
                code=input.code,
                base_price=input.base_price,
                max_adults=input.max_adults,
                max_children=input.max_children,
                amenities=input.amenities,
                is_active=input.is_active,
            )
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
                room_count=0,
            )

    @strawberry.field(description="Deletes (deactivates) a room category if no rooms belong to it.")
    async def delete_room_category(self, info: Info, id: int) -> StatusPayload:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            res = await delete_room_category(db, ctx, category_id=id)
            return StatusPayload(status=res["status"], message=res["message"])

    # =========================================================================
    # Room Mutations (Free-Hand & Category Support)
    # =========================================================================

    @strawberry.field(
        description="Creates a room with either standard category or free-hand custom pricing & amenities."
    )
    async def create_room(self, info: Info, input: CreateRoomInput) -> RoomType:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            r = await create_room(
                db,
                ctx,
                floor_id=input.floor_id,
                room_number=input.room_number,
                category_id=input.category_id,
                custom_name=input.custom_name,
                custom_price=input.custom_price,
                custom_amenities=input.custom_amenities,
            )
            rooms_list = await list_rooms(db, ctx, floor_id=r.floor_id)
            for r_item in rooms_list:
                if r_item["room"].id == r.id:
                    return map_room(r_item)

            return RoomType(
                id=int(r.id),
                room_number=r.room_number,
                status=RoomStatusEnum(r.status),
                floor_id=int(r.floor_id),
                floor_name="",
                category_id=int(r.category_id) if r.category_id else None,
                category_name=r.custom_name or "Custom Room",
                base_price=float(r.custom_price) if r.custom_price is not None else 0.0,
                amenities=input.custom_amenities or [],
                custom_name=r.custom_name,
                custom_price=float(r.custom_price) if r.custom_price is not None else None,
                custom_amenities=input.custom_amenities or [],
                is_active=r.is_active,
            )

    @strawberry.field(description="Bulk generates rooms on a floor.")
    async def create_bulk_rooms(self, info: Info, input: CreateBulkRoomsInput) -> BulkRoomsPayload:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            res = await create_bulk_rooms(
                db,
                ctx,
                floor_id=input.floor_id,
                start_number=input.start_number,
                end_number=input.end_number,
                category_id=input.category_id,
                prefix=input.prefix,
                custom_price=input.custom_price,
            )
            rooms_list = await list_rooms(db, ctx, floor_id=input.floor_id)
            created_ids = {r.id for r in res["rooms"]}
            formatted_rooms = [map_room(item) for item in rooms_list if item["room"].id in created_ids]

            return BulkRoomsPayload(
                status=res["status"],
                message=res["message"],
                created_count=res["created_count"],
                rooms=formatted_rooms,
            )

    @strawberry.field(description="Updates room details or moves room across floors and buildings.")
    async def update_room(self, info: Info, id: int, input: UpdateRoomInput) -> RoomType:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            status_str = input.status.value if input.status else None
            cat_id = input.category_id if input.category_id is not None else "UNSET"
            c_name = input.custom_name if input.custom_name is not None else "UNSET"
            c_price = input.custom_price if input.custom_price is not None else "UNSET"
            c_amenities = input.custom_amenities if input.custom_amenities is not None else "UNSET"

            r = await update_room(
                db,
                ctx,
                room_id=id,
                floor_id=input.floor_id,
                category_id=cat_id,
                room_number=input.room_number,
                custom_name=c_name,
                custom_price=c_price,
                custom_amenities=c_amenities,
                status_val=status_str,
                is_active=input.is_active,
            )

            rooms_list = await list_rooms(db, ctx, floor_id=r.floor_id)
            for r_item in rooms_list:
                if r_item["room"].id == r.id:
                    return map_room(r_item)

            return RoomType(
                id=int(r.id),
                room_number=r.room_number,
                status=RoomStatusEnum(r.status),
                floor_id=int(r.floor_id),
                floor_name="",
                category_id=int(r.category_id) if r.category_id else None,
                category_name=r.custom_name or "Custom Room",
                base_price=float(r.custom_price) if r.custom_price is not None else 0.0,
                amenities=[],
                custom_name=r.custom_name,
                custom_price=float(r.custom_price) if r.custom_price is not None else None,
                custom_amenities=[],
                is_active=r.is_active,
            )

    @strawberry.field(description="Updates live PMS room status (AVAILABLE, OCCUPIED, CLEANING, MAINTENANCE).")
    async def update_room_status(self, info: Info, room_id: int, status: RoomStatusEnum) -> RoomType:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            r = await update_room_status(db, ctx, room_id=room_id, new_status=status.value)
            rooms_list = await list_rooms(db, ctx, floor_id=r.floor_id)
            for r_item in rooms_list:
                if r_item["room"].id == r.id:
                    return map_room(r_item)

            return RoomType(
                id=int(r.id),
                room_number=r.room_number,
                status=RoomStatusEnum(r.status),
                floor_id=int(r.floor_id),
                floor_name="",
                category_id=int(r.category_id) if r.category_id else None,
                category_name="Custom Room",
                base_price=0.0,
                amenities=[],
                is_active=r.is_active,
            )

    @strawberry.field(description="Deletes (deactivates) a room if not currently occupied.")
    async def delete_room(self, info: Info, id: int) -> StatusPayload:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            res = await delete_room(db, ctx, room_id=id)
            return StatusPayload(status=res["status"], message=res["message"])

    # =========================================================================
    # Utility Mutations
    # =========================================================================

    @strawberry.field(description="Creates a new utility/facility (pool, lawn, spa, gym, etc.).")
    async def create_utility(self, info: Info, input: CreateUtilityInput) -> UtilityType:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            u = await create_utility(
                db,
                ctx,
                building_id=input.building_id,
                name=input.name,
                utility_type=input.utility_type,
                floor_id=input.floor_id,
                status=input.status.value if input.status else "OPEN",
                capacity=input.capacity,
                operating_hours=input.operating_hours,
                is_bookable=input.is_bookable,
                rental_price=input.rental_price,
                amenities=input.amenities,
            )
            return map_utility(u)

    @strawberry.field(description="Updates an existing utility/facility.")
    async def update_utility(self, info: Info, id: int, input: UpdateUtilityInput) -> UtilityType:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            f_id = input.floor_id if input.floor_id is not None else "UNSET"
            u = await update_utility(
                db,
                ctx,
                utility_id=id,
                name=input.name,
                utility_type=input.utility_type,
                building_id=input.building_id,
                floor_id=f_id,
                status_val=input.status.value if input.status else None,
                capacity=input.capacity,
                operating_hours=input.operating_hours,
                is_bookable=input.is_bookable,
                rental_price=input.rental_price,
                amenities=input.amenities,
                is_active=input.is_active,
            )
            return map_utility(u)

    @strawberry.field(description="Toggles live status of a utility (OPEN, CLOSED, CLEANING, MAINTENANCE).")
    async def update_utility_status(self, info: Info, id: int, status: UtilityStatusEnum) -> UtilityType:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            u = await update_utility_status(db, ctx, utility_id=id, status_val=status.value)
            return map_utility(u)

    @strawberry.field(description="Deletes (deactivates) a utility.")
    async def delete_utility(self, info: Info, id: int) -> StatusPayload:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            res = await delete_utility(db, ctx, utility_id=id)
            return StatusPayload(status=res["status"], message=res["message"])
