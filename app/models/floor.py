from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, BigInteger, Integer, ForeignKey, UniqueConstraint
from typing import List, TYPE_CHECKING
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.room import Room
    from app.models.client import Client
    from app.models.outlet import Outlet

class Floor(Base):
    __tablename__ = 'floors'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('clients.id', ondelete='CASCADE'), nullable=False, index=True)
    outlet_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('outlets.id', ondelete='CASCADE'), nullable=False, index=True)
    
    floor_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    rooms: Mapped[List['Room']] = relationship('Room', back_populates='floor', cascade='all, delete-orphan')

    __table_args__ = (
        UniqueConstraint('outlet_id', 'floor_number', name='uq_floor_outlet_number'),
    )
