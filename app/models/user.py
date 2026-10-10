from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, ForeignKey
from typing import List, Optional, TYPE_CHECKING
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.mapping import UserClientOutletMapping

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True) # e.g. 'usr_mgr_01'
    client_id: Mapped[str] = mapped_column(String(64), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Encrypted phone number for operational WhatsApp messaging
    phone_encrypted: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # HMAC blind index for instant B-Tree database search
    phone_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)

    role: Mapped[str] = mapped_column(String(50), nullable=False) # 'OWNER', 'MANAGER', 'STAFF'
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # STRICT LOGIN GUARD FLAG: Staff accounts have can_login = False
    can_login: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="users")
    outlet_mappings: Mapped[List["UserClientOutletMapping"]] = relationship("UserClientOutletMapping", back_populates="user", cascade="all, delete-orphan")
