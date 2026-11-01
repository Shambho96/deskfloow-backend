import random
import string
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, not_, func, desc
from sqlalchemy.orm import selectinload

from app.models.client import Client
from app.models.outlet import Outlet
from app.models.building import Building
from app.models.floor import Floor
from app.models.room_category import RoomCategory
from app.models.room import Room
from app.models.guest import Guest
from app.models.reservation import Reservation
from app.models.folio import GuestFolio, FolioLineItem, FolioPayment
from app.models.housekeeping import HousekeepingTask, MaintenanceTicket
from app.models.audit_log import OperationalAuditLog
from app.services.idempotency_service import check_or_lock_idempotency, finalize_idempotency

def generate_random_code(prefix: str, length: int = 5) -> str:
    """Generates human-readable reference codes like RES-2026-9281."""
    digits = ''.join(random.choices(string.digits, k=length))
    year = datetime.utcnow().year
    return f"{prefix}-{year}-{digits}"

def calculate_gst_tax_rate(nightly_rate: Decimal) -> Decimal:
    """Computes Indian GST: 12% for < 7,500/night; 18% for >= 7,500/night."""
    if nightly_rate >= Decimal('7500.00'):
        return Decimal('18.00')
    return Decimal('12.00')

# ==============================================================================
# QUERIES: OPERATIONS BOARD, KANBAN, TAPE CHART, HOUSEKEEPING
# ==============================================================================

