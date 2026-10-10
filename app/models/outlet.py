from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, ForeignKey
from typing import TYPE_CHECKING
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.client import Client

class Outlet(Base):
    __tablename__ = "outlets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True) # e.g. 'out_kolhapur'
    client_id: Mapped[str] = mapped_column(String(64), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="outlets")
