from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from fastapi import HTTPException, status
from typing import Optional, List, Dict, Any, Union
from decimal import Decimal

from app.models import Floor, RoomCategory, Room, Building, Utility
from app.core.context import UserContext

VALID_ROOM_STATUSES = ("AVAILABLE", "OCCUPIED", "CLEANING", "MAINTENANCE")
VALID_UTILITY_STATUSES = ("OPEN", "CLOSED", "CLEANING", "MAINTENANCE")
VALID_BUILDING_TYPES = (
    "HOTEL_TOWER",
    "VILLAS",
    "RESORT_WING",
    "OUTDOOR_GROUNDS",
    "FACILITY_BLOCK",
    "OTHER",
)


def ensure_authorized(ctx: UserContext):
    if ctx.role not in ("OWNER", "MANAGER"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Owners and Managers have access to hotel layout and room operations.",
        )


async def _get_or_create_default_building(db: AsyncSession, ctx: UserContext) -> Building:
    result = await db.execute(
        select(Building)
        .where(Building.outlet_id == ctx.outlet_id, Building.is_active == True)
        .order_by(Building.display_order.asc(), Building.id.asc())
    )
    b = result.scalars().first()
    if not b:
        b = Building(
            client_id=ctx.client_id,
            outlet_id=ctx.outlet_id,
            name="Main Tower",
            code="MT",
            building_type="HOTEL_TOWER",
            display_order=1,
            is_active=True,
        )
        db.add(b)
        await db.commit()
        await db.refresh(b)
    return b


# =========================================================================
# Building Services
# =========================================================================


async def create_building(
    db: AsyncSession,
    ctx: UserContext,
    name: str,
    code: Optional[str] = None,
    building_type: str = "HOTEL_TOWER",
    display_order: Optional[int] = None,
) -> Building:
    ensure_authorized(ctx)
    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Building name cannot be empty.",
        )

    b_type = building_type.upper() if building_type else "HOTEL_TOWER"
    if b_type not in VALID_BUILDING_TYPES:
        b_type = "HOTEL_TOWER"

    # Check for name uniqueness in outlet
    existing = await db.execute(
        select(Building).where(
            Building.outlet_id == ctx.outlet_id,
            Building.name.ilike(clean_name),
            Building.is_active == True,
        )
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Building with name "{clean_name}" already exists in this property.',
        )

    if display_order is None:
        max_order_res = await db.execute(
            select(func.coalesce(func.max(Building.display_order), 0)).where(
                Building.outlet_id == ctx.outlet_id, Building.is_active == True
            )
        )
        display_order = (max_order_res.scalar() or 0) + 1

    building = Building(
        client_id=ctx.client_id,
        outlet_id=ctx.outlet_id,
        name=clean_name,
        code=code.strip().upper() if code else None,
        building_type=b_type,
        display_order=display_order,
        is_active=True,
    )
    db.add(building)
    await db.commit()
    await db.refresh(building)
    return building


async def list_buildings(db: AsyncSession, ctx: UserContext, is_active: bool = True) -> List[Dict[str, Any]]:
    ensure_authorized(ctx)

    # Subquery floor count
    floors_count_subq = (
        select(Floor.building_id, func.count(Floor.id).label("floor_count"))
        .where(Floor.outlet_id == ctx.outlet_id, Floor.is_active == True)
        .group_by(Floor.building_id)
        .subquery()
    )

    # Subquery utility count
    utils_count_subq = (
        select(Utility.building_id, func.count(Utility.id).label("utility_count"))
        .where(Utility.outlet_id == ctx.outlet_id, Utility.is_active == True)
        .group_by(Utility.building_id)
        .subquery()
    )

    # Subquery room count across floors of the building
    rooms_count_subq = (
        select(Floor.building_id, func.count(Room.id).label("room_count"))
        .join(Room, Floor.id == Room.floor_id)
        .where(Room.outlet_id == ctx.outlet_id, Room.is_active == True)
        .group_by(Floor.building_id)
        .subquery()
    )

    query = (
        select(
            Building,
            func.coalesce(floors_count_subq.c.floor_count, 0).label("floor_count"),
            func.coalesce(utils_count_subq.c.utility_count, 0).label("utility_count"),
            func.coalesce(rooms_count_subq.c.room_count, 0).label("room_count"),
        )
        .outerjoin(floors_count_subq, Building.id == floors_count_subq.c.building_id)
        .outerjoin(utils_count_subq, Building.id == utils_count_subq.c.building_id)
        .outerjoin(rooms_count_subq, Building.id == rooms_count_subq.c.building_id)
        .where(Building.outlet_id == ctx.outlet_id, Building.is_active == is_active)
        .order_by(Building.display_order.asc(), Building.id.asc())
    )

    res = await db.execute(query)
    rows = res.all()

    # If no buildings exist yet, automatically create default Main Tower
    if not rows and is_active:
        default_b = await _get_or_create_default_building(db, ctx)
        return [
            {
                "building": default_b,
                "floor_count": 0,
                "utility_count": 0,
                "room_count": 0,
            }
        ]

    return [
        {
            "building": b,
            "floor_count": f_cnt,
            "utility_count": u_cnt,
            "room_count": r_cnt,
        }
        for b, f_cnt, u_cnt, r_cnt in rows
    ]


