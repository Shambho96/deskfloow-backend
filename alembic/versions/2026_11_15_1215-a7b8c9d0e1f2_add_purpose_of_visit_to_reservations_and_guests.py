"""add_purpose_of_visit_to_reservations_and_guests

Revision ID: a7b8c9d0e1f2
Revises: d8471b0e2f91
Create Date: 2026-11-15 12:15:00.000000

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "d8471b0e2f91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add purpose_of_visit column to reservations table if not exists
    op.execute("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS purpose_of_visit VARCHAR(50);")

    # Add purpose_of_visit column to guests table if not exists
    op.execute("ALTER TABLE guests ADD COLUMN IF NOT EXISTS purpose_of_visit VARCHAR(50);")


def downgrade() -> None:
    op.drop_column("reservations", "purpose_of_visit")
    op.drop_column("guests", "purpose_of_visit")
