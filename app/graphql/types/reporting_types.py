import strawberry
from typing import Optional, List, Any
import json


# Custom JSON Scalar for Strawberry
JSON = strawberry.scalar(
    Any,
    name="JSON",
    description="Arbitrary JSON value",
    serialize=lambda v: v,
    parse_value=lambda v: v,
)


@strawberry.type
class ReportMetaType:
    report_type: str
    total_rows: int
    date_from: str
    date_to: str
    group_by: str
    outlet_names: List[str]
    summary: JSON


@strawberry.type
class ChartDataPointType:
    label: str
    value: float


@strawberry.type
class ChartSeriesType:
    name: str
    metric_key: str
    data: List[ChartDataPointType]
    color: str


@strawberry.type
class ReportExecutionPayload:
    meta: ReportMetaType
    rows: JSON
    chart_series: List[ChartSeriesType]


@strawberry.type
class CustomReportCardType:
    id: int
    dashboard_id: int
    client_id: int
    created_by_user_id: int
    title: str
    report_type: str
    chart_type: str
    group_by: str
    date_preset: str
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    selected_metrics: List[str]
    outlet_ids: List[int]
    filters: JSON
    display_order: int
    card_width: int
    created_at: str


@strawberry.type
class CustomDashboardType:
    id: int
    client_id: int
    created_by_user_id: int
    outlet_id: Optional[int]
    name: str
    description: Optional[str]
    icon: str
    visibility: str
    shared_members: JSON
    is_default: bool
    display_order: int
    card_count: int
    cards: List[CustomReportCardType]
    created_at: str


# ─── INPUT TYPES ────────────────────────────────────────────────────────


@strawberry.input
class CreateDashboardInput:
    name: str
    description: Optional[str] = None
    icon: Optional[str] = "LayoutDashboard"
    visibility: Optional[str] = "PRIVATE"
    shared_members: Optional[JSON] = None
    outlet_id: Optional[int] = None


@strawberry.input
class UpdateDashboardInput:
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    visibility: Optional[str] = None
    shared_members: Optional[JSON] = None


@strawberry.input
class CreateReportCardInput:
    dashboard_id: int
    title: str
    report_type: str
    chart_type: Optional[str] = "bar"
    group_by: Optional[str] = "daily"
    date_preset: Optional[str] = "last_30_days"
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    selected_metrics: Optional[List[str]] = None
    outlet_ids: Optional[List[int]] = None
    filters: Optional[JSON] = None
    card_width: Optional[int] = 1


@strawberry.input
class UpdateReportCardInput:
    title: Optional[str] = None
    chart_type: Optional[str] = None
    group_by: Optional[str] = None
    date_preset: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    selected_metrics: Optional[List[str]] = None
    outlet_ids: Optional[List[int]] = None
    filters: Optional[JSON] = None
    card_width: Optional[int] = None


@strawberry.input
class ReorderCardsInput:
    dashboard_id: int
    ordered_ids: List[int]


@strawberry.input
class ReorderDashboardsInput:
    ordered_ids: List[int]
