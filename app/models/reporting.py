from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, BigInteger, ForeignKey, Integer, Date, Text
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional, List, TYPE_CHECKING
from app.db.base import Base, BigIntPK

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.outlet import Outlet
    from app.models.user import User


class CustomDashboard(Base):
    """
    Represents a custom dashboard workspace created by a user.
    Can be private to the user or shared with the outlet / specific members.
    Holds up to 10 custom report cards.
    """

    __tablename__ = "custom_dashboards"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    outlet_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("outlets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    icon: Mapped[str] = mapped_column(String(50), default="LayoutDashboard", nullable=False)

    # Visibility: 'PRIVATE' (Only Creator), 'OUTLET_SHARED' (All members of outlet), 'SPECIFIC_MEMBERS'
    visibility: Mapped[str] = mapped_column(String(50), default="PRIVATE", nullable=False)
    # List of member objects: [{"user_id": 12, "role": "VIEWER" | "EDITOR"}]
    shared_members: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    client: Mapped["Client"] = relationship("Client")
    created_by: Mapped["User"] = relationship("User")
    outlet: Mapped[Optional["Outlet"]] = relationship("Outlet")
    cards: Mapped[List["CustomReportCard"]] = relationship(
        "CustomReportCard",
        back_populates="dashboard",
        cascade="all, delete-orphan",
        order_by="CustomReportCard.display_order",
    )


class CustomReportCard(Base):
    """
    Individual report/chart widget placed inside a CustomDashboard.
    Max 10 per dashboard. Custom named, single or multi-metric.
    """

    __tablename__ = "custom_report_cards"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    dashboard_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("custom_dashboards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # Report domain/template code e.g. 'ROOM_REVENUE', 'DAILY_REVENUE', 'OCCUPANCY', 'ADR_REVPAR', 'PAYMENT_METHODS', etc.
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Chart visual: 'bar' | 'line' | 'area' | 'pie' | 'donut' | 'table'
    chart_type: Mapped[str] = mapped_column(String(50), default="bar", nullable=False)
    # Grouping: 'daily' | 'weekly' | 'monthly'
    group_by: Mapped[str] = mapped_column(String(20), default="daily", nullable=False)

    # Date range configuration
    date_preset: Mapped[str] = mapped_column(String(50), default="last_30_days", nullable=False)
    date_from: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)
    date_to: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)

    # Multi-metric selection: ["room_revenue"] or ["room_revenue", "fb_revenue", "tax_collected"]
    selected_metrics: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    # Outlets to query: [1] or [1, 2]
    outlet_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    # Custom filters (booking_source, vip_status, etc.)
    filters: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Card layout position in dashboard
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Optional width span: 1 (normal / half width on md), 2 (full width)
    card_width: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    dashboard: Mapped["CustomDashboard"] = relationship("CustomDashboard", back_populates="cards")
    client: Mapped["Client"] = relationship("Client")
    created_by: Mapped["User"] = relationship("User")
