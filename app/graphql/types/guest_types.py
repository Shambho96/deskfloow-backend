import strawberry
from typing import Optional, List
from datetime import date, datetime


@strawberry.type
class GuestNoteType:
    id: str
    author_name: str
    text: str
    outlet_id: Optional[int] = None
    created_at: str


@strawberry.type
class LoyaltyTierType:
    id: int
    tier_code: str
    name: str
    min_spend: float
    min_stays: int
    discount_percent: float
    badge_color: str
    perks: List[str]
    display_order: int
    is_active: bool


@strawberry.input
class LoyaltyTierInput:
    tier_code: str
    name: str
    min_spend: float
    min_stays: Optional[int] = 0
    discount_percent: Optional[float] = 0.0
    badge_color: Optional[str] = "primary"
    perks: Optional[List[str]] = strawberry.field(default_factory=list)
    display_order: Optional[int] = 0
    is_active: Optional[bool] = True


@strawberry.type
class GuestCRMItemType:
    id: int
    client_id: int
    outlet_id: int
    first_name: str
    last_name: str
    full_name: str
    phone: str
    email: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    address_line1: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: str = "India"
    company_name: Optional[str] = None
    gst_number: Optional[str] = None
    id_type: Optional[str] = None
    id_number: Optional[str] = None
    id_verified: bool = False
    id_document_url: Optional[str] = None
    vip_status: str = "STANDARD"
    is_blacklisted: bool = False
    blacklist_reason: Optional[str] = None
    nationality: str = "Indian"
    special_preferences: Optional[str] = None
    tags: List[str] = strawberry.field(default_factory=list)
    notes: List[GuestNoteType] = strawberry.field(default_factory=list)

    # Computed Outlet-Scoped Stats
    total_stays: int = 0
    total_nights: int = 0
    total_spend: float = 0.0
    last_visit_date: Optional[str] = None
    active_stay_room: Optional[str] = None

    # Dynamic Loyalty Tier from Settings
    tier_code: str = "BRONZE"
    tier_name: str = "Bronze Member"
    tier_badge_color: str = "slate"
    tier_discount: float = 0.0
    tier_perks: List[str] = strawberry.field(default_factory=list)
    created_at: Optional[str] = None


@strawberry.type
class GuestStayHistoryType:
    reservation_id: int
    reservation_code: str
    room_number: str
    category_name: str
    check_in_date: str
    check_out_date: str
    status: str
    adults_count: int
    children_count: int
    booking_source: str
    total_amount: float
    paid_amount: float
    balance_due: float


@strawberry.type
class TierBreakdownType:
    tier_code: str
    tier_name: str
    badge_color: str
    min_spend: float
    guest_count: int


@strawberry.type
class GuestCRMStatsType:
    total_guests: int
    repeat_guests_count: int
    repeat_guests_rate: float
    kyc_verified_count: int
    blacklisted_count: int
    tier_breakdowns: List[TierBreakdownType]


@strawberry.type
class GuestPaginationPayloadType:
    items: List[GuestCRMItemType]
    total_count: int
    page: int
    total_pages: int


@strawberry.input
class CreateGuestInput:
    first_name: str
    last_name: str
    phone: str
    email: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    address_line1: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = "India"
    company_name: Optional[str] = None
    gst_number: Optional[str] = None
    id_type: Optional[str] = None
    id_number: Optional[str] = None
    id_verified: Optional[bool] = False
    id_document_url: Optional[str] = None
    vip_status: Optional[str] = "STANDARD"
    nationality: Optional[str] = "Indian"
    special_preferences: Optional[str] = None
    tags: Optional[List[str]] = strawberry.field(default_factory=list)


@strawberry.input
class UpdateGuestInput:
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    address_line1: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    company_name: Optional[str] = None
    gst_number: Optional[str] = None
    id_type: Optional[str] = None
    id_number: Optional[str] = None
    id_verified: Optional[bool] = None
    id_document_url: Optional[str] = None
    vip_status: Optional[str] = None
    is_blacklisted: Optional[bool] = None
    blacklist_reason: Optional[str] = None
    nationality: Optional[str] = None
    special_preferences: Optional[str] = None
    tags: Optional[List[str]] = None


@strawberry.input
class VerifyKycInput:
    id_type: Optional[str] = None
    id_number: Optional[str] = None
    id_document_url: Optional[str] = None
    verified: bool = True