async def get_building_by_id(db: AsyncSession, ctx: UserContext, building_id: int) -> Building:
    ensure_authorized(ctx)
    building = await db.get(Building, building_id)
    if not building or building.outlet_id != int(ctx.outlet_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Building with ID {building_id} not found.",
        )
    return building


async def update_building(
    db: AsyncSession,
    ctx: UserContext,
    building_id: int,
    name: Optional[str] = None,
    code: Optional[str] = None,
    building_type: Optional[str] = None,
    display_order: Optional[int] = None,
    is_active: Optional[bool] = None,
) -> Building:
    ensure_authorized(ctx)
    building = await get_building_by_id(db, ctx, building_id)

    if name is not None:
        clean_name = name.strip()
        if not clean_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Building name cannot be empty.",
            )
        existing = await db.execute(
            select(Building).where(
                Building.outlet_id == ctx.outlet_id,
                Building.name.ilike(clean_name),
                Building.id != building_id,
                Building.is_active == True,
            )
        )
        if existing.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Building with name "{clean_name}" already exists in this property.',
            )
        building.name = clean_name

    if code is not None:
        building.code = code.strip().upper() if code else None

    if building_type is not None:
        b_type = building_type.upper()
        if b_type in VALID_BUILDING_TYPES:
            building.building_type = b_type

    if display_order is not None:
        building.display_order = display_order

    if is_active is not None:
        building.is_active = is_active

    await db.commit()
    await db.refresh(building)
    return building


async def delete_building(db: AsyncSession, ctx: UserContext, building_id: int) -> Dict[str, Any]:
    ensure_authorized(ctx)
    building = await get_building_by_id(db, ctx, building_id)

    # Check active rooms across floors in this building
    room_count_res = await db.execute(
        select(func.count(Room.id))
        .join(Floor, Room.floor_id == Floor.id)
        .where(Floor.building_id == building_id, Room.is_active == True)
    )
    room_count = room_count_res.scalar() or 0
    if room_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Cannot delete building "{building.name}" because {room_count} active room(s) reside in it. Move or delete rooms first.',
        )

    # Check total active buildings count
    total_b_res = await db.execute(
        select(func.count(Building.id)).where(Building.outlet_id == ctx.outlet_id, Building.is_active == True)
    )
    if (total_b_res.scalar() or 0) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the only building in this property. A hotel must have at least one building.",
        )

    building.is_active = False
    await db.commit()
    return {
        "status": "success",
        "message": f'Building "{building.name}" removed successfully.',
    }


async def reorder_buildings(db: AsyncSession, ctx: UserContext, building_ids: List[int]) -> List[Building]:
    ensure_authorized(ctx)
    if not building_ids:
        return []

    buildings_res = await db.execute(
        select(Building).where(
            Building.id.in_(building_ids),
            Building.outlet_id == ctx.outlet_id,
            Building.is_active == True,
        )
    )
    buildings_map = {b.id: b for b in buildings_res.scalars().all()}

    # Update order
    ordered_list = []
    for idx, bid in enumerate(building_ids):
        b = buildings_map.get(bid)
        if b:
            b.display_order = idx + 1
            ordered_list.append(b)

    await db.commit()
    for b in ordered_list:
        await db.refresh(b)
    return ordered_list


# =========================================================================
# Floor Services
# =========================================================================


async def create_floor(
    db: AsyncSession,
    ctx: UserContext,
    floor_number: int,
    name: str,
    building_id: Optional[int] = None,
) -> Floor:
    ensure_authorized(ctx)

    if building_id is None:
        def_b = await _get_or_create_default_building(db, ctx)
        building_id = def_b.id
    else:
        # Validate building exists and belongs to outlet
        b = await db.get(Building, building_id)
        if not b or b.outlet_id != int(ctx.outlet_id) or not b.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Building ID {building_id} not found in this hotel property.",
            )

    existing = await db.execute(
        select(Floor).where(
            Floor.building_id == building_id,
            Floor.floor_number == floor_number,
            Floor.is_active == True,
        )
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Floor number {floor_number} already exists in this building.",
        )

    new_floor = Floor(
        client_id=ctx.client_id,
        outlet_id=ctx.outlet_id,
        building_id=building_id,
        floor_number=floor_number,
        name=name.strip(),
        is_active=True,
    )
    db.add(new_floor)
    await db.commit()
    await db.refresh(new_floor)
    return new_floor


