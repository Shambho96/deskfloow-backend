from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, BigInteger, ForeignKey, Numeric, Integer
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional, List, TYPE_CHECKING
from app.db.base import Base, BigIntPK

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.outlet import Outlet


class LoyaltyTier(Base):
    __tablename__ = "loyalty_tiers"

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

    tier_code: Mapped[str] = mapped_column(String(50), nullable=False)  # BRONZE, SILVER, GOLD, PLATINUM, CUSTOM
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # Display Name
    min_spend: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, nullable=False)
    min_stays: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    discount_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0.00, nullable=False)
    badge_color: Mapped[str] = mapped_column(String(50), default="primary", nullable=False)
    perks: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    client: Mapped["Client"] = relationship("Client")
    outlet: Mapped[Optional["Outlet"]] = relationship("Outlet")
