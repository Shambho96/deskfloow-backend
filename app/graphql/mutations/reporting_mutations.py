import strawberry
from datetime import datetime
from strawberry.types import Info

from app.db.session import AsyncSessionLocal
from app.graphql.helpers import get_auth_context
from app.services.custom_dashboard_service import (
    create_custom_dashboard,
    update_custom_dashboard,
    delete_custom_dashboard,
    reorder_dashboards,
    add_report_card,
    update_report_card,
    delete_report_card,
    reorder_report_cards,
)
from app.graphql.types.reporting_types import (
    CustomDashboardType,
    CustomReportCardType,
    CreateDashboardInput,
    UpdateDashboardInput,
    CreateReportCardInput,
    UpdateReportCardInput,
    ReorderCardsInput,
    ReorderDashboardsInput,
)
from app.graphql.queries.reporting_queries import _map_dashboard_to_gql, _map_card_to_gql


@strawberry.type
class ReportingMutation:
    @strawberry.mutation
    async def create_dashboard(
        self,
        info: Info,
        input: CreateDashboardInput,
    ) -> CustomDashboardType:
        """Creates a new dashboard workspace."""
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as session:
            dash = await create_custom_dashboard(
                session=session,
                client_id=int(ctx.client_id),
                user_id=int(ctx.user_id),
                name=input.name,
                description=input.description,
                icon=input.icon or "LayoutDashboard",
                visibility=input.visibility or "PRIVATE",
                shared_members=input.shared_members or [],
                outlet_id=input.outlet_id or (int(ctx.outlet_id) if ctx.outlet_id else None),
            )
            return _map_dashboard_to_gql(dash)

    @strawberry.mutation
    async def update_dashboard(
        self,
        info: Info,
        id: int,
        input: UpdateDashboardInput,
    ) -> CustomDashboardType:
        """Updates dashboard details, visibility, or shared members."""
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as session:
            dash = await update_custom_dashboard(
                session=session,
                dashboard_id=id,
                client_id=int(ctx.client_id),
                user_id=int(ctx.user_id),
                name=input.name,
                description=input.description,
                icon=input.icon,
                visibility=input.visibility,
                shared_members=input.shared_members,
                is_owner=ctx.is_owner,
            )
            return _map_dashboard_to_gql(dash)

    @strawberry.mutation
    async def delete_dashboard(
        self,
        info: Info,
        id: int,
    ) -> bool:
        """Deletes a custom dashboard."""
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as session:
            return await delete_custom_dashboard(
                session=session,
                dashboard_id=id,
                client_id=int(ctx.client_id),
                user_id=int(ctx.user_id),
                is_owner=ctx.is_owner,
            )

    @strawberry.mutation
    async def reorder_dashboards(
        self,
        info: Info,
        input: ReorderDashboardsInput,
    ) -> bool:
        """Reorders dashboard tabs."""
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as session:
            return await reorder_dashboards(
                session=session,
                client_id=int(ctx.client_id),
                user_id=int(ctx.user_id),
                ordered_ids=input.ordered_ids,
            )

    @strawberry.mutation
    async def add_report_card(
        self,
        info: Info,
        input: CreateReportCardInput,
    ) -> CustomReportCardType:
        """
        Adds a new custom report card to a dashboard.
        Strictly enforces maximum of 10 charts per dashboard.
        """
        ctx = get_auth_context(info)
        d_from = datetime.strptime(input.date_from, "%Y-%m-%d").date() if input.date_from else None
        d_to = datetime.strptime(input.date_to, "%Y-%m-%d").date() if input.date_to else None

        async with AsyncSessionLocal() as session:
            card = await add_report_card(
                session=session,
                dashboard_id=input.dashboard_id,
                client_id=int(ctx.client_id),
                user_id=int(ctx.user_id),
                title=input.title,
                report_type=input.report_type,
                chart_type=input.chart_type or "bar",
                group_by=input.group_by or "daily",
                date_preset=input.date_preset or "last_30_days",
                date_from=d_from,
                date_to=d_to,
                selected_metrics=input.selected_metrics or ["room_revenue"],
                outlet_ids=input.outlet_ids or ([int(ctx.outlet_id)] if ctx.outlet_id else []),
                filters=input.filters or {},
                card_width=input.card_width or 1,
                is_owner=ctx.is_owner,
            )
            return _map_card_to_gql(card)

    @strawberry.mutation
    async def update_report_card(
        self,
        info: Info,
        id: int,
        input: UpdateReportCardInput,
    ) -> CustomReportCardType:
        """Updates title, metrics, or chart presentation of an existing card."""
        ctx = get_auth_context(info)
        d_from = datetime.strptime(input.date_from, "%Y-%m-%d").date() if input.date_from else None
        d_to = datetime.strptime(input.date_to, "%Y-%m-%d").date() if input.date_to else None

        async with AsyncSessionLocal() as session:
            card = await update_report_card(
                session=session,
                card_id=id,
                client_id=int(ctx.client_id),
                user_id=int(ctx.user_id),
                title=input.title,
                chart_type=input.chart_type,
                group_by=input.group_by,
                date_preset=input.date_preset,
                date_from=d_from,
                date_to=d_to,
                selected_metrics=input.selected_metrics,
                outlet_ids=input.outlet_ids,
                filters=input.filters,
                card_width=input.card_width,
                is_owner=ctx.is_owner,
            )
            return _map_card_to_gql(card)

    @strawberry.mutation
    async def delete_report_card(
        self,
        info: Info,
        id: int,
    ) -> bool:
        """Deletes a report card from a dashboard."""
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as session:
            return await delete_report_card(
                session=session,
                card_id=id,
                client_id=int(ctx.client_id),
                user_id=int(ctx.user_id),
                is_owner=ctx.is_owner,
            )

    @strawberry.mutation
    async def reorder_report_cards(
        self,
        info: Info,
        input: ReorderCardsInput,
    ) -> bool:
        """Updates the drag-and-drop order of cards within a dashboard."""
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as session:
            return await reorder_report_cards(
                session=session,
                dashboard_id=input.dashboard_id,
                client_id=int(ctx.client_id),
                ordered_ids=input.ordered_ids,
            )
