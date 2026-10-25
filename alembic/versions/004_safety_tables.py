"""Safety tables: emergency_requests, medical_incidents, emergency_timeline, deceased_confirmations

Revision ID: 004
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BINARY, POINT

revision = '004'
down_revision = '003'


def upgrade():
    op.create_table('emergency_requests',
        sa.Column('id', BINARY(16), primary_key=True),
        sa.Column('season_id', BINARY(16), nullable=False),
        sa.Column('pilgrim_id', BINARY(16), nullable=False),
        sa.Column('type', sa.Enum('MEDICAL', 'POLICE', 'STRUCTURAL'), nullable=False),
        sa.Column('location', POINT(srid=4326)),
        sa.Column('location_description', sa.String(500)),
        sa.Column('status', sa.Enum('PENDING', 'ACKNOWLEDGED', 'DISPATCHED', 'ON_SCENE', 'RESOLVED', 'ESCALATED'), nullable=False, default='PENDING'),
        sa.Column('severity', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'), default='HIGH'),
        sa.Column('raised_at', sa.DateTime(), nullable=False),
        sa.Column('acknowledged_at', sa.DateTime()),
        sa.Column('acknowledged_by', BINARY(16)),
        sa.Column('dispatched_at', sa.DateTime()),
        sa.Column('on_scene_at', sa.DateTime()),
        sa.Column('resolved_at', sa.DateTime()),
        sa.Column('sla_deadline', sa.DateTime(), nullable=False),
        sa.Column('sla_breached', sa.Integer(), default=0),
        sa.Column('responder_user_id', BINARY(16)),
        sa.Column('responder_camp_id', BINARY(16)),
        sa.Column('responder_type', sa.Enum('MEDICAL_OFFICER', 'AMBULANCE', 'POLICE', 'RESCUE_TEAM')),
        sa.Column('resolution_summary', sa.Text()),
        sa.Column('resolved_by', BINARY(16)),
        sa.Column('escalation_level', sa.Enum('L1', 'L2', 'L3', 'L4'), default='L1'),
        sa.Column('escalated_at', sa.DateTime()),
        sa.Column('escalation_reason', sa.String(255)),
        sa.Column('source', sa.Enum('APP', 'PORTAL', 'OPERATOR'), default='APP'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_emergency_status', 'emergency_requests', ['status'])
    op.create_index('ix_emergency_pilgrim_season', 'emergency_requests', ['pilgrim_id', 'season_id'])
    op.create_index('ix_emergency_sla', 'emergency_requests', ['sla_deadline', 'status'])

    op.create_table('medical_incidents',
        sa.Column('id', BINARY(16), primary_key=True),
        sa.Column('emergency_id', BINARY(16), sa.ForeignKey('emergency_requests.id'), nullable=False, unique=True),
        sa.Column('pilgrim_id', BINARY(16), nullable=False),
        sa.Column('camp_id', BINARY(16)),
        sa.Column('medical_officer_id', BINARY(16)),
        sa.Column('triage_level', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'), nullable=False),
        sa.Column('primary_complaint', sa.String(500)),
        sa.Column('secondary_complaints', sa.JSON()),
        sa.Column('symptoms_onset', sa.String(255)),
        sa.Column('vitals', sa.JSON()),
        sa.Column('consciousness', sa.Enum('ALERT', 'VERBAL', 'PAIN', 'UNRESPONSIVE')),
        sa.Column('known_conditions', sa.JSON()),
        sa.Column('known_allergies', sa.JSON()),
        sa.Column('current_medications', sa.JSON()),
        sa.Column('blood_group', sa.String(5)),
        sa.Column('diagnosis', sa.String(500)),
        sa.Column('treatment_given', sa.Text()),
        sa.Column('medications_administered', sa.JSON()),
        sa.Column('disposition', sa.Enum('TREATING', 'TREATED', 'TRANSFERRED', 'FATALITY', 'REFERRED'), default='TREATING'),
        sa.Column('disposition_notes', sa.Text()),
        sa.Column('transfer_facility', sa.String(255)),
        sa.Column('transfer_reason', sa.Text()),
        sa.Column('ambulance_id', BINARY(16)),
        sa.Column('incident_started_at', sa.DateTime(), nullable=False),
        sa.Column('triage_completed_at', sa.DateTime()),
        sa.Column('treatment_completed_at', sa.DateTime()),
        sa.Column('transferred_at', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_medical_incident_pilgrim', 'medical_incidents', ['pilgrim_id'])
    op.create_index('ix_medical_incident_disposition', 'medical_incidents', ['disposition'])

    op.create_table('emergency_timeline',
        sa.Column('id', BINARY(16), primary_key=True),
        sa.Column('emergency_id', BINARY(16), sa.ForeignKey('emergency_requests.id'), nullable=False),
        sa.Column('event_type', sa.String(80), nullable=False),
        sa.Column('actor_id', BINARY(16)),
        sa.Column('actor_role', sa.String(50)),
        sa.Column('from_status', sa.String(50)),
        sa.Column('to_status', sa.String(50)),
        sa.Column('payload', sa.JSON()),
        sa.Column('notes', sa.String(500)),
        sa.Column('occurred_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_timeline_emergency', 'emergency_timeline', ['emergency_id', 'occurred_at'])

    op.create_table('deceased_confirmations',
        sa.Column('id', BINARY(16), primary_key=True),
        sa.Column('emergency_id', BINARY(16), sa.ForeignKey('emergency_requests.id'), nullable=False),
        sa.Column('pilgrim_id', BINARY(16), nullable=False),
        sa.Column('first_confirmer_id', BINARY(16)),
        sa.Column('first_confirmed_at', sa.DateTime()),
        sa.Column('first_confirmation_notes', sa.Text()),
        sa.Column('second_confirmer_id', BINARY(16)),
        sa.Column('second_confirmed_at', sa.DateTime()),
        sa.Column('second_confirmation_notes', sa.Text()),
        sa.Column('time_of_death', sa.DateTime()),
        sa.Column('cause_of_death', sa.String(255)),
        sa.Column('body_location', sa.String(255)),
        sa.Column('next_of_kin_notified', sa.Integer(), default=0),
        sa.Column('next_of_kin_notified_at', sa.DateTime()),
        sa.Column('notification_method', sa.String(50)),
        sa.Column('status', sa.Enum('PENDING_FIRST', 'PENDING_SECOND', 'CONFIRMED', 'NOTIFIED'), default='PENDING_FIRST'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_deceased_pilgrim', 'deceased_confirmations', ['pilgrim_id'])


def downgrade():
    op.drop_table('deceased_confirmations')
    op.drop_table('emergency_timeline')
    op.drop_table('medical_incidents')
    op.drop_table('emergency_requests')