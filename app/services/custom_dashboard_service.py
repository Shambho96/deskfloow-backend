"""
Custom Dashboard & Report Card Service
Handles dashboard workspaces, card limits (max 10 charts), user-level sharing and drag-reordering.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reporting import CustomDashboard, CustomReportCard
from app.models.outlet import Outlet
from app.models.user import User


MAX_CHARTS_PER_DASHBOARD = 10


async def list_dashboards_for_user(
    session: AsyncSession,
    client_id: int,
    user_id: int,
    outlet_id: Optional[int] = None,
    is_owner: bool = False,
) -> List[CustomDashboard]:
    """
    Returns all dashboards accessible by the user:
    1. Created by this user.
    2. Shared with this outlet (visibility == 'OUTLET_SHARED').
    3. Specifically shared with this user ID (shared_members contains user_id).
    4. If is_owner, all dashboards in client.
    """
    stmt = (
        select(CustomDashboard)
        .options(
            selectinload(CustomDashboard.cards),
            selectinload(CustomDashboard.created_by),
            selectinload(CustomDashboard.outlet),
        )
        .where(CustomDashboard.client_id == client_id)
        .order_by(CustomDashboard.display_order, CustomDashboard.id)
    )

    # 1. Outlet-level isolation: Only return dashboards belonging to this outlet (or global unassigned)
    if outlet_id is not None:
        stmt = stmt.where(
            or_(
                CustomDashboard.outlet_id == outlet_id,
                CustomDashboard.outlet_id.is_(None),
            )
        )

    # 2. User-level isolation: Creator can see their private boards, or outlet-shared boards
    if not is_owner:
        access_conditions = [
            CustomDashboard.created_by_user_id == user_id,
            CustomDashboard.visibility == "OUTLET_SHARED",
        ]
        stmt = stmt.where(or_(*access_conditions))

    result = await session.execute(stmt)
    dashboards = result.scalars().all()

    # If user has 0 dashboards, automatically seed an initial default dashboard for them!
    if len(dashboards) == 0:
        default_dash = CustomDashboard(
            client_id=client_id,
            created_by_user_id=user_id,
            outlet_id=outlet_id,
            name="Overview Dashboard",
            description="Default dashboard workspace for front desk yield & metrics",
            icon="LayoutDashboard",
            visibility="PRIVATE",
            is_default=True,
            display_order=0,
        )
        session.add(default_dash)
        await session.commit()

        # Refetch with relations
        return await list_dashboards_for_user(session, client_id, user_id, outlet_id, is_owner)

    return dashboards


async def get_dashboard_by_id(
    session: AsyncSession,
    dashboard_id: int,
    client_id: int,
    user_id: int,
    is_owner: bool = False,
) -> CustomDashboard:
    """Fetches a specific dashboard by ID with access verification."""
    stmt = (
        select(CustomDashboard)
        .options(
            selectinload(CustomDashboard.cards),
            selectinload(CustomDashboard.created_by),
            selectinload(CustomDashboard.outlet),
        )
        .where(CustomDashboard.id == dashboard_id, CustomDashboard.client_id == client_id)
    )
    result = await session.execute(stmt)
    dash = result.scalar_one_or_none()
    if not dash:
        raise ValueError(f"Dashboard #{dashboard_id} not found.")

    if not is_owner and dash.created_by_user_id != user_id and dash.visibility == "PRIVATE":
        raise PermissionError("Access denied: This dashboard is private to its creator.")

    return dash


async def create_custom_dashboard(
    session: AsyncSession,
    client_id: int,
    user_id: int,
    name: str,
    description: Optional[str] = None,
    icon: str = "LayoutDashboard",
    visibility: str = "PRIVATE",
    shared_members: Optional[List[Dict[str, Any]]] = None,
    outlet_id: Optional[int] = None,
) -> CustomDashboard:
    """Creates a new dashboard tab."""
    # Count current dashboards to set display_order scoped to outlet and user
    count_stmt = select(func.count(CustomDashboard.id)).where(
        CustomDashboard.client_id == client_id,
        CustomDashboard.created_by_user_id == user_id,
    )
    if outlet_id is not None:
        count_stmt = count_stmt.where(
            or_(
                CustomDashboard.outlet_id == outlet_id,
                CustomDashboard.outlet_id.is_(None),
            )
        )
    current_count = (await session.execute(count_stmt)).scalar() or 0

    dash = CustomDashboard(
        client_id=client_id,
        created_by_user_id=user_id,
        outlet_id=outlet_id,
        name=name.strip(),
        description=description.strip() if description else None,
        icon=icon or "LayoutDashboard",
        visibility=visibility,
        shared_members=shared_members or [],
        display_order=current_count,
    )
    session.add(dash)
    await session.commit()
    await session.refresh(dash)
    return dash


async def update_custom_dashboard(
    session: AsyncSession,
    dashboard_id: int,
    client_id: int,
    user_id: int,
    name: Optional[str] = None,
    description: Optional[str] = None,
    icon: Optional[str] = None,
    visibility: Optional[str] = None,
    shared_members: Optional[List[Dict[str, Any]]] = None,
    is_owner: bool = False,
) -> CustomDashboard:
    """Updates dashboard properties."""
    dash = await get_dashboard_by_id(session, dashboard_id, client_id, user_id, is_owner)

    if not is_owner and dash.created_by_user_id != user_id:
        raise PermissionError("Only the dashboard owner can modify dashboard settings.")

    if name is not None:
        dash.name = name.strip()
    if description is not None:
        dash.description = description.strip()
    if icon is not None:
        dash.icon = icon
    if visibility is not None:
        dash.visibility = visibility
    if shared_members is not None:
        dash.shared_members = shared_members

    await session.commit()
    await session.refresh(dash)
    return dash


async def delete_custom_dashboard(
    session: AsyncSession,
    dashboard_id: int,
    client_id: int,
    user_id: int,
    is_owner: bool = False,
) -> bool:
    """Deletes a dashboard and all its cards."""
    dash = await get_dashboard_by_id(session, dashboard_id, client_id, user_id, is_owner)

    if not is_owner and dash.created_by_user_id != user_id:
        raise PermissionError("Only the creator can delete this dashboard.")

    await session.delete(dash)
    await session.commit()
    return True


async def reorder_dashboards(
    session: AsyncSession,
    client_id: int,
    user_id: int,
    ordered_ids: List[int],
) -> bool:
    """Updates tab display order."""
    for idx, d_id in enumerate(ordered_ids):
        stmt = select(CustomDashboard).where(
            CustomDashboard.id == d_id,
            CustomDashboard.client_id == client_id,
            CustomDashboard.created_by_user_id == user_id,
        )
        dash = (await session.execute(stmt)).scalar_one_or_none()
        if dash:
            dash.display_order = idx

    await session.commit()
    return True


# ─── REPORT CARD OPERATIONS (ENFORCING MAX 10 CHARTS) ───────────────────


async def add_report_card(
    session: AsyncSession,
    dashboard_id: int,
    client_id: int,
    user_id: int,
    title: str,
    report_type: str,
    chart_type: str = "bar",
    group_by: str = "daily",
    date_preset: str = "last_30_days",
    date_from: Optional[Any] = None,
    date_to: Optional[Any] = None,
    selected_metrics: Optional[List[str]] = None,
    outlet_ids: Optional[List[int]] = None,
    filters: Optional[Dict[str, Any]] = None,
    card_width: int = 1,
    is_owner: bool = False,
) -> CustomReportCard:
    """
    Creates and attaches a new chart card to a dashboard.
    Enforces maximum limit of 10 charts per dashboard.
    """
    dash = await get_dashboard_by_id(session, dashboard_id, client_id, user_id, is_owner)

    # 1. Enforce max 10 charts limit
    current_count_res = await session.execute(
        select(func.count(CustomReportCard.id)).where(CustomReportCard.dashboard_id == dashboard_id)
    )
    current_count = current_count_res.scalar() or 0
    if current_count >= MAX_CHARTS_PER_DASHBOARD:
        raise ValueError(
            f"Maximum limit of {MAX_CHARTS_PER_DASHBOARD} charts per dashboard reached. "
            "Please create a new dashboard tab to add more charts."
        )

    card = CustomReportCard(
        dashboard_id=dashboard_id,
        client_id=client_id,
        created_by_user_id=user_id,
        title=title.strip(),
        report_type=report_type,
        chart_type=chart_type or "bar",
        group_by=group_by or "daily",
        date_preset=date_preset or "last_30_days",
        date_from=date_from,
        date_to=date_to,
        selected_metrics=selected_metrics or ["room_revenue"],
        outlet_ids=outlet_ids or ([dash.outlet_id] if dash.outlet_id else []),
        filters=filters or {},
        display_order=current_count,
        card_width=card_width,
    )
    session.add(card)
    await session.commit()
    await session.refresh(card)
    return card


async def update_report_card(
    session: AsyncSession,
    card_id: int,
    client_id: int,
    user_id: int,
    title: Optional[str] = None,
    chart_type: Optional[str] = None,
    group_by: Optional[str] = None,
    date_preset: Optional[str] = None,
    date_from: Optional[Any] = None,
    date_to: Optional[Any] = None,
    selected_metrics: Optional[List[str]] = None,
    outlet_ids: Optional[List[int]] = None,
    filters: Optional[Dict[str, Any]] = None,
    card_width: Optional[int] = None,
    is_owner: bool = False,
) -> CustomReportCard:
    """Updates an existing report card's title, metrics, or chart settings."""
    stmt = select(CustomReportCard).where(CustomReportCard.id == card_id, CustomReportCard.client_id == client_id)
    card = (await session.execute(stmt)).scalar_one_or_none()
    if not card:
        raise ValueError(f"Report card #{card_id} not found.")

    if not is_owner and card.created_by_user_id != user_id:
        dash = await get_dashboard_by_id(session, card.dashboard_id, client_id, user_id, is_owner)
        if dash.created_by_user_id != user_id:
            raise PermissionError("Only the card creator or dashboard owner can modify this report card.")

    if title is not None:
        card.title = title.strip()
    if chart_type is not None:
        card.chart_type = chart_type
    if group_by is not None:
        card.group_by = group_by
    if date_preset is not None:
        card.date_preset = date_preset
    if date_from is not None:
        card.date_from = date_from
    if date_to is not None:
        card.date_to = date_to
    if selected_metrics is not None:
        card.selected_metrics = selected_metrics
    if outlet_ids is not None:
        card.outlet_ids = outlet_ids
    if filters is not None:
        card.filters = filters
    if card_width is not None:
        card.card_width = card_width

    await session.commit()
    await session.refresh(card)
    return card


