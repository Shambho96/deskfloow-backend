from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from fastapi import HTTPException, status
from typing import Optional, List, Dict, Any, Union
from decimal import Decimal

from app.models import Floor, RoomCategory, Room
from app.core.context import UserContext

VALID_ROOM_STATUSES = ('AVAILABLE', 'OCCUPIED', 'CLEANING', 'MAINTENANCE')

def ensure_authorized(ctx: UserContext):
    if ctx.role not in ('OWNER', 'MANAGER'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Only Owners and Managers have access to hotel layout and room operations.'
        )


async def create_floor(
    db: AsyncSession,
    ctx: UserContext,
    floor_number: int,
    name: str
) -> Floor:
    ensure_authorized(ctx)

    existing = await db.execute(
        select(Floor).where(
            Floor.outlet_id == ctx.outlet_id,
            Floor.floor_number == floor_number,
            Floor.is_active == True
        )
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Floor number {floor_number} already exists in this hotel property.'
        )

    new_floor = Floor(
        client_id=ctx.client_id,
        outlet_id=ctx.outlet_id,
        floor_number=floor_number,
        name=name.strip(),
        is_active=True
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
    is_active: Optional[bool] = None
) -> Floor:
    ensure_authorized(ctx)

    floor = await db.get(Floor, floor_id)
    if not floor or floor.outlet_id != int(ctx.outlet_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Floor with ID {floor_id} not found in this hotel property.'
        )

    if floor_number is not None and floor_number != floor.floor_number:
        existing = await db.execute(
            select(Floor).where(
                Floor.outlet_id == ctx.outlet_id,
                Floor.floor_number == floor_number,
                Floor.id != floor_id,
                Floor.is_active == True
            )
        )
        if existing.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Floor number {floor_number} is already in use by another floor.'
            )
        floor.floor_number = floor_number

    if name is not None:
        floor.name = name.strip()
    if is_active is not None:
        floor.is_active = is_active

    await db.commit()
    await db.refresh(floor)
    return floor


async def delete_floor(
    db: AsyncSession,
    ctx: UserContext,
    floor_id: int
) -> Dict[str, Any]:
    ensure_authorized(ctx)

    floor = await db.get(Floor, floor_id)
    if not floor or floor.outlet_id != int(ctx.outlet_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Floor with ID {floor_id} not found.'
        )

    room_count_res = await db.execute(
        select(func.count(Room.id)).where(Room.floor_id == floor_id, Room.is_active == True)
    )
    room_count = room_count_res.scalar() or 0
    if room_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Cannot delete floor \"{floor.name}\" because {room_count} active rooms lie on it. Move or delete rooms first.'
        )

    floor.is_active = False
    await db.commit()
    return {'status': 'success', 'message': f'Floor \"{floor.name}\" removed successfully.'}


async def list_floors(
    db: AsyncSession,
    ctx: UserContext,
    is_active: bool = True
) -> List[Dict[str, Any]]:
    ensure_authorized(ctx)

    query = (
        select(
            Floor,
            func.count(Room.id).filter(Room.is_active == True).label('room_count')
        )
        .outerjoin(Room, Floor.id == Room.floor_id)
        .where(Floor.outlet_id == ctx.outlet_id, Floor.is_active == is_active)
        .group_by(Floor.id)
        .order_by(Floor.floor_number.asc())
    )
    res = await db.execute(query)
    rows = res.all()
    return [{'floor': f, 'room_count': count} for f, count in rows]


async def get_floor_by_id(
    db: AsyncSession,
    ctx: UserContext,
    floor_id: int
) -> Floor:
    ensure_authorized(ctx)
    floor = await db.get(Floor, floor_id)
    if not floor or floor.outlet_id != int(ctx.outlet_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Floor with ID {floor_id} not found.'
        )
    return floor


async def create_room_category(
    db: AsyncSession,
    ctx: UserContext,
    name: str,
    base_price: float,
    code: Optional[str] = None,
    max_adults: int = 2,
    max_children: int = 1,
    amenities: Optional[List[str]] = None
) -> RoomCategory:
    ensure_authorized(ctx)

    clean_name = name.strip()
    existing = await db.execute(
        select(RoomCategory).where(
            RoomCategory.outlet_id == ctx.outlet_id,
            RoomCategory.name.ilike(clean_name),
            RoomCategory.is_active == True
        )
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Room category \"{clean_name}\" already exists in this hotel property.'
        )

    amenities_str = ','.join([a.strip() for a in amenities if a.strip()]) if amenities else ''

    new_cat = RoomCategory(
        client_id=ctx.client_id,
        outlet_id=ctx.outlet_id,
        name=clean_name,
        code=code.strip().upper() if code else None,
        base_price=Decimal(str(base_price)),
        max_adults=max_adults,
        max_children=max_children,
        amenities=amenities_str,
        is_active=True
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
    is_active: Optional[bool] = None
) -> RoomCategory:
    ensure_authorized(ctx)

    cat = await db.get(RoomCategory, category_id)
    if not cat or cat.outlet_id != int(ctx.outlet_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Room category with ID {category_id} not found.'
        )

    if name is not None:
        clean_name = name.strip()
        existing = await db.execute(
            select(RoomCategory).where(
                RoomCategory.outlet_id == ctx.outlet_id,
                RoomCategory.name.ilike(clean_name),
                RoomCategory.id != category_id,
                RoomCategory.is_active == True
            )
        )
        if existing.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Room category \"{clean_name}\" is already in use.'
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
        cat.amenities = ','.join([a.strip() for a in amenities if a.strip()])
    if is_active is not None:
        cat.is_active = is_active

    await db.commit()
    await db.refresh(cat)
    return cat