async def update_floor(
    db: AsyncSession,
    ctx: UserContext,
    floor_id: int,
    floor_number: Optional[int] = None,
    name: Optional[str] = None,
    building_id: Optional[int] = None,
    is_active: Optional[bool] = None,
) -> Floor:
    ensure_authorized(ctx)

    floor = await db.get(Floor, floor_id)
    if not floor or floor.outlet_id != int(ctx.outlet_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Floor with ID {floor_id} not found in this hotel property.",
        )

    target_building_id = building_id if building_id is not None else floor.building_id
    if building_id is not None and building_id != floor.building_id:
        b = await db.get(Building, building_id)
        if not b or b.outlet_id != int(ctx.outlet_id) or not b.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Target building ID {building_id} not found.",
            )
        floor.building_id = building_id

    target_number = floor_number if floor_number is not None else floor.floor_number
    if (floor_number is not None and floor_number != floor.floor_number) or (
        building_id is not None and building_id != floor.building_id
    ):
        existing = await db.execute(
            select(Floor).where(
                Floor.building_id == target_building_id,
                Floor.floor_number == target_number,
                Floor.id != floor_id,
                Floor.is_active == True,
            )
        )
        if existing.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Floor number {target_number} is already in use in this building.",
            )
        floor.floor_number = target_number

    if name is not None:
        floor.name = name.strip()
    if is_active is not None:
        floor.is_active = is_active

    await db.commit()
    await db.refresh(floor)
    return floor


async def delete_floor(db: AsyncSession, ctx: UserContext, floor_id: int) -> Dict[str, Any]:
    ensure_authorized(ctx)

    floor = await db.get(Floor, floor_id)
    if not floor or floor.outlet_id != int(ctx.outlet_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Floor with ID {floor_id} not found.",
        )

    room_count_res = await db.execute(
        select(func.count(Room.id)).where(Room.floor_id == floor_id, Room.is_active == True)
    )
    room_count = room_count_res.scalar() or 0
    if room_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Cannot delete floor "{floor.name}" because {room_count} active rooms lie on it. Move or delete rooms first.',
        )

    floor.is_active = False
    await db.commit()
    return {
        "status": "success",
        "message": f'Floor "{floor.name}" removed successfully.',
    }


async def reorder_floors(
    db: AsyncSession,
    ctx: UserContext,
    building_id: int,
    floor_ids_bottom_to_top: List[int],
) -> List[Floor]:
    """
    Reorders floors according to Physical Elevation (Option 1):
    Index 0 in floor_ids_bottom_to_top = Floor 1 (Ground / Lowest Floor).
    Index N-1 = Floor N (Highest Floor / Rooftop).

    Uses a 2-phase swap to prevent PostgreSQL unique constraint conflicts on (building_id, floor_number).
    """
    ensure_authorized(ctx)
    if not floor_ids_bottom_to_top:
        return []

    # Fetch and verify all floors belong to this building & outlet
    res = await db.execute(
        select(Floor).where(
            Floor.id.in_(floor_ids_bottom_to_top),
            Floor.building_id == building_id,
            Floor.outlet_id == ctx.outlet_id,
            Floor.is_active == True,
        )
    )
    floors_map = {f.id: f for f in res.scalars().all()}
    if len(floors_map) != len(floor_ids_bottom_to_top):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more floor IDs are invalid or do not belong to this building.",
        )

    # Phase 1: Set temporary negative numbers to prevent unique collision
    for idx, fid in enumerate(floor_ids_bottom_to_top):
        f = floors_map[fid]
        f.floor_number = -(10000 + idx * 10 + f.id)
    await db.flush()

    # Phase 2: Set physical 1-based level (Option 1: 1 = bottom floor, N = top floor)
    ordered_floors = []
    for idx, fid in enumerate(floor_ids_bottom_to_top):
        f = floors_map[fid]
        f.floor_number = idx + 1
        ordered_floors.append(f)

    await db.commit()
    for f in ordered_floors:
        await db.refresh(f)
    return ordered_floors


async def list_floors(
    db: AsyncSession,
    ctx: UserContext,
    building_id: Optional[int] = None,
    is_active: bool = True,
) -> List[Dict[str, Any]]:
    ensure_authorized(ctx)

    query = (
        select(
            Floor,
            func.count(Room.id).filter(Room.is_active == True).label("room_count"),
            Building.name.label("building_name"),
        )
        .outerjoin(Room, Floor.id == Room.floor_id)
        .outerjoin(Building, Floor.building_id == Building.id)
        .where(Floor.outlet_id == ctx.outlet_id, Floor.is_active == is_active)
    )

    if building_id is not None:
        query = query.where(Floor.building_id == building_id)

    query = query.group_by(Floor.id, Building.name).order_by(Floor.floor_number.asc())
    res = await db.execute(query)
    rows = res.all()
    return [{"floor": f, "room_count": count, "building_name": b_name or "Main Tower"} for f, count, b_name in rows]


async def get_floor_by_id(db: AsyncSession, ctx: UserContext, floor_id: int) -> Floor:
    ensure_authorized(ctx)
    floor = await db.get(Floor, floor_id)
    if not floor or floor.outlet_id != int(ctx.outlet_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Floor with ID {floor_id} not found.",
        )
    return floor


# =========================================================================
# Room Category Services
# =========================================================================


