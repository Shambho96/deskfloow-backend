import strawberry
from strawberry.types import Info

from app.db.session import AsyncSessionLocal
from app.services.room_service import (
    create_floor,
    update_floor,
    delete_floor,
    create_room_category,
    update_room_category,
    delete_room_category,
    create_room,
    update_room,
    update_room_status,
    delete_room
)
from app.graphql.types.room_types import (
    FloorType,
    RoomCategoryType,
    RoomType,
    RoomStatusEnum,
    CreateFloorInput,
    UpdateFloorInput,
    CreateRoomCategoryInput,
    UpdateRoomCategoryInput,
    CreateRoomInput,
    UpdateRoomInput
)
from app.graphql.types.user_types import StatusPayload
from app.graphql.helpers import get_auth_context

@strawberry.type
class RoomMutation:
    # --- Floor Mutations ---
    @strawberry.field(description="Creates a new floor in active property.")
    async def create_floor(self, info: Info, input: CreateFloorInput) -> FloorType:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            f = await create_floor(db, ctx, floor_number=input.floor_number, name=input.name)
            return FloorType(id=int(f.id), floor_number=f.floor_number, name=f.name, is_active=f.is_active, room_count=0, rooms=[])

    @strawberry.field(description="Updates an existing floor.")
    async def update_floor(self, info: Info, id: int, input: UpdateFloorInput) -> FloorType:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            f = await update_floor(db, ctx, floor_id=id, floor_number=input.floor_number, name=input.name, is_active=input.is_active)
            return FloorType(id=int(f.id), floor_number=f.floor_number, name=f.name, is_active=f.is_active, room_count=0, rooms=[])

    @strawberry.field(description="Deletes (deactivates) a floor if no rooms exist on it.")
    async def delete_floor(self, info: Info, id: int) -> StatusPayload:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            res = await delete_floor(db, ctx, floor_id=id)
            return StatusPayload(status=res["status"], message=res["message"])

    # --- Room Category Mutations ---
    @strawberry.field(description="Creates a room category with pricing and amenities.")
    async def create_room_category(self, info: Info, input: CreateRoomCategoryInput) -> RoomCategoryType:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            c = await create_room_category(
                db, ctx,
                name=input.name,
                base_price=input.base_price,
                code=input.code,
                max_adults=input.max_adults,
                max_children=input.max_children,
                amenities=input.amenities
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
                room_count=0
            )

    @strawberry.field(description="Updates a room category.")
    async def update_room_category(self, info: Info, id: int, input: UpdateRoomCategoryInput) -> RoomCategoryType:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            c = await update_room_category(
                db, ctx,
                category_id=id,
                name=input.name,
                code=input.code,
                base_price=input.base_price,
                max_adults=input.max_adults,
                max_children=input.max_children,
                amenities=input.amenities,
                is_active=input.is_active
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
                room_count=0
            )

    @strawberry.field(description="Deletes (deactivates) a room category if no rooms belong to it.")
    async def delete_room_category(self, info: Info, id: int) -> StatusPayload:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            res = await delete_room_category(db, ctx, category_id=id)
            return StatusPayload(status=res["status"], message=res["message"])

    # --- Room Mutations ---
    @strawberry.field(description="Creates a new room on a specific floor and category.")
    async def create_room(self, info: Info, input: CreateRoomInput) -> RoomType:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            r = await create_room(db, ctx, floor_id=input.floor_id, category_id=input.category_id, room_number=input.room_number)
            # Re-fetch room data for formatted output
            from app.services.room_service import list_rooms
            rooms_list = await list_rooms(db, ctx, floor_id=r.floor_id)
            for r_item in rooms_list:
                if r_item["room"].id == r.id:
                    return RoomType(
                        id=int(r.id),
                        room_number=r.room_number,
                        status=RoomStatusEnum(r.status),
                        floor_id=int(r.floor_id),
                        floor_name=r_item["floor_name"],
                        category_id=int(r.category_id),
                        category_name=r_item["category_name"],
                        base_price=float(r_item["base_price"]),
                        is_active=r.is_active
                    )
            return RoomType(
                id=int(r.id),
                room_number=r.room_number,
                status=RoomStatusEnum(r.status),
                floor_id=int(r.floor_id),
                floor_name="",
                category_id=int(r.category_id),
                category_name="",
                base_price=0.0,
                is_active=r.is_active
            )

    @strawberry.field(description="Updates room number, floor, category, or status.")
    async def update_room(self, info: Info, id: int, input: UpdateRoomInput) -> RoomType:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            status_str = input.status.value if input.status else None
            r = await update_room(
                db, ctx,
                room_id=id,
                floor_id=input.floor_id,
                category_id=input.category_id,
                room_number=input.room_number,
                status_val=status_str,
                is_active=input.is_active
            )
            from app.services.room_service import list_rooms
            rooms_list = await list_rooms(db, ctx, floor_id=r.floor_id)
            for r_item in rooms_list:
                if r_item["room"].id == r.id:
                    return RoomType(
                        id=int(r.id),
                        room_number=r.room_number,
                        status=RoomStatusEnum(r.status),
                        floor_id=int(r.floor_id),
                        floor_name=r_item["floor_name"],
                        category_id=int(r.category_id),
                        category_name=r_item["category_name"],
                        base_price=float(r_item["base_price"]),
                        is_active=r.is_active
                    )
            return RoomType(
                id=int(r.id),
                room_number=r.room_number,
                status=RoomStatusEnum(r.status),
                floor_id=int(r.floor_id),
                floor_name="",
                category_id=int(r.category_id),
                category_name="",
                base_price=0.0,
                is_active=r.is_active
            )

    @strawberry.field(description="Updates live PMS room status (AVAILABLE, OCCUPIED, CLEANING, MAINTENANCE).")
    async def update_room_status(self, info: Info, room_id: int, status: RoomStatusEnum) -> RoomType:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            r = await update_room_status(db, ctx, room_id=room_id, new_status=status.value)
            from app.services.room_service import list_rooms
            rooms_list = await list_rooms(db, ctx, floor_id=r.floor_id)
            for r_item in rooms_list:
                if r_item["room"].id == r.id:
                    return RoomType(
                        id=int(r.id),
                        room_number=r.room_number,
                        status=RoomStatusEnum(r.status),
                        floor_id=int(r.floor_id),
                        floor_name=r_item["floor_name"],
                        category_id=int(r.category_id),
                        category_name=r_item["category_name"],
                        base_price=float(r_item["base_price"]),
                        is_active=r.is_active
                    )
            return RoomType(
                id=int(r.id),
                room_number=r.room_number,
                status=RoomStatusEnum(r.status),
                floor_id=int(r.floor_id),
                floor_name="",
                category_id=int(r.category_id),
                category_name="",
                base_price=0.0,
                is_active=r.is_active
            )

    @strawberry.field(description="Deletes (deactivates) a room if not currently occupied.")
    async def delete_room(self, info: Info, id: int) -> StatusPayload:
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as db:
            res = await delete_room(db, ctx, room_id=id)
            return StatusPayload(status=res["status"], message=res["message"])
