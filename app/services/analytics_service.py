from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional
from sqlalchemy import select, func, and_, or_, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.outlet import Outlet
from app.models.room import Room
from app.models.room_category import RoomCategory
from app.models.reservation import Reservation
from app.models.guest import Guest
from app.models.folio import GuestFolio, FolioLineItem
from app.models.housekeeping import HousekeepingTask, MaintenanceTicket


async def get_dashboard_analytics(
    session: AsyncSession,
    client_id: int,
    outlet_id: int,
    target_date: date,
    trend_days: int = 7,
) -> Dict[str, Any]:
    """
    Computes comprehensive, real-time hotel operational & financial analytics for the Dashboard.
    Strictly isolated by client_id and outlet_id.
    """
    # 1. Fetch Outlet verification
    outlet_res = await session.execute(select(Outlet).where(Outlet.id == outlet_id, Outlet.client_id == client_id))
    outlet = outlet_res.scalar_one_or_none()
    if not outlet:
        raise ValueError(f"Outlet #{outlet_id} not found or does not belong to client #{client_id}.")

    # 2. Fetch all physical active rooms for this outlet
    rooms_stmt = (
        select(Room)
        .options(selectinload(Room.category), selectinload(Room.floor))
        .where(
            Room.client_id == client_id,
            Room.outlet_id == outlet_id,
            Room.is_active.is_(True),
        )
        .order_by(Room.room_number)
    )
    rooms_res = await session.execute(rooms_stmt)
    all_rooms = rooms_res.scalars().all()
    total_rooms_count = len(all_rooms)

    # 3. Fetch active OOO maintenance tickets
    ooo_stmt = select(MaintenanceTicket).where(
        MaintenanceTicket.client_id == client_id,
        MaintenanceTicket.outlet_id == outlet_id,
        MaintenanceTicket.is_room_ooo.is_(True),
        MaintenanceTicket.status != "RESOLVED",
    )
    ooo_res = await session.execute(ooo_stmt)
    ooo_tickets = ooo_res.scalars().all()
    ooo_room_ids = {t.room_id for t in ooo_tickets}

    # 4. Fetch active housekeeping tasks
    hk_stmt = select(HousekeepingTask).where(
        HousekeepingTask.client_id == client_id,
        HousekeepingTask.outlet_id == outlet_id,
        HousekeepingTask.status.in_(["PENDING", "IN_PROGRESS"]),
    )
    hk_res = await session.execute(hk_stmt)
    hk_tasks = hk_res.scalars().all()
    in_progress_room_ids = {t.room_id for t in hk_tasks if t.status == "IN_PROGRESS"}
    pending_room_ids = {t.room_id for t in hk_tasks if t.status == "PENDING"}

    # 5. Classify Housekeeping Status across physical rooms
    clean_rooms = []
    cleaning_rooms = []
    dirty_rooms = []
    ooo_rooms = []
    classified_rooms_list = []

    for r in all_rooms:
        r_id = int(r.id)
        cat_name = r.category.name if r.category else "Standard Room"

        if r_id in ooo_room_ids or r.status == "OOO":
            room_status = "OOO"
            ooo_rooms.append(r)
        elif r_id in in_progress_room_ids or r.status == "CLEANING":
            room_status = "CLEANING"
            cleaning_rooms.append(r)
        elif r_id in pending_room_ids or r.status == "DIRTY":
            room_status = "DIRTY"
            dirty_rooms.append(r)
        else:
            room_status = "CLEAN"
            clean_rooms.append(r)

        classified_rooms_list.append(
            {
                "room_id": r_id,
                "room_number": r.room_number,
                "category_name": cat_name,
                "status": room_status,
            }
        )

    salable_rooms_count = max(0, total_rooms_count - len(ooo_rooms))

    # 6. Fetch Reservations for target date & 7-day trend window
    start_trend_date = target_date - timedelta(days=max(1, trend_days - 1))

    trend_reservations_stmt = (
        select(Reservation)
        .options(
            selectinload(Reservation.guest),
            selectinload(Reservation.room),
            selectinload(Reservation.category),
            selectinload(Reservation.folios),
        )
        .where(
            Reservation.client_id == client_id,
            Reservation.outlet_id == outlet_id,
            Reservation.status.not_in(["CANCELLED", "NO_SHOW"]),
            Reservation.check_in_date <= target_date,
            Reservation.check_out_date > start_trend_date,
        )
    )
    trend_res = await session.execute(trend_reservations_stmt)
    active_range_reservations = trend_res.scalars().all()

    # 7. In-House Occupancy and Revenue for Target Date
    # Guest stays if check_in_date <= target_date < check_out_date
    target_date_inhouse = [
        res for res in active_range_reservations if res.check_in_date <= target_date < res.check_out_date
    ]
    occupied_count = len(target_date_inhouse)
    daily_room_revenue = sum(float(res.rate_per_night or 0.0) for res in target_date_inhouse)

    occupancy_percent = round((occupied_count / salable_rooms_count) * 100.0, 1) if salable_rooms_count > 0 else 0.0
    adr = round(daily_room_revenue / occupied_count, 2) if occupied_count > 0 else 0.0
    revpar = round(daily_room_revenue / salable_rooms_count, 2) if salable_rooms_count > 0 else 0.0

    # 8. Arrivals on Target Date
    arrivals_stmt = (
        select(Reservation)
        .options(
            selectinload(Reservation.guest),
            selectinload(Reservation.room),
            selectinload(Reservation.category),
            selectinload(Reservation.folios),
        )
        .where(
            Reservation.client_id == client_id,
            Reservation.outlet_id == outlet_id,
            Reservation.check_in_date == target_date,
            Reservation.status != "CANCELLED",
        )
    )
    arrivals_res = await session.execute(arrivals_stmt)
    today_arrivals = arrivals_res.scalars().all()

    arrivals_expected = len(today_arrivals)
    arrivals_checked_in = sum(1 for r in today_arrivals if r.status == "CHECKED_IN")
    arrivals_pending = sum(1 for r in today_arrivals if r.status == "RESERVED")

    # 9. Departures on Target Date
    departures_stmt = select(Reservation).where(
        Reservation.client_id == client_id,
        Reservation.outlet_id == outlet_id,
        Reservation.check_out_date == target_date,
        Reservation.status.in_(["CHECKED_IN", "CHECKED_OUT"]),
    )
    departures_res = await session.execute(departures_stmt)
    today_departures = departures_res.scalars().all()

    departures_due = len(today_departures)
    departures_settled = sum(1 for r in today_departures if r.status == "CHECKED_OUT")
    departures_pending = sum(1 for r in today_departures if r.status == "CHECKED_IN")

    # 10. TrevPAR & Total Line Items Revenue Posted Today
    folio_items_stmt = select(func.coalesce(func.sum(FolioLineItem.total_amount), 0.0)).where(
        FolioLineItem.client_id == client_id,
        FolioLineItem.outlet_id == outlet_id,
        cast(FolioLineItem.posted_at, Date) == target_date,
    )
    folio_items_res = await session.execute(folio_items_stmt)
    total_posted_today = float(folio_items_res.scalar_one_or_none() or 0.0)
    effective_total_rev = total_posted_today if total_posted_today > 0 else daily_room_revenue
    trevpar = round(effective_total_rev / salable_rooms_count, 2) if salable_rooms_count > 0 else 0.0

    # 11. ALOS (Average Length of Stay)
    all_active_stmt = select(Reservation).where(
        Reservation.client_id == client_id,
        Reservation.outlet_id == outlet_id,
        Reservation.status.not_in(["CANCELLED", "NO_SHOW"]),
        or_(
            and_(Reservation.check_in_date <= target_date, Reservation.check_out_date > target_date),
            Reservation.check_in_date == target_date,
        ),
    )
    all_active_res = await session.execute(all_active_stmt)
    all_active_reservations = all_active_res.scalars().all()

    total_active_bookings = len(all_active_reservations)
    if total_active_bookings > 0:
        total_nights = sum(max(1, (r.check_out_date - r.check_in_date).days) for r in all_active_reservations)
        alos = round(total_nights / total_active_bookings, 1)
    else:
        alos = 1.0

    # 12. 7-Day Revenue & Occupancy Historical/Pacing Trend
    days_map = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekly_trend = []

    for i in range(trend_days):
        day_date = start_trend_date + timedelta(days=i)
        day_name = days_map[day_date.weekday()]

        # In-house on day_date: check_in_date <= day_date < check_out_date
        day_inhouse = [res for res in active_range_reservations if res.check_in_date <= day_date < res.check_out_date]
        day_occ_count = len(day_inhouse)
        day_rev = sum(float(res.rate_per_night or 0.0) for res in day_inhouse)
        day_occ_pct = round((day_occ_count / salable_rooms_count) * 100.0, 1) if salable_rooms_count > 0 else 0.0
        day_adr = round(day_rev / day_occ_count, 2) if day_occ_count > 0 else 0.0

        weekly_trend.append(
            {
                "day": day_name,
                "date": day_date.isoformat(),
                "revenue": round(day_rev, 2),
                "occupancy": day_occ_pct,
                "adr": day_adr,
            }
        )

    # 13. Channel / Booking Source Mix
    channel_counts: Dict[str, Dict[str, Any]] = {
        "Direct Walk-In": {"source_key": "WALKIN", "count": 0, "revenue": 0.0, "color": "var(--chart-1)"},
        "OTAs (Booking/Agoda)": {"source_key": "OTA", "count": 0, "revenue": 0.0, "color": "var(--primary)"},
        "Direct Website": {"source_key": "WEBSITE", "count": 0, "revenue": 0.0, "color": "var(--chart-4)"},
        "Corporate Accounts": {"source_key": "CORPORATE", "count": 0, "revenue": 0.0, "color": "var(--chart-3)"},
        "Other Direct": {"source_key": "OTHER", "count": 0, "revenue": 0.0, "color": "var(--chart-2)"},
    }

    for res in all_active_reservations:
        src = (res.booking_source or "").upper()
        res_grand_total = float(res.grand_total or 0.0)

        if "WALKIN" in src:
            target_chan = "Direct Walk-In"
        elif any(k in src for k in ["OTA", "BOOKING", "AGODA", "MMT", "MAKEMYTRIP"]):
            target_chan = "OTAs (Booking/Agoda)"
        elif any(k in src for k in ["WEB", "WEBSITE", "DIRECT"]):
            target_chan = "Direct Website"
        elif any(k in src for k in ["CORP", "CORPORATE"]):
            target_chan = "Corporate Accounts"
        else:
            target_chan = "Other Direct"

        channel_counts[target_chan]["count"] += 1
        channel_counts[target_chan]["revenue"] += res_grand_total

    channel_mix_list = []
    for chan_name, info in channel_counts.items():
        cnt = info["count"]
        pct = round((cnt / total_active_bookings) * 100.0, 1) if total_active_bookings > 0 else 0.0
        channel_mix_list.append(
            {
                "name": chan_name,
                "source_key": info["source_key"],
                "count": cnt,
                "percentage": pct,
                "revenue": round(info["revenue"], 2),
                "color": info["color"],
            }
        )

    # 14. Room Category Performance & ADR Yield
    categories_stmt = (
        select(RoomCategory)
        .options(selectinload(RoomCategory.rooms))
        .where(
            RoomCategory.client_id == client_id,
            RoomCategory.outlet_id == outlet_id,
            RoomCategory.is_active.is_(True),
        )
    )
    categories_res = await session.execute(categories_stmt)
    all_categories = categories_res.scalars().all()

    category_performance_list = []
    for cat in all_categories:
        cat_id = int(cat.id)
        cat_total_rooms = sum(1 for r in cat.rooms if r.is_active)

        # Occupied rooms belonging to this category
        cat_occupied_res = [r for r in target_date_inhouse if r.category_id == cat_id]
        cat_occupied_count = len(cat_occupied_res)
        cat_occ_pct = round((cat_occupied_count / cat_total_rooms) * 100.0, 1) if cat_total_rooms > 0 else 0.0
        cat_rev = sum(float(r.rate_per_night or 0.0) for r in cat_occupied_res)
        cat_adr = round(cat_rev / cat_occupied_count, 2) if cat_occupied_count > 0 else float(cat.base_price or 0.0)

        category_performance_list.append(
            {
                "category_id": cat_id,
                "category": cat.name,
                "occupancy": cat_occ_pct,
                "adr": cat_adr,
                "total_rooms": cat_total_rooms,
                "occupied": cat_occupied_count,
            }
        )

    # 15. VIP & Noted Arriving Guests (Today)
    vip_arrivals_list = []
    for r in today_arrivals:
        guest = r.guest
        special_reqs = list(r.special_requests) if r.special_requests else []

        if guest and hasattr(guest, "tags") and guest.tags:
            for t in guest.tags:
                if str(t) not in special_reqs:
                    special_reqs.append(str(t))
        if guest and getattr(guest, "special_preferences", None):
            if guest.special_preferences not in special_reqs:
                special_reqs.append(guest.special_preferences)

        vip_status = getattr(guest, "vip_status", "STANDARD") if guest else "STANDARD"
        is_vip = vip_status in ["VIP", "VVIP"] or len(special_reqs) > 0

        if is_vip and guest:
            guest_full_name = f"{guest.first_name} {guest.last_name}".strip()
            room_num = r.room.room_number if r.room else "Unassigned"
            cat_name = r.category.name if r.category else "Standard"
            folio_id = int(r.folios[0].id) if r.folios else None

            vip_arrivals_list.append(
                {
                    "reservation_id": int(r.id),
                    "reservation_code": r.reservation_code,
                    "guest_name": guest_full_name,
                    "phone": guest.phone,
                    "room_number": room_num,
                    "category_name": cat_name,
                    "eta": r.eta or "12:00 PM",
                    "status": r.status,
                    "vip_status": vip_status,
                    "special_requests": special_reqs,
                    "folio_id": folio_id,
                }
            )

    # Return complete aggregated payload
    return {
        "target_date": target_date.isoformat(),
        "outlet_id": int(outlet.id),
        "outlet_name": outlet.name,
        "kpis": {
            "occupancy_percentage": occupancy_percent,
            "occupied_rooms": occupied_count,
            "total_rooms": total_rooms_count,
            "salable_rooms": salable_rooms_count,
            "arrivals_expected": arrivals_expected,
            "arrivals_checked_in": arrivals_checked_in,
            "arrivals_pending": arrivals_pending,
            "departures_due": departures_due,
            "departures_settled": departures_settled,
            "departures_pending": departures_pending,
            "daily_room_revenue": round(daily_room_revenue, 2),
            "adr": adr,
            "revpar": revpar,
            "trevpar": trevpar,
            "alos": alos,
        },
        "weekly_trend": weekly_trend,
        "channel_mix": channel_mix_list,
        "total_active_bookings": total_active_bookings,
        "housekeeping": {
            "clean_count": len(clean_rooms),
            "cleaning_count": len(cleaning_rooms),
            "dirty_count": len(dirty_rooms),
            "ooo_count": len(ooo_rooms),
            "rooms": classified_rooms_list,
        },
        "category_performance": category_performance_list,
        "vip_arrivals": vip_arrivals_list,
    }
