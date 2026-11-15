"""add_special_requests_and_guest_tags

Revision ID: d8471b0e2f91
Revises: c58319f071bd
Create Date: 2026-11-15 11:00:00.000000

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d8471b0e2f91"
down_revision: Union[str, Sequence[str], None] = "c58319f071bd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create hotel_special_requests table
    op.create_table(
        "hotel_special_requests",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.BigInteger(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("outlet_id", sa.BigInteger(), sa.ForeignKey("outlets.id", ondelete="CASCADE"), nullable=True),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("label", sa.String(length=150), nullable=False),
        sa.Column("category", sa.String(length=50), server_default="ROOM", nullable=False),
        sa.Column("is_chargeable", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), server_default="0.00", nullable=False),
        sa.Column("icon", sa.String(length=50), server_default="Sparkles", nullable=False),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_hotel_special_requests_client", "hotel_special_requests", ["client_id"])
    op.create_index("ix_hotel_special_requests_outlet", "hotel_special_requests", ["outlet_id"])

    # 2. Create hotel_guest_tags table
    op.create_table(
        "hotel_guest_tags",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.BigInteger(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("outlet_id", sa.BigInteger(), sa.ForeignKey("outlets.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("color", sa.String(length=50), server_default="primary", nullable=False),
        sa.Column("category", sa.String(length=50), server_default="PROFILE", nullable=False),
        sa.Column("description", sa.String(length=250), nullable=True),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_hotel_guest_tags_client", "hotel_guest_tags", ["client_id"])
    op.create_index("ix_hotel_guest_tags_outlet", "hotel_guest_tags", ["outlet_id"])


def downgrade() -> None:
    op.drop_table("hotel_guest_tags")
    op.drop_table("hotel_special_requests")