async def delete_report_card(
    session: AsyncSession,
    card_id: int,
    client_id: int,
    user_id: int,
    is_owner: bool = False,
) -> bool:
    """Deletes a report card from its dashboard."""
    stmt = select(CustomReportCard).where(CustomReportCard.id == card_id, CustomReportCard.client_id == client_id)
    card = (await session.execute(stmt)).scalar_one_or_none()
    if not card:
        raise ValueError(f"Report card #{card_id} not found.")

    if not is_owner and card.created_by_user_id != user_id:
        dash = await get_dashboard_by_id(session, card.dashboard_id, client_id, user_id, is_owner)
        if dash.created_by_user_id != user_id:
            raise PermissionError("Only the card creator or dashboard owner can delete this report card.")

    await session.delete(card)
    await session.commit()
    return True


async def reorder_report_cards(
    session: AsyncSession,
    dashboard_id: int,
    client_id: int,
    ordered_ids: List[int],
) -> bool:
    """Updates drag-and-drop sort order for cards inside a dashboard."""
    for idx, c_id in enumerate(ordered_ids):
        stmt = select(CustomReportCard).where(
            CustomReportCard.id == c_id,
            CustomReportCard.dashboard_id == dashboard_id,
            CustomReportCard.client_id == client_id,
        )
        card = (await session.execute(stmt)).scalar_one_or_none()
        if card:
            card.display_order = idx

    await session.commit()
    return True