async def delete_room_category(
    db: AsyncSession,
    ctx: UserContext,
    category_id: int ) -> Dict[str, Any]:
    ensure_authorized(ctx)

    cat = await db.get(RoomCategory, category_id)
    if not cat or cat.outlet_id != int(ctx.outlet_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Room category with ID {category_id} not found.'
        )

    room_count_res = await db.execute(
        select(func.count(Room.id)).where(Room.category_id == category_id, Room.is_active == True)
    )
    room_count = room_count_res.scalar() or 0
    if room_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Cannot delete category \"{cat.name}\" because {room_count} active room(s) belong to it. Reassign rooms first.'
        )

    cat.is_active = False
    await db.commit()
    return  {'status': 'success', 'message': f'Room category \"{cat.name}\" removed successfully.'}


async def list_room_categories(
    db: AsyncSession,
    ctx: UserContext,
    is_active: bool = True
) -> List[Dict[str, Any]]:
    ensure_authorized(ctx)

    query = (
        select(
            RoomCategory,
            func.count(Room.id).filter(Room.is_active == True).label('room_count')
        )
        .outerjoin(Room, RoomCategory.id == Room.category_id)
        .where(RoomCategory.outlet_id == ctx.outlet_id, RoomCategory.is_active == is_active)
        .group_by(RoomCategory.id)
        .order_by(RoomCategory.name.asc())
    )
    res = await db.execute(query)
    rows = res.all()
    return [{'category': c, 'room_count': count} for c, count in rows]


async def get_room_category_by_id(
    db: AsyncSession,
    ctx: UserContext,
    category_id: int
) -> RoomCategory:
    ensure_authorized(ctx)
    cat = await db.get(RoomCategory, category_id)
    if not cat or cat.outlet_id != int(ctx.outlet_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Room category with ID {category_id} not found.'
        )
    return cat


async def create_room(
    db: AsyncSession,
    ctx: UserContext,
    floor_id: int,
    category_id: int,
    room_number: str
) -> Room:
    ensure_authorized(ctx)

    clean_room_number = room_number.strip()

    floor = await db.get(Floor, floor_id)
    if not floor or floor.outlet_id != int(ctx.outlet_id) or not floor.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Floor ID {floor_id} does not exist or is inactive in this hotel property.'
        )

    cat = await db.get(RoomCategory, category_id)
    if not cat or cat.outlet_id != int(ctx.outlet_id) or not cat.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Room category ID {category_id} does not exist or is inactive in this hotel property.'
        )

    existing = await db.execute(
        select(Room).where(
            Room.outlet_id == ctx.outlet_id,
            Room.room_number.ilike(clean_room_number),
            Room.is_active == True
        )
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Room number \"{clean_room_number}\" already exists in this hotel property.'
        )

    new_room = Room(
        client_id=ctx.client_id,
        outlet_id=ctx.outlet_id,
        floor_id=floor_id,
        category_id=category_id,
        room_number=clean_room_number,
        status='AVAILABLE',
        is_active=True
    )
    db.add(new_room)
    await db.commit()
    await db.refresh(new_room)
    return new_room


async def update_room(
    db: AsyncSession,
    ctx: UserContext,
    room_id: int,
    floor_id: Optional[int] = None,
    category_id: Optional[int] = None,
    room_number: Optional[str] = None,
    status_val: Optional[str] = None,
    is_active: Optional[bool] = None
) -> Room:
    ensure_authorized(ctx)

    room = await db.get(Room, room_id)
    if not room or room.outlet_id != int(ctx.outlet_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Room with ID {room_id} not found.'
        )

    if floor_id is not None:
        floor = await db.get(Floor, floor_id)
        if not floor or floor.outlet_id != int(ctx.outlet_id) or not floor.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'Invalid floor ID {floor_id}.')
        room.floor_id = floor_id

    if category_id is not None:
        cat = await db.get(RoomCategory, category_id)
        if not cat or cat.outlet_id != int(ctx.outlet_id) or not cat.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'Invalid category ID {category_id}.')
        room.category_id = category_id

    if room_number is not None:
        clean_num = room_number.strip()
        existing = await db.execute(
            select(Room).where(
                Room.outlet_id == ctx.outlet_id,
                Room.room_number.ilike(clean_num),
                Room.id != room_id,
                Room.is_active == True
            )
        )
        if existing.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Room number \"{clean_num}\" is already in use by another room.'
            )
        room.room_number = clean_num

    if status_val is not None:
        s_upper = status_val.upper()
        if s_upper not in VALID_ROOM_STATUSES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'Invalid room status. Must be one of: {list(VALID_ROOM_STATUSES)}')
        room.status = s_upper

    if is_active is not None:
        room.is_active = is_active

    await db.commit()
    await db.refresh(room)
    return room


