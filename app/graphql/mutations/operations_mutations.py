import strawberry
from datetime import datetime
from typing import Optional
from strawberry.types import Info
from decimal import Decimal

from app.db.session import AsyncSessionLocal
from app.graphql.helpers import get_auth_context
from app.services.operations_service import (
    create_reservation as svc_create_reservation,
    check_in_guest as svc_check_in_guest,
    check_out_guest as svc_check_out_guest,
    settle_folio_payment as svc_settle_folio_payment,
    update_housekeeping_task as svc_update_housekeeping_task,
    reassign_room as svc_reassign_room,
)
from app.graphql.types.operations_types import (
    ReservationType,
    FolioPaymentType,
    HousekeepingTaskType,
    CreateReservationInput,
    SettlePaymentInput,
)
from app.graphql.queries.operations_queries import map_reservation


@strawberry.type
class OperationsMutation:
    @strawberry.mutation
    async def create_reservation(self, info: Info, input: CreateReservationInput) -> ReservationType:
        """Creates a new reservation with double-booking lock, auto folio, and direct source."""
        ctx = get_auth_context(info)
        check_in = datetime.strptime(input.check_in_date, "%Y-%m-%d").date()
        check_out = datetime.strptime(input.check_out_date, "%Y-%m-%d").date()

        data = {
            "category_id": input.category_id,
            "room_id": input.room_id,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "guest_first_name": input.guest_first_name,
            "guest_last_name": input.guest_last_name,
            "guest_phone": input.guest_phone,
            "guest_email": input.guest_email,
            "id_type": input.id_type,
            "id_number": input.id_number,
            "special_requests": input.special_requests or [],
            "booking_source": input.booking_source.value if input.booking_source else "WALKIN",
            "adults_count": input.adults_count or 1,
            "children_count": input.children_count or 0,
            "rate_per_night": input.rate_per_night,
            "advance_payment": input.advance_payment or 0.0,
            "payment_method": input.payment_method.value if input.payment_method else "CASH",
            "transaction_ref": input.transaction_ref,
            "eta": input.eta,
            "idempotency_key": input.idempotency_key,
        }

        async with AsyncSessionLocal() as session:
            res = await svc_create_reservation(
                session,
                client_id=ctx.client_id,
                outlet_id=ctx.outlet_id,
                user_id=ctx.user_id,
                data=data,
            )
            return map_reservation(res)

    @strawberry.mutation
    async def check_in_guest(self, info: Info, reservation_id: int) -> ReservationType:
        """1-Click guest check-in."""
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as session:
            res = await svc_check_in_guest(
                session,
                client_id=ctx.client_id,
                outlet_id=ctx.outlet_id,
                reservation_id=reservation_id,
                user_id=ctx.user_id,
            )
            return map_reservation(res)

    @strawberry.mutation
    async def check_out_guest(self, info: Info, reservation_id: int) -> ReservationType:
        """1-Click guest check-out, dispatches housekeeping, settles open folio."""
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as session:
            res = await svc_check_out_guest(
                session,
                client_id=ctx.client_id,
                outlet_id=ctx.outlet_id,
                reservation_id=reservation_id,
                user_id=ctx.user_id,
            )
            return map_reservation(res)

    @strawberry.mutation
    async def settle_folio_payment(self, info: Info, input: SettlePaymentInput) -> FolioPaymentType:
        """Records folio payment with idempotency key protection."""
        ctx = get_auth_context(info)
        data = {
            "folio_id": input.folio_id,
            "amount": input.amount,
            "payment_method": input.payment_method.value,
            "transaction_ref": input.transaction_ref,
            "idempotency_key": input.idempotency_key,
        }

        async with AsyncSessionLocal() as session:
            p = await svc_settle_folio_payment(
                session,
                client_id=ctx.client_id,
                outlet_id=ctx.outlet_id,
                user_id=ctx.user_id,
                data=data,
            )
            return FolioPaymentType(
                id=int(p.id),
                amount=float(p.amount),
                payment_method=p.payment_method,
                transaction_ref=p.transaction_ref,
                status=p.status,
                receipt_number=p.receipt_number,
                payment_date=p.payment_date.isoformat(),
            )

    @strawberry.mutation
    async def update_housekeeping_task(
        self, info: Info, task_id: int, status: str, notes: Optional[str] = None
    ) -> HousekeepingTaskType:
        """Updates cleaning task status. When marked COMPLETED/INSPECTED, releases room back to AVAILABLE."""
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as session:
            task = await svc_update_housekeeping_task(
                session,
                client_id=ctx.client_id,
                outlet_id=ctx.outlet_id,
                task_id=task_id,
                new_status=status,
                user_id=ctx.user_id,
            )
            return HousekeepingTaskType(
                id=int(task.id),
                room_id=int(task.room_id),
                room_number=task.room.room_number if task.room else "Unknown",
                task_type=task.task_type,
                priority=task.priority,
                status=task.status,
                notes=task.notes,
                started_at=task.started_at.isoformat() if task.started_at else None,
                completed_at=task.completed_at.isoformat() if task.completed_at else None,
            )

    @strawberry.mutation
    async def reassign_room(self, info: Info, reservation_id: int, new_room_id: int) -> ReservationType:
        """Moves reservation to another room with double-booking collision check."""
        ctx = get_auth_context(info)
        async with AsyncSessionLocal() as session:
            res = await svc_reassign_room(
                session,
                client_id=ctx.client_id,
                outlet_id=ctx.outlet_id,
                reservation_id=reservation_id,
                new_room_id=new_room_id,
                user_id=ctx.user_id,
            )
            return map_reservation(res)