async def create_room_category(
    db: AsyncSession,
    ctx: UserContext,
    name: str,
    base_price: float,
    code: Optional[str] = None,
    max_adults: int = 2,
    max_children: int = 1,
    amenities: Optional[List[str]] = None,
) -> RoomCategory:
    ensure_authorized(ctx)

    clean_name = name.strip()
    existing = await db.execute(
        select(RoomCategory).where(
            RoomCategory.outlet_id == ctx.outlet_id,
            RoomCategory.name.ilike(clean_name),
            RoomCategory.is_active == True,
        )
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Room category "{clean_name}" already exists in this hotel property.',
        )

    amenities_str = ",".join([a.strip() for a in amenities if a.strip()]) if amenities else ""

    new_cat = RoomCategory(
        client_id=ctx.client_id,
        outlet_id=ctx.outlet_id,
        name=clean_name,
        code=code.strip().upper() if code else None,
        base_price=Decimal(str(base_price)),
        max_adults=max_adults,
        max_children=max_children,
        amenities=amenities_str,
        is_active=True,
    )
    db.add(new_cat)
    await db.commit()
    await db.refresh(new_cat)
    return new_cat


async def update_room_category(
    db: AsyncSession,
    ctx: UserContext,
    category_id: int,
    name: Optional[str] = None,
    code: Optional[str] = None,
    base_price: Optional[float] = None,
    max_adults: Optional[int] = None,
    max_children: Optional[int] = None,
    amenities: Optional[List[str]] = None,
    is_active: Optional[bool] = None,
) -> RoomCategory:
    ensure_authorized(ctx)

    cat = await db.get(RoomCategory, category_id)
    if not cat or cat.outlet_id != int(ctx.outlet_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room category with ID {category_id} not found.",
        )

    if name is not None:
        clean_name = name.strip()
        existing = await db.execute(
            select(RoomCategory).where(
                RoomCategory.outlet_id == ctx.outlet_id,
                RoomCategory.name.ilike(clean_name),
                RoomCategory.id != category_id,
                RoomCategory.is_active == True,
            )
        )
        if existing.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Room category "{clean_name}" is already in use.',
            )
        cat.name = clean_name

    if code is not None:
        cat.code = code.strip().upper() if code else None
    if base_price is not None:
        cat.base_price = Decimal(str(base_price))
    if max_adults is not None:
        cat.max_adults = max_adults
    if max_children is not None:
        cat.max_children = max_children
    if amenities is not None:
        cat.amenities = ",".join([a.strip() for a in amenities if a.strip()])
    if is_active is not None:
        cat.is_active = is_active

    await db.commit()
    await db.refresh(cat)
    return cat


async def delete_room_category(db: AsyncSession, ctx: UserContext, category_id: int) -> Dict[str, Any]:
    ensure_authorized(ctx)

    cat = await db.get(RoomCategory, category_id)
    if not cat or cat.outlet_id != int(ctx.outlet_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room category with ID {category_id} not found.",
        )

    room_count_res = await db.execute(
        select(func.count(Room.id)).where(Room.category_id == category_id, Room.is_active == True)
    )
    room_count = room_count_res.scalar() or 0
    if room_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Cannot delete category "{cat.name}" because {room_count} active room(s) belong to it. Reassign rooms first.',
        )

    cat.is_active = False
    await db.commit()
    return {
        "status": "success",
        "message": f'Room category "{cat.name}" removed successfully.',
    }


async def list_room_categories(db: AsyncSession, ctx: UserContext, is_active: bool = True) -> List[Dict[str, Any]]:
    ensure_authorized(ctx)

    query = (
        select(
            RoomCategory,
            func.count(Room.id).filter(Room.is_active == True).label("room_count"),
        )
        .outerjoin(Room, RoomCategory.id == Room.category_id)
        .where(RoomCategory.outlet_id == ctx.outlet_id, RoomCategory.is_active == is_active)
        .group_by(RoomCategory.id)
        .order_by(RoomCategory.name.asc())
    )
    res = await db.execute(query)
    rows = res.all()
    return [{"category": c, "room_count": count} for c, count in rows]


async def get_room_category_by_id(db: AsyncSession, ctx: UserContext, category_id: int) -> RoomCategory:
    ensure_authorized(ctx)
    cat = await db.get(RoomCategory, category_id)
    if not cat or cat.outlet_id != int(ctx.outlet_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room category with ID {category_id} not found.",
        )
    return cat


# =========================================================================
# Room Services (Free-Hand & Multi-Entity)
# =========================================================================


async def create_room(
    db: AsyncSession,
    ctx: UserContext,
    floor_id: int,
    room_number: str,
    category_id: Optional[int] = None,
    custom_name: Optional[str] = None,
    custom_price: Optional[float] = None,
    custom_amenities: Optional[List[str]] = None,
) -> Room:
    ensure_authorized(ctx)

    clean_room_number = room_number.strip()
    if not clean_room_number:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Room number is required.")

    floor = await db.get(Floor, floor_id)
    if not floor or floor.outlet_id != int(ctx.outlet_id) or not floor.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Floor ID {floor_id} does not exist or is inactive in this hotel property.",
        )

    if category_id is not None:
        cat = await db.get(RoomCategory, category_id)
        if not cat or cat.outlet_id != int(ctx.outlet_id) or not cat.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Room category ID {category_id} does not exist or is inactive in this hotel property.",
            )

    existing = await db.execute(
        select(Room).where(
            Room.outlet_id == ctx.outlet_id,
            Room.room_number.ilike(clean_room_number),
            Room.is_active == True,
        )
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Room number "{clean_room_number}" already exists in this hotel property.',
        )

    custom_amenities_str = ",".join([a.strip() for a in custom_amenities if a.strip()]) if custom_amenities else None
    c_price = Decimal(str(custom_price)) if custom_price is not None else None

    new_room = Room(
        client_id=ctx.client_id,
        outlet_id=ctx.outlet_id,
        floor_id=floor_id,
        category_id=category_id,
        room_number=clean_room_number,
        custom_name=custom_name.strip() if custom_name else None,
        custom_price=c_price,
        custom_amenities=custom_amenities_str,
        status="AVAILABLE",
        is_active=True,
    )
    db.add(new_room)
    await db.commit()
    await db.refresh(new_room)
    return new_room


