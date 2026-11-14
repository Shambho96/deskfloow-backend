import strawberry
from datetime import datetime, date
from typing import Optional
from strawberry.types import Info

from app.db.session import AsyncSessionLocal
from app.graphql.helpers import get_auth_context
from app.services.analytics_service import get_dashboard_analytics
from app.graphql.types.analytics_types import (
    DashboardAnalyticsPayload,
    KPISummaryType,
    TrendDayPointType,
    ChannelMixItemType,
    HousekeepingSummaryType,
    HousekeepingRoomItemType,
    CategoryPerformanceType,
    VIPArrivalGuestType,
)


@strawberry.type
class AnalyticsQuery:
    @strawberry.field
    async def dashboard_analytics(
        self,
        info: Info,
        target_date: Optional[str] = None,
        trend_days: int = 7,
        outlet_id: Optional[int] = None,
    ) -> DashboardAnalyticsPayload:
        """Fetch comprehensive operational & revenue analytics for the Front Desk dashboard."""
        ctx = get_auth_context(info)

        # Resolve and verify outlet_id
        resolved_outlet_id = int(outlet_id) if outlet_id is not None else int(ctx.outlet_id)

        # Security check: ensure user has rights to access this outlet
        if resolved_outlet_id != int(ctx.outlet_id) and not ctx.is_owner:
            allowed = [int(x) for x in ctx.allowed_outlets]
            if resolved_outlet_id not in allowed:
                raise Exception("Unauthorized: You do not have permission to access analytics for this outlet.")

        # Parse target date
        if target_date:
            try:
                parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
            except ValueError:
                parsed_date = datetime.utcnow().date()
        else:
            parsed_date = datetime.utcnow().date()

        async with AsyncSessionLocal() as session:
            raw = await get_dashboard_analytics(
                session=session,
                client_id=int(ctx.client_id),
                outlet_id=resolved_outlet_id,
                target_date=parsed_date,
                trend_days=trend_days,
            )

        kpis = KPISummaryType(**raw["kpis"])
        weekly_trend = [TrendDayPointType(**item) for item in raw["weekly_trend"]]
        channel_mix = [ChannelMixItemType(**item) for item in raw["channel_mix"]]

        hk_rooms = [HousekeepingRoomItemType(**r) for r in raw["housekeeping"]["rooms"]]
        housekeeping = HousekeepingSummaryType(
            clean_count=raw["housekeeping"]["clean_count"],
            cleaning_count=raw["housekeeping"]["cleaning_count"],
            dirty_count=raw["housekeeping"]["dirty_count"],
            ooo_count=raw["housekeeping"]["ooo_count"],
            rooms=hk_rooms,
        )

        cat_perf = [CategoryPerformanceType(**c) for c in raw["category_performance"]]
        vip_arrivals = [VIPArrivalGuestType(**v) for v in raw["vip_arrivals"]]

        return DashboardAnalyticsPayload(
            target_date=raw["target_date"],
            outlet_id=raw["outlet_id"],
            outlet_name=raw["outlet_name"],
            kpis=kpis,
            weekly_trend=weekly_trend,
            channel_mix=channel_mix,
            total_active_bookings=raw["total_active_bookings"],
            housekeeping=housekeeping,
            category_performance=cat_perf,
            vip_arrivals=vip_arrivals,
        )
