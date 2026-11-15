"""add_custom_dashboards_and_report_cards

Revision ID: c58319f071bd
Revises: 'b472e90f11ac'
Create Date: 2026-11-14 23:00:00.000000

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c58319f071bd"
down_revision: Union[str, Sequence[str], None] = "b472e90f11ac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create custom_dashboards table
    op.create_table(
        "custom_dashboards",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.BigInteger(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("outlet_id", sa.BigInteger(), sa.ForeignKey("outlets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("icon", sa.String(length=50), server_default="LayoutDashboard", nullable=False),
        sa.Column("visibility", sa.String(length=50), server_default="PRIVATE", nullable=False),
        sa.Column("shared_members", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_custom_dashboards_client", "custom_dashboards", ["client_id"])
    op.create_index("ix_custom_dashboards_user", "custom_dashboards", ["created_by_user_id"])
    op.create_index("ix_custom_dashboards_outlet", "custom_dashboards", ["outlet_id"])

    # 2. Create custom_report_cards table
    op.create_table(
        "custom_report_cards",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "dashboard_id", sa.BigInteger(), sa.ForeignKey("custom_dashboards.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("client_id", sa.BigInteger(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("report_type", sa.String(length=50), nullable=False),
        sa.Column("chart_type", sa.String(length=50), server_default="bar", nullable=False),
        sa.Column("group_by", sa.String(length=20), server_default="daily", nullable=False),
        sa.Column("date_preset", sa.String(length=50), server_default="last_30_days", nullable=False),
        sa.Column("date_from", sa.Date(), nullable=True),
        sa.Column("date_to", sa.Date(), nullable=True),
        sa.Column("selected_metrics", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("outlet_ids", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("filters", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("card_width", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_custom_report_cards_dashboard", "custom_report_cards", ["dashboard_id", "display_order"])
    op.create_index("ix_custom_report_cards_client", "custom_report_cards", ["client_id"])


def downgrade() -> None:
    op.drop_table("custom_report_cards")
    op.drop_table("custom_dashboards")