async def update_room_status(
    db: AsyncSession,
    ctx: UserContext,
    room_id: int,
    new_status: str
) -> Room:
    ensure_authorized(ctx)

    s_upper = new_status.upper()
    if s_upper not in VALID_ROOM_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Invalid room status. Must be one of: {list(VALID_ROOM_STATUSES)}'
        )

    room = await db.get(Room, room_id)
    if not room or room.outlet_id != int(ctx.outlet_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Room with ID {room_id} not found.'
        )

    room.status = s_upper
    await db.commit()
    await db.refresh(room)
    return room



async def get_room_by_id(
    db: AsyncSession,
    ctx: UserContext,
    room_id: int
) -> Room:
    ensure_authorized(ctx)
    room = await db.get(Room, room_id)
    if not room or room.outlet_id != int(ctx.outlet_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with ID {room_id} not found."
        )
    return room

async def delete_room(
    db: AsyncSession,
    ctx: UserContext,
    room_id: int
) -> Dict[str, Any]:
    ensure_authorized(ctx)

    room = await db.get(Room, room_id)
    if not room or room.outlet_id != int(ctx.outlet_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Room with ID {room_id} not found.'
        )

    if room.status == 'OCCUPIED':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Cannot delete room \"{room.room_number}\" while it is OCCUPIED by a guest.'
        )

    room.is_active = False
    await db.commit()
    return {'status': 'success', 'message': f'Room \"{room.room_number}\" removed successfully.'}


async def list_rooms(
    db: AsyncSession,
    ctx: UserContext,
    floor_id: Optional[int] = None,
    category_id: Optional[int] = None,
    status_val: Optional[str] = None,
    is_active: bool = True
) -> List[Dict[str, Any]]:
    ensure_authorized(ctx)

    query = (
        select(Room, Floor.name.label('floor_name'), RoomCategory.name.label('category_name'), RoomCategory.base_price.label('base_price'))
        .join(Floor, Room.floor_id == Floor.id)
        .join(RoomCategory, Room.category_id == RoomCategory.id)
        .where(Room.outlet_id == ctx.outlet_id, Room.is_active == is_active)
        .order_by(Floor.floor_number.asc(), Room.room_number.asc())
    )

    if floor_id:
        query = query.where(Room.floor_id == floor_id)
    if category_id:
        query = query.where(Room.category_id == category_id)
    if status_val:
        query = query.where(Room.status == status_val.upper())

    res = await db.execute(query)
    rows = res.all()

    return [{
        'room': r,
        'floor_name': f_name,
        'category_name': c_name,
        'base_price': float(price)
    } for r, f_name, c_name, price in rows]


async def get_hotel_layout(
    db: AsyncSession,
    ctx: UserContext
) -> Dict[str, Any]:
    ensure_authorized(ctx)

    floors_data = await list_floors(db, ctx, is_active=True)
    all_rooms_data = await list_rooms(db, ctx, is_active=True)

    rooms_by_floor: Dict[int, List[Dict[str, Any]]] = {}
    for r_data in all_rooms_data:
        fid = r_data['room'].floor_id
        if fid not in rooms_by_floor:
            rooms_by_floor[fid] = []
        rooms_by_floor[fid].append(r_data)

    total_rooms = len(all_rooms_data)
    available_rooms = sum(1 for r in all_rooms_data if r['room'].status == 'AVAILABLE')
    occupied_rooms = sum(1 for r in all_rooms_data if r['room'].status == 'OCCUPIED')
    cleaning_rooms = sum(1 for r in all_rooms_data if r['room'].status == 'CLEANING')
    maintenance_rooms = sum(1 for r in all_rooms_data if r['room'].status == 'MAINTENANCE')

    layout_floors = []
    for f_item in floors_data:
        f = f_item['floor']
        layout_floors.append({
            'floor': f,
            'room_count': f_item['room_count'],
            'rooms': rooms_by_floor.get(f.id, [])
        })

    return {
        'status': 'success',
        'total_floors': len(floors_data),
        'total_rooms': total_rooms,
        'available_rooms': available_rooms,
        'occupied_rooms': occupied_rooms,
        'cleaning_rooms': cleaning_rooms,
        'maintenance_rooms': maintenance_rooms,
        'floors': layout_floors
    }