async def create_bulk_rooms(
    db: AsyncSession,
    ctx: UserContext,
    floor_id: int,
    start_number: int,
    end_number: int,
    category_id: Optional[int] = None,
    prefix: Optional[str] = None,
    custom_price: Optional[float] = None,
) -> Dict[str, Any]:
    ensure_authorized(ctx)

    if start_number > end_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start number cannot be greater than end number.",
        )

    count = end_number - start_number + 1
    if count > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot generate more than 100 rooms in a single bulk operation.",
        )

    floor = await db.get(Floor, floor_id)
    if not floor or floor.outlet_id != int(ctx.outlet_id) or not floor.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Floor ID {floor_id} does not exist or is inactive in this hotel property.",
        )

    cat = None
    if category_id is not None:
        cat = await db.get(RoomCategory, category_id)
        if not cat or cat.outlet_id != int(ctx.outlet_id) or not cat.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Room category ID {category_id} does not exist or is inactive in this hotel property.",
            )

    pfx = prefix.strip() if prefix else ""
    room_numbers = [f"{pfx}{num}" for num in range(start_number, end_number + 1)]

    # Check for duplicate room numbers in this outlet
    existing_res = await db.execute(
        select(Room.room_number).where(
            Room.outlet_id == ctx.outlet_id,
            Room.room_number.in_(room_numbers),
            Room.is_active == True,
        )
    )
    existing_nums = set(existing_res.scalars().all())
    if existing_nums:
        conflict_str = ", ".join(sorted(existing_nums))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The following room number(s) already exist: {conflict_str}",
        )

    c_price = Decimal(str(custom_price)) if custom_price is not None else None

    created_rooms: List[Room] = []
    for r_num in room_numbers:
        r = Room(
            client_id=ctx.client_id,
            outlet_id=ctx.outlet_id,
            floor_id=floor_id,
            category_id=category_id,
            room_number=r_num,
            custom_price=c_price,
            status="AVAILABLE",
            is_active=True,
        )
        db.add(r)
        created_rooms.append(r)

    await db.commit()
    for r in created_rooms:
        await db.refresh(r)

    return {
        "status": "success",
        "message": f"Successfully created {len(created_rooms)} rooms.",
        "created_count": len(created_rooms),
        "floor": floor,
        "category": cat,
        "rooms": created_rooms,
    }


async def update_room(
    db: AsyncSession,
    ctx: UserContext,
    room_id: int,
    floor_id: Optional[int] = None,
    category_id: Optional[Union[int, str]] = "UNSET",
    room_number: Optional[str] = None,
    custom_name: Optional[Union[str, None]] = "UNSET",
    custom_price: Optional[Union[float, None]] = "UNSET",
    custom_amenities: Optional[Union[List[str], None]] = "UNSET",
    status_val: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Room:
    ensure_authorized(ctx)

    room = await db.get(Room, room_id)
    if not room or room.outlet_id != int(ctx.outlet_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with ID {room_id} not found.",
        )

    if floor_id is not None:
        floor = await db.get(Floor, floor_id)
        if not floor or floor.outlet_id != int(ctx.outlet_id) or not floor.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid floor ID {floor_id}.",
            )
        room.floor_id = floor_id

    if category_id != "UNSET":
        if category_id is None:
            room.category_id = None
        else:
            cat = await db.get(RoomCategory, int(category_id))
            if not cat or cat.outlet_id != int(ctx.outlet_id) or not cat.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid category ID {category_id}.",
                )
            room.category_id = int(category_id)

    if room_number is not None:
        clean_num = room_number.strip()
        existing = await db.execute(
            select(Room).where(
                Room.outlet_id == ctx.outlet_id,
                Room.room_number.ilike(clean_num),
                Room.id != room_id,
                Room.is_active == True,
            )
        )
        if existing.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Room number "{clean_num}" is already in use by another room.',
            )
        room.room_number = clean_num

    if custom_name != "UNSET":
        room.custom_name = custom_name.strip() if custom_name else None

    if custom_price != "UNSET":
        room.custom_price = Decimal(str(custom_price)) if custom_price is not None else None

    if custom_amenities != "UNSET":
        room.custom_amenities = (
            ",".join([a.strip() for a in custom_amenities if a.strip()]) if custom_amenities else None
        )

    if status_val is not None:
        s_upper = status_val.upper()
        if s_upper not in VALID_ROOM_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid room status. Must be one of: {list(VALID_ROOM_STATUSES)}",
            )
        room.status = s_upper

    if is_active is not None:
        room.is_active = is_active

    await db.commit()
    await db.refresh(room)
    return room


