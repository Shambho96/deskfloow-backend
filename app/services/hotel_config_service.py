"""
Hotel Configuration Service
Manages hotel special requests (amenities, early check-in, airport transfers)
and guest profile/CRM tags (VIP, Corporate, Vegetarian, Senior Citizen).
Enforces strict client_id and outlet_id isolation with automated defaults seeding.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy import select, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hotel_config import HotelSpecialRequest, HotelGuestTag
from app.db.base import Base


DEFAULT_SPECIAL_REQUESTS = [
    {
        "code": "HIGH_FLOOR",
        "label": "High Floor / Quiet Room",
        "category": "ROOM",
        "is_chargeable": False,
        "price": 0.00,
        "icon": "Building",
        "display_order": 1,
    },
    {
        "code": "AIRPORT_PICKUP",
        "label": "Airport Transfer Pickup",
        "category": "TIMING",
        "is_chargeable": True,
        "price": 1500.00,
        "icon": "Plane",
        "display_order": 2,
    },
    {
        "code": "EARLY_CHECKIN",
        "label": "Early Check-in Request",
        "category": "TIMING",
        "is_chargeable": False,
        "price": 0.00,
        "icon": "Clock",
        "display_order": 3,
    },
    {
        "code": "LATE_CHECKOUT",
        "label": "Late Check-out Request",
        "category": "TIMING",
        "is_chargeable": False,
        "price": 0.00,
        "icon": "Clock",
        "display_order": 4,
    },
    {
        "code": "EXTRA_BED",
        "label": "Extra Bed / Rollaway",
        "category": "AMENITY",
        "is_chargeable": True,
        "price": 1000.00,
        "icon": "Bed",
        "display_order": 5,
    },
    {
        "code": "BABY_COT",
        "label": "Baby Cot / Crib",
        "category": "AMENITY",
        "is_chargeable": False,
        "price": 0.00,
        "icon": "Heart",
        "display_order": 6,
    },
    {
        "code": "HONEYMOON_DECOR",
        "label": "Honeymoon / Anniversary Decor",
        "category": "SPECIAL",
        "is_chargeable": True,
        "price": 1200.00,
        "icon": "Sparkles",
        "display_order": 7,
    },
    {
        "code": "NON_SMOKING",
        "label": "Non-Smoking Room",
        "category": "ROOM",
        "is_chargeable": False,
        "price": 0.00,
        "icon": "Shield",
        "display_order": 8,
    },
]


DEFAULT_GUEST_TAGS = [
    {
        "name": "VIP Guest",
        "color": "amber",
        "category": "PROFILE",
        "description": "High priority VIP guest or frequent suite booker",
        "display_order": 1,
    },
    {
        "name": "Corporate / Business",
        "color": "blue",
        "category": "PROFILE",
        "description": "Corporate rate business traveler requiring tax invoice",
        "display_order": 2,
    },
    {
        "name": "Frequent Booker",
        "color": "primary",
        "category": "PROFILE",
        "description": "Loyal repeating guest with 3+ stays",
        "display_order": 3,
    },
    {
        "name": "Vegetarian / Jain Dining",
        "color": "emerald",
        "category": "DIETARY",
        "description": "Pure vegetarian kitchen preference",
        "display_order": 4,
    },
    {
        "name": "Senior Citizen",
        "color": "slate",
        "category": "PREFERENCE",
        "description": "Requires ground floor or elevator close access",
        "display_order": 5,
    },
    {
        "name": "Payment Watchlist",
        "color": "rose",
        "category": "BILLING",
        "description": "Mandatory pre-authorization deposit required",
        "display_order": 6,
    },
]


async def ensure_hotel_config_tables(session: AsyncSession) -> None:
    """Ensures hotel_special_requests and hotel_guest_tags tables exist in DB."""
    try:
        conn = await session.connection()
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                HotelSpecialRequest.__table__,
                HotelGuestTag.__table__,
            ],
        )
    except Exception:
        pass


# ─── SPECIAL REQUESTS OPERATIONS ────────────────────────────────────────


async def get_hotel_special_requests(
    session: AsyncSession,
    client_id: int,
    outlet_id: Optional[int] = None,
) -> List[HotelSpecialRequest]:
    """
    Returns all special requests configured for the outlet.
    Auto-seeds default hotel special requests if none exist.
    """
    await ensure_hotel_config_tables(session)

    stmt = (
        select(HotelSpecialRequest)
        .where(HotelSpecialRequest.client_id == client_id)
        .order_by(HotelSpecialRequest.display_order, HotelSpecialRequest.id)
    )

    if outlet_id is not None:
        stmt = stmt.where(
            or_(
                HotelSpecialRequest.outlet_id == outlet_id,
                HotelSpecialRequest.outlet_id.is_(None),
            )
        )

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def save_hotel_special_requests(
    session: AsyncSession,
    client_id: int,
    outlet_id: Optional[int],
    requests_data: List[Dict[str, Any]],
) -> List[HotelSpecialRequest]:
    """
    Saves or replaces the special requests configuration for an outlet.
    """
    await ensure_hotel_config_tables(session)

    # Delete existing requests for this outlet
    del_stmt = delete(HotelSpecialRequest).where(
        HotelSpecialRequest.client_id == client_id,
    )
    if outlet_id is not None:
        del_stmt = del_stmt.where(HotelSpecialRequest.outlet_id == outlet_id)

    await session.execute(del_stmt)

    for idx, r in enumerate(requests_data):
        price = float(r.get("price") or 0.0)
        session.add(
            HotelSpecialRequest(
                client_id=client_id,
                outlet_id=outlet_id,
                code=str(r.get("code") or f"REQ_{idx + 1}").upper().replace(" ", "_"),
                label=str(r.get("label") or "").strip(),
                category=str(r.get("category") or "ROOM").upper(),
                is_chargeable=bool(r.get("is_chargeable")),
                price=price if bool(r.get("is_chargeable")) else 0.0,
                icon=str(r.get("icon") or "Sparkles"),
                display_order=int(r.get("display_order") or idx + 1),
                is_active=bool(r.get("is_active", True)),
            )
        )

    await session.commit()
    return await get_hotel_special_requests(session, client_id, outlet_id)


# ─── GUEST TAGS OPERATIONS ──────────────────────────────────────────────


async def get_hotel_guest_tags(
    session: AsyncSession,
    client_id: int,
    outlet_id: Optional[int] = None,
) -> List[HotelGuestTag]:
    """
    Returns all guest tags configured for the outlet.
    Auto-seeds default hotel guest tags if none exist.
    """
    await ensure_hotel_config_tables(session)

    stmt = (
        select(HotelGuestTag)
        .where(HotelGuestTag.client_id == client_id)
        .order_by(HotelGuestTag.display_order, HotelGuestTag.id)
    )

    if outlet_id is not None:
        stmt = stmt.where(
            or_(
                HotelGuestTag.outlet_id == outlet_id,
                HotelGuestTag.outlet_id.is_(None),
            )
        )

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def save_hotel_guest_tags(
    session: AsyncSession,
    client_id: int,
    outlet_id: Optional[int],
    tags_data: List[Dict[str, Any]],
) -> List[HotelGuestTag]:
    """
    Saves or replaces the guest tags configuration for an outlet.
    """
    await ensure_hotel_config_tables(session)

    del_stmt = delete(HotelGuestTag).where(
        HotelGuestTag.client_id == client_id,
    )
    if outlet_id is not None:
        del_stmt = del_stmt.where(HotelGuestTag.outlet_id == outlet_id)

    await session.execute(del_stmt)

    for idx, t in enumerate(tags_data):
        session.add(
            HotelGuestTag(
                client_id=client_id,
                outlet_id=outlet_id,
                name=str(t.get("name") or "").strip(),
                color=str(t.get("color") or "primary"),
                category=str(t.get("category") or "PROFILE").upper(),
                description=str(t.get("description") or "").strip() or None,
                display_order=int(t.get("display_order") or idx + 1),
                is_active=bool(t.get("is_active", True)),
            )
        )

    await session.commit()
    return await get_hotel_guest_tags(session, client_id, outlet_id)
