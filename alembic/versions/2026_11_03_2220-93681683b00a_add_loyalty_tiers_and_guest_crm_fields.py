"""add_loyalty_tiers_and_guest_crm_fields

Revision ID: 93681683b00a
Revises: 18027caf72b4
Create Date: 2026-11-03 22:20:58.626561

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "93681683b00a"
down_revision: Union[str, Sequence[str], None] = "18027caf72b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "loyalty_tiers",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("client_id", sa.BigInteger(), nullable=False),
        sa.Column("outlet_id", sa.BigInteger(), nullable=True),
        sa.Column("tier_code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("min_spend", sa.Numeric(precision=12, scale=2), server_default="0.00", nullable=False),
        sa.Column("min_stays", sa.Integer(), server_default="0", nullable=False),
        sa.Column("discount_percent", sa.Numeric(precision=5, scale=2), server_default="0.00", nullable=False),
        sa.Column("badge_color", sa.String(length=50), server_default="primary", nullable=False),
        sa.Column("perks", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_loyalty_tiers_client_id"), "loyalty_tiers", ["client_id"], unique=False)
    op.create_index(op.f("ix_loyalty_tiers_outlet_id"), "loyalty_tiers", ["outlet_id"], unique=False)

    op.add_column("guests", sa.Column("outlet_id", sa.BigInteger(), nullable=True))
    op.add_column("guests", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("guests", sa.Column("gender", sa.String(length=20), nullable=True))
    op.add_column("guests", sa.Column("address_line1", sa.String(length=255), nullable=True))
    op.add_column("guests", sa.Column("city", sa.String(length=100), nullable=True))
    op.add_column("guests", sa.Column("state", sa.String(length=100), nullable=True))
    op.add_column("guests", sa.Column("postal_code", sa.String(length=20), nullable=True))
    op.add_column("guests", sa.Column("country", sa.String(length=100), server_default="India", nullable=False))
    op.add_column("guests", sa.Column("company_name", sa.String(length=200), nullable=True))
    op.add_column("guests", sa.Column("gst_number", sa.String(length=50), nullable=True))
    op.add_column("guests", sa.Column("is_blacklisted", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("guests", sa.Column("blacklist_reason", sa.Text(), nullable=True))
    op.add_column(
        "guests", sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False)
    )
    op.create_index(op.f("ix_guests_outlet_id"), "guests", ["outlet_id"], unique=False)
    op.create_foreign_key("fk_guests_outlet_id_outlets", "guests", "outlets", ["outlet_id"], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    op.drop_constraint("fk_guests_outlet_id_outlets", "guests", type_="foreignkey")
    op.drop_index(op.f("ix_guests_outlet_id"), table_name="guests")
    op.drop_column("guests", "notes")
    op.drop_column("guests", "blacklist_reason")
    op.drop_column("guests", "is_blacklisted")
    op.drop_column("guests", "gst_number")
    op.drop_column("guests", "company_name")
    op.drop_column("guests", "country")
    op.drop_column("guests", "postal_code")
    op.drop_column("guests", "state")
    op.drop_column("guests", "city")
    op.drop_column("guests", "address_line1")
    op.drop_column("guests", "gender")
    op.drop_column("guests", "date_of_birth")
    op.drop_column("guests", "outlet_id")
    op.drop_index(op.f("ix_loyalty_tiers_outlet_id"), table_name="loyalty_tiers")
    op.drop_index(op.f("ix_loyalty_tiers_client_id"), table_name="loyalty_tiers")
    op.drop_table("loyalty_tiers")
