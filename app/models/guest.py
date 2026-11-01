from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, BigInteger, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional, List, TYPE_CHECKING
from app.db.base import Base, BigIntPK

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.reservation import Reservation
    from app.models.folio import GuestFolio

class Guest(Base):
    __tablename__ = 'guests'

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('clients.id', ondelete='CASCADE'), nullable=False, index=True)

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    id_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # AADHAAR, PASSPORT, DRIVING_LICENSE, VOTER_ID
    id_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    id_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    id_document_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    vip_status: Mapped[str] = mapped_column(String(50), default='STANDARD', nullable=False)  # STANDARD, VIP, VVIP, BLACKLIST
    nationality: Mapped[str] = mapped_column(String(100), default='Indian', nullable=False)
    special_preferences: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    reservations: Mapped[List['Reservation']] = relationship('Reservation', back_populates='guest', cascade='all, delete-orphan')
    folios: Mapped[List['GuestFolio']] = relationship('GuestFolio', back_populates='guest')

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()