async def update_room_status(db: AsyncSession, ctx: UserContext, room_id: int, new_status: str) -> Room:
    ensure_authorized(ctx)

    s_upper = new_status.upper()
    if s_upper not in VALID_ROOM_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid room status. Must be one of: {list(VALID_ROOM_STATUSES)}",
        )

    room = await db.get(Room, room_id)
    if not room or room.outlet_id != int(ctx.outlet_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with ID {room_id} not found.",
        )

    room.status = s_upper
    await db.commit()
    await db.refresh(room)
    return room


async def get_room_by_id(db: AsyncSession, ctx: UserContext, room_id: int) -> Room:
    ensure_authorized(ctx)
    room = await db.get(Room, room_id)
    if not room or room.outlet_id != int(ctx.outlet_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with ID {room_id} not found.",
        )
    return room


async def delete_room(db: AsyncSession, ctx: UserContext, room_id: int) -> Dict[str, Any]:
    ensure_authorized(ctx)

    room = await db.get(Room, room_id)
    if not room or room.outlet_id != int(ctx.outlet_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with ID {room_id} not found.",
        )

    if room.status == "OCCUPIED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Cannot delete room "{room.room_number}" while it is OCCUPIED by a guest.',
        )

    room.is_active = False
    await db.commit()
    return {
        "status": "success",
        "message": f'Room "{room.room_number}" removed successfully.',
    }


async def list_rooms(
    db: AsyncSession,
    ctx: UserContext,
    building_id: Optional[int] = None,
    floor_id: Optional[int] = None,
    category_id: Optional[int] = None,
    status_val: Optional[str] = None,
    is_active: bool = True,
) -> List[Dict[str, Any]]:
    ensure_authorized(ctx)

    query = (
        select(
            Room,
            Floor.name.label("floor_name"),
            Floor.floor_number.label("floor_number"),
            Floor.building_id.label("building_id"),
            Building.name.label("building_name"),
            RoomCategory.name.label("category_name"),
            RoomCategory.base_price.label("base_price"),
            RoomCategory.amenities.label("category_amenities"),
        )
        .join(Floor, Room.floor_id == Floor.id)
        .outerjoin(Building, Floor.building_id == Building.id)
        .outerjoin(RoomCategory, Room.category_id == RoomCategory.id)
        .where(Room.outlet_id == ctx.outlet_id, Room.is_active == is_active)
        .order_by(Floor.floor_number.asc(), Room.room_number.asc())
    )

    if building_id:
        query = query.where(Floor.building_id == building_id)
    if floor_id:
        query = query.where(Room.floor_id == floor_id)
    if category_id:
        query = query.where(Room.category_id == category_id)
    if status_val:
        query = query.where(Room.status == status_val.upper())

    res = await db.execute(query)
    rows = res.all()

    formatted = []
    for r, f_name, f_num, b_id, b_name, c_name, c_price, c_amenities in rows:
        # Determine effective price: custom_price takes precedence over category base_price
        if r.custom_price is not None:
            eff_price = float(r.custom_price)
        elif c_price is not None:
            eff_price = float(c_price)
        else:
            eff_price = 0.0

        # Determine effective amenities
        if r.custom_amenities:
            eff_amenities = [a.strip() for a in r.custom_amenities.split(",") if a.strip()]
        elif c_amenities:
            eff_amenities = [a.strip() for a in c_amenities.split(",") if a.strip()]
        else:
            eff_amenities = []

        formatted.append(
            {
                "room": r,
                "floor_name": f_name,
                "floor_number": f_num,
                "building_id": b_id,
                "building_name": b_name or "Main Tower",
                "category_id": r.category_id,
                "category_name": c_name or (r.custom_name or "Custom Room"),
                "base_price": eff_price,
                "amenities": eff_amenities,
                "custom_name": r.custom_name,
                "custom_price": float(r.custom_price) if r.custom_price is not None else None,
                "custom_amenities": [a.strip() for a in r.custom_amenities.split(",") if a.strip()]
                if r.custom_amenities
                else [],
            }
        )

    return formatted


# =========================================================================
# Utility Services
# =========================================================================


