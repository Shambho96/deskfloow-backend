from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlalchemy import and_, case, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.folio import GuestFolio
from app.models.guest import Guest
from app.models.loyalty import LoyaltyTier
from app.models.reservation import Reservation
from app.models.room import Room
from app.models.room_category import RoomCategory
from app.services.loyalty_service import get_loyalty_tiers, resolve_guest_tier


async def get_outlet_guests(
    session: AsyncSession,
    client_id: int,
    outlet_id: int,
    search: Optional[str] = None,
    tier_filter: Optional[str] = None,
    id_verified: Optional[bool] = None,
    is_blacklisted: Optional[bool] = None,
    page: int = 1,
    limit: int = 50,
) -> Tuple[List[Dict[str, Any]], int, int]:
    """
    Retrieves guests who have registered at or stayed at this specific outlet.
    Aggregates outlet-specific lifetime spend, total stays, active room, and dynamic tier.
    """
    tiers = await get_loyalty_tiers(session, client_id, outlet_id)

    # 1. Base query: guests linked to this outlet or having reservations at this outlet
    outlet_reservation_guest_ids = select(Reservation.guest_id).where(Reservation.outlet_id == outlet_id).distinct()

    stmt = select(Guest).where(
        Guest.client_id == client_id,
        or_(
            Guest.outlet_id == outlet_id,
            Guest.id.in_(outlet_reservation_guest_ids),
        ),
    )

    if id_verified is not None:
        stmt = stmt.where(Guest.id_verified == id_verified)

    if is_blacklisted is not None:
        stmt = stmt.where(Guest.is_blacklisted == is_blacklisted)

    if search and search.strip():
        q = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Guest.first_name).like(q),
                func.lower(Guest.last_name).like(q),
                Guest.phone.like(q),
                func.lower(Guest.email).like(q),
                func.lower(Guest.id_number).like(q),
                func.lower(Guest.company_name).like(q),
            )
        )

    # Load all matching guests to compute dynamic tier and stats
    # For large datasets this is typically joined, but here we preload reservations & folios for accurate outlet scoping
    stmt = stmt.options(
        selectinload(Guest.reservations),
        selectinload(Guest.folios),
    ).order_by(Guest.id.desc())

    result = await session.execute(stmt)
    all_guests = result.scalars().all()

    # Process and compute outlet-scoped metrics
    enriched_items = []
    for g in all_guests:
        # Outlet-only reservations
        outlet_res = [r for r in g.reservations if r.outlet_id == outlet_id]

        # Fulfilled stays where guest successfully checked in or checked out
        fulfilled_stays = [r for r in outlet_res if r.status in ("CHECKED_IN", "CHECKED_OUT")]
        total_stays = len(fulfilled_stays)

        # Total nights from fulfilled stays
        total_nights = 0
        for r in fulfilled_stays:
            try:
                nights = (r.check_out_date - r.check_in_date).days
                total_nights += max(1, nights)
            except Exception:
                total_nights += 1

        # Spend is only credited when check-in or checkout has been successfully done
        fulfilled_res_ids = {r.id for r in fulfilled_stays}
        fulfilled_folios = [f for f in g.folios if f.outlet_id == outlet_id and f.reservation_id in fulfilled_res_ids]
        total_spend = sum(float(f.paid_amount or 0.0) for f in fulfilled_folios)
        if total_spend == 0.0 and fulfilled_stays:
            # Fallback to reservation charges for checked-in / checked-out stays
            total_spend = sum(float(r.grand_total or 0.0) for r in fulfilled_stays)

        # Last visit date only from checked-in or checked-out stays
        last_visit_date = None
        if fulfilled_stays:
            sorted_stays = sorted(fulfilled_stays, key=lambda r: r.check_in_date, reverse=True)
            last_visit_date = sorted_stays[0].check_in_date.isoformat()

        # Active in-house room
        active_room = None
        in_house = [r for r in outlet_res if r.status == "CHECKED_IN"]
        if in_house and in_house[0].room_id:
            # Look up room number if populated
            active_room = f"Room #{in_house[0].room_id}"

        # Resolve tier dynamically against configured Settings
        resolved_tier = resolve_guest_tier(total_spend, total_stays, tiers)

        # Apply tier filter if requested
        if tier_filter and tier_filter.upper() not in ("ALL", "ANY"):
            if resolved_tier.tier_code.upper() != tier_filter.upper():
                continue

        enriched_items.append(
            {
                "id": g.id,
                "client_id": g.client_id,
                "outlet_id": g.outlet_id or outlet_id,
                "first_name": g.first_name,
                "last_name": g.last_name,
                "full_name": g.full_name,
                "phone": g.phone,
                "email": g.email,
                "date_of_birth": g.date_of_birth.isoformat() if g.date_of_birth else None,
                "gender": g.gender,
                "address_line1": g.address_line1,
                "city": g.city,
                "state": g.state,
                "postal_code": g.postal_code,
                "country": g.country,
                "company_name": g.company_name,
                "gst_number": g.gst_number,
                "id_type": g.id_type,
                "id_number": g.id_number,
                "id_verified": g.id_verified,
                "id_document_url": g.id_document_url,
                "vip_status": g.vip_status,
                "is_blacklisted": g.is_blacklisted,
                "blacklist_reason": g.blacklist_reason,
                "nationality": g.nationality,
                "special_preferences": g.special_preferences,
                "tags": g.tags or [],
                "notes": g.notes or [],
                "total_stays": total_stays,
                "total_nights": total_nights,
                "total_spend": round(total_spend, 2),
                "last_visit_date": last_visit_date,
                "active_stay_room": active_room,
                "tier_code": resolved_tier.tier_code,
                "tier_name": resolved_tier.name,
                "tier_badge_color": resolved_tier.badge_color,
                "tier_discount": float(resolved_tier.discount_percent),
                "tier_perks": resolved_tier.perks or [],
                "created_at": g.created_at.isoformat() if hasattr(g, "created_at") and g.created_at else None,
            }
        )

    # Pagination
    total_count = len(enriched_items)
    total_pages = max(1, (total_count + limit - 1) // limit)
    start_idx = (page - 1) * limit
    paginated_items = enriched_items[start_idx : start_idx + limit]

    return paginated_items, total_count, total_pages


async def get_guest_by_id(
    session: AsyncSession,
    client_id: int,
    outlet_id: int,
    guest_id: int,
) -> Optional[Dict[str, Any]]:
    """
    Retrieves full details for a single guest with outlet-scoped metrics.
    """
    stmt = (
        select(Guest)
        .where(Guest.id == guest_id, Guest.client_id == client_id)
        .options(
            selectinload(Guest.reservations),
            selectinload(Guest.folios),
        )
    )
    result = await session.execute(stmt)
    g = result.scalars().first()
    if not g:
        return None

    tiers = await get_loyalty_tiers(session, client_id, outlet_id)

    outlet_res = [r for r in g.reservations if r.outlet_id == outlet_id]
    fulfilled_stays = [r for r in outlet_res if r.status in ("CHECKED_IN", "CHECKED_OUT")]
    total_stays = len(fulfilled_stays)

    total_nights = 0
    for r in fulfilled_stays:
        try:
            nights = (r.check_out_date - r.check_in_date).days
            total_nights += max(1, nights)
        except Exception:
            total_nights += 1

    fulfilled_res_ids = {r.id for r in fulfilled_stays}
    fulfilled_folios = [f for f in g.folios if f.outlet_id == outlet_id and f.reservation_id in fulfilled_res_ids]
    total_spend = sum(float(f.paid_amount or 0.0) for f in fulfilled_folios)
    if total_spend == 0.0 and fulfilled_stays:
        total_spend = sum(float(r.grand_total or 0.0) for r in fulfilled_stays)

    last_visit_date = None
    if fulfilled_stays:
        sorted_stays = sorted(fulfilled_stays, key=lambda r: r.check_in_date, reverse=True)
        last_visit_date = sorted_stays[0].check_in_date.isoformat()

    resolved_tier = resolve_guest_tier(total_spend, total_stays, tiers)

    return {
        "id": g.id,
        "client_id": g.client_id,
        "outlet_id": g.outlet_id or outlet_id,
        "first_name": g.first_name,
        "last_name": g.last_name,
        "full_name": g.full_name,
        "phone": g.phone,
        "email": g.email,
        "date_of_birth": g.date_of_birth.isoformat() if g.date_of_birth else None,
        "gender": g.gender,
        "address_line1": g.address_line1,
        "city": g.city,
        "state": g.state,
        "postal_code": g.postal_code,
        "country": g.country,
        "company_name": g.company_name,
        "gst_number": g.gst_number,
        "id_type": g.id_type,
        "id_number": g.id_number,
        "id_verified": g.id_verified,
        "id_document_url": g.id_document_url,
        "vip_status": g.vip_status,
        "is_blacklisted": g.is_blacklisted,
        "blacklist_reason": g.blacklist_reason,
        "nationality": g.nationality,
        "special_preferences": g.special_preferences,
        "tags": g.tags or [],
        "notes": g.notes or [],
        "total_stays": total_stays,
        "total_nights": total_nights,
        "total_spend": round(total_spend, 2),
        "last_visit_date": last_visit_date,
        "tier_code": resolved_tier.tier_code,
        "tier_name": resolved_tier.name,
        "tier_badge_color": resolved_tier.badge_color,
        "tier_discount": float(resolved_tier.discount_percent),
        "tier_perks": resolved_tier.perks or [],
        "created_at": g.created_at.isoformat() if hasattr(g, "created_at") and g.created_at else None,
    }


async def get_guest_stay_history(
    session: AsyncSession,
    client_id: int,
    outlet_id: int,
    guest_id: int,
) -> List[Dict[str, Any]]:
    """
    Returns full chronological stay history for this guest at this outlet.
    """
    stmt = (
        select(Reservation)
        .where(
            Reservation.guest_id == guest_id,
            Reservation.outlet_id == outlet_id,
            Reservation.client_id == client_id,
        )
        .options(
            selectinload(Reservation.room),
            selectinload(Reservation.category),
            selectinload(Reservation.folios),
        )
        .order_by(Reservation.check_in_date.desc(), Reservation.id.desc())
    )
    result = await session.execute(stmt)
    reservations = result.scalars().all()

    stays = []
    for r in reservations:
        room_num = r.room.room_number if r.room else "Unassigned"
        category_name = r.category.name if r.category else "Standard"

        total_amount = float(r.grand_total or 0.0)
        paid_amount = 0.0
        if r.folios:
            paid_amount = sum(float(f.paid_amount or 0.0) for f in r.folios)
            if float(r.folios[0].grand_total or 0.0) > 0:
                total_amount = float(r.folios[0].grand_total)

        balance_due = max(0.0, total_amount - paid_amount)

        stays.append(
            {
                "reservation_id": r.id,
                "reservation_code": r.reservation_code,
                "room_number": room_num,
                "category_name": category_name,
                "check_in_date": r.check_in_date.isoformat(),
                "check_out_date": r.check_out_date.isoformat(),
                "status": r.status,
                "adults_count": r.adults_count,
                "children_count": r.children_count,
                "booking_source": r.booking_source,
                "total_amount": round(total_amount, 2),
                "paid_amount": round(paid_amount, 2),
                "balance_due": round(balance_due, 2),
            }
        )

    return stays


async def get_outlet_crm_stats(
    session: AsyncSession,
    client_id: int,
    outlet_id: int,
) -> Dict[str, Any]:
    """
    Calculates outlet-specific CRM KPIs and Tier breakdowns.
    """
    # Fetch all guests for this outlet
    items, total_count, _ = await get_outlet_guests(session, client_id, outlet_id, limit=5000)

    tiers = await get_loyalty_tiers(session, client_id, outlet_id)

    repeat_guests = sum(1 for item in items if item["total_stays"] > 1)
    repeat_rate = round((repeat_guests / total_count * 100), 1) if total_count > 0 else 0.0

    kyc_verified_count = sum(1 for item in items if item["id_verified"])
    blacklisted_count = sum(1 for item in items if item["is_blacklisted"])

    # Count breakdown per configured tier
    tier_counts: Dict[str, int] = {t.tier_code.upper(): 0 for t in tiers}
    for item in items:
        code = item.get("tier_code", "").upper()
        if code in tier_counts:
            tier_counts[code] += 1

    tier_breakdowns = [
        {
            "tier_code": t.tier_code,
            "tier_name": t.name,
            "badge_color": t.badge_color,
            "min_spend": float(t.min_spend),
            "guest_count": tier_counts.get(t.tier_code.upper(), 0),
        }
        for t in tiers
    ]

    return {
        "total_guests": total_count,
        "repeat_guests_count": repeat_guests,
        "repeat_guests_rate": repeat_rate,
        "kyc_verified_count": kyc_verified_count,
        "blacklisted_count": blacklisted_count,
        "tier_breakdowns": tier_breakdowns,
    }


async def create_crm_guest(
    session: AsyncSession,
    client_id: int,
    outlet_id: int,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Creates a new guest profile or updates existing by phone within the client.
    """
    phone = (data.get("phone") or "").strip()
    if not phone:
        raise ValueError("Phone number is required.")

    # Check if guest with phone already exists under this client
    stmt = select(Guest).where(Guest.client_id == client_id, Guest.phone == phone)
    result = await session.execute(stmt)
    existing = result.scalars().first()

    if existing:
        # Update existing guest and ensure outlet_id is linked
        existing.first_name = (data.get("first_name") or existing.first_name).strip()
        existing.last_name = (data.get("last_name") or existing.last_name).strip()
        if data.get("email"):
            existing.email = data["email"].strip()
        if data.get("id_type"):
            existing.id_type = data["id_type"]
        if data.get("id_number"):
            existing.id_number = data["id_number"]
        if data.get("company_name"):
            existing.company_name = data["company_name"]
        if data.get("gst_number"):
            existing.gst_number = data["gst_number"]
        if data.get("city"):
            existing.city = data["city"]
        if data.get("state"):
            existing.state = data["state"]
        if data.get("tags"):
            existing.tags = data["tags"]
        if data.get("special_preferences"):
            existing.special_preferences = data["special_preferences"]
        if not existing.outlet_id:
            existing.outlet_id = outlet_id

        await session.commit()
        return (await get_guest_by_id(session, client_id, outlet_id, existing.id)) or {}

    # Parse date of birth
    dob_val = None
    if data.get("date_of_birth"):
        try:
            dob_val = date.fromisoformat(str(data["date_of_birth"]))
        except Exception:
            dob_val = None

    guest = Guest(
        client_id=client_id,
        outlet_id=outlet_id,
        first_name=str(data.get("first_name") or "Guest").strip(),
        last_name=str(data.get("last_name") or "-").strip(),
        phone=phone,
        email=(data.get("email") or "").strip() or None,
        date_of_birth=dob_val,
        gender=data.get("gender"),
        address_line1=data.get("address_line1"),
        city=data.get("city"),
        state=data.get("state"),
        postal_code=data.get("postal_code"),
        country=data.get("country") or "India",
        company_name=data.get("company_name"),
        gst_number=data.get("gst_number"),
        id_type=data.get("id_type"),
        id_number=data.get("id_number"),
        id_verified=bool(data.get("id_verified", False)),
        id_document_url=data.get("id_document_url"),
        vip_status=data.get("vip_status") or "STANDARD",
        is_blacklisted=bool(data.get("is_blacklisted", False)),
        blacklist_reason=data.get("blacklist_reason"),
        nationality=data.get("nationality") or "Indian",
        special_preferences=data.get("special_preferences"),
        tags=data.get("tags") or [],
        notes=[],
    )
    session.add(guest)
    await session.commit()

    return (await get_guest_by_id(session, client_id, outlet_id, guest.id)) or {}


async def update_crm_guest(
    session: AsyncSession,
    client_id: int,
    outlet_id: int,
    guest_id: int,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Updates an existing guest's demographic, address, corporate, or preference fields.
    """
    guest = await session.get(Guest, guest_id)
    if not guest or guest.client_id != client_id:
        raise ValueError("Guest not found.")

    for field in (
        "first_name",
        "last_name",
        "email",
        "gender",
        "address_line1",
        "city",
        "state",
        "postal_code",
        "country",
        "company_name",
        "gst_number",
        "id_type",
        "id_number",
        "id_document_url",
        "vip_status",
        "nationality",
        "special_preferences",
    ):
        if field in data and data[field] is not None:
            setattr(guest, field, data[field])

    if "phone" in data and data["phone"]:
        guest.phone = data["phone"].strip()

    if "id_verified" in data:
        guest.id_verified = bool(data["id_verified"])

    if "is_blacklisted" in data:
        guest.is_blacklisted = bool(data["is_blacklisted"])
        if "blacklist_reason" in data:
            guest.blacklist_reason = data["blacklist_reason"]

    if "date_of_birth" in data and data["date_of_birth"]:
        try:
            guest.date_of_birth = date.fromisoformat(str(data["date_of_birth"]))
        except Exception:
            pass

    if "tags" in data and isinstance(data["tags"], list):
        guest.tags = data["tags"]

    await session.commit()
    return (await get_guest_by_id(session, client_id, outlet_id, guest.id)) or {}


async def verify_guest_kyc(
    session: AsyncSession,
    client_id: int,
    outlet_id: int,
    guest_id: int,
    id_type: Optional[str] = None,
    id_number: Optional[str] = None,
    id_document_url: Optional[str] = None,
    verified: bool = True,
) -> Dict[str, Any]:
    """
    Verifies or updates guest identity document KYC.
    """
    guest = await session.get(Guest, guest_id)
    if not guest or guest.client_id != client_id:
        raise ValueError("Guest not found.")

    guest.id_verified = verified
    if id_type:
        guest.id_type = id_type
    if id_number:
        guest.id_number = id_number
    if id_document_url:
        guest.id_document_url = id_document_url

    await session.commit()
    return (await get_guest_by_id(session, client_id, outlet_id, guest.id)) or {}


async def add_guest_crm_note(
    session: AsyncSession,
    client_id: int,
    outlet_id: int,
    guest_id: int,
    author_name: str,
    note_text: str,
) -> Dict[str, Any]:
    """
    Appends a new timestamped note to the guest profile notes timeline.
    """
    guest = await session.get(Guest, guest_id)
    if not guest or guest.client_id != client_id:
        raise ValueError("Guest not found.")

    current_notes = list(guest.notes or [])
    new_note = {
        "id": str(uuid.uuid4())[:8],
        "author_name": author_name or "Staff",
        "outlet_id": outlet_id,
        "text": note_text.strip(),
        "created_at": datetime.now().isoformat(),
    }
    current_notes.append(new_note)
    guest.notes = current_notes

    await session.commit()
    return (await get_guest_by_id(session, client_id, outlet_id, guest.id)) or {}


async def set_guest_blacklist(
    session: AsyncSession,
    client_id: int,
    outlet_id: int,
    guest_id: int,
    is_blacklisted: bool,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Blacklists or un-blacklists a guest.
    """
    guest = await session.get(Guest, guest_id)
    if not guest or guest.client_id != client_id:
        raise ValueError("Guest not found.")

    guest.is_blacklisted = is_blacklisted
    guest.blacklist_reason = reason if is_blacklisted else None

    await session.commit()
    return (await get_guest_by_id(session, client_id, outlet_id, guest.id)) or {}
