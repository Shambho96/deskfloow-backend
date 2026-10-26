from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, BigInteger, Integer, ForeignKey, UniqueConstraint
from typing import List, Optional, TYPE_CHECKING
from app.db.base import Base, BigIntPK

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.outlet import Outlet
    from app.models.floor import Floor
    from app.models.utility import Utility

class Building(Base):
    __tablename__ = 'buildings'

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('clients.id', ondelete='CASCADE'), nullable=False, index=True)
    outlet_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('outlets.id', ondelete='CASCADE'), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    building_type: Mapped[str] = mapped_column(String(50), default='HOTEL_TOWER', nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    floors: Mapped[List['Floor']] = relationship('Floor', back_populates='building', cascade='all, delete-orphan', order_by='Floor.floor_number')
    utilities: Mapped[List['Utility']] = relationship('Utility', back_populates='building', cascade='all, delete-orphan')

    __table_args__ = (
        UniqueConstraint('outlet_id', 'name', name='uq_building_outlet_name'),
    )
