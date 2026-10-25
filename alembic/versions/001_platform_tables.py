"""Platform tables

Revision ID: 001
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BINARY

revision = '001'
down_revision = None

def upgrade():
    op.create_table('seasons',
        sa.Column('id', BINARY(16), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('status', sa.Enum('PLANNING', 'ACTIVE', 'ARCHIVED'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table('audit_events',
        sa.Column('id', BINARY(16), primary_key=True),
        sa.Column('season_id', BINARY(16), nullable=False),
        sa.Column('aggregate_type', sa.String(50), nullable=False),
        sa.Column('aggregate_id', BINARY(16), nullable=False),
        sa.Column('event_type', sa.String(80), nullable=False),
        sa.Column('actor_id', BINARY(16), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('occurred_at', sa.DateTime(), nullable=False),
    )

def downgrade():
    op.drop_table('audit_events')
    op.drop_table('seasons')