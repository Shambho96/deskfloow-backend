import strawberry
from enum import Enum
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal

from app.graphql.types.room_types import BuildingPayloadType, RoomType


@strawberry.enum
class BookingSourceEnum(str, Enum):
    WALKIN = "WALKIN"
    DIRECT = "DIRECT"
    WHATSAPP = "WHATSAPP"
    WEBSITE = "WEBSITE"
    OTHER = "OTHER"


@strawberry.enum
class ReservationStatusEnum(str, Enum):
    RESERVED = "RESERVED"
    CHECKED_IN = "CHECKED_IN"
    CHECKED_OUT = "CHECKED_OUT"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


@strawberry.enum
class PaymentMethodEnum(str, Enum):
    CASH = "CASH"
    CREDIT_CARD = "CREDIT_CARD"
    DEBIT_CARD = "DEBIT_CARD"
    UPI_QR = "UPI_QR"
    BANK_TRANSFER = "BANK_TRANSFER"


@strawberry.type
class GuestType:
    id: int
    first_name: str
    last_name: str
    phone: str
    email: Optional[str] = None
    id_type: Optional[str] = None
    id_number: Optional[str] = None
    vip_status: str = "STANDARD"
    nationality: str = "Indian"
    booking_source: Optional[str] = None
    special_requests: List[str] = strawberry.field(default_factory=list)

    @strawberry.field
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


@strawberry.type
class FolioLineItemType:
    id: int
    charge_category: str
    description: str
    unit_price: float
    quantity: int
    tax_rate: float
    tax_amount: float
    total_amount: float
    posted_at: str


@strawberry.type
class FolioPaymentType:
    id: int
    amount: float
    payment_method: str
    transaction_ref: Optional[str] = None
    status: str
    receipt_number: Optional[str] = None
    payment_date: str


@strawberry.type
class GuestFolioType:
    id: int
    folio_number: str
    reservation_id: int
    status: str
    subtotal: float
    tax_total: float
    grand_total: float
    paid_amount: float
    balance_due: float
    line_items: List[FolioLineItemType]
    payments: List[FolioPaymentType]


@strawberry.type
class ReservationType:
    id: int
    reservation_code: str
    room_id: Optional[int] = None
    room_number: Optional[str] = None
    category_id: int
    category_name: str
    check_in_date: str
    check_out_date: str
    actual_check_in_time: Optional[str] = None
    actual_check_out_time: Optional[str] = None
    eta: Optional[str] = None
    status: ReservationStatusEnum
    booking_source: BookingSourceEnum
    adults_count: int
    children_count: int
    rate_per_night: float
    total_room_charges: float
    tax_amount: float
    grand_total: float
    paid_amount: float
    balance_due: float
    guest: GuestType


@strawberry.type
class OperationsBoardRoomType:
    id: int
    room_number: str
    floor_id: int
    building_id: Optional[int] = None
    category_name: str
    effective_price: float
    computed_status: str  # AVAILABLE, RESERVED, OCCUPIED, OOO
    active_reservation: Optional[ReservationType] = None


@strawberry.type
class OccupancySummaryType:
    total_rooms: int
    available_rooms: int
    reserved_rooms: int
    occupied_rooms: int
    ooo_rooms: int
    booked_count: int
    occupancy_percentage: float


@strawberry.type
class OperationsBoardPayload:
    date: str
    summary: OccupancySummaryType
    buildings: List[BuildingPayloadType]
    rooms: List[OperationsBoardRoomType]


@strawberry.type
class OperationsKanbanPayload:
    arrivals: List[ReservationType]
    in_house: List[ReservationType]
    departures: List[ReservationType]
    settled: List[ReservationType]


@strawberry.type
class OperationsTapeChartPayload:
    start_date: str
    days_count: int
    rooms: List[OperationsBoardRoomType]
    reservations: List[ReservationType]


@strawberry.type
class HousekeepingTaskType:
    id: int
    room_id: int
    room_number: str
    task_type: str
    priority: str
    status: str
    notes: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@strawberry.type
class HousekeepingBoardPayload:
    dirty_count: int
    clean_count: int
    occupied_count: int
    ooo_count: int
    tasks: List[HousekeepingTaskType]


# ==============================================================================
# INPUTS
# ==============================================================================


@strawberry.input
class CreateReservationInput:
    category_id: int
    check_in_date: str  # YYYY-MM-DD
    check_out_date: str  # YYYY-MM-DD
    room_id: Optional[int] = None
    guest_first_name: str
    guest_last_name: str
    guest_phone: str
    guest_email: Optional[str] = None
    id_type: Optional[str] = None
    id_number: Optional[str] = None
    special_requests: Optional[List[str]] = None
    booking_source: Optional[BookingSourceEnum] = BookingSourceEnum.WALKIN
    adults_count: Optional[int] = 1
    children_count: Optional[int] = 0
    rate_per_night: Optional[float] = None
    advance_payment: Optional[float] = 0.0
    payment_method: Optional[PaymentMethodEnum] = PaymentMethodEnum.CASH
    transaction_ref: Optional[str] = None
    eta: Optional[str] = None
    idempotency_key: Optional[str] = None


@strawberry.input
class SettlePaymentInput:
    folio_id: int
    amount: float
    payment_method: PaymentMethodEnum
    transaction_ref: Optional[str] = None
    idempotency_key: Optional[str] = None
