"""
Reporting Engine Service
Handles query generation, metric aggregation, time grouping, and chart series transformation.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import select, func, and_, or_, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outlet import Outlet
from app.models.room import Room
from app.models.room_category import RoomCategory
from app.models.reservation import Reservation
from app.models.guest import Guest
from app.models.folio import GuestFolio, FolioLineItem, FolioPayment
from app.models.housekeeping import HousekeepingTask


def resolve_date_range(
    preset: str,
    custom_from: Optional[date] = None,
    custom_to: Optional[date] = None,
) -> Tuple[date, date]:
    """Resolves standard date presets into concrete start and end dates."""
    today = datetime.utcnow().date()
    p = (preset or "last_30_days").lower()

    if p == "today":
        return today, today
    elif p == "yesterday":
        y = today - timedelta(days=1)
        return y, y
    elif p == "last_7_days":
        return today - timedelta(days=6), today
    elif p == "last_14_days":
        return today - timedelta(days=13), today
    elif p == "last_30_days":
        return today - timedelta(days=29), today
    elif p in ("month_to_date", "this_month"):
        start = today.replace(day=1)
        return start, today
    elif p == "last_month":
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        start_prev = last_prev.replace(day=1)
        return start_prev, last_prev
    elif p == "last_3_months":
        return today - timedelta(days=90), today
    elif p == "last_6_months":
        return today - timedelta(days=180), today
    elif p == "year_to_date":
        start_year = today.replace(month=1, day=1)
        return start_year, today
    elif p in ("last_1_year", "last_year"):
        return today - timedelta(days=364), today
    elif p == "custom" and custom_from and custom_to:
        if custom_from > custom_to:
            return custom_to, custom_from
        return custom_from, custom_to
    else:
        # Default fallback
        return today - timedelta(days=29), today


async def execute_custom_report(
    session: AsyncSession,
    client_id: int,
    outlet_ids: List[int],
    report_type: str,
    date_from: date,
    date_to: date,
    group_by: str = "daily",
    selected_metrics: Optional[List[str]] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Executes a custom report query based on selected metrics and group_by window.
    Strictly isolated by client_id and authorized outlet_ids.
    """
    metrics = selected_metrics if selected_metrics and len(selected_metrics) > 0 else ["room_revenue"]
    filters = filters or {}

    # Verify outlets
    outlets_res = await session.execute(select(Outlet).where(Outlet.client_id == client_id, Outlet.id.in_(outlet_ids)))
    outlets = outlets_res.scalars().all()
    outlet_names = [o.name for o in outlets] or ["All Selected Outlets"]

    # 1. Total rooms count in selected outlets for occupancy & RevPAR
    rooms_count_res = await session.execute(
        select(func.count(Room.id)).where(
            Room.client_id == client_id,
            Room.outlet_id.in_(outlet_ids),
            Room.is_active.is_(True),
        )
    )
    total_rooms_count = rooms_count_res.scalar() or 1

    # 2. Build time bucket series (Daily, Weekly, or Monthly)
    curr = date_from
    periods: List[Dict[str, Any]] = []

    if group_by == "monthly":
        # Group by year-month
        month_set = set()
        while curr <= date_to:
            m_key = curr.strftime("%Y-%m")
            if m_key not in month_set:
                month_set.add(m_key)
                m_start = max(curr.replace(day=1), date_from)
                if curr.month == 12:
                    next_month_first = curr.replace(year=curr.year + 1, month=1, day=1)
                else:
                    next_month_first = curr.replace(month=curr.month + 1, day=1)
                m_end = min(next_month_first - timedelta(days=1), date_to)

                periods.append(
                    {
                        "key": m_key,
                        "label": curr.strftime("%b '%y"),
                        "date_range": f"{m_start.strftime('%d %b')} – {m_end.strftime('%d %b')}",
                        "start": m_start,
                        "end": m_end,
                    }
                )
            curr += timedelta(days=1)
    elif group_by == "weekly":
        # Group by ISO week (Monday to Sunday)
        curr_week_start = date_from - timedelta(days=date_from.weekday())
        while curr_week_start <= date_to:
            curr_week_end = curr_week_start + timedelta(days=6)
            iso_year, iso_week, _ = curr_week_start.isocalendar()
            w_key = f"{iso_year}-W{iso_week:02d}"

            # Clamped range within selected report bounds
            active_start = max(curr_week_start, date_from)
            active_end = min(curr_week_end, date_to)

            if curr_week_start.month == curr_week_end.month:
                date_range_display = f"{curr_week_start.strftime('%d')} – {curr_week_end.strftime('%d %b')}"
            else:
                date_range_display = f"{curr_week_start.strftime('%d %b')} – {curr_week_end.strftime('%d %b')}"

            if not any(p["key"] == w_key for p in periods):
                periods.append(
                    {
                        "key": w_key,
                        "label": f"Week {iso_week}",
                        "date_range": date_range_display,
                        "start": active_start,
                        "end": active_end,
                    }
                )
            curr_week_start += timedelta(days=7)
    else:
        # Daily
        while curr <= date_to:
            periods.append(
                {
                    "key": curr.isoformat(),
                    "label": curr.strftime("%d %b"),
                    "date": curr,
                }
            )
            curr += timedelta(days=1)

    # 3. Fetch Line Items Revenue by category in range
    line_items_stmt = (
        select(
            func.date(FolioLineItem.posted_at).label("day"),
            FolioLineItem.charge_category,
            func.sum(FolioLineItem.total_amount).label("total"),
            func.sum(FolioLineItem.tax_amount).label("tax"),
        )
        .where(
            FolioLineItem.client_id == client_id,
            FolioLineItem.outlet_id.in_(outlet_ids),
            func.date(FolioLineItem.posted_at) >= date_from,
            func.date(FolioLineItem.posted_at) <= date_to,
        )
        .group_by(func.date(FolioLineItem.posted_at), FolioLineItem.charge_category)
    )
    line_items_res = await session.execute(line_items_stmt)
    line_items_data = line_items_res.all()

    # 4. Fetch Payments by method in range
    payments_stmt = (
        select(
            func.date(FolioPayment.payment_date).label("day"),
            FolioPayment.payment_method,
            func.sum(FolioPayment.amount).label("total"),
        )
        .where(
            FolioPayment.client_id == client_id,
            FolioPayment.outlet_id.in_(outlet_ids),
            FolioPayment.status == "SUCCESS",
            func.date(FolioPayment.payment_date) >= date_from,
            func.date(FolioPayment.payment_date) <= date_to,
        )
        .group_by(func.date(FolioPayment.payment_date), FolioPayment.payment_method)
    )
    payments_res = await session.execute(payments_stmt)
    payments_data = payments_res.all()

    # 5. Fetch Reservations in range for Occupancy, ADR, Arrivals, Departures
    res_stmt = select(Reservation).where(
        Reservation.client_id == client_id,
        Reservation.outlet_id.in_(outlet_ids),
        Reservation.status.in_(["RESERVED", "CHECKED_IN", "CHECKED_OUT"]),
        or_(
            and_(Reservation.check_in_date <= date_to, Reservation.check_out_date >= date_from),
            and_(Reservation.check_in_date >= date_from, Reservation.check_in_date <= date_to),
        ),
    )
    res_rows = (await session.execute(res_stmt)).scalars().all()

    # Map raw data per day
    day_metrics: Dict[date, Dict[str, float]] = {}
    for p in periods:
        target_d = p.get("date") or p["start"]
        day_metrics[target_d] = {
            "room_revenue": 0.0,
            "fb_revenue": 0.0,
            "other_revenue": 0.0,
            "total_revenue": 0.0,
            "tax_collected": 0.0,
            "cash_collected": 0.0,
            "upi_collected": 0.0,
            "card_collected": 0.0,
            "occupied_rooms": 0.0,
            "occupancy_pct": 0.0,
            "adr": 0.0,
            "revpar": 0.0,
            "arrivals_count": 0.0,
            "departures_count": 0.0,
            "active_bookings": 0.0,
        }

    # Aggregate line items
    for row in line_items_data:
        d = row.day
        if d in day_metrics:
            amt = float(row.total or 0.0)
            tax = float(row.tax or 0.0)
            day_metrics[d]["tax_collected"] += tax
            day_metrics[d]["total_revenue"] += amt

            cat = str(row.charge_category or "").upper()
            if cat == "ROOM_CHARGE":
                day_metrics[d]["room_revenue"] += amt
            elif cat == "FOOD_BEVERAGE":
                day_metrics[d]["fb_revenue"] += amt
            else:
                day_metrics[d]["other_revenue"] += amt

    # Aggregate payments
    for row in payments_data:
        d = row.day
        if d in day_metrics:
            amt = float(row.total or 0.0)
            method = str(row.payment_method or "").upper()
            if method == "CASH":
                day_metrics[d]["cash_collected"] += amt
            elif method == "UPI_QR":
                day_metrics[d]["upi_collected"] += amt
            elif "CARD" in method:
                day_metrics[d]["card_collected"] += amt

    # Aggregate reservations (occupancy & arrivals)
    for r in res_rows:
        # Check arrivals
        if r.check_in_date in day_metrics:
            day_metrics[r.check_in_date]["arrivals_count"] += 1.0
        # Check departures
        if r.check_out_date in day_metrics:
            day_metrics[r.check_out_date]["departures_count"] += 1.0

        # Occupied date range
        start_d = max(r.check_in_date, date_from)
        end_d = min(r.check_out_date, date_to)
        curr_d = start_d
        while curr_d < end_d:
            if curr_d in day_metrics:
                day_metrics[curr_d]["occupied_rooms"] += 1.0
                day_metrics[curr_d]["active_bookings"] += 1.0
            curr_d += timedelta(days=1)

    # Compute Occupancy %, ADR, RevPAR per day
    for d, vals in day_metrics.items():
        occ = (vals["occupied_rooms"] / total_rooms_count) * 100.0 if total_rooms_count > 0 else 0.0
        vals["occupancy_pct"] = round(min(occ, 100.0), 1)

        # Fallback room rev from reservations if folio not closed yet
        room_rev = vals["room_revenue"]
        occupied = vals["occupied_rooms"]
        adr = (room_rev / occupied) if occupied > 0 else 0.0
        revpar = (room_rev / total_rooms_count) if total_rooms_count > 0 else 0.0

        vals["adr"] = round(adr, 2)
        vals["revpar"] = round(revpar, 2)

    # 6. Format Final Result Rows according to group_by
    rows: List[Dict[str, Any]] = []
    summary_totals: Dict[str, float] = {m: 0.0 for m in metrics}

    for p in periods:
        if group_by == "daily":
            target_d = p["date"]
            row_vals = day_metrics.get(target_d, {})
            row_item: Dict[str, Any] = {
                "period": p["label"],
                "date": target_d.isoformat(),
            }
            for m in metrics:
                val = round(row_vals.get(m, 0.0), 2)
                row_item[m] = val
                summary_totals[m] += val
        else:
            # Weekly or Monthly bucket: aggregate metrics across all days in range
            start_d = p["start"]
            end_d = p["end"]
            bucket_days = []
            curr_bucket_d = start_d
            while curr_bucket_d <= end_d:
                bucket_days.append(curr_bucket_d)
                curr_bucket_d += timedelta(days=1)

            num_days = max(len(bucket_days), 1)

            sum_metrics = {
                "room_revenue": 0.0,
                "total_revenue": 0.0,
                "fb_revenue": 0.0,
                "other_revenue": 0.0,
                "tax_collected": 0.0,
                "cash_collected": 0.0,
                "upi_collected": 0.0,
                "card_collected": 0.0,
                "arrivals_count": 0.0,
                "departures_count": 0.0,
                "occupied_rooms": 0.0,
                "active_bookings": 0.0,
            }

            for bd in bucket_days:
                if bd in day_metrics:
                    d_val = day_metrics[bd]
                    for smk in sum_metrics:
                        sum_metrics[smk] += d_val.get(smk, 0.0)

            total_room_rev = sum_metrics["room_revenue"]
            total_occ_rooms = sum_metrics["occupied_rooms"]
            possible_rooms = total_rooms_count * num_days

            occ_pct = (total_occ_rooms / possible_rooms * 100.0) if possible_rooms > 0 else 0.0
            adr = (total_room_rev / total_occ_rooms) if total_occ_rooms > 0 else 0.0
            revpar = (total_room_rev / possible_rooms) if possible_rooms > 0 else 0.0

            bucket_computed = {
                **sum_metrics,
                "occupancy_pct": round(min(occ_pct, 100.0), 1),
                "adr": round(adr, 2),
                "revpar": round(revpar, 2),
            }

            row_item: Dict[str, Any] = {
                "period": p["label"],
                "date": start_d.isoformat(),
                "date_range": p.get("date_range", ""),
            }

            for m in metrics:
                val = round(bucket_computed.get(m, 0.0), 2)
                row_item[m] = val
                summary_totals[m] += val

        rows.append(row_item)

    # Compute summary averages for rate metrics
    if len(rows) > 0:
        if "occupancy_pct" in summary_totals:
            summary_totals["occupancy_pct"] = round(summary_totals["occupancy_pct"] / len(rows), 1)
        if "adr" in summary_totals:
            total_room_rev = summary_totals.get("room_revenue", 0.0)
            total_occ = sum(r.get("occupied_rooms", 0.0) for r in rows)
            summary_totals["adr"] = round(total_room_rev / total_occ, 2) if total_occ > 0 else 0.0
        if "revpar" in summary_totals:
            total_room_rev = summary_totals.get("room_revenue", 0.0)
            days_count = max(len(rows), 1)
            summary_totals["revpar"] = round(total_room_rev / (total_rooms_count * days_count), 2)

    # 7. Build Recharts-ready Chart Series
    # Palette matching theme
    metric_colors = {
        "room_revenue": "#7c3aed",  # Purple
        "total_revenue": "#2563eb",  # Blue
        "fb_revenue": "#f59e0b",  # Amber
        "other_revenue": "#10b981",  # Emerald
        "tax_collected": "#6b7280",  # Zinc
        "cash_collected": "#14b8a6",  # Teal
        "upi_collected": "#8b5cf6",  # Violet
        "card_collected": "#ec4899",  # Pink
        "occupancy_pct": "#06b6d4",  # Cyan
        "adr": "#f97316",  # Orange
        "revpar": "#84cc16",  # Lime
        "arrivals_count": "#3b82f6",  # Sky
        "departures_count": "#ef4444",  # Red
        "active_bookings": "#a855f7",  # Purple
    }

    metric_labels = {
        "room_revenue": "Room Revenue (₹)",
        "total_revenue": "Total Revenue (₹)",
        "fb_revenue": "F&B Revenue (₹)",
        "other_revenue": "Other Revenue (₹)",
        "tax_collected": "Tax Collected (₹)",
        "cash_collected": "Cash Collected (₹)",
        "upi_collected": "UPI Collected (₹)",
        "card_collected": "Card Collected (₹)",
        "occupancy_pct": "Occupancy (%)",
        "adr": "ADR (₹)",
        "revpar": "RevPAR (₹)",
        "arrivals_count": "Arrivals",
        "departures_count": "Departures",
        "active_bookings": "Bookings",
    }

    chart_series = []
    for m in metrics:
        data_points = []
        for r in rows:
            data_points.append(
                {
                    "label": r["period"],
                    "value": float(r.get(m, 0.0)),
                }
            )
        chart_series.append(
            {
                "name": metric_labels.get(m, m.replace("_", " ").title()),
                "metric_key": m,
                "data": data_points,
                "color": metric_colors.get(m, "#7c3aed"),
            }
        )

    return {
        "meta": {
            "report_type": report_type,
            "total_rows": len(rows),
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "group_by": group_by,
            "outlet_names": outlet_names,
            "summary": summary_totals,
        },
        "rows": rows,
        "chart_series": chart_series,
    }
