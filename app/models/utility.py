from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, BigInteger, Integer, ForeignKey, Numeric, Text
from typing import Optional, TYPE_CHECKING
from decimal import Decimal
from app.db.base import Base, BigIntPK

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.outlet import Outlet
    from app.models.building import Building
    from app.models.floor import Floor


class Utility(Base):
    __tablename__ = "utilities"

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
    building_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("buildings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    floor_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("floors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    utility_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="OPEN", nullable=False)
    capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    operating_hours: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_bookable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rental_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    amenities: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    building: Mapped["Building"] = relationship("Building", back_populates="utilities")
    floor: Mapped[Optional["Floor"]] = relationship("Floor", back_populates="utilities")
