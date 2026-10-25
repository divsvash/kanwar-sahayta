"""Identity tables

Revision ID: 002
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BINARY

revision = '002'
down_revision = '001'

def upgrade():
    op.create_table('roles',
        sa.Column('id', BINARY(16), primary_key=True),
        sa.Column('name', sa.String(50), nullable=False, unique=True),
        sa.Column('permissions', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table('users',
        sa.Column('id', BINARY(16), primary_key=True),
        sa.Column('role_id', BINARY(16), sa.ForeignKey('roles.id'), nullable=False),
        sa.Column('phone', sa.String(15), nullable=False, unique=True),
        sa.Column('pin_hash', sa.String(255), nullable=False),
        sa.Column('status', sa.Enum('ACTIVE', 'SUSPENDED'), default='ACTIVE'),
        sa.Column('full_name', sa.String(150)),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    # Groups before Pilgrims (FK dependency)
    op.create_table('groups',
        sa.Column('id', BINARY(16), primary_key=True),
        sa.Column('season_id', BINARY(16), sa.ForeignKey('seasons.id'), nullable=False),
        sa.Column('group_code', sa.String(10), nullable=False),
        sa.Column('leader_id', BINARY(16), nullable=True),  # FK added after pilgrims
        sa.Column('name', sa.String(100)),
        sa.Column('status', sa.Enum('ACTIVE', 'FRAGMENTED', 'COMPLETED'), default='ACTIVE'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('season_id', 'group_code', name='uq_group_code_season'),
    )

    op.create_table('pilgrims',
        sa.Column('id', BINARY(16), primary_key=True),
        sa.Column('season_id', BINARY(16), sa.ForeignKey('seasons.id'), nullable=False),
        sa.Column('group_id', BINARY(16), sa.ForeignKey('groups.id'), nullable=True),
        sa.Column('full_name', sa.String(150), nullable=False),
        sa.Column('phone', sa.String(15)),
        sa.Column('age', sa.Integer()),
        sa.Column('gender', sa.String(10)),
        sa.Column('blood_group', sa.String(5)),
        sa.Column('medical_flags', sa.JSON()),
        sa.Column('emergency_contact_name', sa.String(150)),
        sa.Column('emergency_contact_phone', sa.String(15)),
        sa.Column('emergency_contact_relation', sa.String(50)),
        sa.Column('photo_url', sa.String(500)),
        sa.Column('qr_payload_hash', sa.String(64)),
        sa.Column('qr_version', sa.Integer(), default=1),
        sa.Column('status', sa.Enum('REGISTERED', 'ACTIVE', 'MISSING', 'COMPLETED', 'REVOKED', 'DECEASED'), default='REGISTERED'),
        sa.Column('route_id', BINARY(16), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    # Add FK from groups.leader_id to pilgrims.id
    op.create_foreign_key('fk_groups_leader', 'groups', 'pilgrims', ['leader_id'], ['id'])

    op.create_table('group_members',
        sa.Column('id', BINARY(16), primary_key=True),
        sa.Column('group_id', BINARY(16), sa.ForeignKey('groups.id'), nullable=False),
        sa.Column('pilgrim_id', BINARY(16), sa.ForeignKey('pilgrims.id'), nullable=False),
        sa.Column('joined_at', sa.DateTime(), nullable=False),
        sa.Column('left_at', sa.DateTime()),
        sa.Column('status', sa.Enum('ACTIVE', 'LEFT'), default='ACTIVE'),
    )

def downgrade():
    op.drop_table('group_members')
    op.drop_table('pilgrims')
    op.drop_table('groups')
    op.drop_table('users')
    op.drop_table('roles')