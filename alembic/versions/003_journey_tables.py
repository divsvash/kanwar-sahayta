"""Journey tables

Revision ID: 003
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BINARY, POINT, LINESTRING

revision = '003'
down_revision = '002'

def upgrade():
    op.create_table('checkpoints',
        sa.Column('id', BINARY(16), primary_key=True),
        sa.Column('camp_id', BINARY(16)),
        sa.Column('name', sa.String(150), nullable=False),
        sa.Column('location', POINT(srid=4326), nullable=False),
        sa.Column('direction', sa.Enum('IN', 'OUT', 'EN_ROUTE'), nullable=False),
        sa.Column('checkpoint_type', sa.Enum('ENTRY', 'EXIT', 'REST_CAMP', 'MEDICAL_CAMP', 'TRANSIT_CAMP', 'MILESTONE'), nullable=False),
        sa.Column('status', sa.Enum('ACTIVE', 'OFFLINE', 'CLOSED'), default='ACTIVE'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table('routes',
        sa.Column('id', BINARY(16), primary_key=True),
        sa.Column('season_id', BINARY(16), sa.ForeignKey('seasons.id'), nullable=False),
        sa.Column('name', sa.String(150), nullable=False),
        sa.Column('description', sa.String(500)),
        sa.Column('status', sa.Enum('ACTIVE', 'INACTIVE'), default='ACTIVE'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table('route_segments',
        sa.Column('id', BINARY(16), primary_key=True),
        sa.Column('season_id', BINARY(16), sa.ForeignKey('seasons.id'), nullable=False),
        sa.Column('route_id', BINARY(16), sa.ForeignKey('routes.id'), nullable=False),
        sa.Column('sequence_order', sa.Integer(), nullable=False),
        sa.Column('start_checkpoint_id', BINARY(16), sa.ForeignKey('checkpoints.id'), nullable=False),
        sa.Column('end_checkpoint_id', BINARY(16), sa.ForeignKey('checkpoints.id'), nullable=False),
        sa.Column('polyline', LINESTRING(srid=4326)),
        sa.Column('distance_km', sa.Float(), nullable=False),
        sa.Column('nominal_walking_hours', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table('journeys',
        sa.Column('id', BINARY(16), primary_key=True),
        sa.Column('pilgrim_id', BINARY(16), sa.ForeignKey('pilgrims.id'), nullable=False, unique=True),
        sa.Column('route_id', BINARY(16), sa.ForeignKey('routes.id'), nullable=False),
        sa.Column('status', sa.Enum('PLANNED', 'IN_PROGRESS', 'MISS_RISK', 'COMPLETED'), default='PLANNED'),
        sa.Column('started_at', sa.DateTime()),
        sa.Column('completed_at', sa.DateTime()),
        sa.Column('last_presence_event_id', BINARY(16)),
        sa.Column('last_checkpoint_id', BINARY(16), sa.ForeignKey('checkpoints.id')),
        sa.Column('next_expected_checkpoint_id', BINARY(16), sa.ForeignKey('checkpoints.id')),
        sa.Column('next_expected_arrival_at', sa.DateTime()),
        sa.Column('last_known_location', POINT(srid=4326)),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table('presence_events',
        sa.Column('id', BINARY(16), primary_key=True),
        sa.Column('season_id', BINARY(16), nullable=False),
        sa.Column('pilgrim_id', BINARY(16), nullable=False),
        sa.Column('checkpoint_id', BINARY(16), nullable=False),
        sa.Column('device_id', BINARY(16)),
        sa.Column('operator_user_id', BINARY(16)),
        sa.Column('sync_batch_id', BINARY(16)),
        sa.Column('scanned_at', sa.DateTime(), nullable=False),
        sa.Column('synced_at', sa.DateTime(), nullable=False),
        sa.Column('offline_mutation_id', BINARY(16), nullable=False),
        sa.Column('direction', sa.Enum('CHECKIN', 'CHECKOUT'), nullable=False),
        sa.Column('missing_person_match', sa.Boolean(), default=False),
        sa.Column('scan_result', sa.String(50), default='STANDARD_SUCCESS'),
        sa.Column('notes', sa.String(500)),
    )

def downgrade():
    op.drop_table('presence_events')
    op.drop_table('journeys')
    op.drop_table('route_segments')
    op.drop_table('routes')
    op.drop_table('checkpoints')