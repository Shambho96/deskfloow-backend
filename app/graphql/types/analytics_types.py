import strawberry
from typing import Optional, List


@strawberry.type
class KPISummaryType:
    occupancy_percentage: float
    occupied_rooms: int
    total_rooms: int
    salable_rooms: int
    arrivals_expected: int
    arrivals_checked_in: int
    arrivals_pending: int
    departures_due: int
    departures_settled: int
    departures_pending: int
    daily_room_revenue: float
    adr: float
    revpar: float
    trevpar: float
    alos: float


@strawberry.type
class TrendDayPointType:
    day: str
    date: str
    revenue: float
    occupancy: float
    adr: float


@strawberry.type
class ChannelMixItemType:
    name: str
    source_key: str
    count: int
    percentage: float
    revenue: float
    color: str


@strawberry.type
class HousekeepingRoomItemType:
    room_id: int
    room_number: str
    category_name: str
    status: str  # CLEAN, CLEANING, DIRTY, OOO


@strawberry.type
class HousekeepingSummaryType:
    clean_count: int
    cleaning_count: int
    dirty_count: int
    ooo_count: int
    rooms: List[HousekeepingRoomItemType]


@strawberry.type
class CategoryPerformanceType:
    category_id: int
    category: str
    occupancy: float
    adr: float
    total_rooms: int
    occupied: int


@strawberry.type
class VIPArrivalGuestType:
    reservation_id: int
    reservation_code: str
    guest_name: str
    phone: str
    room_number: Optional[str] = None
    category_name: str
    eta: Optional[str] = None
    status: str
    vip_status: str
    special_requests: List[str] = strawberry.field(default_factory=list)
    folio_id: Optional[int] = None


@strawberry.type
class DashboardAnalyticsPayload:
    target_date: str
    outlet_id: int
    outlet_name: str
    kpis: KPISummaryType
    weekly_trend: List[TrendDayPointType]
    channel_mix: List[ChannelMixItemType]
    total_active_bookings: int
    housekeeping: HousekeepingSummaryType
    category_performance: List[CategoryPerformanceType]
    vip_arrivals: List[VIPArrivalGuestType]
