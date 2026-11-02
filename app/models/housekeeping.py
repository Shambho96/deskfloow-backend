from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, BigInteger, ForeignKey, DateTime, Boolean, Date, Text
from typing import Optional, TYPE_CHECKING
from datetime import datetime, date
from app.db.base import Base, BigIntPK

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.outlet import Outlet
    from app.models.room import Room
    from app.models.user import User


class HousekeepingTask(Base):
    __tablename__ = "housekeeping_tasks"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    outlet_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("outlets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    room_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_to_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True, index=True
    )

    task_type: Mapped[str] = mapped_column(String(50), default="DEPARTURE_CLEAN", nullable=False)
    # DEPARTURE_CLEAN, STAYOVER_CLEAN, DEEP_CLEAN, TURNDOWN, INSPECTION

    priority: Mapped[str] = mapped_column(String(50), default="NORMAL", nullable=False)
    # URGENT_ARRIVAL, HIGH, NORMAL, LOW

    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False, index=True)
    # PENDING, IN_PROGRESS, COMPLETED, INSPECTED

    room_status_before: Mapped[str] = mapped_column(String(50), default="DIRTY", nullable=False)
    room_status_after: Mapped[str] = mapped_column(String(50), default="CLEAN", nullable=False)

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    inspected_by_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    room: Mapped["Room"] = relationship("Room")


class MaintenanceTicket(Base):
    __tablename__ = "maintenance_tickets"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    outlet_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("outlets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    room_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    issue_title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(50), default="MINOR", nullable=False)  # CRITICAL, MAJOR, MINOR
    status: Mapped[str] = mapped_column(
        String(50), default="OPEN", nullable=False, index=True
    )  # OPEN, IN_PROGRESS, RESOLVED, CANCELLED

    is_room_ooo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    blocked_from_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    blocked_to_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    reported_by_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    resolved_by_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    room: Mapped["Room"] = relationship("Room")
