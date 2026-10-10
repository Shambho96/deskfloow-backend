from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, BigInteger
from typing import List, TYPE_CHECKING
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.outlet import Outlet
    from app.models.user import User

class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    outlets: Mapped[List["Outlet"]] = relationship("Outlet", back_populates="client", cascade="all, delete-orphan")
    users: Mapped[List["User"]] = relationship("User", back_populates="client", cascade="all, delete-orphan")
