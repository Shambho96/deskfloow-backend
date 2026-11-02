from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    String,
    Boolean,
    BigInteger,
    Integer,
    ForeignKey,
    UniqueConstraint,
)
from typing import List, Optional, TYPE_CHECKING
from app.db.base import Base, BigIntPK

if TYPE_CHECKING:
    from app.models.room import Room
    from app.models.client import Client
    from app.models.outlet import Outlet
    from app.models.building import Building
    from app.models.utility import Utility


class Floor(Base):
    __tablename__ = "floors"

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
    building_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("buildings.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    floor_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    building: Mapped[Optional["Building"]] = relationship("Building", back_populates="floors")
    rooms: Mapped[List["Room"]] = relationship("Room", back_populates="floor", cascade="all, delete-orphan")
    utilities: Mapped[List["Utility"]] = relationship("Utility", back_populates="floor")

    __table_args__ = (UniqueConstraint("building_id", "floor_number", name="uq_floor_building_number"),)
