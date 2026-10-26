"""add_buildings_utilities_and_freehand_rooms

Revision ID: 9b48c1a2e3f5
Revises: 60a5dd9aa33f
Create Date: 2026-10-24 22:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b48c1a2e3f5'
down_revision: Union[str, Sequence[str], None] = '60a5dd9aa33f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create 'buildings' table
    op.create_table(
        'buildings',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('client_id', sa.BigInteger(), nullable=False),
        sa.Column('outlet_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=True),
        sa.Column('building_type', sa.String(length=50), server_default='HOTEL_TOWER', nullable=False),
        sa.Column('display_order', sa.Integer(), server_default='1', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['outlet_id'], ['outlets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('outlet_id', 'name', name='uq_building_outlet_name')
    )
    op.create_index(op.f('ix_buildings_client_id'), 'buildings', ['client_id'], unique=False)
    op.create_index(op.f('ix_buildings_outlet_id'), 'buildings', ['outlet_id'], unique=False)

    # 2. Add 'building_id' to 'floors'
    op.add_column('floors', sa.Column('building_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key('fk_floors_building_id', 'floors', 'buildings', ['building_id'], ['id'], ondelete='CASCADE')
    op.create_index(op.f('ix_floors_building_id'), 'floors', ['building_id'], unique=False)

    # 3. Data migration: ensure default building for any existing floors
    conn = op.get_bind()
    # Find all distinct outlets with floors
    outlets_with_floors = conn.execute(
        sa.text("SELECT DISTINCT client_id, outlet_id FROM floors WHERE building_id IS NULL")
    ).fetchall()

    for row in outlets_with_floors:
        client_id, outlet_id = row[0], row[1]
        # Check if building exists for this outlet
        existing_bld = conn.execute(
            sa.text("SELECT id FROM buildings WHERE outlet_id = :oid LIMIT 1"),
            {"oid": outlet_id}
        ).fetchone()

        if existing_bld:
            bld_id = existing_bld[0]
        else:
            res = conn.execute(
                sa.text(
                    "INSERT INTO buildings (client_id, outlet_id, name, code, building_type, display_order, is_active) "
                    "VALUES (:cid, :oid, 'Main Tower', 'TWR-1', 'HOTEL_TOWER', 1, true) RETURNING id"
                ),
                {"cid": client_id, "oid": outlet_id}
            ).fetchone()
            bld_id = res[0]

        conn.execute(
            sa.text("UPDATE floors SET building_id = :bid WHERE outlet_id = :oid AND building_id IS NULL"),
            {"bid": bld_id, "oid": outlet_id}
        )

    # 4. Update unique constraint on floors
    try:
        op.drop_constraint('uq_floor_outlet_number', 'floors', type_='unique')
    except Exception:
        pass
    op.create_unique_constraint('uq_floor_building_number', 'floors', ['building_id', 'floor_number'])

    # 5. Modify 'rooms' table for free-hand custom pricing and amenities
    op.alter_column('rooms', 'category_id', existing_type=sa.BigInteger(), nullable=True)
    op.add_column('rooms', sa.Column('custom_name', sa.String(length=100), nullable=True))
    op.add_column('rooms', sa.Column('custom_price', sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column('rooms', sa.Column('custom_amenities', sa.Text(), nullable=True))

    # 6. Create 'utilities' table (Pools, Lawns, Spas, Gyms, Restaurants)
    op.create_table(
        'utilities',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('client_id', sa.BigInteger(), nullable=False),
        sa.Column('outlet_id', sa.BigInteger(), nullable=False),
        sa.Column('building_id', sa.BigInteger(), nullable=False),
        sa.Column('floor_id', sa.BigInteger(), nullable=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('utility_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=30), server_default='OPEN', nullable=False),
        sa.Column('capacity', sa.Integer(), nullable=True),
        sa.Column('operating_hours', sa.String(length=100), nullable=True),
        sa.Column('is_bookable', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('rental_price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('amenities', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['outlet_id'], ['outlets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['building_id'], ['buildings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['floor_id'], ['floors.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_utilities_client_id'), 'utilities', ['client_id'], unique=False)
    op.create_index(op.f('ix_utilities_outlet_id'), 'utilities', ['outlet_id'], unique=False)
    op.create_index(op.f('ix_utilities_building_id'), 'utilities', ['building_id'], unique=False)
    op.create_index(op.f('ix_utilities_floor_id'), 'utilities', ['floor_id'], unique=False)


def downgrade() -> None:
    op.drop_table('utilities')
    op.drop_column('rooms', 'custom_amenities')
    op.drop_column('rooms', 'custom_price')
    op.drop_column('rooms', 'custom_name')
    op.alter_column('rooms', 'category_id', existing_type=sa.BigInteger(), nullable=False)

    op.drop_constraint('uq_floor_building_number', 'floors', type_='unique')
    op.create_unique_constraint('uq_floor_outlet_number', 'floors', ['outlet_id', 'floor_number'])
    op.drop_index(op.f('ix_floors_building_id'), table_name='floors')
    op.drop_constraint('fk_floors_building_id', 'floors', type_='foreignkey')
    op.drop_column('floors', 'building_id')

    op.drop_table('buildings')