async def create_utility(
    db: AsyncSession,
    ctx: UserContext,
    building_id: int,
    name: str,
    utility_type: str,
    floor_id: Optional[int] = None,
    status: str = "OPEN",
    capacity: Optional[int] = None,
    operating_hours: Optional[str] = None,
    is_bookable: bool = False,
    rental_price: Optional[float] = None,
    amenities: Optional[List[str]] = None,
) -> Utility:
    ensure_authorized(ctx)
    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Utility name is required.")

    # Validate building
    building = await db.get(Building, building_id)
    if not building or building.outlet_id != int(ctx.outlet_id) or not building.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Building ID {building_id} not found.",
        )

    # Validate floor if provided
    if floor_id is not None:
        floor = await db.get(Floor, floor_id)
        if not floor or floor.outlet_id != int(ctx.outlet_id) or not floor.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Floor ID {floor_id} not found.",
            )

    s_upper = status.upper() if status else "OPEN"
    if s_upper not in VALID_UTILITY_STATUSES:
        s_upper = "OPEN"

    amenities_str = ",".join([a.strip() for a in amenities if a.strip()]) if amenities else None
    r_price = Decimal(str(rental_price)) if rental_price is not None else None

    utility = Utility(
        client_id=ctx.client_id,
        outlet_id=ctx.outlet_id,
        building_id=building_id,
        floor_id=floor_id,
        name=clean_name,
        utility_type=utility_type.strip().upper(),
        status=s_upper,
        capacity=capacity,
        operating_hours=operating_hours.strip() if operating_hours else None,
        is_bookable=is_bookable,
        rental_price=r_price,
        amenities=amenities_str,
        is_active=True,
    )
    db.add(utility)
    await db.commit()
    await db.refresh(utility)
    return utility


async def update_utility(
    db: AsyncSession,
    ctx: UserContext,
    utility_id: int,
    name: Optional[str] = None,
    utility_type: Optional[str] = None,
    building_id: Optional[int] = None,
    floor_id: Optional[Union[int, None]] = "UNSET",
    status_val: Optional[str] = None,
    capacity: Optional[int] = None,
    operating_hours: Optional[str] = None,
    is_bookable: Optional[bool] = None,
    rental_price: Optional[float] = None,
    amenities: Optional[List[str]] = None,
    is_active: Optional[bool] = None,
) -> Utility:
    ensure_authorized(ctx)

    u = await db.get(Utility, utility_id)
    if not u or u.outlet_id != int(ctx.outlet_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Utility with ID {utility_id} not found.",
        )

    if name is not None:
        u.name = name.strip()

    if utility_type is not None:
        u.utility_type = utility_type.strip().upper()

    if building_id is not None:
        b = await db.get(Building, building_id)
        if not b or b.outlet_id != int(ctx.outlet_id) or not b.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Building ID {building_id} not found.",
            )
        u.building_id = building_id

    if floor_id != "UNSET":
        if floor_id is None:
            u.floor_id = None
        else:
            f = await db.get(Floor, int(floor_id))
            if not f or f.outlet_id != int(ctx.outlet_id) or not f.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Floor ID {floor_id} not found.",
                )
            u.floor_id = int(floor_id)

    if status_val is not None:
        s_upper = status_val.upper()
        if s_upper not in VALID_UTILITY_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Status must be one of: {list(VALID_UTILITY_STATUSES)}",
            )
        u.status = s_upper

    if capacity is not None:
        u.capacity = capacity

    if operating_hours is not None:
        u.operating_hours = operating_hours.strip() if operating_hours else None

    if is_bookable is not None:
        u.is_bookable = is_bookable

    if rental_price is not None:
        u.rental_price = Decimal(str(rental_price)) if rental_price is not None else None

    if amenities is not None:
        u.amenities = ",".join([a.strip() for a in amenities if a.strip()]) if amenities else None

    if is_active is not None:
        u.is_active = is_active

    await db.commit()
    await db.refresh(u)
    return u


async def update_utility_status(db: AsyncSession, ctx: UserContext, utility_id: int, status_val: str) -> Utility:
    ensure_authorized(ctx)
    s_upper = status_val.upper()
    if s_upper not in VALID_UTILITY_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Status must be one of: {list(VALID_UTILITY_STATUSES)}",
        )

    u = await db.get(Utility, utility_id)
    if not u or u.outlet_id != int(ctx.outlet_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Utility with ID {utility_id} not found.",
        )

    u.status = s_upper
    await db.commit()
    await db.refresh(u)
    return u


async def delete_utility(db: AsyncSession, ctx: UserContext, utility_id: int) -> Dict[str, Any]:
    ensure_authorized(ctx)
    u = await db.get(Utility, utility_id)
    if not u or u.outlet_id != int(ctx.outlet_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Utility with ID {utility_id} not found.",
        )

    u.is_active = False
    await db.commit()
    return {"status": "success", "message": f'Utility "{u.name}" removed successfully.'}


async def list_utilities(
    db: AsyncSession,
    ctx: UserContext,
    building_id: Optional[int] = None,
    floor_id: Optional[int] = None,
    is_active: bool = True,
) -> List[Utility]:
    ensure_authorized(ctx)
    query = (
        select(Utility)
        .where(Utility.outlet_id == ctx.outlet_id, Utility.is_active == is_active)
        .order_by(
            Utility.building_id.asc(),
            Utility.floor_id.asc().nullsfirst(),
            Utility.name.asc(),
        )
    )
    if building_id is not None:
        query = query.where(Utility.building_id == building_id)
    if floor_id is not None:
        query = query.where(Utility.floor_id == floor_id)

    res = await db.execute(query)
    return list(res.scalars().all())


# =========================================================================
# Campus & Hotel Layout Services
# =========================================================================