async def get_operations_board(
    session: AsyncSession,
    client_id: int,
    outlet_id: int,
    target_date: date,
    building_id: Optional[int] = None,
    floor_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Returns complete room occupancy board grouped by building and floor for target_date.
    """
    # 1. Fetch buildings, floors, categories, and rooms
    b_query = select(Building).where(
        Building.client_id == client_id,
        Building.outlet_id == outlet_id,
        Building.is_active == True
    ).order_by(Building.display_order, Building.id)
    if building_id:
        b_query = b_query.where(Building.id == building_id)
    b_res = await session.execute(b_query)
    buildings = b_res.scalars().all()

    # 2. Fetch all rooms
    r_query = select(Room).where(
        Room.client_id == client_id,
        Room.outlet_id == outlet_id,
        Room.is_active == True
    ).options(
        selectinload(Room.floor),
        selectinload(Room.category)
    ).order_by(Room.room_number)
    if floor_id:
        r_query = r_query.where(Room.floor_id == floor_id)
    r_res = await session.execute(r_query)
    rooms = r_res.scalars().all()

    # 3. Fetch active reservations covering target_date
    res_query = select(Reservation).where(
        Reservation.client_id == client_id,
        Reservation.outlet_id == outlet_id,
        Reservation.status.in_(['RESERVED', 'CHECKED_IN']),
        or_(
            and_(
                Reservation.check_in_date <= target_date,
                Reservation.check_out_date > target_date
            ),
            and_(
                Reservation.check_out_date == target_date,
                Reservation.status == 'CHECKED_IN'
            )
        )
    ).options(
        selectinload(Reservation.guest),
        selectinload(Reservation.category)
    )
    reservations_res = await session.execute(res_query)
    active_reservations = reservations_res.scalars().all()

    # Index reservations by room_id, prioritizing in-house occupants
    room_res_map: Dict[int, Reservation] = {}
    for res in active_reservations:
        if res.room_id:
            existing = room_res_map.get(res.room_id)
            if not existing or (res.status == 'CHECKED_IN' and existing.status != 'CHECKED_IN'):
                room_res_map[res.room_id] = res

    # 4. Compute statistics
    total_rooms = len(rooms)
    available_count = 0
    reserved_count = 0
    occupied_count = 0
    ooo_count = 0

    room_items = []
    for rm in rooms:
        active_res = room_res_map.get(rm.id)
        computed_status = 'AVAILABLE'

        if rm.status == 'MAINTENANCE':
            computed_status = 'OOO'
            ooo_count += 1
        elif active_res:
            if active_res.status == 'CHECKED_IN':
                computed_status = 'OCCUPIED'
                occupied_count += 1
            else:
                computed_status = 'RESERVED'
                reserved_count += 1
        else:
            available_count += 1

        effective_price = rm.custom_price if rm.custom_price is not None else (rm.category.base_price if rm.category else Decimal('0.00'))
        category_name = rm.custom_name if rm.custom_name else (rm.category.name if rm.category else 'Standard')

        room_items.append({
            'room': rm,
            'computed_status': computed_status,
            'active_reservation': active_res,
            'effective_price': effective_price,
            'category_name': category_name,
            'floor_id': rm.floor_id,
            'building_id': rm.floor.building_id if rm.floor else None
        })

    booked_count = reserved_count + occupied_count
    occupancy_pct = round((booked_count / total_rooms * 100), 1) if total_rooms > 0 else 0.0

    return {
        'date': target_date.isoformat(),
        'summary': {
            'total_rooms': total_rooms,
            'available_rooms': available_count,
            'reserved_rooms': reserved_count,
            'occupied_rooms': occupied_count,
            'ooo_rooms': ooo_count,
            'booked_count': booked_count,
            'occupancy_percentage': occupancy_pct
        },
        'buildings': buildings,
        'rooms_data': room_items
    }

async def get_operations_kanban(
    session: AsyncSession,
    client_id: int,
    outlet_id: int,
    target_date: date
) -> Dict[str, List[Reservation]]:
    """Returns arrivals, in-house, departures, and settled reservations for a date."""
    # Arrivals expected today
    arr_q = select(Reservation).where(
        Reservation.client_id == client_id,
        Reservation.outlet_id == outlet_id,
        Reservation.check_in_date == target_date,
        Reservation.status == 'RESERVED'
    ).options(selectinload(Reservation.guest), selectinload(Reservation.room), selectinload(Reservation.category))
    arrivals = (await session.execute(arr_q)).scalars().all()

    # In-House currently checked in on target_date
    inhouse_q = select(Reservation).where(
        Reservation.client_id == client_id,
        Reservation.outlet_id == outlet_id,
        Reservation.status == 'CHECKED_IN',
        Reservation.check_in_date <= target_date,
        Reservation.check_out_date >= target_date
    ).options(selectinload(Reservation.guest), selectinload(Reservation.room), selectinload(Reservation.category))
    in_house = (await session.execute(inhouse_q)).scalars().all()

    # Departures due today
    dep_q = select(Reservation).where(
        Reservation.client_id == client_id,
        Reservation.outlet_id == outlet_id,
        Reservation.check_out_date == target_date,
        Reservation.status == 'CHECKED_IN'
    ).options(selectinload(Reservation.guest), selectinload(Reservation.room), selectinload(Reservation.category))
    departures = (await session.execute(dep_q)).scalars().all()

    # Settled / Checked out today
    settled_q = select(Reservation).where(
        Reservation.client_id == client_id,
        Reservation.outlet_id == outlet_id,
        Reservation.check_out_date == target_date,
        Reservation.status == 'CHECKED_OUT'
    ).options(selectinload(Reservation.guest), selectinload(Reservation.room), selectinload(Reservation.category))
    settled = (await session.execute(settled_q)).scalars().all()

    return {
        'arrivals': list(arrivals),
        'in_house': list(in_house),
        'departures': list(departures),
        'settled': list(settled)
    }

async def get_operations_tape_chart(
    session: AsyncSession,
    client_id: int,
    outlet_id: int,
    start_date: date,
    days_count: int = 7
) -> Dict[str, Any]:
    """Returns rooms and all intersecting reservations for a multi-day tape chart window."""
    end_date = start_date + timedelta(days=days_count)

    r_query = select(Room).where(
        Room.client_id == client_id,
        Room.outlet_id == outlet_id,
        Room.is_active == True
    ).options(selectinload(Room.floor), selectinload(Room.category)).order_by(Room.room_number)
    rooms = (await session.execute(r_query)).scalars().all()

    res_query = select(Reservation).where(
        Reservation.client_id == client_id,
        Reservation.outlet_id == outlet_id,
        Reservation.status.in_(['RESERVED', 'CHECKED_IN', 'CHECKED_OUT']),
        not_(or_(
            Reservation.check_out_date < start_date,
            Reservation.check_in_date > end_date
        ))
    ).options(selectinload(Reservation.guest), selectinload(Reservation.category))
    reservations = (await session.execute(res_query)).scalars().all()

    return {
        'start_date': start_date.isoformat(),
        'days_count': days_count,
        'rooms': rooms,
        'reservations': reservations
    }

async def get_housekeeping_board(
    session: AsyncSession,
    client_id: int,
    outlet_id: int,
    floor_id: Optional[int] = None
) -> Dict[str, Any]:
    """Returns rooms organized by housekeeping / turnover status and active cleaning tasks."""
    r_query = select(Room).where(
        Room.client_id == client_id,
        Room.outlet_id == outlet_id,
        Room.is_active == True
    ).options(selectinload(Room.floor), selectinload(Room.category)).order_by(Room.room_number)
    if floor_id:
        r_query = r_query.where(Room.floor_id == floor_id)
    rooms = (await session.execute(r_query)).scalars().all()

    tasks_q = select(HousekeepingTask).where(
        HousekeepingTask.client_id == client_id,
        HousekeepingTask.outlet_id == outlet_id,
        HousekeepingTask.status.in_(['PENDING', 'IN_PROGRESS'])
    ).options(selectinload(HousekeepingTask.room))
    active_tasks = (await session.execute(tasks_q)).scalars().all()

    dirty_rooms = [r for r in rooms if r.status == 'CLEANING']
    clean_rooms = [r for r in rooms if r.status == 'AVAILABLE']
    occupied_rooms = [r for r in rooms if r.status == 'OCCUPIED']
    ooo_rooms = [r for r in rooms if r.status == 'MAINTENANCE']

    return {
        'rooms': rooms,
        'dirty_rooms': dirty_rooms,
        'clean_rooms': clean_rooms,
        'occupied_rooms': occupied_rooms,
        'ooo_rooms': ooo_rooms,
        'active_tasks': active_tasks
    }

# ==============================================================================
# MUTATIONS: RESERVATIONS, CHECK-IN, CHECK-OUT, FOLIO & PAYMENTS
# ==============================================================================

async def validate_room_availability(
    session: AsyncSession,
    outlet_id: int,
    room_id: int,
    check_in: date,
    check_out: date,
    exclude_reservation_id: Optional[int] = None
) -> bool:
    """Pessimistic concurrency lock check for double-booking prevention."""
    stmt = select(Reservation.id).where(
        Reservation.outlet_id == outlet_id,
        Reservation.room_id == room_id,
        Reservation.status.in_(['RESERVED', 'CHECKED_IN']),
        not_(or_(
            Reservation.check_out_date <= check_in,
            Reservation.check_in_date >= check_out
        ))
    )
    if exclude_reservation_id:
        stmt = stmt.where(Reservation.id != exclude_reservation_id)

    # Pessimistic write lock on conflicting rows
    stmt = stmt.with_for_update()
    result = await session.execute(stmt)
    conflict = result.scalars().first()
    return conflict is None

async def get_reservation_with_relations(session: AsyncSession, res_id: int) -> Reservation:
    """Eager loads reservation along with guest, room, and category for Strawberry GraphQL serialization."""
    stmt = (
        select(Reservation)
        .where(Reservation.id == res_id)
        .options(
            selectinload(Reservation.guest),
            selectinload(Reservation.room),
            selectinload(Reservation.category)
        )
    )
    result = await session.execute(stmt)
    res = result.scalars().first()
    if not res:
        raise ValueError(f"Reservation ID {res_id} not found.")
    return res

async def create_reservation(
    session: AsyncSession,
    client_id: int,
    outlet_id: int,
    user_id: Optional[int],
    data: Dict[str, Any]
) -> Reservation:
    """
    Creates a new reservation with double-booking lock, automatic guest profile,
    open folio initialization, and optional advance payment.
    """
    idempotency_key = data.get('idempotency_key')
    saved_response, is_new = await check_or_lock_idempotency(
        session, client_id, outlet_id, idempotency_key, 'createReservation', data
    )
    if not is_new and saved_response:
        res_id = saved_response.get('reservation_id')
        existing = await session.get(Reservation, res_id, options=[selectinload(Reservation.guest), selectinload(Reservation.room)])
        if existing:
            return existing

    check_in = data['check_in_date']
    check_out = data['check_out_date']
    if check_out <= check_in:
        raise ValueError("Check-out date must be after check-in date.")

    room_id = data.get('room_id')
    if room_id:
        is_avail = await validate_room_availability(session, outlet_id, room_id, check_in, check_out)
        if not is_avail:
            raise ValueError(f"Room is already reserved for the selected stay dates ({check_in} to {check_out}).")

    # 1. Get or create guest
    guest_id = data.get('guest_id')
    if not guest_id:
        phone = (data.get('guest_phone') or '').strip()
        first_name = (data.get('guest_first_name') or '').strip() or 'Guest'
        last_name = (data.get('guest_last_name') or '').strip() or '-'
        raw_email = (data.get('guest_email') or '').strip()
        email = raw_email if raw_email else None

        g_stmt = select(Guest).where(
            Guest.client_id == client_id,
            Guest.phone == phone
        )
        g_res = await session.execute(g_stmt)
        guest = g_res.scalars().first()

        if not guest:
            guest = Guest(
                client_id=client_id,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                email=email,
                id_type=data.get('id_type'),
                id_number=data.get('id_number')
            )
            session.add(guest)
            await session.flush()
        guest_id = guest.id
    else:
        guest = await session.get(Guest, guest_id)
        if not guest:
            raise ValueError(f"Guest ID {guest_id} not found.")

    # 2. Rate & Tax calculation
    category_id = data['category_id']
    rate_per_night = Decimal(str(data.get('rate_per_night', '1500.00')))
    nights = max(1, (check_out - check_in).days)
    total_room_charges = rate_per_night * nights
    tax_rate = calculate_gst_tax_rate(rate_per_night)
    tax_amount = round(total_room_charges * (tax_rate / Decimal('100.00')), 2)
    grand_total = total_room_charges + tax_amount

    # 3. Direct booking source: WALKIN, DIRECT, WHATSAPP, WEBSITE, OTHER
    booking_source = data.get('booking_source', 'WALKIN').upper()
    if booking_source not in ['WALKIN', 'DIRECT', 'WHATSAPP', 'WEBSITE', 'OTHER']:
        booking_source = 'WALKIN'

    # 4. Insert Reservation
    reservation_code = generate_random_code('RES')
    res = Reservation(
        reservation_code=reservation_code,
        client_id=client_id,
        outlet_id=outlet_id,
        guest_id=guest_id,
        room_id=room_id,
        category_id=category_id,
        check_in_date=check_in,
        check_out_date=check_out,
        eta=data.get('eta'),
        status='RESERVED',
        booking_source=booking_source,
        adults_count=data.get('adults_count', 1),
        children_count=data.get('children_count', 0),
        rate_per_night=rate_per_night,
        total_room_charges=total_room_charges,
        tax_amount=tax_amount,
        grand_total=grand_total,
        paid_amount=Decimal('0.00'),
        idempotency_key=idempotency_key
    )
    session.add(res)
    await session.flush()

    # 5. Automatically Initialize Guest Folio
    folio_number = generate_random_code('FOL')
    folio = GuestFolio(
        folio_number=folio_number,
        client_id=client_id,
        outlet_id=outlet_id,
        reservation_id=res.id,
        guest_id=guest_id,
        status='OPEN',
        subtotal=total_room_charges,
        tax_total=tax_amount,
        grand_total=grand_total,
        paid_amount=Decimal('0.00'),
        balance_due=grand_total
    )
    session.add(folio)
    await session.flush()

    # Post Nightly Room Charge Line Item
    line_item = FolioLineItem(
        client_id=client_id,
        outlet_id=outlet_id,
        folio_id=folio.id,
        charge_category='ROOM_CHARGE',
        description=f"Room Tariff ({nights} night{'s' if nights > 1 else ''} @ ₹{rate_per_night}/nt)",
        unit_price=rate_per_night,
        quantity=nights,
        tax_rate=tax_rate,
        tax_amount=tax_amount,
        total_amount=grand_total,
        posted_by_user_id=user_id
    )
    session.add(line_item)

    # 6. Optional Advance Payment
    advance_amount = Decimal(str(data.get('advance_payment', '0.00')))
    if advance_amount > Decimal('0.00'):
        payment = FolioPayment(
            client_id=client_id,
            outlet_id=outlet_id,
            folio_id=folio.id,
            amount=advance_amount,
            payment_method=data.get('payment_method', 'CASH').upper(),
            transaction_ref=data.get('transaction_ref'),
            receipt_number=generate_random_code('RCP'),
            received_by_user_id=user_id
        )
        session.add(payment)
        folio.paid_amount += advance_amount
        folio.balance_due = max(Decimal('0.00'), folio.grand_total - folio.paid_amount)
        res.paid_amount += advance_amount

    await session.flush()

    # Finalize Idempotency
    await finalize_idempotency(
        session, client_id, idempotency_key, 201, {
            'reservation_id': res.id,
            'reservation_code': res.reservation_code,
            'folio_id': folio.id
        }
    )

    # Audit Log
    audit = OperationalAuditLog(
        client_id=client_id,
        outlet_id=outlet_id,
        action='CREATE_RESERVATION',
        entity_type='RESERVATION',
        entity_id=res.id,
        new_state={'code': res.reservation_code, 'room_id': room_id, 'source': booking_source, 'total': float(grand_total)},
        performed_by_user_id=user_id
    )
    session.add(audit)
    await session.commit()

    # Reload fresh with all relationships eagerly loaded
    return await get_reservation_with_relations(session, res.id)

async def check_in_guest(
    session: AsyncSession,
    client_id: int,
    outlet_id: int,
    reservation_id: int,
    user_id: Optional[int]
) -> Reservation:
    """1-Click Guest Check-In with state machine idempotency."""
    res = await session.get(Reservation, reservation_id, options=[
        selectinload(Reservation.guest),
        selectinload(Reservation.room)
    ])
    if not res or res.client_id != client_id or res.outlet_id != outlet_id:
        raise ValueError("Reservation not found.")

    # Idempotent safety: if already checked in, return current state
    if res.status == 'CHECKED_IN':
        return res

    res.status = 'CHECKED_IN'
    res.actual_check_in_time = datetime.utcnow()

    # Update assigned room to OCCUPIED
    if res.room:
        res.room.status = 'OCCUPIED'

    audit = OperationalAuditLog(
        client_id=client_id,
        outlet_id=outlet_id,
        action='CHECK_IN',
        entity_type='RESERVATION',
        entity_id=res.id,
        notes=f"Guest checked into Room #{res.room.room_number if res.room else 'Unallocated'}",
        performed_by_user_id=user_id
    )
    session.add(audit)
    await session.commit()
    return await get_reservation_with_relations(session, res.id)

async def check_out_guest(
    session: AsyncSession,
    client_id: int,
    outlet_id: int,
    reservation_id: int,
    user_id: Optional[int]
) -> Reservation:
    """1-Click Guest Check-Out, closes folio, switches room to CLEANING, and creates housekeeping task."""
    res = await session.get(Reservation, reservation_id, options=[
        selectinload(Reservation.guest),
        selectinload(Reservation.room),
        selectinload(Reservation.folios)
    ])
    if not res or res.client_id != client_id or res.outlet_id != outlet_id:
        raise ValueError("Reservation not found.")

    if res.status == 'CHECKED_OUT':
        return res

    res.status = 'CHECKED_OUT'
    res.actual_check_out_time = datetime.utcnow()

    # Settle folios
    for f in res.folios:
        if f.status == 'OPEN':
            f.status = 'SETTLED'
            f.closed_at = datetime.utcnow()
            f.closed_by_user_id = user_id

    # Switch room to dirty and dispatch housekeeping
    if res.room:
        res.room.status = 'CLEANING'
        hk_task = HousekeepingTask(
            client_id=client_id,
            outlet_id=outlet_id,
            room_id=res.room.id,
            task_type='DEPARTURE_CLEAN',
            priority='NORMAL',
            status='PENDING',
            room_status_before='DIRTY',
            room_status_after='CLEAN',
            notes=f"Auto-dispatched turnover after check-out of {res.guest.full_name}"
        )
        session.add(hk_task)

    audit = OperationalAuditLog(
        client_id=client_id,
        outlet_id=outlet_id,
        action='CHECK_OUT',
        entity_type='RESERVATION',
        entity_id=res.id,
        performed_by_user_id=user_id
    )
    session.add(audit)
    await session.commit()
    return await get_reservation_with_relations(session, res.id)

async def settle_folio_payment(
    session: AsyncSession,
    client_id: int,
    outlet_id: int,
    user_id: Optional[int],
    data: Dict[str, Any]
) -> FolioPayment:
    """Records folio payment with idempotency protection and updates balance due."""
    idempotency_key = data.get('idempotency_key')
    saved_response, is_new = await check_or_lock_idempotency(
        session, client_id, outlet_id, idempotency_key, 'settleFolioPayment', data
    )
    if not is_new and saved_response:
        p_id = saved_response.get('payment_id')
        existing = await session.get(FolioPayment, p_id)
        if existing:
            return existing

    folio_id = data['folio_id']
    folio = await session.get(GuestFolio, folio_id)
    if not folio or folio.client_id != client_id or folio.outlet_id != outlet_id:
        raise ValueError("Folio not found.")

    amount = Decimal(str(data['amount']))
    receipt_number = generate_random_code('RCP')

    payment = FolioPayment(
        client_id=client_id,
        outlet_id=outlet_id,
        folio_id=folio.id,
        amount=amount,
        payment_method=data.get('payment_method', 'CASH').upper(),
        transaction_ref=data.get('transaction_ref'),
        receipt_number=receipt_number,
        idempotency_key=idempotency_key,
        received_by_user_id=user_id
    )
    session.add(payment)

    folio.paid_amount += amount
    folio.balance_due = max(Decimal('0.00'), folio.grand_total - folio.paid_amount)
    if folio.balance_due == Decimal('0.00'):
        folio.status = 'SETTLED'

    # Update parent reservation paid_amount
    res = await session.get(Reservation, folio.reservation_id)
    if res:
        res.paid_amount += amount

    await session.flush()

    await finalize_idempotency(
        session, client_id, idempotency_key, 200, {
            'payment_id': payment.id,
            'receipt_number': payment.receipt_number,
            'balance_due': float(folio.balance_due)
        }
    )

    audit = OperationalAuditLog(
        client_id=client_id,
        outlet_id=outlet_id,
        action='SETTLE_PAYMENT',
        entity_type='FOLIO',
        entity_id=folio.id,
        notes=f"Recorded {payment.payment_method} payment of ₹{amount} (Receipt: {receipt_number})",
        performed_by_user_id=user_id
    )
    session.add(audit)
    await session.commit()
    return payment

async def update_housekeeping_task(
    session: AsyncSession,
    client_id: int,
    outlet_id: int,
    task_id: int,
    new_status: str,
    user_id: Optional[int]
) -> HousekeepingTask:
    """Updates cleaning task status. When marked COMPLETED/INSPECTED, releases room to AVAILABLE."""
    task = await session.get(HousekeepingTask, task_id, options=[selectinload(HousekeepingTask.room)])
    if not task or task.client_id != client_id or task.outlet_id != outlet_id:
        raise ValueError("Task not found.")

    task.status = new_status
    if new_status == 'IN_PROGRESS':
        task.started_at = datetime.utcnow()
    elif new_status in ['COMPLETED', 'INSPECTED']:
        task.completed_at = datetime.utcnow()
        if new_status == 'INSPECTED':
            task.inspected_by_user_id = user_id
        # Release room back to AVAILABLE (Clean)
        if task.room and task.room.status == 'CLEANING':
            task.room.status = 'AVAILABLE'

    await session.commit()
    return task

async def reassign_room(
    session: AsyncSession,
    client_id: int,
    outlet_id: int,
    reservation_id: int,
    new_room_id: int,
    user_id: Optional[int]
) -> Reservation:
    """Moves reservation to a new room with double-booking check."""
    res = await session.get(Reservation, reservation_id, options=[selectinload(Reservation.room)])
    if not res or res.client_id != client_id or res.outlet_id != outlet_id:
        raise ValueError("Reservation not found.")

    is_avail = await validate_room_availability(
        session, outlet_id, new_room_id, res.check_in_date, res.check_out_date, exclude_reservation_id=res.id
    )
    if not is_avail:
        raise ValueError("Target room is occupied or reserved for the stay period.")

    old_room_id = res.room_id
    res.room_id = new_room_id

    # If guest is in-house, release old room and occupy new room
    if res.status == 'CHECKED_IN':
        if old_room_id:
            old_r = await session.get(Room, old_room_id)
            if old_r:
                old_r.status = 'CLEANING'
        new_r = await session.get(Room, new_room_id)
        if new_r:
            new_r.status = 'OCCUPIED'

    audit = OperationalAuditLog(
        client_id=client_id,
        outlet_id=outlet_id,
        action='ROOM_REASSIGN',
        entity_type='RESERVATION',
        entity_id=res.id,
        notes=f"Reassigned from Room ID {old_room_id} to Room ID {new_room_id}",
        performed_by_user_id=user_id
    )
    session.add(audit)
    await session.commit()
    return await get_reservation_with_relations(session, res.id)
