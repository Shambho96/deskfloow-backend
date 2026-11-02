from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    String,
    BigInteger,
    ForeignKey,
    UniqueConstraint,
    Numeric,
    Date,
    DateTime,
    Integer,
    CheckConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional, List, TYPE_CHECKING
from datetime import date, datetime
from decimal import Decimal
from app.db.base import Base, BigIntPK

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.outlet import Outlet
    from app.models.guest import Guest
    from app.models.room import Room
    from app.models.room_category import RoomCategory
    from app.models.folio import GuestFolio


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    reservation_code: Mapped[str] = mapped_column(String(50), nullable=False)
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
    guest_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("guests.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    room_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("rooms.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    category_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("room_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    check_in_date: Mapped[date] = mapped_column(Date, nullable=False)
    check_out_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_check_in_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_check_out_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    eta: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    status: Mapped[str] = mapped_column(String(50), default="RESERVED", nullable=False)
    # RESERVED, CHECKED_IN, CHECKED_OUT, CANCELLED, NO_SHOW

    # Direct Channels Only: WALKIN, DIRECT, WHATSAPP, WEBSITE, OTHER
    booking_source: Mapped[str] = mapped_column(String(50), default="WALKIN", nullable=False)

    adults_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    children_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    special_requests: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    rate_per_night: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total_room_charges: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)

    cancellation_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    guest: Mapped["Guest"] = relationship("Guest", back_populates="reservations")
    room: Mapped[Optional["Room"]] = relationship("Room")
    category: Mapped["RoomCategory"] = relationship("RoomCategory")
    folios: Mapped[List["GuestFolio"]] = relationship(
        "GuestFolio", back_populates="reservation", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("outlet_id", "reservation_code", name="uq_reservation_code_outlet"),
        UniqueConstraint("outlet_id", "idempotency_key", name="uq_reservation_idempotency"),
        CheckConstraint("check_out_date > check_in_date", name="chk_reservation_dates"),
        Index("ix_res_outlet_dates", "outlet_id", "check_in_date", "check_out_date"),
        Index("ix_res_room_status", "room_id", "status"),
        Index("ix_res_status", "outlet_id", "status"),
        Index("ix_res_source", "outlet_id", "booking_source"),
    )