async def get_campus_layout(db: AsyncSession, ctx: UserContext) -> Dict[str, Any]:
    """
    Returns full campus hierarchical architecture:
    Buildings -> Floors -> Rooms & Floor-level Utilities
    + Building-level Facilities (Pools, Lawns, Spas, Banquet Halls)
    + Campus-wide Room and Facility status metrics.
    """
    ensure_authorized(ctx)

    buildings_list = await list_buildings(db, ctx, is_active=True)
    all_floors = await list_floors(db, ctx, is_active=True)
    all_rooms = await list_rooms(db, ctx, is_active=True)
    all_utilities = await list_utilities(db, ctx, is_active=True)

    # Index rooms by floor_id
    rooms_by_floor: Dict[int, List[Dict[str, Any]]] = {}
    for r_item in all_rooms:
        fid = r_item["room"].floor_id
        if fid not in rooms_by_floor:
            rooms_by_floor[fid] = []
        rooms_by_floor[fid].append(r_item)

    # Index utilities by (building_id, floor_id)
    utils_by_floor: Dict[int, List[Utility]] = {}
    utils_by_building: Dict[int, List[Utility]] = {}
    for u in all_utilities:
        if u.floor_id is not None:
            if u.floor_id not in utils_by_floor:
                utils_by_floor[u.floor_id] = []
            utils_by_floor[u.floor_id].append(u)
        else:
            bid = u.building_id
            if bid not in utils_by_building:
                utils_by_building[bid] = []
            utils_by_building[bid].append(u)

    # Index floors by building_id
    floors_by_building: Dict[int, List[Dict[str, Any]]] = {}
    for f_item in all_floors:
        f = f_item["floor"]
        bid = f.building_id
        if bid not in floors_by_building:
            floors_by_building[bid] = []
        floors_by_building[bid].append(f_item)

    # Campus statistics
    total_rooms = len(all_rooms)
    available_rooms = sum(1 for r in all_rooms if r["room"].status == "AVAILABLE")
    occupied_rooms = sum(1 for r in all_rooms if r["room"].status == "OCCUPIED")
    cleaning_rooms = sum(1 for r in all_rooms if r["room"].status == "CLEANING")
    maintenance_rooms = sum(1 for r in all_rooms if r["room"].status == "MAINTENANCE")

    # Assemble campus buildings
    campus_buildings = []
    for b_data in buildings_list:
        b = b_data["building"]
        b_floors_raw = floors_by_building.get(b.id, [])

        # Sort floors by floor_number ascending (Option 1: Floor 1 is at the bottom, Floor N on top)
        b_floors_raw.sort(key=lambda x: x["floor"].floor_number)

        b_floors = []
        for f_data in b_floors_raw:
            f = f_data["floor"]
            b_floors.append(
                {
                    "floor": f,
                    "room_count": len(rooms_by_floor.get(f.id, [])),
                    "rooms": rooms_by_floor.get(f.id, []),
                    "utilities": utils_by_floor.get(f.id, []),
                }
            )

        campus_buildings.append(
            {
                "building": b,
                "total_floors": len(b_floors),
                "total_rooms": b_data["room_count"],
                "floors": b_floors,
                "utilities": utils_by_building.get(b.id, []),
            }
        )

    return {
        "status": "success",
        "total_buildings": len(campus_buildings),
        "total_floors": len(all_floors),
        "total_rooms": total_rooms,
        "available_rooms": available_rooms,
        "occupied_rooms": occupied_rooms,
        "cleaning_rooms": cleaning_rooms,
        "maintenance_rooms": maintenance_rooms,
        "total_utilities": len(all_utilities),
        "buildings": campus_buildings,
    }


async def get_hotel_layout(db: AsyncSession, ctx: UserContext) -> Dict[str, Any]:
    """
    Retained for backward compatibility with existing hotel_layout queries.
    """
    ensure_authorized(ctx)

    floors_data = await list_floors(db, ctx, is_active=True)
    all_rooms_data = await list_rooms(db, ctx, is_active=True)

    rooms_by_floor: Dict[int, List[Dict[str, Any]]] = {}
    for r_data in all_rooms_data:
        fid = r_data["room"].floor_id
        if fid not in rooms_by_floor:
            rooms_by_floor[fid] = []
        rooms_by_floor[fid].append(r_data)

    total_rooms = len(all_rooms_data)
    available_rooms = sum(1 for r in all_rooms_data if r["room"].status == "AVAILABLE")
    occupied_rooms = sum(1 for r in all_rooms_data if r["room"].status == "OCCUPIED")
    cleaning_rooms = sum(1 for r in all_rooms_data if r["room"].status == "CLEANING")
    maintenance_rooms = sum(1 for r in all_rooms_data if r["room"].status == "MAINTENANCE")

    layout_floors = []
    for f_item in floors_data:
        f = f_item["floor"]
        layout_floors.append(
            {
                "floor": f,
                "room_count": f_item["room_count"],
                "rooms": rooms_by_floor.get(f.id, []),
            }
        )

    return {
        "status": "success",
        "total_floors": len(floors_data),
        "total_rooms": total_rooms,
        "available_rooms": available_rooms,
        "occupied_rooms": occupied_rooms,
        "cleaning_rooms": cleaning_rooms,
        "maintenance_rooms": maintenance_rooms,
        "floors": layout_floors,
    }
