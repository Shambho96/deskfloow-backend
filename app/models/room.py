from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, BigInteger, ForeignKey, UniqueConstraint
from typing import TYPE_CHECKING
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.floor import Floor
    from app.models.room_category import RoomCategory
    from app.models.client import Client
    from app.models.outlet import Outlet

class Room(Base):
    __tablename__ = 'rooms'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('clients.id', ondelete='CASCADE'), nullable=False, index=True)
    outlet_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('outlets.id', ondelete='CASCADE'), nullable=False, index=True)
    floor_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('floors.id', ondelete='RESTRICT'), nullable=False, index=True)
    category_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('room_categories.id', ondelete='RESTRICT'), nullable=False, index=True)
    
    room_number: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default='AVAILABLE', nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    floor: Mapped['Floor'] = relationship('Floor', back_populates='rooms')
    category: Mapped['RoomCategory'] = relationship('RoomCategory', back_populates='rooms')

    __table_args__ = (
        UniqueConstraint('outlet_id', 'room_number', name='uq_room_outlet_number'),
    )
