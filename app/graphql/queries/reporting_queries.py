import strawberry
from datetime import datetime, date
from typing import Optional, List
from strawberry.types import Info

from app.db.session import AsyncSessionLocal
from app.graphql.helpers import get_auth_context
from app.services.reporting_service import execute_custom_report, resolve_date_range
from app.services.custom_dashboard_service import (
    list_dashboards_for_user,
    get_dashboard_by_id,
)
from app.graphql.types.reporting_types import (
    ReportExecutionPayload,
    ReportMetaType,
    ChartSeriesType,
    ChartDataPointType,
    CustomDashboardType,
    CustomReportCardType,
    JSON,
)


def _map_card_to_gql(c) -> CustomReportCardType:
    return CustomReportCardType(
        id=int(c.id),
        dashboard_id=int(c.dashboard_id),
        client_id=int(c.client_id),
        created_by_user_id=int(c.created_by_user_id),
        title=c.title,
        report_type=c.report_type,
        chart_type=c.chart_type,
        group_by=c.group_by,
        date_preset=c.date_preset,
        date_from=c.date_from.isoformat() if c.date_from else None,
        date_to=c.date_to.isoformat() if c.date_to else None,
        selected_metrics=[str(m) for m in (c.selected_metrics or [])],
        outlet_ids=[int(x) for x in (c.outlet_ids or [])],
        filters=c.filters or {},
        display_order=int(c.display_order),
        card_width=int(c.card_width),
        created_at=c.created_at.isoformat() if hasattr(c.created_at, "isoformat") else str(c.created_at),
    )


def _map_dashboard_to_gql(d) -> CustomDashboardType:
    cards = [_map_card_to_gql(c) for c in (d.cards or [])]
    return CustomDashboardType(
        id=int(d.id),
        client_id=int(d.client_id),
        created_by_user_id=int(d.created_by_user_id),
        outlet_id=int(d.outlet_id) if d.outlet_id is not None else None,
        name=d.name,
        description=d.description,
        icon=d.icon or "LayoutDashboard",
        visibility=d.visibility,
        shared_members=d.shared_members or [],
        is_default=bool(d.is_default),
        display_order=int(d.display_order),
        card_count=len(cards),
        cards=cards,
        created_at=d.created_at.isoformat() if hasattr(d.created_at, "isoformat") else str(d.created_at),
    )


@strawberry.type
class ReportingQuery:
    @strawberry.field
    async def execute_report(
        self,
        info: Info,
        report_type: str = "ROOM_REVENUE",
        outlet_ids: Optional[List[int]] = None,
        date_preset: str = "last_30_days",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        group_by: str = "daily",
        selected_metrics: Optional[List[str]] = None,
        filters: Optional[JSON] = None,
    ) -> ReportExecutionPayload:
        """
        Executes a live custom report query and returns aggregated rows + chart series.
        """
        ctx = get_auth_context(info)

        # Resolve authorized outlet IDs
        resolved_outlets = outlet_ids or ([int(ctx.outlet_id)] if ctx.outlet_id else [])
        if not resolved_outlets:
            resolved_outlets = [int(ctx.outlet_id)] if ctx.outlet_id else [1]

        # Security check
        if not ctx.is_owner:
            allowed = set([int(x) for x in ctx.allowed_outlets] + [int(ctx.outlet_id)])
            for oid in resolved_outlets:
                if oid not in allowed:
                    raise Exception(f"Unauthorized: You do not have permission for outlet #{oid}.")

        # Parse date range
        parsed_from = datetime.strptime(date_from, "%Y-%m-%d").date() if date_from else None
        parsed_to = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else None
        start_d, end_d = resolve_date_range(date_preset, parsed_from, parsed_to)

        async with AsyncSessionLocal() as session:
            raw = await execute_custom_report(
                session=session,
                client_id=int(ctx.client_id),
                outlet_ids=resolved_outlets,
                report_type=report_type,
                date_from=start_d,
                date_to=end_d,
                group_by=group_by,
                selected_metrics=selected_metrics,
                filters=filters or {},
            )

        meta = ReportMetaType(
            report_type=raw["meta"]["report_type"],
            total_rows=raw["meta"]["total_rows"],
            date_from=raw["meta"]["date_from"],
            date_to=raw["meta"]["date_to"],
            group_by=raw["meta"]["group_by"],
            outlet_names=raw["meta"]["outlet_names"],
            summary=raw["meta"]["summary"],
        )

        series = [
            ChartSeriesType(
                name=s["name"],
                metric_key=s["metric_key"],
                color=s["color"],
                data=[ChartDataPointType(label=dp["label"], value=dp["value"]) for dp in s["data"]],
            )
            for s in raw["chart_series"]
        ]

        return ReportExecutionPayload(
            meta=meta,
            rows=raw["rows"],
            chart_series=series,
        )

    @strawberry.field
    async def user_dashboards(
        self,
        info: Info,
        outlet_id: Optional[int] = None,
    ) -> List[CustomDashboardType]:
        """
        Returns all dashboard workspaces accessible to current user.
        """
        ctx = get_auth_context(info)
        resolved_outlet_id = (
            int(outlet_id) if outlet_id is not None else (int(ctx.outlet_id) if ctx.outlet_id else None)
        )

        async with AsyncSessionLocal() as session:
            dashboards = await list_dashboards_for_user(
                session=session,
                client_id=int(ctx.client_id),
                user_id=int(ctx.user_id),
                outlet_id=resolved_outlet_id,
                is_owner=ctx.is_owner,
            )
            return [_map_dashboard_to_gql(d) for d in dashboards]

    @strawberry.field
    async def custom_dashboard(
        self,
        info: Info,
        dashboard_id: int,
    ) -> CustomDashboardType:
        """
        Fetches a single dashboard by ID with all its report cards.
        """
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as session:
            dash = await get_dashboard_by_id(
                session=session,
                dashboard_id=dashboard_id,
                client_id=int(ctx.client_id),
                user_id=int(ctx.user_id),
                is_owner=ctx.is_owner,
            )
            return _map_dashboard_to_gql(dash)
