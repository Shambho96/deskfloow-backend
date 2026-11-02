from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    String,
    BigInteger,
    ForeignKey,
    UniqueConstraint,
    Numeric,
    DateTime,
    Integer,
    Index,
)
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from decimal import Decimal
from app.db.base import Base, BigIntPK

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.outlet import Outlet
    from app.models.reservation import Reservation
    from app.models.guest import Guest
    from app.models.user import User


class GuestFolio(Base):
    __tablename__ = "guest_folios"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    folio_number: Mapped[str] = mapped_column(String(50), nullable=False)
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
    reservation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("reservations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    guest_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("guests.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(String(50), default="OPEN", nullable=False)  # OPEN, SETTLED, VOID
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    balance_due: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)

    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)

    reservation: Mapped["Reservation"] = relationship("Reservation", back_populates="folios")
    guest: Mapped["Guest"] = relationship("Guest", back_populates="folios")
    line_items: Mapped[List["FolioLineItem"]] = relationship(
        "FolioLineItem", back_populates="folio", cascade="all, delete-orphan"
    )
    payments: Mapped[List["FolioPayment"]] = relationship(
        "FolioPayment", back_populates="folio", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("outlet_id", "folio_number", name="uq_folio_number_outlet"),)


class FolioLineItem(Base):
    __tablename__ = "folio_line_items"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    outlet_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("outlets.id", ondelete="CASCADE"), nullable=False)
    folio_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("guest_folios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    charge_category: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # ROOM_CHARGE, FOOD_BEVERAGE, LAUNDRY, SPA, MINIBAR, MISC
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("12.00"), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    service_ref_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    posted_by_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    folio: Mapped["GuestFolio"] = relationship("GuestFolio", back_populates="line_items")


class FolioPayment(Base):
    __tablename__ = "folio_payments"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    outlet_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("outlets.id", ondelete="CASCADE"), nullable=False)
    folio_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("guest_folios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # CASH, CREDIT_CARD, DEBIT_CARD, UPI_QR, BANK_TRANSFER
    transaction_ref: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="SUCCESS", nullable=False)  # SUCCESS, PENDING, REFUNDED

    receipt_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    received_by_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    payment_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    folio: Mapped["GuestFolio"] = relationship("GuestFolio", back_populates="payments")

    __table_args__ = (
        UniqueConstraint("outlet_id", "idempotency_key", name="uq_payment_idempotency"),
        Index("ix_payments_folio", "folio_id"),
    )
