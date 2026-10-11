from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, BigInteger, Integer, Numeric, ForeignKey, UniqueConstraint
from typing import List, Optional, TYPE_CHECKING
from decimal import Decimal
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.room import Room
    from app.models.client import Client
    from app.models.outlet import Outlet

class RoomCategory(Base):
    __tablename__ = 'room_categories'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('clients.id', ondelete='CASCADE'), nullable=False, index=True)
    outlet_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('outlets.id', ondelete='CASCADE'), nullable=False, index=True)
    
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    max_adults: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    max_children: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    amenities: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    rooms: Mapped[List['Room']] = relationship('Room', back_populates='category', cascade='all, delete-orphan')

    __table_args__ = (
        UniqueConstraint('outlet_id', 'name', name='uq_category_outlet_name'),
    )
