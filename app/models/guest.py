from datetime import date
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, BigIntPK

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.outlet import Outlet
    from app.models.reservation import Reservation
    from app.models.folio import GuestFolio


class Guest(Base):
    __tablename__ = "guests"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    outlet_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("outlets.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # MALE, FEMALE, OTHER
    address_line1: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    country: Mapped[str] = mapped_column(String(100), default="India", nullable=False)

    company_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    gst_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    id_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # AADHAAR, PASSPORT, DRIVING_LICENSE, VOTER_ID
    id_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    id_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    id_document_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    vip_status: Mapped[str] = mapped_column(
        String(50), default="STANDARD", nullable=False
    )  # STANDARD, SILVER, GOLD, PLATINUM, VIP
    is_blacklisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    blacklist_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    nationality: Mapped[str] = mapped_column(String(100), default="Indian", nullable=False)
    purpose_of_visit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    special_preferences: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    notes: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    client: Mapped["Client"] = relationship("Client")
    outlet: Mapped[Optional["Outlet"]] = relationship("Outlet")
    reservations: Mapped[List["Reservation"]] = relationship(
        "Reservation", back_populates="guest", cascade="all, delete-orphan"
    )
    folios: Mapped[List["GuestFolio"]] = relationship("GuestFolio", back_populates="guest")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()
