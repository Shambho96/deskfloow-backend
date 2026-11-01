import strawberry
from datetime import datetime, date
from typing import Optional, List
from strawberry.types import Info
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.graphql.helpers import get_auth_context
from app.models.folio import GuestFolio
from app.services.operations_service import (
    get_operations_board,
    get_operations_kanban,
    get_operations_tape_chart,
    get_housekeeping_board
)
from app.graphql.types.operations_types import (
    OperationsBoardPayload,
    OperationsBoardRoomType,
    OccupancySummaryType,
    OperationsKanbanPayload,
    OperationsTapeChartPayload,
    HousekeepingBoardPayload,
    HousekeepingTaskType,
    GuestFolioType,
    FolioLineItemType,
    FolioPaymentType,
    ReservationType,
    GuestType,
    BookingSourceEnum,
    ReservationStatusEnum
)
from app.graphql.types.room_types import BuildingPayloadType

def map_guest(g) -> GuestType:
    return GuestType(
        id=int(g.id),
        first_name=g.first_name,
        last_name=g.last_name,
        phone=g.phone,
        email=g.email,
        id_type=g.id_type,
        id_number=g.id_number,
        vip_status=g.vip_status,
        nationality=g.nationality
    )

def map_reservation(res) -> ReservationType:
    paid = float(res.paid_amount)
    total = float(res.grand_total)
    return ReservationType(
        id=int(res.id),
        reservation_code=res.reservation_code,
        room_id=int(res.room_id) if res.room_id else None,
        room_number=res.room.room_number if res.room else None,
        category_id=int(res.category_id),
        category_name=res.category.name if res.category else 'Standard',
        check_in_date=res.check_in_date.isoformat(),
        check_out_date=res.check_out_date.isoformat(),
        actual_check_in_time=res.actual_check_in_time.isoformat() if res.actual_check_in_time else None,
        actual_check_out_time=res.actual_check_out_time.isoformat() if res.actual_check_out_time else None,
        eta=res.eta,
        status=ReservationStatusEnum(res.status),
        booking_source=BookingSourceEnum(res.booking_source),
        adults_count=int(res.adults_count),
        children_count=int(res.children_count),
        rate_per_night=float(res.rate_per_night),
        total_room_charges=float(res.total_room_charges),
        tax_amount=float(res.tax_amount),
        grand_total=total,
        paid_amount=paid,
        balance_due=max(0.0, total - paid),
        guest=map_guest(res.guest)
    )

