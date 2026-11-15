from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, BigInteger, ForeignKey, Numeric, Integer
from typing import Optional, TYPE_CHECKING
from app.db.base import Base, BigIntPK

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.outlet import Outlet


class HotelSpecialRequest(Base):
    """
    Configurable special requests offered by a hotel property.
    e.g. Airport Transfer, Extra Bed, High Floor, Late Checkout, Honeymoon Decor.
    Can be complimentary or chargeable with custom price.
    """

    __tablename__ = "hotel_special_requests"

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

    code: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(
        String(50), default="ROOM", nullable=False
    )  # ROOM, TIMING, AMENITY, DINING, SPECIAL
    is_chargeable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2), default=0.00, nullable=False)
    icon: Mapped[str] = mapped_column(String(50), default="Sparkles", nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    client: Mapped["Client"] = relationship("Client")
    outlet: Mapped[Optional["Outlet"]] = relationship("Outlet")


class HotelGuestTag(Base):
    """
    Configurable guest profile & CRM tags.
    e.g. VIP, Corporate, Frequent Stay, Senior Citizen, Vegetarian, Watchlist.
    """

    __tablename__ = "hotel_guest_tags"

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

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str] = mapped_column(
        String(50), default="primary", nullable=False
    )  # amber, primary, emerald, blue, rose, slate
    category: Mapped[str] = mapped_column(
        String(50), default="PROFILE", nullable=False
    )  # PROFILE, PREFERENCE, DIETARY, BILLING
    description: Mapped[Optional[str]] = mapped_column(String(250), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    client: Mapped["Client"] = relationship("Client")
    outlet: Mapped[Optional["Outlet"]] = relationship("Outlet")
