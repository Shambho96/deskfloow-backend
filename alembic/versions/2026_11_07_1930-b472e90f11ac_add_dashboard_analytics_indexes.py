"""add_dashboard_analytics_indexes

Revision ID: b472e90f11ac
Revises: '93681683b00a'
Create Date: 2026-11-07 19:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b472e90f11ac'
down_revision: Union[str, Sequence[str], None] = '93681683b00a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Composite indexes on reservations for fast occupancy and analytics queries
    op.create_index(
        'ix_reservations_analytics_range',
        'reservations',
        ['outlet_id', 'check_in_date', 'check_out_date', 'status'],
        unique=False,
    )
    op.create_index(
        'ix_reservations_arrivals_date',
        'reservations',
        ['outlet_id', 'check_in_date', 'status'],
        unique=False,
    )
    op.create_index(
        'ix_reservations_departures_date',
        'reservations',
        ['outlet_id', 'check_out_date', 'status'],
        unique=False,
    )

    # 2. Composite indexes on housekeeping & maintenance
    op.create_index(
        'ix_housekeeping_outlet_status',
        'housekeeping_tasks',
        ['outlet_id', 'status'],
        unique=False,
    )
    op.create_index(
        'ix_maintenance_outlet_ooo',
        'maintenance_tickets',
        ['outlet_id', 'is_room_ooo', 'status'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_maintenance_outlet_ooo', table_name='maintenance_tickets')
    op.drop_index('ix_housekeeping_outlet_status', table_name='housekeeping_tasks')
    op.drop_index('ix_reservations_departures_date', table_name='reservations')
    op.drop_index('ix_reservations_arrivals_date', table_name='reservations')
    op.drop_index('ix_reservations_analytics_range', table_name='reservations')