@strawberry.type
class OperationsQuery:
    @strawberry.field
    async def operations_board(
        self,
        info: Info,
        date_str: str,
        building_id: Optional[int] = None,
        floor_id: Optional[int] = None
    ) -> OperationsBoardPayload:
        """Fetch daily operations board grouped by building and floor."""
        ctx = get_auth_context(info)
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        async with AsyncSessionLocal() as session:
            raw = await get_operations_board(
                session,
                client_id=ctx.client_id,
                outlet_id=ctx.outlet_id,
                target_date=target_date,
                building_id=building_id,
                floor_id=floor_id
            )

            buildings = [
                BuildingPayloadType(
                    id=int(b.id),
                    name=b.name,
                    code=b.code,
                    building_type=b.building_type,
                    display_order=b.display_order,
                    is_active=b.is_active
                ) for b in raw['buildings']
            ]

            rooms = [
                OperationsBoardRoomType(
                    id=int(r['room'].id),
                    room_number=r['room'].room_number,
                    floor_id=int(r['floor_id']),
                    building_id=int(r['building_id']) if r['building_id'] else None,
                    category_name=r['category_name'],
                    effective_price=float(r['effective_price']),
                    computed_status=r['computed_status'],
                    active_reservation=map_reservation(r['active_reservation']) if r['active_reservation'] else None
                ) for r in raw['rooms_data']
            ]

            summary = OccupancySummaryType(**raw['summary'])

            return OperationsBoardPayload(
                date=raw['date'],
                summary=summary,
                buildings=buildings,
                rooms=rooms
            )

    @strawberry.field
    async def operations_kanban(
        self,
        info: Info,
        date_str: str
    ) -> OperationsKanbanPayload:
        """Fetch Kanban daily operational movements."""
        ctx = get_auth_context(info)
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        async with AsyncSessionLocal() as session:
            raw = await get_operations_kanban(session, ctx.client_id, ctx.outlet_id, target_date)
            return OperationsKanbanPayload(
                arrivals=[map_reservation(r) for r in raw['arrivals']],
                in_house=[map_reservation(r) for r in raw['in_house']],
                departures=[map_reservation(r) for r in raw['departures']],
                settled=[map_reservation(r) for r in raw['settled']]
            )

    @strawberry.field
    async def operations_tape_chart(
        self,
        info: Info,
        start_date_str: str,
        days_count: int = 7
    ) -> OperationsTapeChartPayload:
        """Fetch 7-day multi-room tape chart window."""
        ctx = get_auth_context(info)
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()

        async with AsyncSessionLocal() as session:
            raw = await get_operations_tape_chart(session, ctx.client_id, ctx.outlet_id, start_date, days_count)

            rooms = [
                OperationsBoardRoomType(
                    id=int(rm.id),
                    room_number=rm.room_number,
                    floor_id=int(rm.floor_id),
                    building_id=int(rm.floor.building_id) if rm.floor and rm.floor.building_id else None,
                    category_name=rm.category.name if rm.category else 'Standard',
                    effective_price=float(rm.category.base_price) if rm.category else 0.0,
                    computed_status=rm.status,
                    active_reservation=None
                ) for rm in raw['rooms']
            ]

            reservations = [map_reservation(r) for r in raw['reservations']]

            return OperationsTapeChartPayload(
                start_date=raw['start_date'],
                days_count=raw['days_count'],
                rooms=rooms,
                reservations=reservations
            )

    @strawberry.field
    async def housekeeping_board(
        self,
        info: Info,
        floor_id: Optional[int] = None
    ) -> HousekeepingBoardPayload:
        """Fetch rooms organized by cleaning & maintenance status."""
        ctx = get_auth_context(info)

        async with AsyncSessionLocal() as session:
            raw = await get_housekeeping_board(session, ctx.client_id, ctx.outlet_id, floor_id)
            tasks = [
                HousekeepingTaskType(
                    id=int(t.id),
                    room_id=int(t.room_id),
                    room_number=t.room.room_number if t.room else 'Unknown',
                    task_type=t.task_type,
                    priority=t.priority,
                    status=t.status,
                    notes=t.notes,
                    started_at=t.started_at.isoformat() if t.started_at else None,
                    completed_at=t.completed_at.isoformat() if t.completed_at else None
                ) for t in raw['active_tasks']
            ]

            return HousekeepingBoardPayload(
                dirty_count=len(raw['dirty_rooms']),
                clean_count=len(raw['clean_rooms']),
                occupied_count=len(raw['occupied_rooms']),
                ooo_count=len(raw['ooo_rooms']),
                tasks=tasks
            )

    @strawberry.field
    async def guest_folio(
        self,
        info: Info,
        reservation_id: int
    ) -> Optional[GuestFolioType]:
        """Fetch active guest billing folio with itemized charges and receipts."""
        ctx = get_auth_context(info)

        async with AsyncSessionLocal() as session:
            stmt = select(GuestFolio).where(
                GuestFolio.client_id == ctx.client_id,
                GuestFolio.outlet_id == ctx.outlet_id,
                GuestFolio.reservation_id == reservation_id
            ).options(
                selectinload(GuestFolio.line_items),
                selectinload(GuestFolio.payments)
            )
            result = await session.execute(stmt)
            folio = result.scalars().first()

            if not folio:
                return None

            items = [
                FolioLineItemType(
                    id=int(i.id),
                    charge_category=i.charge_category,
                    description=i.description,
                    unit_price=float(i.unit_price),
                    quantity=int(i.quantity),
                    tax_rate=float(i.tax_rate),
                    tax_amount=float(i.tax_amount),
                    total_amount=float(i.total_amount),
                    posted_at=i.posted_at.isoformat()
                ) for i in folio.line_items
            ]

            payments = [
                FolioPaymentType(
                    id=int(p.id),
                    amount=float(p.amount),
                    payment_method=p.payment_method,
                    transaction_ref=p.transaction_ref,
                    status=p.status,
                    receipt_number=p.receipt_number,
                    payment_date=p.payment_date.isoformat()
                ) for p in folio.payments
            ]

            return GuestFolioType(
                id=int(folio.id),
                folio_number=folio.folio_number,
                reservation_id=int(folio.reservation_id),
                status=folio.status,
                subtotal=float(folio.subtotal),
                tax_total=float(folio.tax_total),
                grand_total=float(folio.grand_total),
                paid_amount=float(folio.paid_amount),
                balance_due=float(folio.balance_due),
                line_items=items,
                payments=payments
            )
