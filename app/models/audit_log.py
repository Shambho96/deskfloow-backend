from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, BigInteger, ForeignKey, Text, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional
from datetime import datetime
from app.db.base import Base, BigIntPK

class OperationalAuditLog(Base):
    __tablename__ = 'operational_audit_logs'

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('clients.id', ondelete='CASCADE'), nullable=False, index=True)
    outlet_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('outlets.id', ondelete='CASCADE'), nullable=False, index=True)

    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # CHECK_IN, CHECK_OUT, CREATE_RESERVATION, CANCEL_RESERVATION, ROOM_REASSIGN, SETTLE_PAYMENT, STATUS_UPDATE

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # RESERVATION, ROOM, FOLIO, HOUSEKEEPING
    entity_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    old_state: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    new_state: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    performed_by_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey('users.id'), nullable=True, index=True)
