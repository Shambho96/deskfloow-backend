from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, ForeignKey
from typing import TYPE_CHECKING
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.client import Client
    from app.models.outlet import Outlet

class UserClientOutletMapping(Base):
    __tablename__ = "user_client_outlet_mapping"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(String(64), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    outlet_id: Mapped[str] = mapped_column(String(64), ForeignKey("outlets.id", ondelete="CASCADE"), nullable=False, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="outlet_mappings")
