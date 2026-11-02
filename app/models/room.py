from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    String,
    Boolean,
    BigInteger,
    ForeignKey,
    UniqueConstraint,
    Numeric,
    Text,
)
from typing import Optional, TYPE_CHECKING
from decimal import Decimal
from app.db.base import Base, BigIntPK

if TYPE_CHECKING:
    from app.models.floor import Floor
    from app.models.room_category import RoomCategory
    from app.models.client import Client
    from app.models.outlet import Outlet


class Room(Base):
    __tablename__ = "rooms"

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
    floor_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("floors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("room_categories.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    room_number: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="AVAILABLE", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Free-Hand Custom Overrides
    custom_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    custom_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    custom_amenities: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    floor: Mapped["Floor"] = relationship("Floor", back_populates="rooms")
    category: Mapped[Optional["RoomCategory"]] = relationship("RoomCategory", back_populates="rooms")

    __table_args__ = (UniqueConstraint("outlet_id", "room_number", name="uq_room_outlet_number"),)
